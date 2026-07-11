"""Email result models (Sprint 15.12 — immutable result DTOs).

The immutable, provider-independent results of the Email capability's operations: a
send/draft, a folder or single-message read, a search, a folder listing, and the
generic single-message operation (delete/move/mark/metadata/download). Kept in
their own module (mirroring the browser/python/filesystem model split); each carries
only plain data — no SMTP/IMAP/``email.message`` object, and no credential, crosses
this boundary. Strictly additive to Sprints 15.1–15.11, whose modules are left
untouched.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.email_capability_models import (
    EmailArtifact,
    EmailAttachment,
    EmailFolder,
    EmailMessage,
    EmailMetadata,
)


class SendEmailResult(BaseModel):
    """Immutable result of sending or drafting a message (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``message_id`` is the stored
    message's id (``None`` on failure); ``is_draft`` marks a draft vs a sent
    message; ``recipient_count``/``attachment_count`` are tallies; ``message`` is
    the stored :class:`EmailMessage`; ``artifact`` is the ``SENT``/``DRAFT``
    :class:`EmailArtifact`; ``attachment_artifacts`` are the
    ``UPLOADED_ATTACHMENT`` artifacts; ``operation_status`` is an
    :class:`EmailOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors. Producing this DTO sends nothing further.
    """

    model_config = ConfigDict(frozen=True)

    message_id: Optional[str] = None
    is_draft: bool = False
    recipient_count: int = 0
    attachment_count: int = 0
    message: Optional[EmailMessage] = None
    artifact: Optional[EmailArtifact] = None
    attachment_artifacts: List[EmailArtifact] = Field(default_factory=list)
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class ReadEmailResult(BaseModel):
    """Immutable result of reading a folder or a single message (no SDK object).

    ``frozen=True`` makes instances immutable. ``folder`` is the folder read;
    ``messages`` are the ordered :class:`EmailMessage` records (one for a single
    read); ``message`` is the single message when reading one (``None`` for a folder
    read); ``message_count`` is the tally; ``operation_status`` is an
    :class:`EmailOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors. Producing this DTO reads nothing further.
    """

    model_config = ConfigDict(frozen=True)

    folder: Optional[str] = None
    messages: List[EmailMessage] = Field(default_factory=list)
    message: Optional[EmailMessage] = None
    message_count: int = 0
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchEmailResult(BaseModel):
    """Immutable result of searching messages (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``query`` is the search text;
    ``search_field`` is the field searched; ``matches`` are the ordered
    :class:`EmailMessage` records; ``match_count`` is the tally; ``artifact`` is an
    optional ``REPORT`` :class:`EmailArtifact` summarising the search;
    ``operation_status`` is an :class:`EmailOperationStatus` label; and
    ``operation_metadata`` carries plain descriptors. Producing this DTO reads
    nothing further.
    """

    model_config = ConfigDict(frozen=True)

    query: str = ""
    search_field: str = "any"
    matches: List[EmailMessage] = Field(default_factory=list)
    match_count: int = 0
    artifact: Optional[EmailArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class FolderListResult(BaseModel):
    """Immutable result of listing mailbox folders (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``folders`` are the ordered
    :class:`EmailFolder` records; ``folder_count`` is the tally; ``operation_status``
    is an :class:`EmailOperationStatus` label; and ``operation_metadata`` carries
    plain descriptors. Producing this DTO reads nothing further.
    """

    model_config = ConfigDict(frozen=True)

    folders: List[EmailFolder] = Field(default_factory=list)
    folder_count: int = 0
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class OperationResult(BaseModel):
    """Immutable result of a single-message email operation (no SDK object).

    Covers delete, move, mark read/unread, mark starred/unstarred, metadata, and
    attachment download. ``frozen=True`` makes instances immutable. ``operation`` is
    an :class:`EmailOperation` label; ``message_id`` names the affected message;
    ``source_folder``/``destination_folder`` are the operands for a move (``None``
    otherwise); ``success`` marks a completed operation; ``email_metadata`` carries
    the descriptor for a ``METADATA`` request (``None`` otherwise); ``attachment``
    carries the descriptor for a ``DOWNLOAD_ATTACHMENT`` request (``None``
    otherwise); ``artifact`` is the :class:`EmailArtifact` recorded for a change
    (``None`` when none applies); ``operation_status`` is an
    :class:`EmailOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors. Producing this DTO runs nothing further.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    message_id: Optional[str] = None
    source_folder: Optional[str] = None
    destination_folder: Optional[str] = None
    success: bool = False
    email_metadata: Optional[EmailMetadata] = None
    attachment: Optional[EmailAttachment] = None
    artifact: Optional[EmailArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)
