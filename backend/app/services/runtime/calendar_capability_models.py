"""Calendar capability models (Sprint 15.13 — immutable calendar DTOs).

Provider-independent, immutable DTOs and enums for the Calendar execution
capability: events, attendees, organizers, reminders, metadata, availability, the
change artifact, and the operation request. A :class:`CalendarEvent` is a plain
snapshot of one event (never a Google/Outlook/CalDAV object or an internal storage
object); times are ISO-8601 strings plus a ``time_zone`` label, so no ``datetime``
or SDK object crosses the boundary.

Validation helpers live here because they produce/guard these DTOs:
:func:`validate_event_times` (start < end), :func:`validate_timezone`,
:func:`validate_recurrence`, :func:`validate_attendees`, and
:func:`deterministic_event_id` (stable, content-addressed ids). They raise
:class:`CalendarValidationError`, which the capability catches at its boundary.
Strictly additive to Sprints 15.1–15.12. The result DTOs live in
:mod:`app.services.runtime.calendar_results`.
"""

import hashlib
import re
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# A pragmatic address shape check for organizer/attendee emails.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Recurrence frequencies the deterministic default understands.
_ALLOWED_FREQ = frozenset({"DAILY", "WEEKLY", "MONTHLY", "YEARLY"})

# Curated set of always-valid IANA time zones (plus UTC/GMT). Any zone outside this
# set is accepted only if :mod:`zoneinfo` can load it, so validation stays
# deterministic on systems without the full tz database.
_KNOWN_TIMEZONES = frozenset(
    {
        "UTC", "GMT",
        "America/New_York", "America/Chicago", "America/Denver",
        "America/Los_Angeles", "America/Sao_Paulo",
        "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid",
        "Asia/Kolkata", "Asia/Dubai", "Asia/Tokyo", "Asia/Shanghai",
        "Australia/Sydney", "Pacific/Auckland",
    }
)


class CalendarValidationError(ValueError):
    """Raised when an event is semantically invalid (times, tz, recurrence, ...).

    The capability catches this at its boundary and reports a graceful ``FAILED``
    result; the exception object never crosses a capability boundary.
    """


class CalendarOperation(str, Enum):
    """The allowed, deterministic calendar operation labels."""

    CREATE = "CREATE"
    READ = "READ"
    LIST = "LIST"
    SEARCH = "SEARCH"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    METADATA = "METADATA"
    CHECK_AVAILABILITY = "CHECK_AVAILABILITY"
    IMPORT_ICS = "IMPORT_ICS"
    EXPORT_ICS = "EXPORT_ICS"


class CalendarOperationStatus(str, Enum):
    """The allowed, deterministic calendar operation outcomes.

    ``SUCCESS`` — completed. ``NOT_FOUND`` — a required event did not exist.
    ``FAILED`` — invalid times/tz/recurrence/attendees or a bad import/export. The
    bridge maps ``SUCCESS`` to ``COMPLETED`` and everything else to ``FAILED``.
    """

    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    FAILED = "FAILED"


class AttendeeResponseStatus(str, Enum):
    """An attendee's RSVP state."""

    NEEDS_ACTION = "NEEDS_ACTION"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    TENTATIVE = "TENTATIVE"


class ReminderMethod(str, Enum):
    """How a reminder is delivered."""

    POPUP = "POPUP"
    EMAIL = "EMAIL"


class AvailabilityStatus(str, Enum):
    """Whether a time range is ``BUSY`` or ``FREE``."""

    BUSY = "BUSY"
    FREE = "FREE"


class CalendarArtifactType(str, Enum):
    """The kind of change an artifact records."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    IMPORTED = "IMPORTED"
    EXPORTED = "EXPORTED"
    REPORT = "REPORT"


class CalendarOrganizer(BaseModel):
    """Immutable event organizer (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``email`` is the organizer address;
    ``display_name`` is the optional friendly name.
    """

    model_config = ConfigDict(frozen=True)

    email: str
    display_name: Optional[str] = None


class CalendarAttendee(BaseModel):
    """Immutable event attendee (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``email`` is the attendee address;
    ``display_name`` is optional; ``response_status`` is an
    :class:`AttendeeResponseStatus` label; ``optional`` marks a non-required
    attendee.
    """

    model_config = ConfigDict(frozen=True)

    email: str
    display_name: Optional[str] = None
    response_status: str = AttendeeResponseStatus.NEEDS_ACTION.value
    optional: bool = False


class CalendarReminder(BaseModel):
    """Immutable reminder configuration (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``minutes_before`` is how long before
    the event start it fires; ``method`` is a :class:`ReminderMethod` label.
    """

    model_config = ConfigDict(frozen=True)

    minutes_before: int
    method: str = ReminderMethod.POPUP.value


class CalendarEvent(BaseModel):
    """Immutable snapshot of one calendar event (no SDK/storage object exposed).

    ``frozen=True`` makes instances immutable — every mutation (update, expand)
    produces a *new* event. ``event_id`` is the deterministic id; ``uid`` is the ICS
    UID (``None`` if none); ``summary``/``description``/``location`` are the details;
    ``start_time``/``end_time`` are ISO-8601 strings; ``time_zone`` is the IANA zone;
    ``all_day`` marks an all-day event; ``busy`` marks it as busy (vs free);
    ``organizer``/``attendees``/``reminders`` are the people and alerts;
    ``recurrence`` is an RRULE string (``None`` if single); ``is_recurring_instance``
    and ``recurrence_id`` describe an expanded occurrence; and ``event_metadata``
    carries plain descriptors. Never a provider or storage object.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str
    uid: Optional[str] = None
    summary: str = ""
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    time_zone: str = "UTC"
    all_day: bool = False
    busy: bool = True
    organizer: Optional[CalendarOrganizer] = None
    attendees: List[CalendarAttendee] = Field(default_factory=list)
    reminders: List[CalendarReminder] = Field(default_factory=list)
    recurrence: Optional[str] = None
    is_recurring_instance: bool = False
    recurrence_id: Optional[str] = None
    event_metadata: Dict[str, Any] = Field(default_factory=dict)


class CalendarMetadata(BaseModel):
    """Immutable metadata summary for one event (no SDK object exposed).

    ``frozen=True`` makes instances immutable. Carries the event's identity and key
    facts — ``event_id``, ``summary``, ``start_time``/``end_time``, ``time_zone``,
    ``all_day``, ``busy``, ``organizer_email``, ``attendee_count``,
    ``reminder_count``, ``is_recurring`` — plus plain ``metadata``.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str
    summary: str = ""
    start_time: str = ""
    end_time: Optional[str] = None
    time_zone: str = "UTC"
    all_day: bool = False
    busy: bool = True
    organizer_email: Optional[str] = None
    attendee_count: int = 0
    reminder_count: int = 0
    is_recurring: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CalendarAvailability(BaseModel):
    """Immutable busy/free result for a time range (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``status`` is an
    :class:`AvailabilityStatus` label; ``range_start``/``range_end`` are the queried
    window; ``busy_event_ids`` are the overlapping busy events; and ``metadata``
    carries plain descriptors.
    """

    model_config = ConfigDict(frozen=True)

    status: str
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    busy_event_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CalendarArtifact(BaseModel):
    """Immutable description of one change an operation produced (no SDK object).

    ``frozen=True`` makes instances immutable. ``artifact_id`` is a deterministic
    identifier; ``artifact_type`` is a :class:`CalendarArtifactType` label;
    ``artifact_name`` is a human name; ``artifact_path`` is a workspace-relative path
    for ICS artifacts (``None`` otherwise); and ``artifact_metadata`` carries plain
    descriptors. Building it runs nothing and carries no credential.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    artifact_type: str
    artifact_name: str
    artifact_path: Optional[str] = None
    artifact_metadata: Dict[str, Any] = Field(default_factory=dict)


class CalendarOperationRequest(BaseModel):
    """Immutable request to perform one calendar operation (no execution).

    ``frozen=True`` makes instances immutable. ``operation`` is a
    :class:`CalendarOperation` label. The remaining fields are the union the
    operations need: event details (``summary``/``description``/``location``/
    ``start_time``/``end_time``/``time_zone``/``all_day``/``busy``/``organizer``/
    ``organizer_name``/``attendees``/``reminders``/``recurrence``/``uid``) for
    create; ``event_id`` for read/update/delete/metadata; ``update_fields`` for a
    targeted update; ``query``/``search_field`` for search; ``range_start``/
    ``range_end``/``expand_recurring`` for list and availability; ``ics_path`` for
    import/export; and ``request_metadata`` for plain descriptors. Building this DTO
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    event_id: Optional[str] = None
    uid: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    time_zone: str = "UTC"
    all_day: bool = False
    busy: bool = True
    organizer: Optional[str] = None
    organizer_name: Optional[str] = None
    attendees: List[str] = Field(default_factory=list)
    reminders: List[int] = Field(default_factory=list)
    recurrence: Optional[str] = None
    update_fields: Dict[str, Any] = Field(default_factory=dict)
    query: Optional[str] = None
    search_field: str = "any"
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    expand_recurring: bool = False
    ics_path: Optional[str] = None
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Validation helpers
# =====================================================================
def parse_calendar_datetime(value: str) -> datetime:
    """Parse an ISO-8601 date or datetime string into a naive :class:`datetime`.

    Accepts ``YYYY-MM-DD`` (all-day) and ``YYYY-MM-DDTHH:MM[:SS]`` forms, tolerating
    a trailing ``Z``. Any offset is dropped (comparisons are within one event's
    zone). Raises :class:`CalendarValidationError` on a malformed value.
    """
    if not isinstance(value, str) or not value.strip():
        raise CalendarValidationError("datetime must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        if "T" in text:
            parsed = datetime.fromisoformat(text)
        else:
            day = date.fromisoformat(text)
            parsed = datetime(day.year, day.month, day.day)
    except ValueError:
        raise CalendarValidationError(f"invalid datetime: {value!r}")
    return parsed.replace(tzinfo=None)


def validate_timezone(time_zone: str) -> str:
    """Return ``time_zone`` if it is a valid IANA zone, else raise.

    A zone in the curated set is always accepted; otherwise :mod:`zoneinfo` is asked
    to load it. Raises :class:`CalendarValidationError` if neither recognises it.
    """
    if not isinstance(time_zone, str) or not time_zone.strip():
        raise CalendarValidationError("time zone must be a non-empty string")
    if time_zone in _KNOWN_TIMEZONES:
        return time_zone
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(time_zone)
        return time_zone
    except Exception:  # noqa: BLE001 - any failure means "not a valid zone here"
        raise CalendarValidationError(f"invalid time zone: {time_zone!r}")


def validate_event_times(
    start_time: str, end_time: Optional[str], all_day: bool
) -> None:
    """Validate that ``start_time`` precedes ``end_time`` (start < end).

    For a timed event ``end_time`` is required and must be strictly after the start.
    For an all-day event ``end_time`` may be omitted (single day); if present it must
    not precede the start. Raises :class:`CalendarValidationError` otherwise.
    """
    start = parse_calendar_datetime(start_time)
    if end_time is None:
        if not all_day:
            raise CalendarValidationError("end_time is required for a timed event")
        return
    end = parse_calendar_datetime(end_time)
    if all_day:
        if end < start:
            raise CalendarValidationError("all-day end date precedes the start date")
        return
    if end <= start:
        raise CalendarValidationError("start_time must be before end_time")


def validate_recurrence(recurrence: Optional[str]) -> Optional[Dict[str, str]]:
    """Validate an RRULE string and return it parsed, or ``None`` when absent.

    Requires a valid ``FREQ`` (DAILY/WEEKLY/MONTHLY/YEARLY); ``INTERVAL`` and
    ``COUNT`` (when present) must be positive integers. Raises
    :class:`CalendarValidationError` on anything malformed.
    """
    if recurrence is None or not str(recurrence).strip():
        return None
    parts: Dict[str, str] = {}
    for token in str(recurrence).split(";"):
        if not token.strip():
            continue
        if "=" not in token:
            raise CalendarValidationError(f"invalid recurrence token: {token!r}")
        key, value = token.split("=", 1)
        parts[key.strip().upper()] = value.strip()
    freq = parts.get("FREQ", "").upper()
    if freq not in _ALLOWED_FREQ:
        raise CalendarValidationError(f"invalid recurrence FREQ: {freq!r}")
    for numeric in ("INTERVAL", "COUNT"):
        if numeric in parts:
            try:
                if int(parts[numeric]) <= 0:
                    raise ValueError
            except ValueError:
                raise CalendarValidationError(
                    f"recurrence {numeric} must be a positive integer"
                )
    parts["FREQ"] = freq
    return parts


def validate_attendees(emails: List[str]) -> List[str]:
    """Validate attendee emails: each well-formed, no duplicates (case-insensitive).

    Returns the normalised list. Raises :class:`CalendarValidationError` for a
    malformed address or a duplicate.
    """
    seen = set()
    normalised: List[str] = []
    for raw in emails:
        if not isinstance(raw, str) or not _EMAIL_RE.match(raw.strip()):
            raise CalendarValidationError(f"invalid attendee email: {raw!r}")
        lowered = raw.strip().lower()
        if lowered in seen:
            raise CalendarValidationError(f"duplicate attendee: {raw!r}")
        seen.add(lowered)
        normalised.append(raw.strip())
    return normalised


def validate_email(raw: str) -> str:
    """Return ``raw`` if it is a well-formed address, else raise."""
    if not isinstance(raw, str) or not _EMAIL_RE.match(raw.strip()):
        raise CalendarValidationError(f"invalid email address: {raw!r}")
    return raw.strip()


def deterministic_event_id(
    *,
    uid: Optional[str] = None,
    summary: str = "",
    start_time: str = "",
    end_time: str = "",
    organizer: str = "",
) -> str:
    """Return a deterministic, content-addressed event id.

    Uses the ICS ``uid`` when present (so re-importing the same calendar yields the
    same id); otherwise hashes the summary, start, end, and organizer. The result is
    ``evt-<12-hex>`` and is stable across processes and runs.
    """
    basis = uid if uid else f"{summary}|{start_time}|{end_time}|{organizer}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
    return f"evt-{digest}"


def add_recurrence_step(moment: datetime, freq: str, interval: int) -> datetime:
    """Return ``moment`` advanced by one recurrence step (deterministic, offline).

    Supports DAILY/WEEKLY (via ``timedelta``) and MONTHLY/YEARLY (via calendar
    arithmetic that clamps the day to the target month's length).
    """
    if freq == "DAILY":
        return moment + timedelta(days=interval)
    if freq == "WEEKLY":
        return moment + timedelta(weeks=interval)
    if freq == "MONTHLY":
        return _add_months(moment, interval)
    if freq == "YEARLY":
        return _add_months(moment, interval * 12)
    return moment + timedelta(days=interval)


def _add_months(moment: datetime, months: int) -> datetime:
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, _days_in_month(year, month))
    return moment.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - date(year, month, 1)).days
