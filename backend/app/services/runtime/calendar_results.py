"""Calendar result models (Sprint 15.13 — immutable result DTOs).

The immutable, provider-independent results of the Calendar capability's operations:
a create, a single read, a list, a search, and the generic single-event operation
(update/delete/metadata/availability/import/export). Kept in their own module
(mirroring the browser/python/filesystem/email split); each carries only plain data
— no provider SDK object, no calendar API model, and no internal storage object
crosses this boundary. Strictly additive to Sprints 15.1–15.12.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.calendar_capability_models import (
    CalendarArtifact,
    CalendarAvailability,
    CalendarEvent,
    CalendarMetadata,
)


class CreateEventResult(BaseModel):
    """Immutable result of creating an event (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``event_id`` is the created event's
    deterministic id (``None`` on failure); ``event`` is the stored
    :class:`CalendarEvent`; ``artifact`` is the ``CREATED`` :class:`CalendarArtifact`;
    ``operation_status`` is a :class:`CalendarOperationStatus` label; and
    ``operation_metadata`` carries plain descriptors.
    """

    model_config = ConfigDict(frozen=True)

    event_id: Optional[str] = None
    event: Optional[CalendarEvent] = None
    artifact: Optional[CalendarArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class ReadEventResult(BaseModel):
    """Immutable result of reading a single event (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``event`` is the found
    :class:`CalendarEvent` (``None`` when not found); ``operation_status`` is a
    :class:`CalendarOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    event: Optional[CalendarEvent] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class ListEventsResult(BaseModel):
    """Immutable result of listing events (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``events`` are the ordered
    :class:`CalendarEvent` records; ``event_count`` is the tally; ``expanded`` marks
    whether recurring events were expanded into occurrences; ``range_start``/
    ``range_end`` echo any window; ``operation_status`` is a
    :class:`CalendarOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    events: List[CalendarEvent] = Field(default_factory=list)
    event_count: int = 0
    expanded: bool = False
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchEventsResult(BaseModel):
    """Immutable result of searching events (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``query`` is the search text;
    ``search_field`` is the field searched; ``matches`` are the ordered
    :class:`CalendarEvent` records; ``match_count`` is the tally; ``artifact`` is an
    optional ``REPORT`` :class:`CalendarArtifact`; ``operation_status`` is a
    :class:`CalendarOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    query: str = ""
    search_field: str = "any"
    matches: List[CalendarEvent] = Field(default_factory=list)
    match_count: int = 0
    artifact: Optional[CalendarArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class OperationResult(BaseModel):
    """Immutable result of a single-event or ICS operation (no SDK object exposed).

    Covers update, delete, metadata, availability, import, and export.
    ``frozen=True`` makes instances immutable. ``operation`` is a
    :class:`CalendarOperation` label; ``event_id`` names the affected event;
    ``success`` marks a completed operation; ``event`` carries the updated event for
    an update; ``calendar_metadata`` carries the descriptor for a ``METADATA``
    request; ``availability`` carries the busy/free result for a
    ``CHECK_AVAILABILITY`` request; ``event_ids`` are the events created by an import;
    ``imported_count``/``exported_count`` are the ICS tallies; ``ics_content`` is the
    generated ICS text for an export (``None`` otherwise); ``artifact`` is the
    :class:`CalendarArtifact` recorded for a change; ``operation_status`` is a
    :class:`CalendarOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    event_id: Optional[str] = None
    success: bool = False
    event: Optional[CalendarEvent] = None
    calendar_metadata: Optional[CalendarMetadata] = None
    availability: Optional[CalendarAvailability] = None
    event_ids: List[str] = Field(default_factory=list)
    imported_count: int = 0
    exported_count: int = 0
    ics_content: Optional[str] = None
    artifact: Optional[CalendarArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)
