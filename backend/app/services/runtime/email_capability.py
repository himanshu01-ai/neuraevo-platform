"""Email capability (Sprint 15.12 — first-class email ExecutionCapability).

Implements the Sprint 14.3 :class:`ExecutionCapability` contract by coordinating an
attachment workspace, an email execution seam, and an artifact manager into one
email operation: validate addresses/recipients → stage & validate attachments →
delegate the operation to the execution layer → record artifacts → return an
immutable result DTO.

The actual email logic runs behind the injectable :class:`EmailExecutor` seam — the
analog of the File System layer's ``FileSystemExecutor`` — so a future provider
(Gmail API, Microsoft Graph, IMAP, SMTP, Exchange) drops in without touching the
Runtime or this capability. The default :class:`LocalEmailExecutor` is a
deterministic in-memory mailbox and never lets an SMTP/IMAP/``email.message`` object
or a credential escape into a DTO. The capability itself coordinates only: it owns no
provider logic and no planning. Stateless beyond its injected collaborators and a
default-sender config. Strictly additive to Sprints 15.1–15.11 — it moves no
Runtime, Planning, Browser, Python, or File System code.
"""

import base64
from typing import List, Optional, Union

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.email_artifact_manager import EmailArtifactManager
from app.services.runtime.email_capability_models import (
    EmailAddress,
    EmailArtifactType,
    EmailOperation,
    EmailOperationRequest,
    EmailOperationStatus,
    EmailRecipient,
    EmailValidationError,
    RecipientType,
    parse_email_address,
)
from app.services.runtime.email_execution import (
    EmailExecutionContext,
    EmailExecutor,
    LocalEmailExecutor,
)
from app.services.runtime.email_results import (
    FolderListResult,
    OperationResult,
    ReadEmailResult,
    SearchEmailResult,
    SendEmailResult,
)
from app.services.runtime.email_workspace import (
    AttachmentError,
    EmailWorkspace,
    EmailWorkspaceManager,
)

# Everything ``run`` may return; the runtime bridge serialises whichever it gets.
EmailRunResult = Union[
    SendEmailResult,
    ReadEmailResult,
    SearchEmailResult,
    FolderListResult,
    OperationResult,
]

_SUCCESS = EmailOperationStatus.SUCCESS.value
_FAILED = EmailOperationStatus.FAILED.value

DEFAULT_SENDER = "user@neuraevo.local"


class EmailCapability(ExecutionCapability):
    """Email execution capability implementing the Sprint 14.3 contract.

    Coordinates the validate → stage → execute → artifact pipeline. ``run`` validates
    addresses/recipients and stages attachments (for send/draft), delegates to the
    injected :class:`EmailExecutor`, and records artifacts;
    ``current_workspace``/``create_temporary_workspace``/``cleanup_workspace`` expose
    attachment-workspace lifecycle; ``execute`` bridges the runtime
    :class:`CapabilityExecutionRequest`/``Result``. Stateless beyond its injected
    collaborators and default-sender config — it owns no provider logic and never lets
    an SMTP/IMAP/``email.message`` object or a credential escape.
    """

    def __init__(
        self,
        executor: Optional[EmailExecutor] = None,
        artifact_manager: Optional[EmailArtifactManager] = None,
        workspace_manager: Optional[EmailWorkspaceManager] = None,
        default_sender: str = DEFAULT_SENDER,
        staging_root: Optional[str] = None,
        attachment_root: Optional[str] = None,
    ) -> None:
        self.executor = executor or LocalEmailExecutor()
        self.artifact_manager = artifact_manager or EmailArtifactManager()
        self.workspace_manager = workspace_manager or EmailWorkspaceManager()
        self.default_sender = default_sender
        self.staging_root = staging_root
        self.attachment_root = attachment_root

    # --- workspace lifecycle --------------------------------------------
    def current_workspace(self) -> EmailWorkspace:
        """Return the persistent attachment-staging workspace."""
        return self.workspace_manager.current_workspace(
            self.staging_root, self.attachment_root
        )

    def create_temporary_workspace(self, prefix: str = "email") -> EmailWorkspace:
        """Return a fresh, isolated temporary attachment-staging workspace."""
        return self.workspace_manager.create_temporary_workspace(
            prefix, self.attachment_root
        )

    def cleanup_workspace(self, workspace: EmailWorkspace) -> OperationResult:
        """Clean up ``workspace`` and report the outcome as an immutable result."""
        try:
            self.workspace_manager.cleanup(workspace)
        except OSError as exc:  # graceful — never leak the OS object
            return OperationResult(
                operation="CLEANUP",
                success=False,
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
        request: EmailOperationRequest,
        workspace: Optional[EmailWorkspace] = None,
    ) -> EmailRunResult:
        """Run one operation, staging attachments in ``workspace`` when needed.

        Send/draft validate addresses and stage attachments first (a bad address or a
        missing/oversized attachment becomes a graceful ``FAILED`` result), then
        delegate to the executor and record artifacts. Download writes the attachment
        into the workspace and records a downloaded-attachment artifact. All other
        operations delegate directly. Never raises for user errors.
        """
        operation = request.operation
        if operation in (EmailOperation.SEND.value, EmailOperation.DRAFT.value):
            return self._run_send(request, workspace)
        if operation == EmailOperation.DOWNLOAD_ATTACHMENT.value:
            return self._run_download(request, workspace)
        result = self.executor.perform(request, self._empty_context())
        if operation == EmailOperation.SEARCH.value:
            return self._with_search_artifact(result)
        return result

    # --- ExecutionCapability contract (Sprint 14.3) ---------------------
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Bridge the runtime contract to one email operation.

        Reads the operation and its operands from ``capability_inputs``, runs it, and
        maps the result to a :class:`CapabilityExecutionResult` with plain,
        JSON-serialisable outputs (attachment bytes are base64-encoded) — never an
        SMTP/IMAP object or a credential.
        """
        inputs = request.capability_inputs
        email_request = EmailOperationRequest(
            operation=inputs.get("operation", ""),
            message_id=inputs.get("message_id"),
            folder=inputs.get("folder"),
            destination_folder=inputs.get("destination_folder"),
            subject=inputs.get("subject"),
            sender=inputs.get("sender"),
            to=list(inputs.get("to", []) or []),
            cc=list(inputs.get("cc", []) or []),
            bcc=list(inputs.get("bcc", []) or []),
            body_text=inputs.get("body_text"),
            body_html=inputs.get("body_html"),
            attachment_paths=list(inputs.get("attachment_paths", []) or []),
            attachment_filename=inputs.get("attachment_filename"),
            query=inputs.get("query"),
            search_field=inputs.get("search_field", "any"),
            flag_value=bool(inputs.get("flag_value", True)),
        )
        result = self.run(email_request)
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
                "operation": email_request.operation,
                "operation_status": result.operation_status,
            },
        )

    # --- send / draft coordination --------------------------------------
    def _run_send(self, request, workspace) -> SendEmailResult:
        active = workspace or self.current_workspace()
        try:
            sender = self._resolve_sender(request.sender)
            recipients = self._build_recipients(request)
            if request.operation == EmailOperation.SEND.value and not any(
                r.recipient_type == RecipientType.TO.value for r in recipients
            ):
                raise EmailValidationError("at least one TO recipient is required")
            attachments = [
                active.stage_attachment(path) for path in request.attachment_paths
            ]
        except (EmailValidationError, AttachmentError) as exc:
            return SendEmailResult(
                is_draft=request.operation == EmailOperation.DRAFT.value,
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        context = EmailExecutionContext(sender, recipients, attachments)
        result = self.executor.perform(request, context)
        return self._with_send_artifacts(result)

    def _run_download(self, request, workspace) -> OperationResult:
        active = workspace or self.current_workspace()
        result = self.executor.perform(request, self._empty_context())
        if result.operation_status != _SUCCESS or result.attachment is None:
            return result
        attachment = result.attachment
        staged_name = active.save_download(
            attachment.filename, attachment.content or b""
        )
        artifact = self.artifact_manager.downloaded_attachment(
            attachment.filename,
            staged_name,
            {"message_id": result.message_id, "size_bytes": attachment.size_bytes},
        )
        return result.model_copy(update={"artifact": artifact})

    # --- artifact coordination ------------------------------------------
    def _with_send_artifacts(self, result: SendEmailResult) -> SendEmailResult:
        if result.operation_status != _SUCCESS or result.message is None:
            return result
        message = result.message
        primary_type = (
            EmailArtifactType.DRAFT.value
            if result.is_draft
            else EmailArtifactType.SENT.value
        )
        primary = self.artifact_manager.build(
            primary_type,
            message.subject or message.message_id,
            None,
            {
                "message_id": message.message_id,
                "recipient_count": result.recipient_count,
            },
        )
        attachment_artifacts = [
            self.artifact_manager.uploaded_attachment(
                attachment.filename,
                attachment.staged_path,
                {"size_bytes": attachment.size_bytes},
            )
            for attachment in message.attachments
        ]
        return result.model_copy(
            update={"artifact": primary, "attachment_artifacts": attachment_artifacts}
        )

    def _with_search_artifact(self, result: SearchEmailResult) -> SearchEmailResult:
        if result.operation_status != _SUCCESS:
            return result
        artifact = self.artifact_manager.report(
            f"search:{result.query or '*'}",
            {"query": result.query, "match_count": result.match_count},
        )
        return result.model_copy(update={"artifact": artifact})

    # --- validation helpers ---------------------------------------------
    def _resolve_sender(self, raw: Optional[str]) -> EmailAddress:
        return parse_email_address(raw if raw else self.default_sender)

    def _build_recipients(self, request) -> List[EmailRecipient]:
        recipients: List[EmailRecipient] = []
        for raw in request.to:
            recipients.append(self._recipient(raw, RecipientType.TO.value))
        for raw in request.cc:
            recipients.append(self._recipient(raw, RecipientType.CC.value))
        for raw in request.bcc:
            recipients.append(self._recipient(raw, RecipientType.BCC.value))
        return recipients

    @staticmethod
    def _recipient(raw: str, recipient_type: str) -> EmailRecipient:
        return EmailRecipient(
            address=parse_email_address(raw), recipient_type=recipient_type
        )

    @staticmethod
    def _empty_context() -> EmailExecutionContext:
        return EmailExecutionContext(sender=None, recipients=[], attachments=[])

    # --- runtime bridge helper ------------------------------------------
    @classmethod
    def _serialize(cls, result: EmailRunResult) -> dict:
        """Return a plain, JSON-serialisable dict of ``result`` (no bytes/objects).

        Nested DTOs become plain dicts and any attachment bytes are base64-encoded,
        so nothing but plain data crosses the runtime boundary.
        """
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
