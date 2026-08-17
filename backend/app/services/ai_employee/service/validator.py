"""Request validator (Sprint 16.10 — validate incoming service requests).

Defines :class:`RequestValidator`, which validates every incoming
:class:`TaskSubmissionRequest` before the Service Layer acts on it. Structural
constraints (non-empty ids/task, correct types) are already enforced by the frozen
immutable DTOs; this validator adds the deterministic *business* checks — a
well-formed request object, unique and well-formed workflow steps — and raises a
:class:`ValidationException` carrying the exact issues.

It is deterministic and stateless: it validates only and decides, delegates, and
executes nothing. It never touches the Workflow Coordinator, a capability, a
repository, a database, an LLM provider, a thread, or the network. Strictly additive
to Sprints 1.x–16.9, whose modules are left untouched.
"""

from typing import List

from app.services.ai_employee.service.models import (
    TaskSubmissionRequest,
    ValidationException,
)


class RequestValidator:
    """Validates a :class:`TaskSubmissionRequest` deterministically (no execution).

    ``validate`` returns ``None`` for a valid request and raises a
    :class:`ValidationException` (carrying the ordered list of issues) for an invalid
    one — a wrong object type, an empty/duplicate workflow step id, or a step missing
    its capability name. Deterministic and stateless.
    """

    def validate(self, request: TaskSubmissionRequest) -> None:
        """Validate ``request``; raise :class:`ValidationException` on any issue."""
        issues: List[str] = []
        if not isinstance(request, TaskSubmissionRequest):
            raise ValidationException(
                "request must be a TaskSubmissionRequest",
                issues=["request: wrong type"],
            )

        seen_step_ids = set()
        for index, step in enumerate(request.workflow_steps):
            if not step.step_id.strip():
                issues.append(f"workflow_steps[{index}]: empty step_id")
            elif step.step_id in seen_step_ids:
                issues.append(
                    f"workflow_steps[{index}]: duplicate step_id "
                    f"{step.step_id!r}"
                )
            else:
                seen_step_ids.add(step.step_id)
            if not step.capability_name.strip():
                issues.append(
                    f"workflow_steps[{index}]: empty capability_name"
                )

        if issues:
            raise ValidationException(
                f"invalid task submission ({len(issues)} issue(s))",
                issues=issues,
            )
