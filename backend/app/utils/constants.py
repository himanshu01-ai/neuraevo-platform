"""Shared enumerations and constants."""

from enum import Enum


class MemoryType(str, Enum):
    """Categories of employee memory.

    - ``permanent``: long-lived facts that should always be retained.
    - ``working``: short-lived context for the current activity.
    - ``learned``: information inferred from interactions over time.
    """

    PERMANENT = "permanent"
    WORKING = "working"
    LEARNED = "learned"


class SessionStatus(str, Enum):
    """Lifecycle status of an interview session.

    - ``created``: session created but not yet started.
    - ``in_progress``: session underway.
    - ``completed``: session finished.
    """

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class SessionQuestionStatus(str, Enum):
    """Completion status of a question within an interview session.

    - ``pending``: the question has been added but not yet answered.
    - ``answered``: the question has been answered in this session.
    """

    PENDING = "pending"
    ANSWERED = "answered"


class ConversationStatus(str, Enum):
    """Lifecycle status of a conversation.

    - ``active``: the conversation is in use.
    - ``archived``: the conversation has been archived.
    """

    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(str, Enum):
    """Author role of a conversation message.

    - ``user``: a message from the human user.
    - ``assistant``: a message from the AI employee.
    - ``system``: a system/instruction message.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageChannel(str, Enum):
    """The channel a conversation message came in or went out on.

    Voice is a first-class conversation *channel*, not a separate domain: a
    spoken turn is transcribed to text and stored as an ordinary message, tagged
    with the channel it happened on. Text and voice therefore produce the same
    internal message model — the only difference is this tag.

    The persisted subset of the multimodal
    :class:`app.services.interaction.models.InteractionType`
    (``text``/``voice``/``image``/``document``); only the two channels the
    platform speaks today are stored, and new ones slot in here without a
    schema redesign. Stored lowercase like every other status column, and
    defaulting to ``text`` so every pre-existing message reads as typed.
    """

    TEXT = "text"
    VOICE = "voice"


# --- Employee domain (Sprint 18.2A) --------------------------------------
#
# These replace the free-form strings the employee domain used previously.
# Values are lower-case so they read the same on the wire as every other
# enumeration above; the frontend maps them to its own display vocabulary.


class EmployeeStatus(str, Enum):
    """Lifecycle status of an AI employee.

    - ``draft``: being described; not ready to be used. The historical default,
      so every pre-Sprint-18.2A employee is a draft.
    - ``ready``: fully described and available to be activated.
    - ``active``: in service.
    - ``paused``: temporarily taken out of service by its owner.
    - ``archived``: retired but retained, and restorable.
    - ``error``: the platform reported a problem with this employee.
    """

    DRAFT = "draft"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    ERROR = "error"


class EmployeeCapability(str, Enum):
    """A subsystem an employee may be granted.

    The first six are executable capabilities; the last three are platform
    grants (memory, approval, notification) that gate a subsystem rather than
    an action. Granting one records intent — nothing here executes anything.
    """

    BROWSER = "browser"
    PYTHON = "python"
    FILES = "files"
    EMAIL = "email"
    CALENDAR = "calendar"
    GITHUB = "github"
    MEMORY = "memory"
    APPROVAL = "approval"
    NOTIFICATION = "notification"


class EmployeePermission(str, Enum):
    """A specific action a capability opens up."""

    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    BROWSE_WEB = "browse_web"
    RUN_CODE = "run_code"
    MODIFY_FILES = "modify_files"
    SEND_EMAIL = "send_email"
    SCHEDULE_EVENTS = "schedule_events"
    REQUEST_APPROVAL = "request_approval"


class PermissionLevel(str, Enum):
    """How freely a permission may be exercised."""

    ALLOWED = "allowed"
    ASK_FIRST = "ask_first"
    BLOCKED = "blocked"


class AutonomyLevel(str, Enum):
    """How much an employee decides on its own."""

    ASK = "ask"
    BALANCED = "balanced"
    AUTONOMOUS = "autonomous"


class EmployeeTone(str, Enum):
    """How an employee communicates."""

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CONCISE = "concise"


class EmployeePriority(str, Enum):
    """How an employee's work ranks against other employees'."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ExecutionMode(str, Enum):
    """Default ordering the platform would use for this employee's work."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


class EmployeeAccent(str, Enum):
    """Avatar accent. Presentation only — names a tone the theme already ships."""

    VIOLET = "violet"
    BLUE = "blue"
    EMERALD = "emerald"
    AMBER = "amber"
    ROSE = "rose"
    SLATE = "slate"


class EmployeeGlyph(str, Enum):
    """Avatar glyph. Presentation only."""

    INITIALS = "initials"
    BOT = "bot"
    BRAIN = "brain"
    CODE = "code"
    CHART = "chart"
    PEN = "pen"
    HEADSET = "headset"
    BRIEFCASE = "briefcase"
    SPARKLES = "sparkles"


class EmployeeActivityKind(str, Enum):
    """A recorded change in an employee's history.

    Written by the service when the change actually happens, so the history is
    a record of events rather than a reconstruction.
    """

    CREATED = "created"
    UPDATED = "updated"
    CONFIGURATION_CHANGED = "configuration_changed"
    STATUS_CHANGED = "status_changed"
    ARCHIVED = "archived"
    RESTORED = "restored"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"


class EmployeeHealth(str, Enum):
    """Whether an employee is in a usable state.

    Derived from stored facts only (see ``app.services.employee_health``);
    nothing here is sampled, measured, or estimated.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class WorkflowStatus(str, Enum):
    """Lifecycle status of an *authored* workflow definition.

    Distinct from ``app.services.planning.execution_workflow_models``'s
    ``WorkflowStatus`` (``PLANNED``/``READY``/``WAITING``/``BLOCKED``), which
    describes how ready a *run* is to proceed. This one describes how far along
    its author is, and is the value persisted on ``workflows.status``.

    - ``draft``: being authored; not released for use.
    - ``published``: released and available to be used.
    - ``archived``: retired but retained, and restorable.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    """Where a task stands (Sprint 19 Task Engine).

    The persisted vocabulary behind the frontend's ``TASK_STATES`` — the same
    ten states, stored lowercase like every other status column. Seven mirror
    the platform's ``LifecycleStatus``; ``planning``, ``waiting_approval`` and
    ``blocked`` are the task-specific additions the UI already names.

    Ordered as a task moves, not alphabetically.
    """

    PENDING = "pending"
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class TaskExecutionMode(str, Enum):
    """What starts a task (Sprint 19 Task Engine).

    Deliberately *not* :class:`ExecutionMode` — that orders an employee's
    steps (sequential/parallel/hybrid), which is a different question from what
    triggers a task. The frontend keeps the same two vocabularies apart for the
    same reason.
    """

    AUTOMATIC = "automatic"
    MANUAL = "manual"
    APPROVAL_REQUIRED = "approval_required"
    SCHEDULED = "scheduled"


class CollaborationResourceType(str, Enum):
    """A platform resource that can be collaborated on (Sprint 20 Collaboration).

    Polymorphic on purpose: collaboration attaches to any of these by
    ``(resource_type, resource_id)`` rather than a per-domain foreign key, so
    one participant, permission and activity model serves every domain and a
    future domain plugs in by adding a member here. Ownership of each is *not*
    re-implemented — it is read back through the resource's existing chain
    (``Task``/``Workflow`` own a ``user_id``; ``Conversation``/``Memory`` reach
    a user through their employee).
    """

    CONVERSATION = "conversation"
    TASK = "task"
    WORKFLOW = "workflow"
    MEMORY = "memory"


class ParticipantType(str, Enum):
    """What kind of collaborator a participant is (Sprint 20 Collaboration).

    A participant is never assumed to be a human: an AI employee joins a
    resource on the same footing as a user, so collaboration is not user-only.
    """

    USER = "user"
    EMPLOYEE = "employee"


class CollaborationRole(str, Enum):
    """What a participant may do on a shared resource (Sprint 20 Collaboration).

    Ordered by authority. ``OWNER`` is never stored as a participant row — it is
    derived from the resource's existing ownership chain — but is named here so
    effective-role resolution has one vocabulary. ``EDITOR`` may change the
    resource; ``VIEWER`` is read-only.
    """

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ActivityActorType(str, Enum):
    """Who caused an activity event (Sprint 20C).

    An actor is a user, an AI employee, or the platform itself — the same
    open set of collaborators the participant model recognises, plus ``system``
    for events no one person triggered.
    """

    USER = "user"
    EMPLOYEE = "employee"
    SYSTEM = "system"


class ActivityKind(str, Enum):
    """What happened, in the platform's own verbs (Sprint 20C).

    The first nine mirror the frontend's activity vocabulary (a generic
    lifecycle any domain can record); the rest are the collaboration-specific
    events this platform emits itself — a participant joining, a role changing,
    a link being shared or withdrawn.
    """

    CREATED = "created"
    UPDATED = "updated"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    COMMENTED = "commented"
    MENTIONED = "mentioned"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    # Collaboration-specific
    PARTICIPANT_ADDED = "participant_added"
    PARTICIPANT_REMOVED = "participant_removed"
    ROLE_CHANGED = "role_changed"
    SHARED = "shared"
    SHARE_REVOKED = "share_revoked"
    JOINED = "joined"


class NotificationType(str, Enum):
    """What a notification is about — which subsystem raised it (Sprint 20D).

    Mirrors the frontend's notification vocabulary so the inbox reads in one set
    of categories. The first four are the collaborated resource types; the rest
    cover approvals, employee events, and platform-level notices.
    """

    TASK = "task"
    WORKFLOW = "workflow"
    MEMORY = "memory"
    CONVERSATION = "conversation"
    APPROVAL = "approval"
    EMPLOYEE = "employee"
    SYSTEM = "system"
