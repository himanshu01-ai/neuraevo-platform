"""Heuristic planning provider (Sprint 13.1 — deterministic default strategy).

The default, provider-independent :class:`PlanningProvider`. It reasons purely
from the request text using intent heuristics and curated plan templates — no
AI/LLM, SDK, network, or configuration. Given a :class:`PlanningRequest` it:

1. detects the goal category (travel, interview, fitness, business, study, daily
   scheduling, or a generic fallback) from keywords in the combined request,
   conversation context, and memory summary;
2. materialises the matching template into an ordered, linearly-dependent
   sequence of :class:`ExecutionStep` objects (each ``PLANNED``); and
3. prunes any prerequisite the caller already supplied, leaving the rest in
   ``missing_information``.

It never executes a step. Because the strategy is deterministic, the same input
always yields the same plan — which keeps it trivially testable and a safe,
offline default until an LLM-backed provider replaces it.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.services.planning.models import ExecutionPlan, ExecutionStep, PlanningRequest
from app.services.planning.providers.base import PlanningProvider

# (description, reason, expected_tool | None) — one planned reasoning step.
_StepSpec = Tuple[str, str, Optional[str]]


@dataclass(frozen=True)
class _Prerequisite:
    """A fact the plan needs, plus keywords that mark it as already supplied."""

    label: str
    satisfied_by: Tuple[str, ...]


@dataclass(frozen=True)
class _Template:
    """A reusable plan skeleton for one goal category (internal, not a DTO)."""

    category: str
    goal: str
    summary: str
    steps: Tuple[_StepSpec, ...]
    requires_user_confirmation: bool
    prerequisites: Tuple[_Prerequisite, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Intent detection. Ordered: the first category with a keyword hit wins, so
# more specific categories are listed before broader ones.
# ---------------------------------------------------------------------------
_INTENT_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "travel",
        ("trip", "travel", "flight", "flights", "vacation", "hotel",
         "destination", "holiday", "getaway", "itinerary"),
    ),
    (
        "interview",
        ("interview", "resume", "cv", "recruiter", "hiring", "job offer",
         "job application", "mock interview"),
    ),
    (
        "fitness",
        ("fitness", "workout", "exercise", "gym", "nutrition", "diet",
         "weight", "muscle", "training", "marathon"),
    ),
    (
        "business",
        ("business", "startup", "revenue", "marketing", "sales", "proposal",
         "strategy", "launch", "client"),
    ),
    (
        "study",
        ("study", "learn", "exam", "course", "certification", "syllabus",
         "revision", "tutorial"),
    ),
    (
        "scheduling",
        ("schedule", "calendar", "agenda", "plan my day", "organize my day",
         "time block", "daily plan", "my day"),
    ),
)


_TEMPLATES: Tuple[_Template, ...] = (
    _Template(
        category="travel",
        goal="Plan your trip",
        summary=(
            "Confirm the destination and dates, check your calendar, compare "
            "flights and hotels, and present a recommendation for your approval."
        ),
        steps=(
            ("Understand the destination",
             "Clarify where you want to go so every later step targets the "
             "right place.", None),
            ("Collect the travel dates",
             "Fix the date range that flights, hotels, and calendar checks all "
             "depend on.", None),
            ("Review your calendar",
             "Check existing commitments so the trip does not clash with them.",
             "calendar"),
            ("Search flights",
             "Find flight options that fit the destination and dates.",
             "flight_search"),
            ("Search hotels",
             "Find lodging options for the same destination and dates.",
             "hotel_search"),
            ("Compare options",
             "Weigh price, timing, and convenience across the flight and hotel "
             "choices.", None),
            ("Present a recommendation",
             "Summarise the best combination for you to review.", None),
            ("Await your approval",
             "Pause for your decision before anything is booked.", None),
        ),
        requires_user_confirmation=True,
        prerequisites=(
            _Prerequisite("the destination",
                          ("destination", "going to", "travel to", "trip to",
                           "visit", "fly to", "flying to")),
            _Prerequisite("your travel dates",
                          ("date", "dates", "day", "week", "month", "weekend")),
        ),
    ),
    _Template(
        category="interview",
        goal="Prepare you for the interview",
        summary=(
            "Understand the target role, research the company, review your "
            "resume, build a preparation roadmap, and run a mock interview for "
            "your approval."
        ),
        steps=(
            ("Understand the target role",
             "Anchor preparation to the specific role and its expectations.",
             None),
            ("Research the company",
             "Gather context on the company so answers can be tailored.",
             "web_search"),
            ("Review your resume",
             "Identify strengths and gaps to emphasise or address.",
             "document_review"),
            ("Create a preparation roadmap",
             "Sequence the topics and materials to cover before the interview.",
             None),
            ("Generate a mock interview",
             "Produce practice questions matched to the role and company.",
             None),
            ("Await your approval",
             "Pause for your go-ahead before acting on the roadmap.", None),
        ),
        requires_user_confirmation=True,
        prerequisites=(
            _Prerequisite("the target role",
                          ("role", "position", "as a", "as an", "title")),
            _Prerequisite("the company",
                          ("company", "employer", "at ", "organisation",
                           "organization")),
        ),
    ),
    _Template(
        category="fitness",
        goal="Build your fitness plan",
        summary=(
            "Understand the objective, collect health information, create "
            "nutrition and workout plans, define milestones, and schedule "
            "reviews."
        ),
        steps=(
            ("Understand the objective",
             "Clarify the fitness goal so the plan targets the right outcome.",
             None),
            ("Collect health information",
             "Gather the health details needed to make the plan safe and "
             "realistic.", None),
            ("Create a nutrition plan",
             "Design eating guidance aligned to the objective.",
             "nutrition_planner"),
            ("Create a workout plan",
             "Design a training routine aligned to the objective.",
             "workout_planner"),
            ("Define milestones",
             "Set measurable checkpoints to track progress.", None),
            ("Schedule reviews",
             "Plan check-ins to reassess and adjust the plan.", "calendar"),
        ),
        requires_user_confirmation=False,
        prerequisites=(
            _Prerequisite("your objective",
                          ("lose", "gain", "build", "run", "tone", "strength",
                           "endurance", "goal")),
            _Prerequisite("your health information",
                          ("height", "weight", "age", "health", "medical",
                           "injury", "bmi")),
        ),
    ),
    _Template(
        category="business",
        goal="Work through your business task",
        summary=(
            "Understand the objective, gather context, analyse options, draft a "
            "plan, identify risks, and present a recommendation for your "
            "approval."
        ),
        steps=(
            ("Understand the objective",
             "Define the business outcome the work should achieve.", None),
            ("Gather relevant context",
             "Collect the market, product, or customer facts the analysis "
             "needs.", "web_search"),
            ("Analyse the options",
             "Compare viable approaches against the objective and constraints.",
             None),
            ("Draft a plan",
             "Turn the chosen approach into concrete, ordered actions.", None),
            ("Identify risks",
             "Surface the assumptions and risks that could derail the plan.",
             None),
            ("Present a recommendation",
             "Summarise the recommended plan for your review.", None),
            ("Await your approval",
             "Pause for your decision before anything is acted on.", None),
        ),
        requires_user_confirmation=True,
        prerequisites=(
            _Prerequisite("the objective or target",
                          ("goal", "target", "objective", "kpi", "revenue "
                           "goal")),
            _Prerequisite("the constraints or budget",
                          ("budget", "timeline", "deadline", "resources",
                           "constraint")),
        ),
    ),
    _Template(
        category="study",
        goal="Build your study plan",
        summary=(
            "Understand the learning goal, assess the current level, identify "
            "resources, create a study roadmap, define milestones, and schedule "
            "review sessions."
        ),
        steps=(
            ("Understand the learning goal",
             "Clarify what you want to learn and to what depth.", None),
            ("Assess the current level",
             "Establish the starting point so the plan is right-sized.", None),
            ("Identify resources",
             "Find the materials that best fit the goal and level.",
             "resource_finder"),
            ("Create a study roadmap",
             "Sequence topics into an ordered, time-aware plan.", None),
            ("Define milestones",
             "Set checkpoints to measure understanding along the way.", None),
            ("Schedule review sessions",
             "Plan spaced reviews to reinforce retention.", "calendar"),
        ),
        requires_user_confirmation=False,
        prerequisites=(
            _Prerequisite("the learning goal",
                          ("learn", "exam", "certification", "topic",
                           "subject", "goal")),
            _Prerequisite("your available time",
                          ("hours", "time", "deadline", "week", "schedule")),
        ),
    ),
    _Template(
        category="scheduling",
        goal="Organise your day",
        summary=(
            "Understand the day's priorities, review your calendar, resolve "
            "conflicts, allocate time blocks, and present a schedule for your "
            "confirmation."
        ),
        steps=(
            ("Understand the day's priorities",
             "Establish what must get done so time is spent on what matters.",
             None),
            ("Review your calendar",
             "Load existing commitments to plan around them.", "calendar"),
            ("Identify conflicts",
             "Spot overlaps or overloads before committing to a plan.", None),
            ("Allocate time blocks",
             "Assign focused blocks to each priority.", None),
            ("Build the schedule",
             "Assemble the blocks into an ordered daily schedule.", None),
            ("Present the schedule",
             "Show the proposed schedule for your review.", None),
            ("Await your confirmation",
             "Pause for your go-ahead before anything is committed.", None),
        ),
        requires_user_confirmation=True,
        prerequisites=(
            _Prerequisite("today's priorities",
                          ("priority", "priorities", "task", "tasks", "todo",
                           "to-do", "deadline")),
        ),
    ),
)

# Fallback used when no category keyword matches the request text.
_GENERIC_TEMPLATE = _Template(
    category="generic",
    goal="Address your request",
    summary=(
        "Break the request into clear, ordered steps and confirm the approach "
        "before doing anything."
    ),
    steps=(
        ("Understand the request",
         "Make sure the goal and constraints are clear before planning.", None),
        ("Gather relevant information",
         "Collect the context needed to plan a sound approach.", None),
        ("Identify the required steps",
         "Break the goal into an ordered sequence of actions.", None),
        ("Draft an approach",
         "Assemble the steps into a coherent plan.", None),
        ("Present the plan",
         "Summarise the proposed approach for your review.", None),
        ("Await your approval",
         "Pause for your decision before anything is acted on.", None),
    ),
    requires_user_confirmation=True,
)


class HeuristicPlanningProvider(PlanningProvider):
    """Deterministic, offline default planner (no AI/SDK/network).

    Detects the goal category from the request text and materialises a curated
    template into a validated-shape :class:`ExecutionPlan`. Stateless and
    side-effect free; it only reasons and never executes a step.
    """

    name = "heuristic"

    def create_plan(self, request: PlanningRequest) -> ExecutionPlan:
        """Return a deterministic :class:`ExecutionPlan` for ``request``.

        Selects a template by intent, builds a linear, dependency-correct step
        sequence (each step depends on the immediately preceding one), and lists
        any prerequisite the caller has not already supplied in
        ``missing_information``. Nothing is executed.
        """
        text = " ".join(
            (
                request.user_request,
                request.conversation_context,
                request.memory_summary,
            )
        ).lower()

        template = self._select_template(text)
        steps = self._build_steps(template.steps)
        missing = self._missing_information(template, text)

        return ExecutionPlan(
            goal=template.goal,
            summary=template.summary,
            steps=steps,
            missing_information=missing,
            requires_user_confirmation=template.requires_user_confirmation,
            metadata={"provider": self.name, "category": template.category},
        )

    @staticmethod
    def _select_template(text: str) -> _Template:
        """Return the first template whose category keyword appears in ``text``.

        Falls back to the generic template when nothing matches. ``_TEMPLATES``
        and ``_INTENT_KEYWORDS`` share an order, so detection precedence is
        explicit and deterministic.
        """
        by_category = {t.category: t for t in _TEMPLATES}
        for category, keywords in _INTENT_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                return by_category[category]
        return _GENERIC_TEMPLATE

    @staticmethod
    def _build_steps(specs: Tuple[_StepSpec, ...]) -> List[ExecutionStep]:
        """Materialise step specs into a linear, dependency-correct sequence.

        Step ``k`` (1-based) depends on step ``k - 1``; the first step has no
        dependencies. This mirrors the sequential example plans and always
        satisfies the :class:`PlanValidator` ordering/dependency rules.
        """
        steps: List[ExecutionStep] = []
        for index, (description, reason, expected_tool) in enumerate(specs):
            step_number = index + 1
            dependencies = [step_number - 1] if index > 0 else []
            steps.append(
                ExecutionStep(
                    step_number=step_number,
                    description=description,
                    reason=reason,
                    expected_tool=expected_tool,
                    dependencies=dependencies,
                )
            )
        return steps

    @staticmethod
    def _missing_information(template: _Template, text: str) -> List[str]:
        """List prerequisites not already evidenced in the request text.

        A prerequisite is considered supplied when any of its ``satisfied_by``
        keywords appears in ``text``; otherwise its label is reported so a caller
        knows what to ask the user before execution could begin.
        """
        return [
            prerequisite.label
            for prerequisite in template.prerequisites
            if not any(keyword in text for keyword in prerequisite.satisfied_by)
        ]
