"""Email execution layer (Sprint 15.12 — the replaceable provider seam).

Defines the :class:`EmailExecutor` seam that performs the actual email operations
and its default :class:`LocalEmailExecutor` — a deterministic, offline, in-memory
mailbox (the analog of the File System layer's ``LocalFileSystemExecutor``). The
capability coordinates and validates; this layer performs. A single ``perform``
method keeps the seam tiny so a future provider (Gmail API, Microsoft Graph, IMAP,
SMTP, Exchange) can implement it without any change to the Runtime or the capability.

The default executor keeps folders (INBOX/SENT/DRAFTS/TRASH) of immutable
:class:`EmailMessage` DTOs; a "mutation" (mark read, move) replaces the stored DTO
with a new one, so the store only ever holds immutable data. It builds no
``smtplib``/``imaplib``/``email.message`` object into a result and holds no
credential — sending simply files the message into ``SENT``. Instance state only
(each capability gets its own mailbox); no static/singleton state, no network,
thread, or subprocess. Strictly additive to Sprints 15.1–15.11.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, NamedTuple, Optional, Union

from app.services.runtime.email_capability_models import (
    EmailAddress,
    EmailAttachment,
    EmailFolder,
    EmailFolderType,
    EmailMessage,
    EmailMetadata,
    EmailOperation,
    EmailOperationRequest,
    EmailOperationStatus,
    EmailRecipient,
)
from app.services.runtime.email_results import (
    FolderListResult,
    OperationResult,
    ReadEmailResult,
    SearchEmailResult,
    SendEmailResult,
)

_SUCCESS = EmailOperationStatus.SUCCESS.value
_FAILED = EmailOperationStatus.FAILED.value
_NOT_FOUND = EmailOperationStatus.NOT_FOUND.value

_SYSTEM_FOLDERS = (
    EmailFolderType.INBOX.value,
    EmailFolderType.SENT.value,
    EmailFolderType.DRAFTS.value,
    EmailFolderType.TRASH.value,
)

# The union every operation may return; the capability enriches these with
# artifacts but never constructs a different shape.
EmailOperationOutcome = Union[
    SendEmailResult,
    ReadEmailResult,
    SearchEmailResult,
    FolderListResult,
    OperationResult,
]


class EmailExecutionContext(NamedTuple):
    """Plain, validated inputs the capability hands to the executor.

    ``sender`` is the validated :class:`EmailAddress` of the sender (``None`` for
    non-send operations); ``recipients`` are the validated :class:`EmailRecipient`
    records; ``attachments`` are the staged :class:`EmailAttachment` records. Carries
    only plain DTOs — never a provider object or credential.
    """

    sender: Optional[EmailAddress]
    recipients: List[EmailRecipient]
    attachments: List[EmailAttachment]


class EmailExecutor(ABC):
    """Replaceable seam that performs one email operation and reports a DTO.

    Concrete executors own all mailbox/provider mechanics behind this single
    interface so the capability stays testable and provider-independent. An executor
    must never let an SMTP/IMAP/``email.message`` object or a credential escape — it
    returns only a plain result DTO.
    """

    @abstractmethod
    def perform(
        self,
        request: EmailOperationRequest,
        context: EmailExecutionContext,
    ) -> EmailOperationOutcome:
        """Perform ``request`` with the validated ``context`` and return its result."""


class LocalEmailExecutor(EmailExecutor):
    """Default executor: a deterministic, offline in-memory mailbox.

    Dispatches on the request's operation to a focused handler over four system
    folders of immutable :class:`EmailMessage` DTOs. Sending files the message into
    ``SENT``; drafting into ``DRAFTS``; other operations read or replace stored DTOs.
    A missing message/folder becomes ``NOT_FOUND`` and an invalid folder becomes
    ``FAILED`` — never a raised provider object. Holds per-instance mailbox state
    only (no static/singleton state) and contacts no network.
    """

    def __init__(
        self,
        account_address: str = "user@neuraevo.local",
        seed_messages: Optional[List[EmailMessage]] = None,
    ) -> None:
        self.account_address = account_address
        self._folders: Dict[str, List[EmailMessage]] = {
            folder: [] for folder in _SYSTEM_FOLDERS
        }
        self._sequence = 0
        for message in seed_messages or []:
            self._folders.setdefault(message.folder, []).append(message)
            self._sequence = max(self._sequence, int(message.timestamp) + 1)

    # --- test/seed support (received mail) ------------------------------
    def deliver(
        self,
        *,
        subject: str,
        sender: EmailAddress,
        recipients: Optional[List[EmailRecipient]] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        folder: str = EmailFolderType.INBOX.value,
        is_read: bool = False,
    ) -> EmailMessage:
        """Add a message to ``folder`` (simulating received mail); return it.

        A local-mailbox convenience for seeding folders; it performs no network I/O.
        """
        message = EmailMessage(
            message_id=self._next_id(),
            subject=subject,
            sender=sender,
            recipients=list(recipients or []),
            body_text=body_text,
            body_html=body_html,
            attachments=list(attachments or []),
            folder=folder,
            is_read=is_read,
            timestamp=self._next_sequence(),
        )
        self._folders.setdefault(folder, []).append(message)
        return message

    # --- dispatch -------------------------------------------------------
    def perform(self, request, context) -> EmailOperationOutcome:
        operation = request.operation
        if operation == EmailOperation.SEND.value:
            return self._store_message(request, context, is_draft=False)
        if operation == EmailOperation.DRAFT.value:
            return self._store_message(request, context, is_draft=True)
        if operation == EmailOperation.READ_FOLDER.value:
            return self._read_folder(request)
        if operation == EmailOperation.READ_MESSAGE.value:
            return self._read_message(request)
        if operation == EmailOperation.SEARCH.value:
            return self._search(request)
        if operation == EmailOperation.LIST_FOLDERS.value:
            return self._list_folders()
        if operation == EmailOperation.DELETE.value:
            return self._delete(request)
        if operation == EmailOperation.MOVE.value:
            return self._move(request)
        if operation in (
            EmailOperation.MARK_READ.value,
            EmailOperation.MARK_UNREAD.value,
        ):
            return self._mark(request, "is_read", operation)
        if operation in (
            EmailOperation.MARK_STARRED.value,
            EmailOperation.MARK_UNSTARRED.value,
        ):
            return self._mark(request, "is_starred", operation)
        if operation == EmailOperation.METADATA.value:
            return self._metadata(request)
        if operation == EmailOperation.DOWNLOAD_ATTACHMENT.value:
            return self._download_attachment(request)
        return OperationResult(
            operation=operation or "UNKNOWN",
            operation_status=_FAILED,
            operation_metadata={"error": f"unsupported operation: {operation}"},
        )

    # --- send / draft ---------------------------------------------------
    def _store_message(self, request, context, is_draft) -> SendEmailResult:
        folder = (
            EmailFolderType.DRAFTS.value if is_draft else EmailFolderType.SENT.value
        )
        message = EmailMessage(
            message_id=self._next_id(),
            subject=request.subject or "",
            sender=context.sender,
            recipients=list(context.recipients),
            body_text=request.body_text,
            body_html=request.body_html,
            attachments=list(context.attachments),
            folder=folder,
            is_read=True,
            is_draft=is_draft,
            timestamp=self._next_sequence(),
            headers=self._headers(context),
        )
        self._folders[folder].append(message)
        return SendEmailResult(
            message_id=message.message_id,
            is_draft=is_draft,
            recipient_count=len(message.recipients),
            attachment_count=len(message.attachments),
            message=message,
            operation_status=_SUCCESS,
            operation_metadata={"folder": folder},
        )

    # --- read -----------------------------------------------------------
    def _read_folder(self, request) -> ReadEmailResult:
        folder = request.folder or EmailFolderType.INBOX.value
        if folder not in self._folders:
            return ReadEmailResult(
                folder=folder,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": f"folder not found: {folder}"},
            )
        messages = list(self._folders[folder])
        return ReadEmailResult(
            folder=folder,
            messages=messages,
            message_count=len(messages),
            operation_status=_SUCCESS,
        )

    def _read_message(self, request) -> ReadEmailResult:
        located = self._locate(request.message_id)
        if located is None:
            return ReadEmailResult(
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "message not found"},
            )
        folder, index, message = located
        if not message.is_read:  # reading marks the message read
            message = message.model_copy(update={"is_read": True})
            self._folders[folder][index] = message
        return ReadEmailResult(
            folder=folder,
            messages=[message],
            message=message,
            message_count=1,
            operation_status=_SUCCESS,
        )

    # --- search ---------------------------------------------------------
    def _search(self, request) -> SearchEmailResult:
        query = (request.query or "").strip().lower()
        field = request.search_field or "any"
        folders = (
            [request.folder]
            if request.folder and request.folder in self._folders
            else list(self._folders)
        )
        matches: List[EmailMessage] = []
        for folder in folders:
            for message in self._folders[folder]:
                if not query or self._matches(message, query, field):
                    matches.append(message)
        matches.sort(key=lambda m: m.timestamp)
        return SearchEmailResult(
            query=request.query or "",
            search_field=field,
            matches=matches,
            match_count=len(matches),
            operation_status=_SUCCESS,
        )

    # --- folders --------------------------------------------------------
    def _list_folders(self) -> FolderListResult:
        folders = []
        for name, messages in self._folders.items():
            folders.append(
                EmailFolder(
                    name=name,
                    folder_type=self._folder_type(name),
                    message_count=len(messages),
                    unread_count=sum(1 for m in messages if not m.is_read),
                )
            )
        folders.sort(key=lambda f: f.name)
        return FolderListResult(
            folders=folders,
            folder_count=len(folders),
            operation_status=_SUCCESS,
        )

    # --- delete / move --------------------------------------------------
    def _delete(self, request) -> OperationResult:
        located = self._locate(request.message_id)
        if located is None:
            return self._op_not_found(EmailOperation.DELETE.value, request.message_id)
        folder, index, message = located
        del self._folders[folder][index]
        if folder != EmailFolderType.TRASH.value:  # soft delete -> Trash
            trashed = message.model_copy(
                update={"folder": EmailFolderType.TRASH.value}
            )
            self._folders[EmailFolderType.TRASH.value].append(trashed)
            permanent = False
        else:
            permanent = True
        return OperationResult(
            operation=EmailOperation.DELETE.value,
            message_id=message.message_id,
            source_folder=folder,
            success=True,
            operation_status=_SUCCESS,
            operation_metadata={"permanent": permanent},
        )

    def _move(self, request) -> OperationResult:
        destination = request.destination_folder
        if not destination:
            return self._op_failed(
                EmailOperation.MOVE.value, request.message_id,
                "destination folder is required",
            )
        if destination not in self._folders:
            return self._op_failed(
                EmailOperation.MOVE.value, request.message_id,
                f"invalid destination folder: {destination}",
            )
        located = self._locate(request.message_id)
        if located is None:
            return self._op_not_found(EmailOperation.MOVE.value, request.message_id)
        folder, index, message = located
        del self._folders[folder][index]
        moved = message.model_copy(update={"folder": destination})
        self._folders[destination].append(moved)
        return OperationResult(
            operation=EmailOperation.MOVE.value,
            message_id=message.message_id,
            source_folder=folder,
            destination_folder=destination,
            success=True,
            operation_status=_SUCCESS,
        )

    # --- flags ----------------------------------------------------------
    def _mark(self, request, attribute, operation) -> OperationResult:
        value = operation in (
            EmailOperation.MARK_READ.value,
            EmailOperation.MARK_STARRED.value,
        )
        located = self._locate(request.message_id)
        if located is None:
            return self._op_not_found(operation, request.message_id)
        folder, index, message = located
        updated = message.model_copy(update={attribute: value})
        self._folders[folder][index] = updated
        return OperationResult(
            operation=operation,
            message_id=message.message_id,
            source_folder=folder,
            success=True,
            operation_status=_SUCCESS,
            operation_metadata={attribute: value},
        )

    # --- metadata / attachments -----------------------------------------
    def _metadata(self, request) -> OperationResult:
        located = self._locate(request.message_id)
        if located is None:
            return self._op_not_found(EmailOperation.METADATA.value, request.message_id)
        folder, _, message = located
        return OperationResult(
            operation=EmailOperation.METADATA.value,
            message_id=message.message_id,
            source_folder=folder,
            success=True,
            email_metadata=self._build_metadata(message),
            operation_status=_SUCCESS,
        )

    def _download_attachment(self, request) -> OperationResult:
        located = self._locate(request.message_id)
        if located is None:
            return self._op_not_found(
                EmailOperation.DOWNLOAD_ATTACHMENT.value, request.message_id
            )
        _, _, message = located
        wanted = request.attachment_filename
        attachment = None
        for candidate in message.attachments:
            if wanted is None or candidate.filename == wanted:
                attachment = candidate
                break
        if attachment is None:
            return self._op_failed(
                EmailOperation.DOWNLOAD_ATTACHMENT.value, request.message_id,
                f"attachment not found: {wanted}",
                status=_NOT_FOUND,
            )
        return OperationResult(
            operation=EmailOperation.DOWNLOAD_ATTACHMENT.value,
            message_id=message.message_id,
            success=True,
            attachment=attachment,
            operation_status=_SUCCESS,
        )

    # --- deterministic helpers ------------------------------------------
    def _locate(self, message_id):
        """Return ``(folder, index, message)`` for ``message_id`` or ``None``."""
        if not message_id:
            return None
        for folder, messages in self._folders.items():
            for index, message in enumerate(messages):
                if message.message_id == message_id:
                    return folder, index, message
        return None

    @staticmethod
    def _matches(message, query, field) -> bool:
        if field == "subject":
            haystacks = [message.subject]
        elif field == "body":
            haystacks = [message.body_text or "", message.body_html or ""]
        elif field == "sender":
            haystacks = [message.sender.address, message.sender.display_name or ""]
        elif field == "recipient":
            haystacks = [r.address.address for r in message.recipients]
        else:  # any
            haystacks = [
                message.subject,
                message.body_text or "",
                message.body_html or "",
                message.sender.address,
                *[r.address.address for r in message.recipients],
            ]
        return any(query in text.lower() for text in haystacks)

    @staticmethod
    def _build_metadata(message) -> EmailMetadata:
        return EmailMetadata(
            message_id=message.message_id,
            subject=message.subject,
            sender=message.sender,
            folder=message.folder,
            recipient_count=len(message.recipients),
            attachment_count=len(message.attachments),
            size_bytes=LocalEmailExecutor._message_size(message),
            is_read=message.is_read,
            is_starred=message.is_starred,
            is_draft=message.is_draft,
            timestamp=message.timestamp,
        )

    @staticmethod
    def _message_size(message) -> int:
        size = len(message.subject or "")
        size += len((message.body_text or "").encode("utf-8"))
        size += len((message.body_html or "").encode("utf-8"))
        size += sum(a.size_bytes for a in message.attachments)
        return size

    @staticmethod
    def _headers(context) -> Dict[str, str]:
        headers = {}
        if context.sender:
            headers["From"] = context.sender.address
        to = [r.address.address for r in context.recipients if r.recipient_type == "TO"]
        cc = [r.address.address for r in context.recipients if r.recipient_type == "CC"]
        if to:
            headers["To"] = ", ".join(to)
        if cc:
            headers["Cc"] = ", ".join(cc)
        return headers

    @staticmethod
    def _folder_type(name) -> str:
        return name if name in _SYSTEM_FOLDERS else EmailFolderType.CUSTOM.value

    def _next_id(self) -> str:
        return f"msg-{self._sequence}"

    def _next_sequence(self) -> float:
        value = float(self._sequence)
        self._sequence += 1
        return value

    @staticmethod
    def _op_failed(operation, message_id, error, status=_FAILED) -> OperationResult:
        return OperationResult(
            operation=operation,
            message_id=message_id,
            success=False,
            operation_status=status,
            operation_metadata={"error": error},
        )

    @staticmethod
    def _op_not_found(operation, message_id) -> OperationResult:
        return OperationResult(
            operation=operation,
            message_id=message_id,
            success=False,
            operation_status=_NOT_FOUND,
            operation_metadata={"error": "message not found"},
        )
