"""Calendar execution layer (Sprint 15.13 — the replaceable provider seam).

Defines the :class:`CalendarExecutor` seam that performs the actual calendar
operations and its default :class:`LocalCalendarExecutor` — a deterministic, offline
in-memory calendar (the analog of the Email layer's ``LocalEmailExecutor``). The
capability coordinates, validates, and builds DTOs; this layer performs the store,
query, recurrence expansion, and availability check. A single ``perform`` method
keeps the seam tiny so a future provider (Google Calendar, Microsoft Graph, Outlook,
Exchange, Apple Calendar, CalDAV) can implement it without any change to the Runtime
or the capability.

The default executor keeps a ``dict`` of immutable :class:`CalendarEvent` DTOs keyed
by their deterministic id; a "mutation" (update) replaces the stored DTO, so the
store only ever holds immutable data. It builds no provider/API/storage object into a
result and holds no credential. Instance state only (each capability gets its own
calendar); no static/singleton state, no network, thread, or subprocess. Strictly
additive to Sprints 15.1–15.12.
"""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Dict, List, NamedTuple, Optional, Union

from app.services.runtime.calendar_capability_models import (
    AvailabilityStatus,
    CalendarAvailability,
    CalendarEvent,
    CalendarMetadata,
    CalendarOperation,
    CalendarOperationRequest,
    CalendarOperationStatus,
    add_recurrence_step,
    parse_calendar_datetime,
    validate_recurrence,
)
from app.services.runtime.calendar_results import (
    CreateEventResult,
    ListEventsResult,
    OperationResult,
    ReadEventResult,
    SearchEventsResult,
)

_SUCCESS = CalendarOperationStatus.SUCCESS.value
_FAILED = CalendarOperationStatus.FAILED.value
_NOT_FOUND = CalendarOperationStatus.NOT_FOUND.value

# Hard cap on expanded occurrences so an unbounded recurrence never runs away.
_MAX_OCCURRENCES = 500

CalendarOperationOutcome = Union[
    CreateEventResult,
    ReadEventResult,
    ListEventsResult,
    SearchEventsResult,
    OperationResult,
]


class CalendarExecutionContext(NamedTuple):
    """Plain, validated inputs the capability hands to the executor.

    ``events`` are the already-validated :class:`CalendarEvent` DTOs to store (one
    for create/update, many for import; empty for read-only operations). Carries only
    plain DTOs — never a provider object or credential.
    """

    events: List[CalendarEvent]


class CalendarExecutor(ABC):
    """Replaceable seam that performs one calendar operation and reports a DTO.

    Concrete executors own all calendar/provider mechanics behind this single
    interface so the capability stays testable and provider-independent. An executor
    must never let a provider/API/storage object or a credential escape — it returns
    only a plain result DTO.
    """

    @abstractmethod
    def perform(
        self,
        request: CalendarOperationRequest,
        context: CalendarExecutionContext,
    ) -> CalendarOperationOutcome:
        """Perform ``request`` with the validated ``context`` and return its result."""


class LocalCalendarExecutor(CalendarExecutor):
    """Default executor: a deterministic, offline in-memory calendar.

    Dispatches on the request's operation to a focused handler over a ``dict`` of
    immutable :class:`CalendarEvent` DTOs keyed by id. Create/update/import store the
    validated events from the context; read/list/search/metadata/availability query;
    delete removes. A missing event becomes ``NOT_FOUND`` — never a raised provider
    object. Holds per-instance calendar state only (no static/singleton state) and
    contacts no network.
    """

    def __init__(self, seed_events: Optional[List[CalendarEvent]] = None) -> None:
        self._events: Dict[str, CalendarEvent] = {}
        for event in seed_events or []:
            self._events[event.event_id] = event

    # --- dispatch -------------------------------------------------------
    def perform(self, request, context) -> CalendarOperationOutcome:
        operation = request.operation
        if operation == CalendarOperation.CREATE.value:
            return self._create(context)
        if operation == CalendarOperation.READ.value:
            return self._read(request)
        if operation == CalendarOperation.LIST.value:
            return self._list(request)
        if operation == CalendarOperation.SEARCH.value:
            return self._search(request)
        if operation == CalendarOperation.UPDATE.value:
            return self._update(request, context)
        if operation == CalendarOperation.DELETE.value:
            return self._delete(request)
        if operation == CalendarOperation.METADATA.value:
            return self._metadata(request)
        if operation == CalendarOperation.CHECK_AVAILABILITY.value:
            return self._availability(request)
        if operation == CalendarOperation.IMPORT_ICS.value:
            return self._import(context)
        return OperationResult(
            operation=operation or "UNKNOWN",
            operation_status=_FAILED,
            operation_metadata={"error": f"unsupported operation: {operation}"},
        )

    # --- create / update / import ---------------------------------------
    def _create(self, context) -> CreateEventResult:
        event = context.events[0]
        self._events[event.event_id] = event
        return CreateEventResult(
            event_id=event.event_id,
            event=event,
            operation_status=_SUCCESS,
        )

    def _update(self, request, context) -> OperationResult:
        event = context.events[0]
        self._events[event.event_id] = event
        return OperationResult(
            operation=CalendarOperation.UPDATE.value,
            event_id=event.event_id,
            success=True,
            event=event,
            operation_status=_SUCCESS,
        )

    def _import(self, context) -> OperationResult:
        stored_ids = []
        for event in context.events:
            self._events[event.event_id] = event
            stored_ids.append(event.event_id)
        return OperationResult(
            operation=CalendarOperation.IMPORT_ICS.value,
            success=True,
            event_ids=stored_ids,
            imported_count=len(stored_ids),
            operation_status=_SUCCESS,
        )

    # --- read / list / search -------------------------------------------
    def _read(self, request) -> ReadEventResult:
        event = self._events.get(request.event_id)
        if event is None:
            return ReadEventResult(
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "event not found"},
            )
        return ReadEventResult(event=event, operation_status=_SUCCESS)

    def _list(self, request) -> ListEventsResult:
        window = self._window(request.range_start, request.range_end)
        events = self._effective_events(window, request.expand_recurring)
        events.sort(key=lambda e: e.start_time)
        return ListEventsResult(
            events=events,
            event_count=len(events),
            expanded=bool(request.expand_recurring and window is not None),
            range_start=request.range_start,
            range_end=request.range_end,
            operation_status=_SUCCESS,
        )

    def _search(self, request) -> SearchEventsResult:
        query = (request.query or "").strip().lower()
        field = request.search_field or "any"
        matches = [
            event
            for event in self._events.values()
            if not query or self._matches(event, query, field)
        ]
        matches.sort(key=lambda e: e.start_time)
        return SearchEventsResult(
            query=request.query or "",
            search_field=field,
            matches=matches,
            match_count=len(matches),
            operation_status=_SUCCESS,
        )

    # --- delete / metadata / availability -------------------------------
    def _delete(self, request) -> OperationResult:
        event = self._events.pop(request.event_id, None)
        if event is None:
            return OperationResult(
                operation=CalendarOperation.DELETE.value,
                event_id=request.event_id,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "event not found"},
            )
        return OperationResult(
            operation=CalendarOperation.DELETE.value,
            event_id=event.event_id,
            success=True,
            operation_status=_SUCCESS,
        )

    def _metadata(self, request) -> OperationResult:
        event = self._events.get(request.event_id)
        if event is None:
            return OperationResult(
                operation=CalendarOperation.METADATA.value,
                event_id=request.event_id,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "event not found"},
            )
        return OperationResult(
            operation=CalendarOperation.METADATA.value,
            event_id=event.event_id,
            success=True,
            calendar_metadata=self._build_metadata(event),
            operation_status=_SUCCESS,
        )

    def _availability(self, request) -> OperationResult:
        window = self._window(request.range_start, request.range_end)
        events = self._effective_events(window, expand=True)
        start_dt, end_dt = window if window else (None, None)
        busy_ids = []
        for event in events:
            if not event.busy:
                continue
            if window is None or self._overlaps(event, start_dt, end_dt):
                busy_ids.append(event.event_id)
        status = (
            AvailabilityStatus.BUSY.value
            if busy_ids
            else AvailabilityStatus.FREE.value
        )
        return OperationResult(
            operation=CalendarOperation.CHECK_AVAILABILITY.value,
            success=True,
            availability=CalendarAvailability(
                status=status,
                range_start=request.range_start,
                range_end=request.range_end,
                busy_event_ids=busy_ids,
            ),
            operation_status=_SUCCESS,
        )

    # --- deterministic helpers ------------------------------------------
    def _effective_events(self, window, expand) -> List[CalendarEvent]:
        """Return events (optionally expanding recurrences) within ``window``."""
        result: List[CalendarEvent] = []
        start_dt, end_dt = window if window else (None, None)
        for event in self._events.values():
            if expand and event.recurrence and window is not None:
                result.extend(self._expand(event, start_dt, end_dt))
            elif window is None or self._overlaps(event, start_dt, end_dt):
                result.append(event)
        return result

    def _expand(self, event, start_dt, end_dt) -> List[CalendarEvent]:
        rule = validate_recurrence(event.recurrence)
        if rule is None:
            return [event] if self._overlaps(event, start_dt, end_dt) else []
        freq = rule["FREQ"]
        interval = int(rule.get("INTERVAL", "1"))
        count = int(rule["COUNT"]) if "COUNT" in rule else None
        until = (
            parse_calendar_datetime(rule["UNTIL"]) if "UNTIL" in rule else None
        )
        base_start = parse_calendar_datetime(event.start_time)
        duration = self._duration(event)
        occurrences: List[CalendarEvent] = []
        moment = base_start
        emitted = 0
        for _ in range(_MAX_OCCURRENCES):
            if count is not None and emitted >= count:
                break
            if until is not None and moment > until:
                break
            if moment > end_dt:
                break
            occ_end = moment + duration
            if occ_end > start_dt:  # occurrence overlaps the window
                occurrences.append(
                    event.model_copy(
                        update={
                            "start_time": moment.isoformat(),
                            "end_time": (
                                occ_end.isoformat() if event.end_time else None
                            ),
                            "is_recurring_instance": True,
                            "recurrence_id": moment.isoformat(),
                        }
                    )
                )
            moment = add_recurrence_step(moment, freq, interval)
            emitted += 1
        return occurrences

    @staticmethod
    def _duration(event) -> timedelta:
        if not event.end_time:
            return timedelta(0)
        try:
            start = parse_calendar_datetime(event.start_time)
            end = parse_calendar_datetime(event.end_time)
        except Exception:  # noqa: BLE001 - defensive; validated on the way in
            return timedelta(0)
        return end - start

    @staticmethod
    def _overlaps(event, start_dt, end_dt) -> bool:
        try:
            event_start = parse_calendar_datetime(event.start_time)
            event_end = (
                parse_calendar_datetime(event.end_time)
                if event.end_time
                else event_start
            )
        except Exception:  # noqa: BLE001 - defensive
            return False
        return event_start < end_dt and event_end >= start_dt

    @staticmethod
    def _window(range_start, range_end):
        if not range_start or not range_end:
            return None
        return (
            parse_calendar_datetime(range_start),
            parse_calendar_datetime(range_end),
        )

    @staticmethod
    def _matches(event, query, field) -> bool:
        if field == "summary":
            haystacks = [event.summary]
        elif field == "description":
            haystacks = [event.description or ""]
        elif field == "location":
            haystacks = [event.location or ""]
        elif field == "attendee":
            haystacks = [a.email for a in event.attendees]
        else:  # any
            haystacks = [
                event.summary,
                event.description or "",
                event.location or "",
                *[a.email for a in event.attendees],
            ]
        return any(query in text.lower() for text in haystacks)

    @staticmethod
    def _build_metadata(event) -> CalendarMetadata:
        return CalendarMetadata(
            event_id=event.event_id,
            summary=event.summary,
            start_time=event.start_time,
            end_time=event.end_time,
            time_zone=event.time_zone,
            all_day=event.all_day,
            busy=event.busy,
            organizer_email=event.organizer.email if event.organizer else None,
            attendee_count=len(event.attendees),
            reminder_count=len(event.reminders),
            is_recurring=bool(event.recurrence),
        )
