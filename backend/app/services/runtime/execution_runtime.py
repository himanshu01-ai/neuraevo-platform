"""Execution runtime (Sprint 14.1 — deterministic runtime-context creation).

Owns the lifecycle of one execution session by consuming a Sprint 13
:class:`ExecutionOrchestrationResult` and establishing an immutable
:class:`ExecutionRuntimeContext` for it. It ONLY establishes runtime state: it
creates the context, derives a deterministic runtime id from the execution id,
stores the orchestration untouched, and initializes the empty variable/output/
metadata working stores. It never dispatches work, executes capabilities, calls
tools, recovers, approves, or performs any networking or I/O, and it never
mutates the orchestration.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, dispatcher,
capability knowledge, Runtime global, or persistence. Same orchestration in ->
same runtime context out.
"""

from app.services.planning.planning_engine import ExecutionOrchestrationResult
from app.services.runtime.execution_runtime_models import (
    ExecutionRuntimeContext,
    ExecutionRuntimeStatus,
)

# The genesis sequence position of a freshly initialized runtime session. It is a
# fixed, deterministic ordinal — never a clock time and never a global counter
# (the runtime is stateless) — so one orchestration always yields one identical
# context.
_GENESIS_SEQUENCE = 0


class ExecutionRuntime:
    """Stateless runtime: :class:`ExecutionOrchestrationResult` -> context.

    Holds no state and owns no session, provider, cache, clock, or global. It
    creates exactly one immutable :class:`ExecutionRuntimeContext` per
    orchestration — status ``INITIALIZED``, no current unit, and empty variable/
    output/metadata stores — with a deterministic ``runtime_id`` derived from the
    execution id. It never dispatches, executes, recovers, approves, or performs
    any I/O, and it never modifies the orchestration.
    """

    def create_context(
        self, orchestration: ExecutionOrchestrationResult
    ) -> ExecutionRuntimeContext:
        """Return a deterministic :class:`ExecutionRuntimeContext` (no execution).

        The runtime id is derived from the orchestration's execution id; the
        status is always ``INITIALIZED``; the orchestration is stored unchanged;
        the current unit is ``None``; and the runtime variable, output, and
        metadata stores start empty. The orchestration is only read — never
        modified — and nothing is executed, dispatched, recovered, or approved.
        """
        execution_id = orchestration.state.execution_id
        return ExecutionRuntimeContext(
            runtime_id=f"runtime-{execution_id}",
            execution_id=execution_id,
            runtime_status=ExecutionRuntimeStatus.INITIALIZED.value,
            orchestration=orchestration,
            current_execution_unit_id=None,
            execution_variables={},
            execution_outputs={},
            execution_metadata={},
            created_at_sequence=_GENESIS_SEQUENCE,
            metadata={
                "total_execution_units": len(
                    orchestration.queue.execution_units
                ),
                "source_execution_id": execution_id,
            },
        )
