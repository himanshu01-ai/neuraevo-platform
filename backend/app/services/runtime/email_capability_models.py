"""Email capability models (Sprint 15.12 — immutable email DTOs).

Provider-independent, immutable DTOs and enums for the Email execution capability:
addresses, recipients, attachments, messages, folders, metadata, the change
artifact, and the operation request. A :class:`EmailMessage` is a plain snapshot of
one message (never an ``smtplib``/``imaplib``/``email.message`` object); a
:class:`EmailAttachment` describes one attachment (its bytes are plain data, never
a file handle); a :class:`EmailFolder` describes a mailbox folder.

These carry only plain data across the boundary — no SMTP/IMAP/SDK object, no
``email.message.Message``, and no credential ever appears. Address validation
(:func:`parse_email_address`) lives here because it produces an
:class:`EmailAddress`; it raises :class:`EmailValidationError` on a malformed
address. Strictly additive to Sprints 15.1–15.11, whose modules are left untouched.
The result DTOs live in :mod:`app.services.runtime.email_results`.
"""

import re
from email.utils import parseaddr
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# A pragmatic address shape check (local@domain.tld) — enough to reject the
# malformed addresses the capability must guard against without pretending to be a
# full RFC 5322 parser.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailValidationError(ValueError):
    """Raised when an email address (or recipient list) is invalid.

    The capability catches this at its boundary and reports a graceful ``FAILED``
    result; the exception object never crosses a capability boundary.
    """


class EmailOperation(str, Enum):
    """The allowed, deterministic email operation labels.

    Each maps one requested operation to a stable ``str`` label so requests
    serialise cleanly and the runtime bridge stays a pass-through. These are
    request labels only — naming one causes nothing to run until it is executed.
    """

    SEND = "SEND"
    DRAFT = "DRAFT"
    READ_FOLDER = "READ_FOLDER"
    READ_MESSAGE = "READ_MESSAGE"
    SEARCH = "SEARCH"
    LIST_FOLDERS = "LIST_FOLDERS"
    DELETE = "DELETE"
    MOVE = "MOVE"
    MARK_READ = "MARK_READ"
    MARK_UNREAD = "MARK_UNREAD"
    MARK_STARRED = "MARK_STARRED"
    MARK_UNSTARRED = "MARK_UNSTARRED"
    METADATA = "METADATA"
    DOWNLOAD_ATTACHMENT = "DOWNLOAD_ATTACHMENT"


class EmailOperationStatus(str, Enum):
    """The allowed, deterministic email operation outcomes.

    ``SUCCESS`` — the operation completed. ``NOT_FOUND`` — a required message/folder
    did not exist. ``FAILED`` — the operation could not complete (invalid address,
    missing/oversized attachment, invalid folder, or provider error). Kept as a
    ``str`` enum; the bridge maps ``SUCCESS`` to ``COMPLETED`` and everything else
    to ``FAILED``.
    """

    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    FAILED = "FAILED"


class RecipientType(str, Enum):
    """The role of a recipient on a message: ``TO``, ``CC``, or ``BCC``."""

    TO = "TO"
    CC = "CC"
    BCC = "BCC"


class EmailFolderType(str, Enum):
    """The kind of a mailbox folder.

    The four system folders plus ``CUSTOM`` for any user-created folder. Plain
    labels only.
    """

    INBOX = "INBOX"
    SENT = "SENT"
    DRAFTS = "DRAFTS"
    TRASH = "TRASH"
    CUSTOM = "CUSTOM"


class EmailArtifactType(str, Enum):
    """The kind of change an artifact records.

    ``SENT``/``DRAFT`` describe a stored message; ``UPLOADED_ATTACHMENT``/
    ``DOWNLOADED_ATTACHMENT`` describe an attachment moved through the workspace;
    ``REPORT`` describes a generated report (e.g. a search summary). Plain labels.
    """

    SENT = "SENT"
    DRAFT = "DRAFT"
    UPLOADED_ATTACHMENT = "UPLOADED_ATTACHMENT"
    DOWNLOADED_ATTACHMENT = "DOWNLOADED_ATTACHMENT"
    REPORT = "REPORT"


class EmailAddress(BaseModel):
    """Immutable email address with an optional display name (no SDK object).

    ``frozen=True`` makes instances immutable. ``address`` is the bare address
    (``local@domain.tld``); ``display_name`` is the optional friendly name. Building
    this DTO validates nothing on its own — use :func:`parse_email_address` to
    validate and construct one.
    """

    model_config = ConfigDict(frozen=True)

    address: str
    display_name: Optional[str] = None


class EmailRecipient(BaseModel):
    """Immutable recipient: an address plus its role (no SDK object).

    ``frozen=True`` makes instances immutable. ``address`` is the
    :class:`EmailAddress`; ``recipient_type`` is a :class:`RecipientType` label
    (``TO``/``CC``/``BCC``).
    """

    model_config = ConfigDict(frozen=True)

    address: EmailAddress
    recipient_type: str


class EmailAttachment(BaseModel):
    """Immutable attachment descriptor (bytes are plain data, no file handle).

    ``frozen=True`` makes instances immutable. ``filename`` is the attachment name;
    ``content_type`` is the guessed MIME type; ``size_bytes`` is its size;
    ``source_path`` is the workspace-relative or original path it was staged from
    (``None`` for inline content); ``staged_path`` is its name inside the email
    workspace staging area (``None`` before staging); ``content`` is the raw bytes
    (``None`` when omitted for a lightweight descriptor); and ``attachment_metadata``
    carries plain descriptors. Never a file handle or SDK object.
    """

    model_config = ConfigDict(frozen=True)

    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    source_path: Optional[str] = None
    staged_path: Optional[str] = None
    content: Optional[bytes] = None
    attachment_metadata: Dict[str, Any] = Field(default_factory=dict)


class EmailMessage(BaseModel):
    """Immutable snapshot of one email message (no SDK object exposed).

    ``frozen=True`` makes instances immutable — every mutation (mark read, move)
    produces a *new* message. ``message_id`` identifies it; ``subject``/``sender``/
    ``recipients`` are the envelope; ``body_text``/``body_html`` are the bodies
    (either may be ``None``); ``attachments`` are the :class:`EmailAttachment`
    records; ``folder`` is the containing folder name; ``is_read``/``is_starred``/
    ``is_draft`` are the flags; ``timestamp`` is a deterministic ordering value;
    ``headers`` carries plain header strings; and ``message_metadata`` carries plain
    descriptors. Never an ``email.message.Message`` or provider object.
    """

    model_config = ConfigDict(frozen=True)

    message_id: str
    subject: str = ""
    sender: EmailAddress
    recipients: List[EmailRecipient] = Field(default_factory=list)
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    attachments: List[EmailAttachment] = Field(default_factory=list)
    folder: str = EmailFolderType.INBOX.value
    is_read: bool = False
    is_starred: bool = False
    is_draft: bool = False
    timestamp: float = 0.0
    headers: Dict[str, str] = Field(default_factory=dict)
    message_metadata: Dict[str, Any] = Field(default_factory=dict)


class EmailFolder(BaseModel):
    """Immutable description of one mailbox folder (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``name`` is the folder name;
    ``folder_type`` is an :class:`EmailFolderType` label; ``message_count`` and
    ``unread_count`` are the tallies; and ``folder_metadata`` carries plain
    descriptors. Building this DTO contacts no mailbox.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    folder_type: str
    message_count: int = 0
    unread_count: int = 0
    folder_metadata: Dict[str, Any] = Field(default_factory=dict)


class EmailMetadata(BaseModel):
    """Immutable metadata summary for one message (no SDK object exposed).

    ``frozen=True`` makes instances immutable. Carries the message's identity
    (``message_id``, ``subject``, ``sender``, ``folder``), its tallies
    (``recipient_count``, ``attachment_count``, ``size_bytes``), its flags
    (``is_read``, ``is_starred``, ``is_draft``), its ``timestamp``, and plain
    ``metadata``. Producing this DTO reads nothing further.
    """

    model_config = ConfigDict(frozen=True)

    message_id: str
    subject: str = ""
    sender: EmailAddress
    folder: str = ""
    recipient_count: int = 0
    attachment_count: int = 0
    size_bytes: int = 0
    is_read: bool = False
    is_starred: bool = False
    is_draft: bool = False
    timestamp: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmailArtifact(BaseModel):
    """Immutable description of one change an operation produced (no SDK object).

    ``frozen=True`` makes instances immutable. ``artifact_id`` is a deterministic
    identifier; ``artifact_type`` is an :class:`EmailArtifactType` label;
    ``artifact_name`` is a human name (subject or filename); ``artifact_path`` is a
    workspace-relative path for attachment artifacts (``None`` for message
    artifacts); and ``artifact_metadata`` carries plain descriptors. Building this
    DTO runs nothing and never carries a credential.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    artifact_type: str
    artifact_name: str
    artifact_path: Optional[str] = None
    artifact_metadata: Dict[str, Any] = Field(default_factory=dict)


class EmailOperationRequest(BaseModel):
    """Immutable request to perform one email operation (no execution).

    ``frozen=True`` makes instances immutable. ``operation`` is an
    :class:`EmailOperation` label. The remaining fields are the union of what the
    operations need: ``message_id`` (read/delete/move/mark/metadata/download);
    ``folder``/``destination_folder`` (read/move); ``subject``/``sender``/``to``/
    ``cc``/``bcc``/``body_text``/``body_html``/``attachment_paths`` (send/draft);
    ``attachment_filename`` (download); ``query``/``search_field`` (search);
    ``flag_value`` (mark read/unread/starred/unstarred); and ``request_metadata``
    for plain call-context descriptors. Building this DTO sends nothing.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    message_id: Optional[str] = None
    folder: Optional[str] = None
    destination_folder: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    to: List[str] = Field(default_factory=list)
    cc: List[str] = Field(default_factory=list)
    bcc: List[str] = Field(default_factory=list)
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    attachment_paths: List[str] = Field(default_factory=list)
    attachment_filename: Optional[str] = None
    query: Optional[str] = None
    search_field: str = "any"
    flag_value: bool = True
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


def parse_email_address(raw: str) -> EmailAddress:
    """Validate and parse ``raw`` into an :class:`EmailAddress`.

    Accepts a bare address or a ``Display Name <addr>`` form; the display name is
    preserved. Raises :class:`EmailValidationError` for anything that is not a
    plausible ``local@domain.tld`` address. Performs no network lookup.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise EmailValidationError("email address must be a non-empty string")
    display_name, address = parseaddr(raw)
    if not _EMAIL_RE.match(address):
        raise EmailValidationError(f"invalid email address: {raw!r}")
    return EmailAddress(address=address, display_name=display_name or None)
