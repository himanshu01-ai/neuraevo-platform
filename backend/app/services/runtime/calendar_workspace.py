"""Calendar workspace abstraction (Sprint 15.13 — ICS staging + (de)serialisation).

Defines the workspace every Calendar operation uses for ICS handling. A
:class:`CalendarWorkspace` owns a single temporary staging directory and is the
*only* place ICS filesystem/format logic lives: it stages an ICS source, validates
and parses it into :class:`CalendarEvent` DTOs (import), generates ICS text from
events and writes it into staging (export), and cleans everything up safely.

The :class:`CalendarWorkspaceManager` is the stateless factory that mints the
current (persistent) staging workspace and throwaway temporary workspaces. The
workspace performs *no calendar logic* — no CRUD, no recurrence expansion, no
availability; it only reads/writes and (de)serialises the iCalendar format
(deterministic, stdlib only). An import source can come from a File System capability
workspace by pointing ``ics_root`` at it. No ``Path`` ever leaves in a DTO. Strictly
additive to Sprints 15.1–15.12.
"""

import pathlib
import shutil
import tempfile
from typing import Dict, List, Optional

from app.services.runtime.calendar_capability_models import (
    CalendarAttendee,
    CalendarEvent,
    CalendarOrganizer,
    deterministic_event_id,
)

# Product id stamped into generated calendars.
_PRODID = "-//NeuraEvo//Calendar Capability//EN"


class CalendarImportError(ValueError):
    """Raised when an ICS source is missing, unreadable, or malformed.

    The capability catches this at its boundary and reports a graceful ``FAILED``
    result; the exception object never crosses a capability boundary.
    """


class CalendarWorkspace:
    """One isolated staging workspace for ICS import/export.

    Holds a resolved staging ``root`` and an optional ``ics_root`` (e.g. a File
    System capability workspace root) that relative import paths are confined to. Its
    responsibilities are ICS staging, import parsing/validation, export generation,
    and cleanup — it performs no calendar CRUD. Instances are effectively immutable
    (their roots never change) and expose paths only as plain strings.
    """

    def __init__(
        self,
        workspace_id: str,
        staging_path,
        ics_root=None,
        is_temporary: bool = False,
    ) -> None:
        self.workspace_id = workspace_id
        self._staging = pathlib.Path(staging_path).resolve()
        self._ics_root = pathlib.Path(ics_root).resolve() if ics_root else None
        self.is_temporary = is_temporary
        self._staging.mkdir(parents=True, exist_ok=True)

    # --- plain-string accessors (no Path leaks) -------------------------
    @property
    def staging_path(self) -> str:
        """The resolved staging directory, as a plain string."""
        return str(self._staging)

    @property
    def ics_root(self) -> Optional[str]:
        """The configured ICS source root, as a plain string (or ``None``)."""
        return str(self._ics_root) if self._ics_root else None

    def exists(self) -> bool:
        """Return whether the staging directory currently exists."""
        return self._staging.is_dir()

    # --- import (read + validate + parse) -------------------------------
    def read_ics(self, source) -> List[CalendarEvent]:
        """Read and parse an ICS ``source`` into :class:`CalendarEvent` DTOs.

        Resolves the source (confined to ``ics_root`` for relative paths), reads it,
        and parses each ``VEVENT``. Raises :class:`CalendarImportError` if the source
        is missing/unreadable or the content is not a well-formed calendar (missing
        ``VCALENDAR`` wrapper, or a ``VEVENT`` without ``DTSTART``/``SUMMARY``).
        Performs no calendar logic beyond format parsing.
        """
        resolved, label = self._resolve_source(source)
        if not resolved.exists() or not resolved.is_file():
            raise CalendarImportError(f"ICS source not found: {label}")
        try:
            text = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            raise CalendarImportError(
                f"ICS source could not be read ({type(exc).__name__}): {label}"
            )
        return self.parse_ics(text)

    def parse_ics(self, text: str) -> List[CalendarEvent]:
        """Parse ICS ``text`` into :class:`CalendarEvent` DTOs (structural only).

        Raises :class:`CalendarImportError` on a missing ``VCALENDAR`` wrapper or a
        ``VEVENT`` lacking ``DTSTART``/``SUMMARY``.
        """
        if "BEGIN:VCALENDAR" not in text or "END:VCALENDAR" not in text:
            raise CalendarImportError("not a valid VCALENDAR document")
        lines = self._unfold(text)
        events: List[CalendarEvent] = []
        current: Optional[Dict[str, object]] = None
        for line in lines:
            if line == "BEGIN:VEVENT":
                current = {"attendees": []}
            elif line == "END:VEVENT":
                if current is None:
                    raise CalendarImportError("END:VEVENT without BEGIN:VEVENT")
                events.append(self._build_event(current))
                current = None
            elif current is not None:
                self._apply_property(current, line)
        return events

    # --- export (generate + write) --------------------------------------
    def write_ics(self, events: List[CalendarEvent], filename: str) -> Dict[str, str]:
        """Generate ICS text from ``events`` and write it into staging.

        Returns ``{"staged_name": <rel name>, "content": <ics text>}``. The filename
        is reduced to its bare name so an export can never write outside staging.
        """
        content = self.generate_ics(events)
        safe_name = pathlib.Path(filename or "calendar.ics").name or "calendar.ics"
        if not safe_name.lower().endswith(".ics"):
            safe_name += ".ics"
        (self._staging / safe_name).write_text(content, encoding="utf-8")
        return {"staged_name": safe_name, "content": content}

    def generate_ics(self, events: List[CalendarEvent]) -> str:
        """Return the ICS text for ``events`` (deterministic; no file I/O)."""
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{_PRODID}"]
        for event in events:
            lines.extend(self._event_lines(event))
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    # --- lifecycle ------------------------------------------------------
    def cleanup(self) -> None:
        """Clean the workspace's staging directory (temp removed, persistent emptied)."""
        if not self._staging.exists():
            return
        if self.is_temporary:
            shutil.rmtree(self._staging, ignore_errors=True)
            return
        for child in self._staging.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass

    # --- ICS generation helpers -----------------------------------------
    def _event_lines(self, event: CalendarEvent) -> List[str]:
        lines = ["BEGIN:VEVENT"]
        uid = event.uid or event.event_id
        lines.append(f"UID:{uid}")
        lines.append(f"SUMMARY:{self._escape(event.summary)}")
        lines.append(self._dt_line("DTSTART", event.start_time, event.all_day))
        if event.end_time:
            lines.append(self._dt_line("DTEND", event.end_time, event.all_day))
        if event.location:
            lines.append(f"LOCATION:{self._escape(event.location)}")
        if event.description:
            lines.append(f"DESCRIPTION:{self._escape(event.description)}")
        if event.recurrence:
            lines.append(f"RRULE:{event.recurrence}")
        if event.organizer:
            lines.append(f"ORGANIZER:mailto:{event.organizer.email}")
        for attendee in event.attendees:
            lines.append(f"ATTENDEE:mailto:{attendee.email}")
        lines.append("TRANSP:" + ("OPAQUE" if event.busy else "TRANSPARENT"))
        lines.append("END:VEVENT")
        return lines

    @staticmethod
    def _dt_line(prop: str, iso_value: str, all_day: bool) -> str:
        compact = CalendarWorkspace._iso_to_ics(iso_value, all_day)
        if all_day:
            return f"{prop};VALUE=DATE:{compact}"
        return f"{prop}:{compact}"

    @staticmethod
    def _iso_to_ics(iso_value: str, all_day: bool) -> str:
        text = iso_value.strip()
        if text.endswith("Z"):
            text = text[:-1]
        if all_day or "T" not in text:
            return text[:10].replace("-", "")
        date_part, time_part = text.split("T", 1)
        time_part = time_part.split("+")[0].split("-")[0]
        hms = (time_part.replace(":", "") + "000000")[:6]
        return f"{date_part.replace('-', '')}T{hms}"

    @staticmethod
    def _escape(value: Optional[str]) -> str:
        if value is None:
            return ""
        return (
            value.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
        )

    # --- ICS parsing helpers --------------------------------------------
    @staticmethod
    def _unfold(text: str) -> List[str]:
        """Return logical lines with RFC 5545 line folding undone."""
        raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines: List[str] = []
        for line in raw:
            if line[:1] in (" ", "\t") and lines:
                lines[-1] += line[1:]
            elif line.strip():
                lines.append(line.rstrip())
        return lines

    def _apply_property(self, current: Dict[str, object], line: str) -> None:
        if ":" not in line:
            return
        name_part, value = line.split(":", 1)
        name = name_part.split(";", 1)[0].upper()
        params = name_part.split(";")[1:]
        if name == "SUMMARY":
            current["summary"] = self._unescape(value)
        elif name == "DESCRIPTION":
            current["description"] = self._unescape(value)
        elif name == "LOCATION":
            current["location"] = self._unescape(value)
        elif name == "UID":
            current["uid"] = value.strip()
        elif name == "DTSTART":
            current["start_time"] = self._ics_to_iso(value)
            if any("VALUE=DATE" in p.upper() for p in params):
                current["all_day"] = True
        elif name == "DTEND":
            current["end_time"] = self._ics_to_iso(value)
        elif name == "RRULE":
            current["recurrence"] = value.strip()
        elif name == "ORGANIZER":
            current["organizer"] = value.strip().replace("mailto:", "")
        elif name == "ATTENDEE":
            current["attendees"].append(value.strip().replace("mailto:", ""))  # type: ignore[union-attr]
        elif name == "TRANSP":
            current["busy"] = value.strip().upper() != "TRANSPARENT"

    def _build_event(self, current: Dict[str, object]) -> CalendarEvent:
        if "start_time" not in current or "summary" not in current:
            raise CalendarImportError("VEVENT missing DTSTART or SUMMARY")
        uid = current.get("uid")  # type: ignore[assignment]
        organizer_email = current.get("organizer")
        organizer = (
            CalendarOrganizer(email=str(organizer_email))
            if organizer_email
            else None
        )
        attendees = [
            CalendarAttendee(email=str(email))
            for email in current.get("attendees", [])  # type: ignore[union-attr]
        ]
        return CalendarEvent(
            event_id=deterministic_event_id(
                uid=str(uid) if uid else None,
                summary=str(current.get("summary", "")),
                start_time=str(current.get("start_time", "")),
                end_time=str(current.get("end_time", "") or ""),
                organizer=str(organizer_email or ""),
            ),
            uid=str(uid) if uid else None,
            summary=str(current.get("summary", "")),
            description=current.get("description"),  # type: ignore[arg-type]
            location=current.get("location"),  # type: ignore[arg-type]
            start_time=str(current["start_time"]),
            end_time=current.get("end_time"),  # type: ignore[arg-type]
            all_day=bool(current.get("all_day", False)),
            busy=bool(current.get("busy", True)),
            organizer=organizer,
            attendees=attendees,
            recurrence=current.get("recurrence"),  # type: ignore[arg-type]
        )

    @staticmethod
    def _ics_to_iso(value: str) -> str:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1]
        if "T" in text:
            date_part, time_part = text.split("T", 1)
            iso_date = f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
            iso_time = f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
            return f"{iso_date}T{iso_time}"
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"

    @staticmethod
    def _unescape(value: str) -> str:
        return (
            value.replace("\\n", "\n")
            .replace("\\,", ",")
            .replace("\\;", ";")
            .replace("\\\\", "\\")
        )

    # --- source resolution ----------------------------------------------
    def _resolve_source(self, source):
        text = str(source).strip().replace("\\", "/")
        candidate = pathlib.Path(text)
        if candidate.is_absolute() or (len(text) >= 2 and text[1] == ":"):
            return pathlib.Path(source).resolve(), text
        if self._ics_root is not None:
            parts = [
                part
                for part in pathlib.PurePosixPath(text).parts
                if part not in ("", "/", ".")
            ]
            resolved = self._ics_root.joinpath(*parts).resolve()
            try:
                resolved.relative_to(self._ics_root)
            except ValueError:
                raise CalendarImportError(
                    f"ICS path escapes the ICS root: {source!r}"
                )
            return resolved, text
        return candidate.resolve(), text


class CalendarWorkspaceManager:
    """Stateless factory for :class:`CalendarWorkspace` instances.

    ``current_workspace`` returns the persistent staging workspace rooted at the
    configured staging root (or a deterministic default under the system temp dir);
    ``create_temporary_workspace`` mints a fresh throwaway workspace; ``cleanup``
    delegates to the workspace. It holds no state between calls and performs no
    calendar logic.
    """

    DEFAULT_DIRNAME = "neuraevo_calendar"

    def current_workspace(
        self,
        staging_root: Optional[str] = None,
        ics_root: Optional[str] = None,
    ) -> CalendarWorkspace:
        """Return the persistent ICS staging workspace (created)."""
        base = (
            pathlib.Path(staging_root)
            if staging_root
            else pathlib.Path(tempfile.gettempdir()) / self.DEFAULT_DIRNAME
        )
        base.mkdir(parents=True, exist_ok=True)
        return CalendarWorkspace("current", base, ics_root=ics_root)

    def create_temporary_workspace(
        self,
        prefix: str = "calendar",
        ics_root: Optional[str] = None,
    ) -> CalendarWorkspace:
        """Return a fresh, isolated temporary ICS staging workspace."""
        temp_dir = tempfile.mkdtemp(prefix=f"neuraevo_calendar_{prefix}_")
        return CalendarWorkspace(
            f"temp-{pathlib.Path(temp_dir).name}",
            temp_dir,
            ics_root=ics_root,
            is_temporary=True,
        )

    def cleanup(self, workspace: CalendarWorkspace) -> None:
        """Clean up ``workspace`` (delegates to :meth:`CalendarWorkspace.cleanup`)."""
        workspace.cleanup()
