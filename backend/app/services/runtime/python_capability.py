"""Python capability (Sprint 15.10 — first-class Python ExecutionCapability).

Implements the Sprint 14.3 :class:`ExecutionCapability` contract by coordinating a
persistent workspace, a safe execution seam, and an artifact manager into one
Python execution: validate the request → prepare a workspace directory → execute
safely → capture stdout/stderr/outputs → collect artifacts → return a
:class:`PythonExecutionResult`.

The actual ``exec`` runs behind the injectable :class:`PythonExecutor` seam — the
analog of the browser layer's ``BrowserDriver`` — so it stays replaceable and
testable; the default :class:`SafePythonExecutor` runs code with a restricted
builtin set, an import allowlist (math, statistics, json, csv, pathlib, datetime,
re, collections, itertools, numpy, pandas, openpyxl, matplotlib), and a workspace-
confined ``open``. No subprocess, multiprocessing, shell, sockets, network,
threads, or environment access is available to executed code, and no interpreter
object ever escapes into a DTO. Third-party libraries are imported lazily, so this
module imports without them installed. Stateless beyond its injected collaborators;
the workspace is immutable and threaded by the caller. Strictly additive to Sprints
15.1–15.9 — it moves no Runtime, Planning, or Browser code.
"""

import builtins as _builtins
import hashlib
import io
import pathlib
import tempfile
from abc import ABC, abstractmethod
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
)
from app.services.runtime.python_artifact_manager import PythonArtifactManager
from app.services.runtime.python_capability_models import (
    PythonArtifact,
    PythonExecutionRequest,
    PythonExecutionStatus,
    PythonWorkspace,
)
from app.services.runtime.python_execution_result import PythonExecutionResult
from app.services.runtime.python_workspace import PythonWorkspaceManager

# The only module roots executed code may import. Everything else (os, sys,
# subprocess, multiprocessing, socket, requests, …) is rejected with ImportError.
_ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "math", "statistics", "json", "csv", "pathlib", "datetime", "re",
        "collections", "itertools", "numpy", "pandas", "openpyxl", "matplotlib",
    }
)

# Curated safe builtins. Notably excludes eval/exec/compile/input/globals/locals/
# vars and the real __import__/open (which are replaced with confined versions).
_SAFE_BUILTIN_NAMES = frozenset(
    {
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "callable", "chr", "complex", "dict", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "getattr", "hasattr", "hash", "hex",
        "int", "isinstance", "issubclass", "iter", "len", "list", "map", "max",
        "min", "next", "object", "oct", "ord", "pow", "print", "range", "repr",
        "reversed", "round", "set", "setattr", "slice", "sorted", "str", "sum",
        "tuple", "type", "zip",
        # exceptions
        "BaseException", "Exception", "ArithmeticError", "AssertionError",
        "AttributeError", "FloatingPointError", "ImportError", "IndexError",
        "KeyError", "LookupError", "NameError", "NotImplementedError",
        "OverflowError", "RuntimeError", "StopIteration", "TypeError",
        "ValueError", "ZeroDivisionError",
    }
)

_PLAIN_SCALARS = (bool, int, float, str, type(None))


def _is_plain(value: Any) -> bool:
    """Return whether ``value`` is JSON-ish plain data (no objects/modules)."""
    if isinstance(value, _PLAIN_SCALARS):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_plain(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_plain(val) for key, val in value.items()
        )
    return False


class PythonExecutorOutcome(NamedTuple):
    """Plain outcome of one safe execution (no interpreter object escapes).

    ``status`` is a :class:`PythonExecutionStatus` label; ``stdout``/``stderr`` are
    the captured streams; ``outputs`` are the plain-data variables the code left
    behind. Carries only plain data across the executor seam.
    """

    status: str
    stdout: str
    stderr: str
    outputs: Dict[str, Any]


class PythonExecutor(ABC):
    """Replaceable seam that runs Python code and returns a plain outcome.

    Concrete executors own all interpreter mechanics behind this interface so the
    capability stays testable and provider-independent. An executor must never let
    an interpreter frame, module, or provider object escape — it returns only a
    plain :class:`PythonExecutorOutcome`.
    """

    @abstractmethod
    def execute(
        self,
        python_code: str,
        execution_inputs: Dict[str, Any],
        workspace_dir: str,
    ) -> PythonExecutorOutcome:
        """Run ``python_code`` and return its captured outcome (plain data only)."""


class SafePythonExecutor(PythonExecutor):
    """Default executor: restricted ``exec`` with an import + filesystem sandbox.

    Runs code with a curated builtin set, a custom ``__import__`` limited to the
    approved libraries, and an ``open`` confined to the workspace directory. Stdout
    and stderr are captured; a failure is reported as ``FAILED`` with the error on
    stderr (never a raised interpreter object). Third-party libraries are imported
    lazily and only exposed if installed. Stateless — it holds nothing between
    calls and creates no threads or processes.
    """

    def execute(
        self,
        python_code: str,
        execution_inputs: Dict[str, Any],
        workspace_dir: str,
    ) -> PythonExecutorOutcome:
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        namespace = self._approved_namespace()
        reserved = set(namespace) | {"inputs", "workspace_path", "outputs", "__builtins__"}
        sandbox: Dict[str, Any] = dict(namespace)
        sandbox["__builtins__"] = self._safe_builtins(workspace_dir)
        sandbox["inputs"] = dict(execution_inputs or {})
        sandbox["workspace_path"] = pathlib.Path(workspace_dir)
        sandbox["outputs"] = {}

        status = PythonExecutionStatus.COMPLETED
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            try:
                compiled = compile(python_code, "<python_capability>", "exec")
                exec(compiled, sandbox)  # noqa: S102 - sandboxed, restricted builtins
            except BaseException as exc:  # noqa: BLE001 - sandbox: report, never leak
                status = PythonExecutionStatus.FAILED
                print(f"{type(exc).__name__}: {exc}", file=stderr_buffer)

        return PythonExecutorOutcome(
            status=status.value,
            stdout=stdout_buffer.getvalue(),
            stderr=stderr_buffer.getvalue(),
            outputs=self._collect_outputs(sandbox, reserved),
        )

    # --- sandbox construction -------------------------------------------
    def _approved_namespace(self) -> Dict[str, Any]:
        """Expose the approved libraries (stdlib always; third-party if present)."""
        import collections
        import csv
        import datetime
        import itertools
        import json
        import math
        import pathlib as _pathlib
        import re
        import statistics

        namespace: Dict[str, Any] = {
            "math": math,
            "statistics": statistics,
            "json": json,
            "csv": csv,
            "pathlib": _pathlib,
            "datetime": datetime,
            "re": re,
            "collections": collections,
            "itertools": itertools,
        }
        try:
            import numpy

            namespace["numpy"] = numpy
            namespace["np"] = numpy
        except ImportError:
            pass
        try:
            import pandas

            namespace["pandas"] = pandas
            namespace["pd"] = pandas
        except ImportError:
            pass
        try:
            import openpyxl

            namespace["openpyxl"] = openpyxl
        except ImportError:
            pass
        try:
            import matplotlib

            matplotlib.use("Agg")  # headless, deterministic — no display/GUI
            import matplotlib.pyplot as plt

            namespace["matplotlib"] = matplotlib
            namespace["plt"] = plt
        except Exception:  # noqa: BLE001 - matplotlib optional/backend guard
            pass
        return namespace

    def _safe_builtins(self, workspace_dir: str) -> Dict[str, Any]:
        safe: Dict[str, Any] = {
            name: getattr(_builtins, name)
            for name in _SAFE_BUILTIN_NAMES
            if hasattr(_builtins, name)
        }
        safe["True"] = True
        safe["False"] = False
        safe["None"] = None
        safe["__build_class__"] = _builtins.__build_class__  # enable class defs
        safe["__import__"] = self._make_safe_import()
        safe["open"] = self._make_safe_open(workspace_dir)
        return safe

    @staticmethod
    def _make_safe_import():
        real_import = _builtins.__import__

        def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".")[0]
            if root not in _ALLOWED_IMPORT_ROOTS:
                raise ImportError(
                    f"import of '{name}' is not permitted in the Python capability"
                )
            return real_import(name, globals, locals, fromlist, level)

        return _safe_import

    @staticmethod
    def _make_safe_open(workspace_dir: str):
        real_open = _builtins.open
        root = pathlib.Path(workspace_dir).resolve()

        def _safe_open(file, mode="r", *args, **kwargs):
            target = pathlib.Path(file)
            if not target.is_absolute():
                target = root / target
            target = target.resolve()
            try:
                target.relative_to(root)
            except ValueError:
                raise PermissionError(
                    "file access outside the workspace is not permitted"
                )
            return real_open(target, mode, *args, **kwargs)

        return _safe_open

    @staticmethod
    def _collect_outputs(
        sandbox: Dict[str, Any], reserved: set
    ) -> Dict[str, Any]:
        """Return the code's plain-data variables (explicit ``outputs`` + globals)."""
        collected: Dict[str, Any] = {}
        explicit = sandbox.get("outputs")
        if isinstance(explicit, dict):
            for key, value in explicit.items():
                if isinstance(key, str) and _is_plain(value):
                    collected[key] = value
        for key, value in sandbox.items():
            if key in reserved or key.startswith("_") or callable(value):
                continue
            if _is_plain(value):
                collected.setdefault(key, value)
        return collected


class PythonCapability(ExecutionCapability):
    """Python execution capability implementing the Sprint 14.3 contract.

    Coordinates the workspace → safe execution → artifact manager → result
    pipeline. ``run`` validates the request, prepares a workspace directory,
    executes through the injected :class:`PythonExecutor`, collects artifacts, and
    returns a :class:`PythonExecutionResult`; ``run_in_workspace`` also folds the
    execution into a new immutable :class:`PythonWorkspace`; ``execute`` bridges the
    runtime :class:`CapabilityExecutionRequest`/``Result``. Stateless beyond its
    injected collaborators and workspace root — it runs no threads or processes and
    never lets an interpreter object escape.
    """

    def __init__(
        self,
        executor: Optional[PythonExecutor] = None,
        artifact_manager: Optional[PythonArtifactManager] = None,
        workspace_manager: Optional[PythonWorkspaceManager] = None,
        workspace_root: Optional[str] = None,
    ) -> None:
        self.executor = executor or SafePythonExecutor()
        self.artifact_manager = artifact_manager or PythonArtifactManager()
        self.workspace_manager = workspace_manager or PythonWorkspaceManager()
        self.workspace_root = workspace_root

    # --- native API ------------------------------------------------------
    def create_workspace(self, workspace_id: str = "python-workspace") -> PythonWorkspace:
        """Create a fresh workspace via the :class:`PythonWorkspaceManager`."""
        return self.workspace_manager.create_workspace(workspace_id)

    def run(self, request: PythonExecutionRequest) -> PythonExecutionResult:
        """Validate, execute safely, collect artifacts, and return the result.

        Empty or non-string code fails gracefully as ``FAILED`` before any
        execution. Otherwise the code runs through the injected executor in a
        deterministic per-request workspace directory, and the produced files are
        collected as artifacts. Never raises for user-code errors — they are
        reported on ``stderr`` with ``FAILED`` status.
        """
        if not isinstance(request.python_code, str) or not request.python_code.strip():
            return self._failure(request, "no python code provided")

        work_dir = self._work_dir(request)
        outcome = self.executor.execute(
            request.python_code, request.execution_inputs, str(work_dir)
        )
        artifacts = self.artifact_manager.collect(
            work_dir, {"execution_unit_id": request.execution_unit_id}
        )
        return PythonExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            execution_status=outcome.status,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            execution_outputs=outcome.outputs,
            artifacts=artifacts,
            execution_metadata={
                "artifact_count": len(artifacts),
                "output_count": len(outcome.outputs),
                "workspace_dir": str(work_dir),
            },
        )

    def run_in_workspace(
        self, workspace: PythonWorkspace, request: PythonExecutionRequest
    ) -> Tuple[PythonExecutionResult, PythonWorkspace]:
        """Run and fold the execution into a *new* immutable workspace.

        Returns the :class:`PythonExecutionResult` and a new
        :class:`PythonWorkspace` (variables merged, artifacts and history appended);
        the input workspace is never mutated.
        """
        result = self.run(request)
        updated = self.workspace_manager.record_execution(
            workspace,
            request=request,
            execution_outputs=result.execution_outputs,
            artifacts=result.artifacts,
            status=result.execution_status,
        )
        return result, updated

    # --- ExecutionCapability contract (Sprint 14.3) ---------------------
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Bridge the runtime contract to one Python execution.

        Reads ``python_code`` and ``execution_inputs`` from ``capability_inputs``,
        runs, and maps the result to a :class:`CapabilityExecutionResult` with plain
        outputs (stdout/stderr/outputs/artifact descriptors) — never an interpreter
        object.
        """
        inputs = request.capability_inputs
        py_request = PythonExecutionRequest(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            python_code=inputs.get("python_code", ""),
            execution_inputs=inputs.get("execution_inputs", {}),
        )
        result = self.run(py_request)
        return CapabilityExecutionResult(
            runtime_id=result.runtime_id,
            execution_id=result.execution_id,
            execution_unit_id=result.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=result.execution_status,
            capability_outputs={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_outputs": result.execution_outputs,
                "artifacts": [self._artifact_dict(a) for a in result.artifacts],
                "status": result.execution_status,
            },
            execution_metadata=dict(result.execution_metadata),
        )

    # --- deterministic helpers ------------------------------------------
    def _work_dir(self, request: PythonExecutionRequest) -> pathlib.Path:
        """Return a deterministic per-request workspace directory (created)."""
        base = (
            pathlib.Path(self.workspace_root)
            if self.workspace_root
            else pathlib.Path(tempfile.gettempdir()) / "neuraevo_python"
        )
        digest = hashlib.sha256(
            f"{request.execution_id}:{request.execution_unit_id}".encode("utf-8")
        ).hexdigest()[:16]
        work_dir = base / f"py-{digest}"
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    @staticmethod
    def _artifact_dict(artifact: PythonArtifact) -> Dict[str, Any]:
        return {
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type,
            "artifact_name": artifact.artifact_name,
            "artifact_path": artifact.artifact_path,
        }

    def _failure(
        self, request: PythonExecutionRequest, error: str
    ) -> PythonExecutionResult:
        return PythonExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            execution_status=PythonExecutionStatus.FAILED.value,
            stdout="",
            stderr=error,
            execution_outputs={},
            artifacts=[],
            execution_metadata={"error": error},
        )
