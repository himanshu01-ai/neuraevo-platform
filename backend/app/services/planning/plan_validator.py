"""Plan validator (Sprint 13.1 — structural/logical guarantees).

Provider-independent validation that every :class:`ExecutionPlan` the engine
returns is well-formed before it reaches a caller (or, later, an execution
layer). It inspects only the plan's plain data and performs NO execution,
provider, AI, or runtime work.

Rules enforced:

* **Non-empty** — a plan must contain at least one step.
* **No duplicate steps** — ``step_number`` values are unique, and step
  descriptions are distinct.
* **Logical ordering** — step numbers are exactly ``1..N`` in order.
* **Dependency correctness** — every dependency references a distinct, earlier
  step that exists; no step depends on itself or on a later step.
"""

from app.services.planning.models import ExecutionPlan


class PlanValidationError(ValueError):
    """Raised when an :class:`ExecutionPlan` violates a structural/logical rule.

    Subclasses :class:`ValueError` so callers may treat it as an ordinary
    validation failure. The message names the specific rule that failed.
    """


class PlanValidator:
    """Stateless validator for :class:`ExecutionPlan` well-formedness.

    Holds no state and owns no session, provider, or cache. ``validate`` raises
    :class:`PlanValidationError` on the first rule violation and otherwise
    returns ``None``; ``is_valid`` is a boolean convenience over it.
    """

    def validate(self, plan: ExecutionPlan) -> None:
        """Raise :class:`PlanValidationError` if ``plan`` is not well-formed.

        Checks emptiness, duplicate steps, logical ordering, then per-step
        dependency correctness — in that order — so the raised message points at
        the most fundamental problem first.
        """
        steps = plan.steps

        # 1. Empty plans are not plannable output.
        if not steps:
            raise PlanValidationError(
                "Plan has no steps; an empty plan is not valid."
            )

        step_numbers = [step.step_number for step in steps]

        # 2a. Duplicate step numbers.
        if len(set(step_numbers)) != len(step_numbers):
            raise PlanValidationError(
                f"Duplicate step numbers found: {step_numbers}."
            )

        # 2b. Duplicate step descriptions (case-insensitive, trimmed).
        normalized = [step.description.strip().lower() for step in steps]
        if len(set(normalized)) != len(normalized):
            raise PlanValidationError(
                "Duplicate step descriptions found; steps must be distinct."
            )

        # 3. Logical ordering: numbers must be exactly 1..N in listed order.
        expected = list(range(1, len(steps) + 1))
        if step_numbers != expected:
            raise PlanValidationError(
                "Step numbers must be sequential 1.."
                f"{len(steps)} in order; got {step_numbers}."
            )

        # 4. Dependency correctness (all dependencies precede their step).
        valid_numbers = set(step_numbers)
        for step in steps:
            dependencies = step.dependencies

            if len(set(dependencies)) != len(dependencies):
                raise PlanValidationError(
                    f"Step {step.step_number} has duplicate dependencies: "
                    f"{dependencies}."
                )

            for dependency in dependencies:
                if dependency == step.step_number:
                    raise PlanValidationError(
                        f"Step {step.step_number} depends on itself."
                    )
                if dependency not in valid_numbers:
                    raise PlanValidationError(
                        f"Step {step.step_number} depends on unknown step "
                        f"{dependency}."
                    )
                if dependency > step.step_number:
                    raise PlanValidationError(
                        f"Step {step.step_number} depends on later step "
                        f"{dependency}; dependencies must come earlier."
                    )

    def is_valid(self, plan: ExecutionPlan) -> bool:
        """Return ``True`` if ``plan`` passes :meth:`validate`, else ``False``."""
        try:
            self.validate(plan)
        except PlanValidationError:
            return False
        return True
