"""Unit tests for the Sprint 15.13 Calendar Capability.

Covers the first-class calendar :class:`ExecutionCapability` end to end without any
network, calendar server, or SDK: operations run in-process through the deterministic
:class:`LocalCalendarExecutor` in-memory calendar, and each test uses fresh temporary
staging/ICS directories that are cleaned up.

Covers:

* the immutable DTOs (:class:`CalendarEvent`, :class:`CalendarAttendee`,
  :class:`CalendarOrganizer`, :class:`CalendarReminder`, :class:`CalendarMetadata`,
  :class:`CalendarAvailability`, :class:`CalendarArtifact`, and the five result DTOs)
  and the enums;
* create, read, list, search, update, delete, metadata, and availability;
* recurring events (expansion), attendees, organizer, location, description, busy/free,
  all-day events, time zones, and reminder configuration;
* ICS export and import (round-trip) plus invalid-ICS handling;
* validation and clear errors (start < end, time zones, recurrence, duplicate
  attendees, invalid event ids, invalid imports);
* artifact generation (created/updated/deleted/imported/exported/report);
* provider independence (an injected fake executor), ExecutionCapability compliance
  / runtime-bridge JSON safety, and workspace lifecycle;
* the composition-root wiring; and
* regression that prior seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_calendar_capability
"""

import os
import shutil
import tempfile
import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionStatus,
)
from app.services.runtime.calendar_artifact_manager import CalendarArtifactManager
from app.services.runtime.calendar_capability import CalendarCapability
from app.services.runtime.calendar_capability_models import (
    AvailabilityStatus,
    CalendarArtifact,
    CalendarArtifactType,
    CalendarAttendee,
    CalendarAvailability,
    CalendarEvent,
    CalendarMetadata,
    CalendarOperation,
    CalendarOperationRequest,
    CalendarOperationStatus,
    CalendarOrganizer,
    CalendarReminder,
    CalendarValidationError,
    deterministic_event_id,
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

_OP = CalendarOperation
_STATUS = CalendarOperationStatus


class _CalendarTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.staging = tempfile.mkdtemp(prefix="neuraevo_cal_stage_")
        self.ics_root = tempfile.mkdtemp(prefix="neuraevo_cal_ics_")
        self.executor = LocalCalendarExecutor()
        self.capability = CalendarCapability(
            executor=self.executor, staging_root=self.staging, ics_root=self.ics_root
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.staging, ignore_errors=True)
        shutil.rmtree(self.ics_root, ignore_errors=True)

    def _run(self, operation, **kwargs):
        return self.capability.run(
            CalendarOperationRequest(operation=operation, **kwargs)
        )

    def _create(self, summary="Event", start="2026-07-13T09:00:00",
                end="2026-07-13T10:00:00", **kwargs):
        return self._run(
            _OP.CREATE.value, summary=summary, start_time=start, end_time=end, **kwargs
        )


# =====================================================================
# DTOs and validation helpers
# =====================================================================
class CalendarDtoTests(unittest.TestCase):
    def test_operation_and_status_enums(self):
        self.assertEqual(len(list(CalendarOperation)), 10)
        self.assertEqual(
            [s.value for s in CalendarOperationStatus], ["SUCCESS", "NOT_FOUND", "FAILED"]
        )
        self.assertEqual(
            [a.value for a in CalendarArtifactType],
            ["CREATED", "UPDATED", "DELETED", "IMPORTED", "EXPORTED", "REPORT"],
        )
        self.assertEqual([a.value for a in AvailabilityStatus], ["BUSY", "FREE"])

    def test_dtos_are_immutable(self):
        event = CalendarEvent(event_id="e", start_time="2026-01-01T00:00:00")
        with self.assertRaises(ValidationError):
            event.summary = "x"
        with self.assertRaises(ValidationError):
            CalendarAttendee(email="a@b.com").optional = True
        with self.assertRaises(ValidationError):
            CalendarOrganizer(email="a@b.com").email = "z@b.com"
        with self.assertRaises(ValidationError):
            CalendarReminder(minutes_before=5).method = "EMAIL"
        with self.assertRaises(ValidationError):
            CalendarMetadata(event_id="e").summary = "x"
        with self.assertRaises(ValidationError):
            CalendarAvailability(status="FREE").status = "BUSY"
        with self.assertRaises(ValidationError):
            CalendarArtifact(
                artifact_id="x", artifact_type="CREATED", artifact_name="n"
            ).artifact_type = "DELETED"

    def test_result_dtos_immutable(self):
        results = [
            CreateEventResult(operation_status="SUCCESS"),
            ReadEventResult(operation_status="SUCCESS"),
            ListEventsResult(operation_status="SUCCESS"),
            SearchEventsResult(operation_status="SUCCESS"),
            OperationResult(operation="DELETE", operation_status="SUCCESS"),
        ]
        for result in results:
            with self.assertRaises(ValidationError):
                result.operation_status = "FAILED"

    def test_validate_event_times(self):
        validate_event_times("2026-07-13T09:00:00", "2026-07-13T10:00:00", False)
        validate_event_times("2026-12-25", None, True)  # all-day, no end
        with self.assertRaises(CalendarValidationError):
            validate_event_times("2026-07-13T10:00:00", "2026-07-13T09:00:00", False)
        with self.assertRaises(CalendarValidationError):
            validate_event_times("2026-07-13T09:00:00", None, False)  # timed needs end

    def test_validate_timezone(self):
        self.assertEqual(validate_timezone("UTC"), "UTC")
        self.assertEqual(validate_timezone("Europe/London"), "Europe/London")
        with self.assertRaises(CalendarValidationError):
            validate_timezone("Nowhere/Void")

    def test_validate_recurrence(self):
        self.assertEqual(validate_recurrence("FREQ=WEEKLY;INTERVAL=2")["FREQ"], "WEEKLY")
        self.assertIsNone(validate_recurrence(None))
        with self.assertRaises(CalendarValidationError):
            validate_recurrence("FREQ=HOURLY")
        with self.assertRaises(CalendarValidationError):
            validate_recurrence("FREQ=DAILY;COUNT=0")

    def test_deterministic_event_id_is_stable(self):
        first = deterministic_event_id(summary="A", start_time="s", end_time="e")
        second = deterministic_event_id(summary="A", start_time="s", end_time="e")
        by_uid = deterministic_event_id(uid="uid-123")
        self.assertEqual(first, second)
        self.assertEqual(by_uid, deterministic_event_id(uid="uid-123"))
        self.assertTrue(first.startswith("evt-"))


# =====================================================================
# Create / Read
# =====================================================================
class CalendarCreateReadTests(_CalendarTestBase):
    def test_create_full_event(self):
        result = self._create(
            summary="Standup", location="Zoom", description="daily sync",
            time_zone="America/New_York", organizer="boss@x.com",
            attendees=["a@x.com", "b@x.com"], reminders=[10, 30], busy=True,
        )
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        event = result.event
        self.assertEqual(event.summary, "Standup")
        self.assertEqual(event.location, "Zoom")
        self.assertEqual(event.description, "daily sync")
        self.assertEqual(event.time_zone, "America/New_York")
        self.assertEqual(event.organizer.email, "boss@x.com")
        self.assertEqual(len(event.attendees), 2)
        self.assertEqual([r.minutes_before for r in event.reminders], [10, 30])
        self.assertTrue(event.busy)
        self.assertEqual(result.artifact.artifact_type, CalendarArtifactType.CREATED.value)

    def test_create_rejects_start_after_end(self):
        result = self._create(start="2026-07-13T10:00:00", end="2026-07-13T09:00:00")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("before end_time", result.operation_metadata["error"])

    def test_create_rejects_invalid_timezone(self):
        result = self._create(time_zone="Mars/Phobos")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("time zone", result.operation_metadata["error"])

    def test_create_rejects_duplicate_attendees(self):
        result = self._create(attendees=["a@x.com", "A@x.com"])
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("duplicate attendee", result.operation_metadata["error"])

    def test_create_rejects_invalid_recurrence(self):
        result = self._create(recurrence="FREQ=HOURLY")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_create_all_day_event(self):
        result = self._run(_OP.CREATE.value, summary="Holiday", start_time="2026-12-25", all_day=True)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(result.event.all_day)
        self.assertIsNone(result.event.end_time)

    def test_deterministic_ids_across_instances(self):
        other = CalendarCapability(
            executor=LocalCalendarExecutor(), staging_root=self.staging
        )
        a = self._create(summary="Sync", start="2026-07-13T09:00:00", end="2026-07-13T09:30:00")
        b = other.run(CalendarOperationRequest(
            operation=_OP.CREATE.value, summary="Sync",
            start_time="2026-07-13T09:00:00", end_time="2026-07-13T09:30:00",
        ))
        self.assertEqual(a.event_id, b.event_id)

    def test_read_event(self):
        created = self._create(summary="Read me")
        result = self._run(_OP.READ.value, event_id=created.event_id)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.event.summary, "Read me")

    def test_read_invalid_id_is_not_found(self):
        self.assertEqual(
            self._run(_OP.READ.value, event_id="evt-missing").operation_status,
            _STATUS.NOT_FOUND.value,
        )


# =====================================================================
# List / Search / Recurring
# =====================================================================
class CalendarListSearchTests(_CalendarTestBase):
    def test_list_all_events(self):
        self._create(summary="A", start="2026-07-13T09:00:00", end="2026-07-13T10:00:00")
        self._create(summary="B", start="2026-07-14T09:00:00", end="2026-07-14T10:00:00")
        result = self._run(_OP.LIST.value)
        self.assertEqual(result.event_count, 2)
        self.assertFalse(result.expanded)

    def test_list_within_range(self):
        self._create(summary="In", start="2026-07-13T09:00:00", end="2026-07-13T10:00:00")
        self._create(summary="Out", start="2026-08-01T09:00:00", end="2026-08-01T10:00:00")
        result = self._run(
            _OP.LIST.value, range_start="2026-07-01T00:00:00", range_end="2026-07-31T00:00:00"
        )
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.events[0].summary, "In")

    def test_list_bad_range_fails(self):
        result = self._run(_OP.LIST.value, range_start="not-a-date", range_end="2026-07-31T00:00:00")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_recurring_expansion(self):
        self._run(
            _OP.CREATE.value, summary="Daily", start_time="2026-07-01T08:00:00",
            end_time="2026-07-01T08:30:00", recurrence="FREQ=DAILY;COUNT=10",
        )
        result = self._run(
            _OP.LIST.value, range_start="2026-07-01T00:00:00",
            range_end="2026-07-04T00:00:00", expand_recurring=True,
        )
        occurrences = [e for e in result.events if e.summary == "Daily"]
        self.assertTrue(result.expanded)
        self.assertEqual(len(occurrences), 3)  # Jul 1, 2, 3
        self.assertTrue(all(e.is_recurring_instance for e in occurrences))
        self.assertEqual(occurrences[0].recurrence_id, "2026-07-01T08:00:00")

    def test_weekly_recurrence_expansion(self):
        self._run(
            _OP.CREATE.value, summary="Weekly", start_time="2026-07-01T08:00:00",
            end_time="2026-07-01T09:00:00", recurrence="FREQ=WEEKLY;COUNT=4",
        )
        result = self._run(
            _OP.LIST.value, range_start="2026-07-01T00:00:00",
            range_end="2026-07-31T00:00:00", expand_recurring=True,
        )
        occurrences = [e for e in result.events if e.summary == "Weekly"]
        self.assertEqual(len(occurrences), 4)  # Jul 1, 8, 15, 22

    def test_search_by_field(self):
        self._create(summary="Budget review", location="Room 5", attendees=["cfo@x.com"])
        self._create(summary="Lunch", location="Cafe")
        self.assertEqual(self._run(_OP.SEARCH.value, query="budget", search_field="summary").match_count, 1)
        self.assertEqual(self._run(_OP.SEARCH.value, query="cafe", search_field="location").match_count, 1)
        self.assertEqual(self._run(_OP.SEARCH.value, query="cfo", search_field="attendee").match_count, 1)

    def test_search_produces_report_artifact(self):
        self._create(summary="Findable")
        result = self._run(_OP.SEARCH.value, query="findable")
        self.assertEqual(result.match_count, 1)
        self.assertEqual(result.artifact.artifact_type, CalendarArtifactType.REPORT.value)


# =====================================================================
# Update / Delete / Metadata / Availability
# =====================================================================
class CalendarMutationTests(_CalendarTestBase):
    def test_update_scalar_fields(self):
        created = self._create(summary="Old", location="A")
        result = self._run(
            _OP.UPDATE.value, event_id=created.event_id,
            update_fields={"summary": "New", "location": "B", "busy": False},
        )
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.event.summary, "New")
        self.assertEqual(result.event.location, "B")
        self.assertFalse(result.event.busy)
        self.assertEqual(result.event.event_id, created.event_id)  # id stable
        self.assertEqual(result.artifact.artifact_type, CalendarArtifactType.UPDATED.value)

    def test_update_attendees_and_organizer(self):
        created = self._create()
        result = self._run(
            _OP.UPDATE.value, event_id=created.event_id,
            update_fields={"attendees": ["x@x.com", "y@x.com"], "organizer": "chair@x.com"},
        )
        self.assertEqual(len(result.event.attendees), 2)
        self.assertEqual(result.event.organizer.email, "chair@x.com")

    def test_update_missing_event_is_not_found(self):
        self.assertEqual(
            self._run(_OP.UPDATE.value, event_id="evt-missing", update_fields={"summary": "x"}).operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_update_rejects_invalid_times(self):
        created = self._create(start="2026-07-13T09:00:00", end="2026-07-13T10:00:00")
        result = self._run(
            _OP.UPDATE.value, event_id=created.event_id,
            update_fields={"end_time": "2026-07-13T08:00:00"},
        )
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_delete_event(self):
        created = self._create()
        result = self._run(_OP.DELETE.value, event_id=created.event_id)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.artifact.artifact_type, CalendarArtifactType.DELETED.value)
        self.assertEqual(
            self._run(_OP.READ.value, event_id=created.event_id).operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_delete_missing_is_not_found(self):
        self.assertEqual(
            self._run(_OP.DELETE.value, event_id="evt-missing").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_metadata(self):
        created = self._create(
            summary="Meta", attendees=["a@x.com", "b@x.com"], reminders=[15],
            organizer="boss@x.com", recurrence="FREQ=DAILY",
        )
        result = self._run(_OP.METADATA.value, event_id=created.event_id)
        meta = result.calendar_metadata
        self.assertIsInstance(meta, CalendarMetadata)
        self.assertEqual(meta.summary, "Meta")
        self.assertEqual(meta.attendee_count, 2)
        self.assertEqual(meta.reminder_count, 1)
        self.assertEqual(meta.organizer_email, "boss@x.com")
        self.assertTrue(meta.is_recurring)

    def test_availability_busy(self):
        self._create(summary="Busy", start="2026-07-13T09:00:00", end="2026-07-13T10:00:00", busy=True)
        result = self._run(
            _OP.CHECK_AVAILABILITY.value,
            range_start="2026-07-13T09:30:00", range_end="2026-07-13T09:45:00",
        )
        self.assertEqual(result.availability.status, AvailabilityStatus.BUSY.value)
        self.assertEqual(len(result.availability.busy_event_ids), 1)

    def test_availability_free(self):
        self._create(summary="Free", start="2026-07-13T09:00:00", end="2026-07-13T10:00:00", busy=False)
        result = self._run(
            _OP.CHECK_AVAILABILITY.value,
            range_start="2026-07-13T09:30:00", range_end="2026-07-13T09:45:00",
        )
        self.assertEqual(result.availability.status, AvailabilityStatus.FREE.value)

    def test_availability_requires_range(self):
        self.assertEqual(
            self._run(_OP.CHECK_AVAILABILITY.value).operation_status,
            _STATUS.FAILED.value,
        )


# =====================================================================
# ICS import / export
# =====================================================================
class CalendarIcsTests(_CalendarTestBase):
    def test_export_generates_ics(self):
        self._create(summary="Exported", location="HQ")
        result = self._run(_OP.EXPORT_ICS.value, ics_path="out.ics")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.exported_count, 1)
        self.assertIn("BEGIN:VEVENT", result.ics_content)
        self.assertIn("SUMMARY:Exported", result.ics_content)
        self.assertEqual(result.artifact.artifact_type, CalendarArtifactType.EXPORTED.value)
        self.assertTrue(os.path.exists(os.path.join(self.staging, "out.ics")))

    def test_import_round_trip(self):
        self._create(summary="Trip", start="2026-07-13T09:00:00", end="2026-07-13T10:00:00",
                     location="Rome", description="details", attendees=["a@x.com"])
        exported = self._run(_OP.EXPORT_ICS.value, ics_path="cal.ics")
        # write the exported ICS into the ICS root and import it into a fresh calendar
        with open(os.path.join(self.ics_root, "cal.ics"), "w", encoding="utf-8") as handle:
            handle.write(exported.ics_content)
        fresh = CalendarCapability(
            executor=LocalCalendarExecutor(),
            staging_root=tempfile.mkdtemp(prefix="neuraevo_cal_imp_"),
            ics_root=self.ics_root,
        )
        result = fresh.run(CalendarOperationRequest(operation=_OP.IMPORT_ICS.value, ics_path="cal.ics"))
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.artifact.artifact_type, CalendarArtifactType.IMPORTED.value)
        imported = fresh.run(CalendarOperationRequest(operation=_OP.READ.value, event_id=result.event_ids[0]))
        self.assertEqual(imported.event.summary, "Trip")
        self.assertEqual(imported.event.location, "Rome")

    def test_import_all_day_event(self):
        ics = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:h1\r\n"
            "SUMMARY:Holiday\r\nDTSTART;VALUE=DATE:20261225\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        with open(os.path.join(self.ics_root, "holiday.ics"), "w", encoding="utf-8") as handle:
            handle.write(ics)
        result = self._run(_OP.IMPORT_ICS.value, ics_path="holiday.ics")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        event = self._run(_OP.READ.value, event_id=result.event_ids[0]).event
        self.assertTrue(event.all_day)
        self.assertEqual(event.start_time, "2026-12-25")

    def test_import_missing_file_fails(self):
        result = self._run(_OP.IMPORT_ICS.value, ics_path="ghost.ics")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("not found", result.operation_metadata["error"])

    def test_import_invalid_ics_fails(self):
        with open(os.path.join(self.ics_root, "bad.ics"), "w", encoding="utf-8") as handle:
            handle.write("this is not iCalendar")
        result = self._run(_OP.IMPORT_ICS.value, ics_path="bad.ics")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("VCALENDAR", result.operation_metadata["error"])

    def test_import_vevent_missing_fields_fails(self):
        ics = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:x\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        with open(os.path.join(self.ics_root, "partial.ics"), "w", encoding="utf-8") as handle:
            handle.write(ics)
        result = self._run(_OP.IMPORT_ICS.value, ics_path="partial.ics")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_ics_path_traversal_is_blocked(self):
        with self.assertRaises(CalendarImportError):
            self.capability.current_workspace().read_ics("../escape.ics")


# =====================================================================
# Artifacts
# =====================================================================
class CalendarArtifactTests(_CalendarTestBase):
    def test_artifact_ids_are_deterministic(self):
        manager = CalendarArtifactManager()
        self.assertEqual(manager.created("Sync").artifact_id, manager.created("Sync").artifact_id)
        self.assertTrue(manager.created("Sync").artifact_id.startswith("cal-created-"))

    def test_artifact_manager_supports_all_kinds_and_is_stateless(self):
        manager = CalendarArtifactManager()
        self.assertEqual(manager.created("a").artifact_type, "CREATED")
        self.assertEqual(manager.updated("a").artifact_type, "UPDATED")
        self.assertEqual(manager.deleted("a").artifact_type, "DELETED")
        self.assertEqual(manager.imported("a").artifact_type, "IMPORTED")
        self.assertEqual(manager.exported("a", "a.ics").artifact_type, "EXPORTED")
        self.assertEqual(manager.report("a").artifact_type, "REPORT")
        self.assertEqual(vars(CalendarArtifactManager()), {})

    def test_failed_create_has_no_artifact(self):
        result = self._create(time_zone="Bad/Zone")
        self.assertIsNone(result.artifact)


# =====================================================================
# Provider independence / ExecutionCapability compliance / bridge
# =====================================================================
class _FakeExecutor(CalendarExecutor):
    def __init__(self) -> None:
        self.calls = []

    def perform(self, request, context):
        self.calls.append((request, context))
        return OperationResult(
            operation=request.operation,
            event_id="fake-1",
            success=True,
            operation_status=CalendarOperationStatus.SUCCESS.value,
            operation_metadata={"fake": True},
        )


class CalendarProviderTests(_CalendarTestBase):
    def test_provider_independence_with_injected_executor(self):
        fake = _FakeExecutor()
        capability = CalendarCapability(executor=fake, staging_root=self.staging)
        result = capability.run(CalendarOperationRequest(operation=_OP.DELETE.value, event_id="e"))
        self.assertTrue(result.operation_metadata["fake"])
        self.assertEqual(len(fake.calls), 1)

    def test_capability_is_execution_capability(self):
        self.assertIsInstance(self.capability, ExecutionCapability)

    def test_local_executor_holds_only_instance_state(self):
        executor = LocalCalendarExecutor()
        result = executor.perform(
            CalendarOperationRequest(operation=_OP.LIST.value),
            CalendarExecutionContext(events=[]),
        )
        self.assertEqual(result.event_count, 0)

    def test_results_are_plain_dtos(self):
        result = self._create()
        self.assertIsInstance(result, CreateEventResult)
        self.assertIsInstance(result, BaseModel)

    def test_execute_bridges_create(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="calendar",
            capability_inputs={
                "operation": "CREATE", "summary": "Bridge",
                "start_time": "2026-07-20T10:00:00", "end_time": "2026-07-20T11:00:00",
            },
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.COMPLETED.value)
        self.assertEqual(result.capability_name, "calendar")
        self.assertIsNotNone(result.capability_outputs["event_id"])
        self.assertEqual(result.execution_metadata["operation"], "CREATE")

    def test_execute_maps_failure(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="calendar",
            capability_inputs={"operation": "READ", "event_id": "evt-missing"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.FAILED.value)

    def test_execute_outputs_are_json_safe(self):
        created = self._create(summary="JSON", attendees=["a@x.com"])
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="calendar",
            capability_inputs={"operation": "READ", "event_id": created.event_id},
        )
        result = self.capability.execute(request)
        self._assert_json_safe(result.capability_outputs)

    def _assert_json_safe(self, value):
        if isinstance(value, dict):
            for item in value.values():
                self._assert_json_safe(item)
        elif isinstance(value, list):
            for item in value:
                self._assert_json_safe(item)
        else:
            self.assertNotIsInstance(value, (bytes, bytearray, BaseModel))


# =====================================================================
# Workspace lifecycle
# =====================================================================
class CalendarWorkspaceTests(_CalendarTestBase):
    def test_current_workspace_staging(self):
        workspace = self.capability.current_workspace()
        self.assertTrue(workspace.exists())
        self.assertEqual(
            os.path.realpath(workspace.staging_path), os.path.realpath(self.staging)
        )

    def test_temporary_workspace_is_isolated(self):
        temp = self.capability.create_temporary_workspace()
        self.assertTrue(temp.is_temporary)
        self.assertTrue(temp.exists())
        self.assertNotEqual(
            os.path.realpath(temp.staging_path), os.path.realpath(self.staging)
        )

    def test_cleanup_temporary_removes_it(self):
        temp = self.capability.create_temporary_workspace()
        path = temp.staging_path
        result = self.capability.cleanup_workspace(temp)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(path))

    def test_cleanup_current_empties_but_keeps(self):
        self._create(summary="x")
        self._run(_OP.EXPORT_ICS.value, ics_path="a.ics")
        workspace = self.capability.current_workspace()
        self.capability.cleanup_workspace(workspace)
        self.assertTrue(workspace.exists())
        self.assertEqual(list(os.scandir(self.staging)), [])

    def test_workspace_manager_is_stateless(self):
        self.assertEqual(vars(CalendarWorkspaceManager()), {})


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class CalendarDependencyInjectionTests(unittest.TestCase):
    def test_get_calendar_capability_returns_capability(self):
        from app.core.dependencies import get_calendar_capability

        capability = get_calendar_capability()
        self.assertIsInstance(capability, CalendarCapability)
        self.assertIsInstance(capability, ExecutionCapability)

    def test_calendar_capability_dep_is_wired(self):
        from app.core.dependencies import CalendarCapabilityDep

        self.assertIn(CalendarCapability, getattr(CalendarCapabilityDep, "__args__", ()))

    def test_wired_capability_executes(self):
        from app.core.dependencies import get_calendar_capability

        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="calendar",
            capability_inputs={"operation": "LIST"},
        )
        result = get_calendar_capability().execute(request)
        self.assertEqual(result.execution_status, "COMPLETED")


# =====================================================================
# Regression — prior seams unchanged
# =====================================================================
class CalendarRegressionTests(unittest.TestCase):
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

    def test_sprint_15_10_python_capability_unchanged(self):
        from app.core.dependencies import get_python_capability

        self.assertIsInstance(get_python_capability(), ExecutionCapability)

    def test_sprint_15_11_filesystem_capability_unchanged(self):
        from app.core.dependencies import get_filesystem_capability

        self.assertIsInstance(get_filesystem_capability(), ExecutionCapability)

    def test_sprint_15_12_email_capability_unchanged(self):
        from app.core.dependencies import get_email_capability

        self.assertIsInstance(get_email_capability(), ExecutionCapability)


if __name__ == "__main__":
    unittest.main()
