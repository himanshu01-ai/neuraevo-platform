"""Unit tests for the Sprint 15.10 Python Capability.

Covers the first-class Python :class:`ExecutionCapability` end to end without any
network, subprocess, or SDK: code runs in-process through the deterministic
:class:`SafePythonExecutor` sandbox, and each test uses a fresh temporary workspace
root that is cleaned up. Tests for the optional third-party libraries (numpy,
pandas, openpyxl, matplotlib) are skipped when those libraries are not installed.

Covers:

* the immutable :class:`PythonExecutionRequest` / :class:`PythonExecutionResult` /
  :class:`PythonWorkspace` / :class:`PythonArtifact` DTOs and the
  :class:`PythonExecutionStatus` enum;
* workspace creation, history preservation, and immutability;
* successful execution, stdout/stderr capture, output collection, determinism;
* artifact generation (text/CSV/JSON always; Excel/DataFrame/NumPy/matplotlib when
  available);
* the sandbox security controls (blocked imports, workspace-confined filesystem);
* provider independence (an injected fake executor) and ExecutionCapability
  compliance;
* the composition-root wiring; and
* regression that prior seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_python_capability
"""

import shutil
import tempfile
import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionStatus,
)
from app.services.runtime.python_artifact_manager import PythonArtifactManager
from app.services.runtime.python_capability import (
    PythonCapability,
    PythonExecutor,
    PythonExecutorOutcome,
    SafePythonExecutor,
)
from app.services.runtime.python_capability_models import (
    PythonArtifact,
    PythonExecutionRequest,
    PythonExecutionStatus,
    PythonWorkspace,
)
from app.services.runtime.python_execution_result import PythonExecutionResult
from app.services.runtime.python_workspace import PythonWorkspaceManager


def _available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


_HAS_NUMPY = _available("numpy")
_HAS_PANDAS = _available("pandas")
_HAS_OPENPYXL = _available("openpyxl")
_HAS_MATPLOTLIB = _available("matplotlib")


class _PythonCapabilityTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace_root = tempfile.mkdtemp(prefix="neuraevo_py_test_")
        self.capability = PythonCapability(workspace_root=self.workspace_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.workspace_root, ignore_errors=True)

    def _request(self, code, unit_id="unit-1", **inputs) -> PythonExecutionRequest:
        return PythonExecutionRequest(
            runtime_id="rt",
            execution_id="ex",
            execution_unit_id=unit_id,
            python_code=code,
            execution_inputs=inputs,
        )

    def _run(self, code, unit_id="unit-1", **inputs) -> PythonExecutionResult:
        return self.capability.run(self._request(code, unit_id, **inputs))


# =====================================================================
# DTOs
# =====================================================================
class PythonDtoTests(unittest.TestCase):
    def test_status_values(self):
        self.assertEqual(
            [s.value for s in PythonExecutionStatus],
            ["READY", "EXECUTING", "COMPLETED", "FAILED", "CANCELLED"],
        )

    def test_request_defaults_and_immutable(self):
        req = PythonExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u", python_code="x=1"
        )
        self.assertEqual(req.execution_inputs, {})
        self.assertEqual(req.execution_metadata, {})
        with self.assertRaises(ValidationError):
            req.python_code = "y=2"

    def test_result_defaults_and_immutable(self):
        result = PythonExecutionResult(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            execution_status="COMPLETED",
        )
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.artifacts, [])
        with self.assertRaises(ValidationError):
            result.execution_status = "FAILED"

    def test_workspace_immutable(self):
        workspace = PythonWorkspace(workspace_id="w")
        with self.assertRaises(ValidationError):
            workspace.variables = {"a": 1}
        with self.assertRaises(ValidationError):
            workspace.execution_history = []

    def test_artifact_immutable(self):
        artifact = PythonArtifact(
            artifact_id="a", artifact_type="CSV", artifact_name="d.csv", artifact_path="/tmp/d.csv"
        )
        with self.assertRaises(ValidationError):
            artifact.artifact_type = "JSON"


# =====================================================================
# Workspace lifecycle
# =====================================================================
class PythonWorkspaceTests(_PythonCapabilityTestBase):
    def test_create_workspace_is_empty(self):
        workspace = self.capability.create_workspace("w1")
        self.assertEqual(workspace.workspace_id, "w1")
        self.assertEqual(workspace.variables, {})
        self.assertEqual(workspace.artifacts, [])
        self.assertEqual(workspace.execution_history, [])
        self.assertEqual(workspace.workspace_metadata["execution_count"], 0)

    def test_history_is_preserved_across_executions(self):
        workspace = self.capability.create_workspace("w1")
        _, workspace = self.capability.run_in_workspace(
            workspace, self._request('outputs["a"] = 1', unit_id="h1")
        )
        _, workspace = self.capability.run_in_workspace(
            workspace, self._request('outputs["b"] = 2', unit_id="h2")
        )
        self.assertEqual(len(workspace.execution_history), 2)
        self.assertEqual(workspace.variables, {"a": 1, "b": 2})
        self.assertEqual(workspace.workspace_metadata["execution_count"], 2)

    def test_workspace_is_immutable_new_instance_each_run(self):
        original = self.capability.create_workspace("w1")
        _, updated = self.capability.run_in_workspace(
            original, self._request('outputs["a"] = 1', unit_id="h1")
        )
        # The original is untouched; a new workspace is returned.
        self.assertEqual(original.variables, {})
        self.assertEqual(original.execution_history, [])
        self.assertIsNot(updated, original)
        self.assertEqual(updated.variables, {"a": 1})

    def test_workspace_manager_is_stateless(self):
        self.assertEqual(vars(PythonWorkspaceManager()), {})


# =====================================================================
# Execution
# =====================================================================
class PythonExecutionTests(_PythonCapabilityTestBase):
    def test_successful_execution(self):
        result = self._run('x = 2 + 3\noutputs["y"] = x * 2')
        self.assertEqual(result.execution_status, PythonExecutionStatus.COMPLETED.value)
        self.assertEqual(result.execution_outputs["y"], 10)
        self.assertEqual(result.execution_outputs["x"], 5)

    def test_stdout_capture(self):
        result = self._run('print("hello world")')
        self.assertEqual(result.stdout, "hello world\n")
        self.assertEqual(result.execution_status, "COMPLETED")

    def test_stderr_capture_on_error(self):
        result = self._run('print("before")\nraise ValueError("boom")')
        self.assertEqual(result.execution_status, PythonExecutionStatus.FAILED.value)
        self.assertEqual(result.stdout, "before\n")
        self.assertIn("ValueError: boom", result.stderr)

    def test_empty_code_fails_gracefully(self):
        self.assertEqual(self._run("   ").execution_status, "FAILED")

    def test_execution_inputs_are_exposed(self):
        result = self._run('outputs["total"] = inputs["a"] + inputs["b"]', a=3, b=4)
        self.assertEqual(result.execution_outputs["total"], 7)

    def test_outputs_are_plain_data_only(self):
        # A module / function assigned to a variable is not collected as output.
        result = self._run('import math\nf = lambda x: x\nn = math.pi > 3')
        self.assertNotIn("math", result.execution_outputs)
        self.assertNotIn("f", result.execution_outputs)
        self.assertEqual(result.execution_outputs.get("n"), True)

    def test_determinism(self):
        a = self._run('outputs["v"] = sum(range(10))', unit_id="det")
        b = self._run('outputs["v"] = sum(range(10))', unit_id="det")
        self.assertEqual(a.execution_outputs, b.execution_outputs)
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(a.execution_status, b.execution_status)

    def test_approved_stdlib_libraries_work(self):
        code = (
            "import statistics, itertools\n"
            "from collections import Counter\n"
            'outputs["mean"] = statistics.mean([1, 2, 3])\n'
            'outputs["count"] = Counter("aab")["a"]\n'
        )
        result = self._run(code)
        self.assertEqual(result.execution_outputs["mean"], 2)
        self.assertEqual(result.execution_outputs["count"], 2)


# =====================================================================
# Security sandbox
# =====================================================================
class PythonSecurityTests(_PythonCapabilityTestBase):
    def test_dangerous_imports_are_blocked(self):
        for library in ("os", "sys", "subprocess", "multiprocessing", "socket", "requests"):
            result = self._run(f"import {library}", unit_id=f"imp-{library}")
            self.assertEqual(result.execution_status, "FAILED", library)
            self.assertIn("not permitted", result.stderr, library)

    def test_filesystem_outside_workspace_is_blocked(self):
        result = self._run('open("/etc/passwd", "r")')
        self.assertEqual(result.execution_status, "FAILED")
        self.assertIn("not permitted", result.stderr)

    def test_eval_and_exec_are_unavailable(self):
        for builtin in ("eval", "exec", "__import__(\"os\")"):
            result = self._run(f'{builtin}("1")' if "(" not in builtin else builtin, unit_id="b")
            self.assertEqual(result.execution_status, "FAILED")

    def test_workspace_confined_open_writes_inside_workspace(self):
        result = self._run('open(workspace_path / "safe.txt", "w").write("ok")')
        self.assertEqual(result.execution_status, "COMPLETED")
        self.assertTrue(any(a.artifact_name == "safe.txt" for a in result.artifacts))


# =====================================================================
# Artifacts
# =====================================================================
class PythonArtifactTests(_PythonCapabilityTestBase):
    def test_text_artifact(self):
        result = self._run('open(workspace_path / "note.txt", "w").write("hi")')
        artifact = next(a for a in result.artifacts if a.artifact_name == "note.txt")
        self.assertEqual(artifact.artifact_type, "TEXT")

    def test_csv_creation(self):
        code = (
            "import csv\n"
            'with open(workspace_path / "data.csv", "w", newline="") as f:\n'
            "    w = csv.writer(f)\n"
            '    w.writerow(["a", "b"])\n'
            "    w.writerow([1, 2])\n"
        )
        result = self._run(code)
        artifact = next(a for a in result.artifacts if a.artifact_name == "data.csv")
        self.assertEqual(artifact.artifact_type, "CSV")
        self.assertEqual(result.execution_status, "COMPLETED")

    def test_json_generation(self):
        code = (
            "import json\n"
            'with open(workspace_path / "out.json", "w") as f:\n'
            '    json.dump({"k": 1}, f)\n'
        )
        result = self._run(code)
        artifact = next(a for a in result.artifacts if a.artifact_name == "out.json")
        self.assertEqual(artifact.artifact_type, "JSON")

    def test_artifacts_have_deterministic_ordered_ids(self):
        code = (
            'open(workspace_path / "b.txt", "w").write("b")\n'
            'open(workspace_path / "a.txt", "w").write("a")\n'
        )
        result = self._run(code)
        ids = [(a.artifact_id, a.artifact_name) for a in result.artifacts]
        self.assertEqual(ids, [("artifact-0", "a.txt"), ("artifact-1", "b.txt")])

    def test_artifact_manager_is_stateless_and_runs_no_python(self):
        self.assertEqual(vars(PythonArtifactManager()), {})
        self.assertEqual(PythonArtifactManager().classify("x.png"), "PNG")
        self.assertEqual(PythonArtifactManager().classify("x.pdf"), "PDF")

    @unittest.skipUnless(_HAS_OPENPYXL, "openpyxl not installed")
    def test_excel_creation(self):
        code = (
            "import openpyxl\n"
            "wb = openpyxl.Workbook()\n"
            'wb.active["A1"] = "hello"\n'
            'wb.save(str(workspace_path / "book.xlsx"))\n'
        )
        result = self._run(code)
        self.assertEqual(result.execution_status, "COMPLETED", result.stderr)
        self.assertTrue(any(a.artifact_type == "EXCEL" for a in result.artifacts))

    @unittest.skipUnless(_HAS_MATPLOTLIB, "matplotlib not installed")
    def test_matplotlib_chart_generation(self):
        code = (
            "import matplotlib.pyplot as plt\n"
            "plt.plot([1, 2, 3], [4, 5, 6])\n"
            'plt.savefig(str(workspace_path / "chart.png"))\n'
        )
        result = self._run(code)
        self.assertEqual(result.execution_status, "COMPLETED", result.stderr)
        self.assertTrue(any(a.artifact_type == "PNG" for a in result.artifacts))


# =====================================================================
# Structured data (optional libraries)
# =====================================================================
class PythonDataTests(_PythonCapabilityTestBase):
    @unittest.skipUnless(_HAS_NUMPY, "numpy not installed")
    def test_numpy_operations(self):
        code = (
            "import numpy as np\n"
            "arr = np.array([1, 2, 3, 4])\n"
            'outputs["sum"] = int(arr.sum())\n'
            'outputs["mean"] = float(arr.mean())\n'
        )
        result = self._run(code)
        self.assertEqual(result.execution_status, "COMPLETED", result.stderr)
        self.assertEqual(result.execution_outputs["sum"], 10)
        self.assertEqual(result.execution_outputs["mean"], 2.5)

    @unittest.skipUnless(_HAS_PANDAS, "pandas not installed")
    def test_dataframe_support(self):
        code = (
            "import pandas as pd\n"
            'df = pd.DataFrame({"x": [1, 2, 3]})\n'
            'outputs["rows"] = int(len(df))\n'
            'outputs["total"] = int(df["x"].sum())\n'
            'df.to_csv(str(workspace_path / "df.csv"), index=False)\n'
        )
        result = self._run(code)
        self.assertEqual(result.execution_status, "COMPLETED", result.stderr)
        self.assertEqual(result.execution_outputs["rows"], 3)
        self.assertEqual(result.execution_outputs["total"], 6)
        self.assertTrue(any(a.artifact_type == "CSV" for a in result.artifacts))


# =====================================================================
# Provider independence / ExecutionCapability compliance
# =====================================================================
class _FakeExecutor(PythonExecutor):
    def __init__(self) -> None:
        self.calls = []

    def execute(self, python_code, execution_inputs, workspace_dir):
        self.calls.append((python_code, execution_inputs, workspace_dir))
        return PythonExecutorOutcome(
            status="COMPLETED", stdout="fake-out", stderr="", outputs={"z": 42}
        )


class PythonProviderTests(_PythonCapabilityTestBase):
    def test_provider_independence_with_injected_executor(self):
        fake = _FakeExecutor()
        capability = PythonCapability(executor=fake, workspace_root=self.workspace_root)
        result = capability.run(self._request('print("ignored")'))
        self.assertEqual(result.stdout, "fake-out")
        self.assertEqual(result.execution_outputs, {"z": 42})
        self.assertEqual(len(fake.calls), 1)

    def test_results_are_plain_dtos(self):
        result = self._run('outputs["a"] = 1')
        self.assertIsInstance(result, PythonExecutionResult)
        self.assertIsInstance(result, BaseModel)
        for artifact in result.artifacts:
            self.assertIsInstance(artifact, PythonArtifact)

    def test_is_execution_capability(self):
        self.assertIsInstance(self.capability, ExecutionCapability)

    def test_execute_bridges_runtime_contract(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="python",
            capability_inputs={"python_code": 'print("hi")\noutputs["v"] = 9'},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.COMPLETED.value)
        self.assertEqual(result.capability_outputs["stdout"], "hi\n")
        self.assertEqual(result.capability_outputs["execution_outputs"]["v"], 9)
        self.assertEqual(result.capability_name, "python")

    def test_execute_maps_failure(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="python", capability_inputs={"python_code": "raise KeyError()"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.FAILED.value)

    def test_execute_outputs_are_plain_data(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="python", capability_inputs={"python_code": 'outputs["a"]=1'},
        )
        result = self.capability.execute(request)
        for value in result.capability_outputs.values():
            self.assertNotIsInstance(value, BaseModel)


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class PythonCapabilityDependencyInjectionTests(unittest.TestCase):
    def test_get_python_capability_returns_capability(self):
        from app.core.dependencies import get_python_capability

        capability = get_python_capability()
        self.assertIsInstance(capability, PythonCapability)
        self.assertIsInstance(capability, ExecutionCapability)

    def test_python_capability_dep_is_wired(self):
        from app.core.dependencies import PythonCapabilityDep

        self.assertIn(PythonCapability, getattr(PythonCapabilityDep, "__args__", ()))

    def test_wired_capability_executes(self):
        from app.core.dependencies import get_python_capability

        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="python", capability_inputs={"python_code": 'outputs["ok"]=True'},
        )
        result = get_python_capability().execute(request)
        self.assertEqual(result.execution_status, "COMPLETED")


# =====================================================================
# Regression — prior seams unchanged
# =====================================================================
class PythonCapabilityRegressionTests(unittest.TestCase):
    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)

    def test_sprint_15_6_browser_capability_unchanged(self):
        from app.core.dependencies import get_browser_capability

        self.assertIsInstance(get_browser_capability(), ExecutionCapability)

    def test_safe_executor_is_stateless(self):
        self.assertEqual(vars(SafePythonExecutor()), {})


if __name__ == "__main__":
    unittest.main()
