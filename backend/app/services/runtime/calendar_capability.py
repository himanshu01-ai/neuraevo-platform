"""Calendar capability (Sprint 15.13 — first-class calendar ExecutionCapability).

Implements the Sprint 14.3 :class:`ExecutionCapability` contract by coordinating an
ICS workspace, a calendar execution seam, and an artifact manager into one calendar
operation: validate (times, time zone, recurrence, attendees) → build immutable
event DTOs → delegate the operation to the execution layer → record artifacts →
return an immutable result DTO. Import/export additionally route through the
workspace for ICS (de)serialisation.

The actual calendar logic runs behind the injectable :class:`CalendarExecutor` seam
— the analog of the Email layer's ``EmailExecutor`` — so a future provider (Google
Calendar, Microsoft Graph, Outlook, Exchange, Apple Calendar, CalDAV) drops in
without touching the Runtime or this capability. The default
:class:`LocalCalendarExecutor` is a deterministic in-memory calendar and never lets a
provider/API/storage object or a credential escape into a DTO. The capability itself
coordinates only: it owns no provider logic and no planning. Stateless beyond its
injected collaborators and config. Strictly additive to Sprints 15.1–15.12 — it moves
no Runtime, Planning, Browser, Python, File System, or Email code.
"""

import base64
from typing import List, Optional, Union

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.calendar_artifact_manager import CalendarArtifactManager
from app.services.runtime.calendar_capability_models import (
    CalendarAttendee,
    CalendarEvent,
    CalendarOperation,
    CalendarOperationRequest,
    CalendarOperationStatus,
    CalendarOrganizer,
    CalendarReminder,
    CalendarValidationError,
    deterministic_event_id,
    parse_calendar_datetime,
    validate_attendees,
    validate_email,
    validate_event_times,
    validate_recurrence,
    validate_timezone,
)
from app.services.runtime.calendar_execution import (
    CalendarExecutionContext,
    CalendarExecutor,
    LocalCalendarExecutor,
)
from app.services.runtime.calendar_results import (
    CreateEventResult,
    ListEventsResult,
    OperationResult,
    ReadEventResult,
    SearchEventsResult,
)
from app.services.runtime.calendar_workspace import (
    CalendarImportError,
    CalendarWorkspace,
    CalendarWorkspaceManager,
)

# Everything ``run`` may return; the runtime bridge serialises whichever it gets.
CalendarRunResult = Union[
    CreateEventResult,
    ReadEventResult,
    ListEventsResult,
    SearchEventsResult,
    OperationResult,
]

_SUCCESS = CalendarOperationStatus.SUCCESS.value
_FAILED = CalendarOperationStatus.FAILED.value

# Which update_fields keys the capability applies (scalar event fields).
_SCALAR_UPDATE_KEYS = frozenset(
    {
        "summary", "description", "location", "start_time", "end_time",
        "time_zone", "all_day", "busy",
    }
)


class CalendarCapability(ExecutionCapability):
    """Calendar execution capability implementing the Sprint 14.3 contract.

    Coordinates the validate → build → execute → artifact pipeline. ``run`` validates
    and builds immutable event DTOs, delegates to the injected
    :class:`CalendarExecutor`, routes ICS import/export through the workspace, and
    records artifacts; ``current_workspace``/``create_temporary_workspace``/
    ``cleanup_workspace`` expose ICS-workspace lifecycle; ``execute`` bridges the
    runtime :class:`CapabilityExecutionRequest`/``Result``. Stateless beyond its
    injected collaborators and config — it owns no provider logic and never lets a
    provider/API/storage object or a credential escape.
    """

    def __init__(
        self,
        executor: Optional[CalendarExecutor] = None,
        artifact_manager: Optional[CalendarArtifactManager] = None,
        workspace_manager: Optional[CalendarWorkspaceManager] = None,
        staging_root: Optional[str] = None,
        ics_root: Optional[str] = None,
    ) -> None:
        self.executor = executor or LocalCalendarExecutor()
        self.artifact_manager = artifact_manager or CalendarArtifactManager()
        self.workspace_manager = workspace_manager or CalendarWorkspaceManager()
        self.staging_root = staging_root
        self.ics_root = ics_root

    # --- workspace lifecycle --------------------------------------------
    def current_workspace(self) -> CalendarWorkspace:
        """Return the persistent ICS-staging workspace."""
        return self.workspace_manager.current_workspace(
            self.staging_root, self.ics_root
        )

    def create_temporary_workspace(self, prefix: str = "calendar") -> CalendarWorkspace:
        """Return a fresh, isolated temporary ICS-staging workspace."""
        return self.workspace_manager.create_temporary_workspace(
            prefix, self.ics_root
        )

    def cleanup_workspace(self, workspace: CalendarWorkspace) -> OperationResult:
        """Clean up ``workspace`` and report the outcome as an immutable result."""
        try:
            self.workspace_manager.cleanup(workspace)
        except OSError as exc:  # graceful — never leak the OS object
            return OperationResult(
                operation="CLEANUP",
                operation_status=_FAILED,
                operation_metadata={"error": type(exc).__name__},
            )
        return OperationResult(
            operation="CLEANUP",
            success=True,
            operation_status=_SUCCESS,
            operation_metadata={"workspace_id": workspace.workspace_id},
        )

    # --- native API ------------------------------------------------------
    def run(
        self,
        request: CalendarOperationRequest,
        workspace: Optional[CalendarWorkspace] = None,
    ) -> CalendarRunResult:
        """Run one operation, routing ICS import/export through ``workspace``.

        Create/update validate the event first (a bad time/tz/recurrence/attendee
        becomes a graceful ``FAILED``). Import parses/validates through the workspace;
        export generates ICS through the workspace. All other operations delegate to
        the executor. Never raises for user errors.
        """
        operation = request.operation
        if operation == CalendarOperation.CREATE.value:
            return self._run_create(request)
        if operation == CalendarOperation.UPDATE.value:
            return self._run_update(request)
        if operation == CalendarOperation.DELETE.value:
            return self._run_delete(request)
        if operation == CalendarOperation.SEARCH.value:
            return self._with_search_artifact(
                self.executor.perform(request, self._empty_context())
            )
        if operation in (
            CalendarOperation.LIST.value,
            CalendarOperation.CHECK_AVAILABILITY.value,
        ):
            return self._run_ranged(request)
        if operation == CalendarOperation.IMPORT_ICS.value:
            return self._run_import(request, workspace)
        if operation == CalendarOperation.EXPORT_ICS.value:
            return self._run_export(request, workspace)
        # READ, METADATA, and any unsupported operation
        return self.executor.perform(request, self._empty_context())

    # --- ExecutionCapability contract (Sprint 14.3) ---------------------
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Bridge the runtime contract to one calendar operation.

        Reads the operation and its operands from ``capability_inputs``, runs it, and
        maps the result to a :class:`CapabilityExecutionResult` with plain,
        JSON-serialisable outputs — never a provider/API/storage object or a
        credential.
        """
        inputs = request.capability_inputs
        calendar_request = CalendarOperationRequest(
            operation=inputs.get("operation", ""),
            event_id=inputs.get("event_id"),
            uid=inputs.get("uid"),
            summary=inputs.get("summary"),
            description=inputs.get("description"),
            location=inputs.get("location"),
            start_time=inputs.get("start_time"),
            end_time=inputs.get("end_time"),
            time_zone=inputs.get("time_zone", "UTC"),
            all_day=bool(inputs.get("all_day", False)),
            busy=bool(inputs.get("busy", True)),
            organizer=inputs.get("organizer"),
            organizer_name=inputs.get("organizer_name"),
            attendees=list(inputs.get("attendees", []) or []),
            reminders=list(inputs.get("reminders", []) or []),
            recurrence=inputs.get("recurrence"),
            update_fields=dict(inputs.get("update_fields", {}) or {}),
            query=inputs.get("query"),
            search_field=inputs.get("search_field", "any"),
            range_start=inputs.get("range_start"),
            range_end=inputs.get("range_end"),
            expand_recurring=bool(inputs.get("expand_recurring", False)),
            ics_path=inputs.get("ics_path"),
        )
        result = self.run(calendar_request)
        status = (
            CapabilityExecutionStatus.COMPLETED.value
            if result.operation_status == _SUCCESS
            else CapabilityExecutionStatus.FAILED.value
        )
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=status,
            capability_outputs=self._serialize(result),
            execution_metadata={
                "operation": calendar_request.operation,
                "operation_status": result.operation_status,
            },
        )

    # --- create / update / delete ---------------------------------------
    def _run_create(self, request) -> CreateEventResult:
        try:
            event = self._build_event(request)
        except CalendarValidationError as exc:
            return CreateEventResult(
                operation_status=_FAILED, operation_metadata={"error": str(exc)}
            )
        result = self.executor.perform(request, CalendarExecutionContext([event]))
        artifact = self.artifact_manager.created(
            event.summary or event.event_id, {"event_id": event.event_id}
        )
        return result.model_copy(update={"artifact": artifact})

    def _run_update(self, request) -> OperationResult:
        current = self.executor.perform(
            CalendarOperationRequest(
                operation=CalendarOperation.READ.value, event_id=request.event_id
            ),
            self._empty_context(),
        )
        if current.operation_status != _SUCCESS or current.event is None:
            return OperationResult(
                operation=CalendarOperation.UPDATE.value,
                event_id=request.event_id,
                operation_status=current.operation_status,
                operation_metadata={"error": "event not found"},
            )
        try:
            merged = self._apply_updates(current.event, request.update_fields)
        except CalendarValidationError as exc:
            return OperationResult(
                operation=CalendarOperation.UPDATE.value,
                event_id=request.event_id,
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        result = self.executor.perform(request, CalendarExecutionContext([merged]))
        artifact = self.artifact_manager.updated(
            merged.summary or merged.event_id, {"event_id": merged.event_id}
        )
        return result.model_copy(update={"artifact": artifact})

    def _run_delete(self, request) -> OperationResult:
        result = self.executor.perform(request, self._empty_context())
        if result.operation_status != _SUCCESS:
            return result
        artifact = self.artifact_manager.deleted(
            result.event_id or "event", {"event_id": result.event_id}
        )
        return result.model_copy(update={"artifact": artifact})

    # --- ranged (list / availability) -----------------------------------
    def _run_ranged(self, request) -> CalendarRunResult:
        error = self._validate_range(
            request.range_start,
            request.range_end,
            required=request.operation == CalendarOperation.CHECK_AVAILABILITY.value,
        )
        if error is not None:
            if request.operation == CalendarOperation.LIST.value:
                return ListEventsResult(
                    operation_status=_FAILED, operation_metadata={"error": error}
                )
            return OperationResult(
                operation=request.operation,
                operation_status=_FAILED,
                operation_metadata={"error": error},
            )
        return self.executor.perform(request, self._empty_context())

    # --- import / export -------------------------------------------------
    def _run_import(self, request, workspace) -> OperationResult:
        active = workspace or self.current_workspace()
        try:
            events = active.read_ics(request.ics_path or "")
            for event in events:
                self._validate_imported(event)
        except (CalendarImportError, CalendarValidationError) as exc:
            return OperationResult(
                operation=CalendarOperation.IMPORT_ICS.value,
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        result = self.executor.perform(request, CalendarExecutionContext(events))
        artifact = self.artifact_manager.imported(
            request.ics_path or "calendar.ics",
            {"imported_count": result.imported_count},
        )
        return result.model_copy(update={"artifact": artifact})

    def _run_export(self, request, workspace) -> OperationResult:
        active = workspace or self.current_workspace()
        listing = self.executor.perform(
            CalendarOperationRequest(
                operation=CalendarOperation.LIST.value,
                range_start=request.range_start,
                range_end=request.range_end,
            ),
            self._empty_context(),
        )
        filename = request.ics_path or "calendar.ics"
        try:
            written = active.write_ics(listing.events, filename)
        except OSError as exc:
            return OperationResult(
                operation=CalendarOperation.EXPORT_ICS.value,
                operation_status=_FAILED,
                operation_metadata={"error": type(exc).__name__},
            )
        artifact = self.artifact_manager.exported(
            written["staged_name"],
            written["staged_name"],
            {"exported_count": listing.event_count},
        )
        return OperationResult(
            operation=CalendarOperation.EXPORT_ICS.value,
            success=True,
            exported_count=listing.event_count,
            ics_content=written["content"],
            artifact=artifact,
            operation_status=_SUCCESS,
        )

    # --- artifact coordination ------------------------------------------
    def _with_search_artifact(self, result: SearchEventsResult) -> SearchEventsResult:
        if result.operation_status != _SUCCESS:
            return result
        artifact = self.artifact_manager.report(
            f"search:{result.query or '*'}",
            {"query": result.query, "match_count": result.match_count},
        )
        return result.model_copy(update={"artifact": artifact})

    # --- validation + DTO construction ----------------------------------
    def _build_event(self, request) -> CalendarEvent:
        validate_event_times(request.start_time, request.end_time, request.all_day)
        validate_timezone(request.time_zone)
        validate_recurrence(request.recurrence)
        attendees = self._build_attendees(request.attendees)
        organizer = self._build_organizer(request.organizer, request.organizer_name)
        reminders = self._build_reminders(request.reminders)
        organizer_email = organizer.email if organizer else ""
        event_id = deterministic_event_id(
            uid=request.uid,
            summary=request.summary or "",
            start_time=request.start_time or "",
            end_time=request.end_time or "",
            organizer=organizer_email,
        )
        return CalendarEvent(
            event_id=event_id,
            uid=request.uid,
            summary=request.summary or "",
            description=request.description,
            location=request.location,
            start_time=request.start_time,
            end_time=request.end_time,
            time_zone=request.time_zone,
            all_day=request.all_day,
            busy=request.busy,
            organizer=organizer,
            attendees=attendees,
            reminders=reminders,
            recurrence=request.recurrence,
        )

    def _apply_updates(self, event: CalendarEvent, update_fields) -> CalendarEvent:
        updates = {
            key: value
            for key, value in update_fields.items()
            if key in _SCALAR_UPDATE_KEYS
        }
        if "recurrence" in update_fields:
            validate_recurrence(update_fields["recurrence"])
            updates["recurrence"] = update_fields["recurrence"]
        if "attendees" in update_fields:
            updates["attendees"] = self._build_attendees(update_fields["attendees"])
        if "reminders" in update_fields:
            updates["reminders"] = self._build_reminders(update_fields["reminders"])
        if "organizer" in update_fields:
            organizer_value = update_fields["organizer"]
            updates["organizer"] = (
                self._build_organizer(organizer_value, None)
                if organizer_value
                else None
            )
        merged = event.model_copy(update=updates)
        validate_timezone(merged.time_zone)
        validate_event_times(merged.start_time, merged.end_time, merged.all_day)
        return merged

    def _validate_imported(self, event: CalendarEvent) -> None:
        validate_event_times(event.start_time, event.end_time, event.all_day)
        validate_timezone(event.time_zone)
        validate_attendees([attendee.email for attendee in event.attendees])

    @staticmethod
    def _build_attendees(emails) -> List[CalendarAttendee]:
        return [
            CalendarAttendee(email=email)
            for email in validate_attendees(list(emails or []))
        ]

    @staticmethod
    def _build_organizer(email, name) -> Optional[CalendarOrganizer]:
        if not email:
            return None
        return CalendarOrganizer(email=validate_email(email), display_name=name)

    @staticmethod
    def _build_reminders(minutes) -> List[CalendarReminder]:
        reminders = []
        for value in minutes or []:
            if int(value) < 0:
                raise CalendarValidationError(
                    "reminder minutes_before must be non-negative"
                )
            reminders.append(CalendarReminder(minutes_before=int(value)))
        return reminders

    @staticmethod
    def _validate_range(range_start, range_end, required) -> Optional[str]:
        if not range_start and not range_end:
            return "range_start and range_end are required" if required else None
        if not range_start or not range_end:
            return "both range_start and range_end are required"
        try:
            start = parse_calendar_datetime(range_start)
            end = parse_calendar_datetime(range_end)
        except CalendarValidationError as exc:
            return str(exc)
        if end < start:
            return "range_start must not be after range_end"
        return None

    @staticmethod
    def _empty_context() -> CalendarExecutionContext:
        return CalendarExecutionContext(events=[])

    # --- runtime bridge helper ------------------------------------------
    @classmethod
    def _serialize(cls, result: CalendarRunResult) -> dict:
        """Return a plain, JSON-serialisable dict of ``result`` (no bytes/objects)."""
        return cls._sanitize(result.model_dump())

    @classmethod
    def _sanitize(cls, value):
        if isinstance(value, dict):
            return {key: cls._sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._sanitize(item) for item in value]
        if isinstance(value, (bytes, bytearray)):
            return base64.b64encode(bytes(value)).decode("ascii")
        return value
