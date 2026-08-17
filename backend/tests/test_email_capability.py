"""Unit tests for the Sprint 15.12 Email Capability.

Covers the first-class email :class:`ExecutionCapability` end to end without any
network, SMTP/IMAP server, or SDK: operations run in-process through the
deterministic :class:`LocalEmailExecutor` in-memory mailbox, and each test uses fresh
temporary staging/attachment directories that are cleaned up.

Covers:

* the immutable DTOs (:class:`EmailAddress`, :class:`EmailRecipient`,
  :class:`EmailAttachment`, :class:`EmailMessage`, :class:`EmailFolder`,
  :class:`EmailMetadata`, :class:`SendEmailResult`, :class:`ReadEmailResult`,
  :class:`SearchEmailResult`, :class:`FolderListResult`, :class:`OperationResult`,
  :class:`EmailArtifact`) and the enums;
* send, draft, read folder, read single, search, folder listing, move, delete,
  mark read/unread, star/unstar, metadata, and attachment download;
* multiple recipients, CC, BCC, HTML and plain-text bodies;
* attachments (single, multiple, from a File System workspace, missing, oversized);
* address/recipient validation and clear errors;
* artifact generation (sent/draft/uploaded/downloaded/report);
* provider independence (an injected fake executor), ExecutionCapability
  compliance / runtime bridge (no bytes/objects leak), and workspace cleanup;
* the composition-root wiring; and
* regression that prior seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_email_capability
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
from app.services.runtime.email_artifact_manager import EmailArtifactManager
from app.services.runtime.email_capability import EmailCapability
from app.services.runtime.email_capability_models import (
    EmailAddress,
    EmailArtifact,
    EmailArtifactType,
    EmailAttachment,
    EmailFolder,
    EmailFolderType,
    EmailMessage,
    EmailMetadata,
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

_OP = EmailOperation
_STATUS = EmailOperationStatus


class _EmailTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.staging = tempfile.mkdtemp(prefix="neuraevo_em_stage_")
        self.attach_dir = tempfile.mkdtemp(prefix="neuraevo_em_att_")
        self.executor = LocalEmailExecutor()
        self.capability = EmailCapability(
            executor=self.executor,
            staging_root=self.staging,
            attachment_root=self.attach_dir,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.staging, ignore_errors=True)
        shutil.rmtree(self.attach_dir, ignore_errors=True)

    def _make_attachment(self, name, content=b"data") -> str:
        path = os.path.join(self.attach_dir, name)
        with open(path, "wb") as handle:
            handle.write(content)
        return name

    def _run(self, operation, **kwargs):
        return self.capability.run(EmailOperationRequest(operation=operation, **kwargs))

    def _deliver(self, subject="Hello", sender="boss@corp.com", **kwargs):
        return self.executor.deliver(
            subject=subject, sender=parse_email_address(sender), **kwargs
        )


# =====================================================================
# DTOs and validation
# =====================================================================
class EmailDtoTests(unittest.TestCase):
    def test_operation_enum_count(self):
        self.assertEqual(len(list(EmailOperation)), 14)
        self.assertIn("SEND", [o.value for o in EmailOperation])
        self.assertIn("DOWNLOAD_ATTACHMENT", [o.value for o in EmailOperation])

    def test_status_recipient_folder_artifact_enums(self):
        self.assertEqual(
            [s.value for s in EmailOperationStatus], ["SUCCESS", "NOT_FOUND", "FAILED"]
        )
        self.assertEqual([r.value for r in RecipientType], ["TO", "CC", "BCC"])
        self.assertEqual(
            [f.value for f in EmailFolderType],
            ["INBOX", "SENT", "DRAFTS", "TRASH", "CUSTOM"],
        )
        self.assertEqual(
            [a.value for a in EmailArtifactType],
            ["SENT", "DRAFT", "UPLOADED_ATTACHMENT", "DOWNLOADED_ATTACHMENT", "REPORT"],
        )

    def test_dtos_are_immutable(self):
        address = EmailAddress(address="a@b.com")
        with self.assertRaises(ValidationError):
            address.address = "z@b.com"
        with self.assertRaises(ValidationError):
            EmailRecipient(address=address, recipient_type="TO").recipient_type = "CC"
        with self.assertRaises(ValidationError):
            EmailAttachment(filename="f.txt").filename = "g.txt"
        with self.assertRaises(ValidationError):
            EmailFolder(name="INBOX", folder_type="INBOX").message_count = 3
        with self.assertRaises(ValidationError):
            EmailMetadata(message_id="m", sender=address).subject = "x"
        with self.assertRaises(ValidationError):
            EmailArtifact(
                artifact_id="x", artifact_type="SENT", artifact_name="s"
            ).artifact_type = "DRAFT"

    def test_result_dtos_immutable(self):
        results = [
            SendEmailResult(operation_status="SUCCESS"),
            ReadEmailResult(operation_status="SUCCESS"),
            SearchEmailResult(operation_status="SUCCESS"),
            FolderListResult(operation_status="SUCCESS"),
            OperationResult(operation="DELETE", operation_status="SUCCESS"),
        ]
        for result in results:
            with self.assertRaises(ValidationError):
                result.operation_status = "FAILED"

    def test_message_dto_immutable(self):
        message = EmailMessage(message_id="m", sender=EmailAddress(address="a@b.com"))
        with self.assertRaises(ValidationError):
            message.subject = "changed"

    def test_parse_valid_addresses(self):
        plain = parse_email_address("a@b.com")
        named = parse_email_address("Boss <boss@corp.com>")
        self.assertEqual(plain.address, "a@b.com")
        self.assertIsNone(plain.display_name)
        self.assertEqual(named.address, "boss@corp.com")
        self.assertEqual(named.display_name, "Boss")

    def test_parse_invalid_addresses_raise(self):
        for bad in ("", "not-an-email", "missing@domain", "a@b@c.com", "  "):
            with self.assertRaises(EmailValidationError):
                parse_email_address(bad)


# =====================================================================
# Send / Draft, recipients, bodies
# =====================================================================
class EmailSendTests(_EmailTestBase):
    def test_send_stores_to_sent(self):
        result = self._run(_OP.SEND.value, subject="Hi", to=["a@x.com"], body_text="hello")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(result.is_draft)
        self.assertEqual(result.message.folder, EmailFolderType.SENT.value)
        self.assertTrue(result.message.is_read)

    def test_send_requires_a_to_recipient(self):
        result = self._run(_OP.SEND.value, subject="Hi", cc=["c@x.com"])
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("TO recipient", result.operation_metadata["error"])

    def test_send_multiple_recipients_cc_bcc(self):
        result = self._run(
            _OP.SEND.value, subject="Team", to=["a@x.com", "b@x.com"],
            cc=["c@x.com"], bcc=["d@x.com"], body_text="hi",
        )
        self.assertEqual(result.recipient_count, 4)
        kinds = [r.recipient_type for r in result.message.recipients]
        self.assertEqual(kinds.count("TO"), 2)
        self.assertEqual(kinds.count("CC"), 1)
        self.assertEqual(kinds.count("BCC"), 1)
        self.assertEqual(result.message.headers["To"], "a@x.com, b@x.com")
        self.assertEqual(result.message.headers["Cc"], "c@x.com")

    def test_send_html_and_plain_bodies(self):
        result = self._run(
            _OP.SEND.value, subject="Rich", to=["a@x.com"],
            body_text="plain", body_html="<h1>rich</h1>",
        )
        self.assertEqual(result.message.body_text, "plain")
        self.assertEqual(result.message.body_html, "<h1>rich</h1>")

    def test_invalid_recipient_fails_gracefully(self):
        result = self._run(_OP.SEND.value, subject="x", to=["bad-address"])
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("invalid email address", result.operation_metadata["error"])

    def test_invalid_sender_fails_gracefully(self):
        result = self._run(_OP.SEND.value, subject="x", to=["a@x.com"], sender="nope")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_default_sender_is_used(self):
        result = self._run(_OP.SEND.value, subject="x", to=["a@x.com"])
        self.assertEqual(result.message.sender.address, "user@neuraevo.local")

    def test_draft_allows_no_recipients(self):
        result = self._run(_OP.DRAFT.value, subject="WIP", body_text="later")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(result.is_draft)
        self.assertEqual(result.message.folder, EmailFolderType.DRAFTS.value)


# =====================================================================
# Attachments
# =====================================================================
class EmailAttachmentTests(_EmailTestBase):
    def test_single_attachment_is_staged(self):
        self._make_attachment("report.pdf", b"%PDF-1.4 data")
        result = self._run(
            _OP.SEND.value, subject="Doc", to=["a@x.com"], attachment_paths=["report.pdf"]
        )
        self.assertEqual(result.attachment_count, 1)
        attachment = result.message.attachments[0]
        self.assertEqual(attachment.filename, "report.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(attachment.size_bytes, len(b"%PDF-1.4 data"))
        # staged into the email workspace staging dir
        self.assertTrue(os.path.exists(os.path.join(self.staging, "report.pdf")))

    def test_multiple_attachments(self):
        self._make_attachment("a.txt", b"aaa")
        self._make_attachment("b.csv", b"1,2,3")
        result = self._run(
            _OP.SEND.value, subject="Two", to=["a@x.com"],
            attachment_paths=["a.txt", "b.csv"],
        )
        self.assertEqual(result.attachment_count, 2)
        names = sorted(a.filename for a in result.message.attachments)
        self.assertEqual(names, ["a.txt", "b.csv"])

    def test_attachment_from_filesystem_workspace(self):
        # Simulate a File System capability workspace by pointing the attachment
        # root at a directory and referencing a relative path inside it.
        subdir = os.path.join(self.attach_dir, "docs")
        os.makedirs(subdir, exist_ok=True)
        with open(os.path.join(subdir, "note.txt"), "wb") as handle:
            handle.write(b"from fs workspace")
        result = self._run(
            _OP.SEND.value, subject="FS", to=["a@x.com"],
            attachment_paths=["docs/note.txt"],
        )
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.message.attachments[0].filename, "note.txt")

    def test_missing_attachment_fails_clearly(self):
        result = self._run(
            _OP.SEND.value, subject="x", to=["a@x.com"], attachment_paths=["ghost.txt"]
        )
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("attachment not found", result.operation_metadata["error"])

    def test_oversized_attachment_fails_clearly(self):
        self._make_attachment("big.bin", b"x" * 2048)
        capability = EmailCapability(
            executor=LocalEmailExecutor(),
            workspace_manager=_SmallLimitWorkspaceManager(limit=1024),
            staging_root=self.staging,
            attachment_root=self.attach_dir,
        )
        result = capability.run(
            EmailOperationRequest(
                operation=_OP.SEND.value, subject="x", to=["a@x.com"],
                attachment_paths=["big.bin"],
            )
        )
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("size limit", result.operation_metadata["error"])

    def test_attachment_traversal_is_blocked(self):
        with self.assertRaises(AttachmentError):
            self.capability.current_workspace().stage_attachment("../escape.txt")

    def test_download_attachment_writes_to_workspace(self):
        self._make_attachment("data.bin", b"\x00\x01\x02\x03")
        sent = self._run(
            _OP.SEND.value, subject="Doc", to=["a@x.com"], attachment_paths=["data.bin"]
        )
        result = self._run(
            _OP.DOWNLOAD_ATTACHMENT.value, message_id=sent.message_id,
            attachment_filename="data.bin",
        )
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.artifact.artifact_type, EmailArtifactType.DOWNLOADED_ATTACHMENT.value)
        self.assertTrue(os.path.exists(os.path.join(self.staging, "data.bin")))

    def test_download_missing_attachment_is_not_found(self):
        sent = self._run(_OP.SEND.value, subject="x", to=["a@x.com"])
        result = self._run(
            _OP.DOWNLOAD_ATTACHMENT.value, message_id=sent.message_id,
            attachment_filename="nope.bin",
        )
        self.assertEqual(result.operation_status, _STATUS.NOT_FOUND.value)


class _SmallLimitWorkspaceManager(EmailWorkspaceManager):
    def __init__(self, limit):
        self._limit = limit

    def current_workspace(self, staging_root=None, attachment_root=None, max_attachment_bytes=None):
        return super().current_workspace(staging_root, attachment_root, self._limit)


# =====================================================================
# Read / Search / Folders
# =====================================================================
class EmailReadTests(_EmailTestBase):
    def test_read_folder(self):
        self._deliver(subject="One", body_text="1")
        self._deliver(subject="Two", body_text="2")
        result = self._run(_OP.READ_FOLDER.value, folder="INBOX")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.message_count, 2)

    def test_read_unknown_folder_is_not_found(self):
        self.assertEqual(
            self._run(_OP.READ_FOLDER.value, folder="ARCHIVE").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_read_single_marks_read(self):
        delivered = self._deliver(subject="Unread", body_text="x")
        self.assertFalse(delivered.is_read)
        result = self._run(_OP.READ_MESSAGE.value, message_id=delivered.message_id)
        self.assertTrue(result.message.is_read)
        self.assertEqual(result.message_count, 1)

    def test_read_missing_message_is_not_found(self):
        self.assertEqual(
            self._run(_OP.READ_MESSAGE.value, message_id="msg-999").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_search_by_field(self):
        self._deliver(subject="Invoice", sender="billing@corp.com", body_text="pay now")
        self._deliver(subject="Lunch", sender="friend@corp.com", body_text="tacos")
        by_subject = self._run(_OP.SEARCH.value, query="invoice", search_field="subject")
        by_body = self._run(_OP.SEARCH.value, query="tacos", search_field="body")
        by_sender = self._run(_OP.SEARCH.value, query="billing", search_field="sender")
        self.assertEqual(by_subject.match_count, 1)
        self.assertEqual(by_body.match_count, 1)
        self.assertEqual(by_sender.match_count, 1)

    def test_search_any_field_and_report_artifact(self):
        self._deliver(subject="Alpha", body_text="beta")
        result = self._run(_OP.SEARCH.value, query="alpha")
        self.assertEqual(result.match_count, 1)
        self.assertEqual(result.artifact.artifact_type, EmailArtifactType.REPORT.value)

    def test_list_folders_counts(self):
        self._deliver(subject="X")  # unread inbox
        self._run(_OP.SEND.value, subject="S", to=["a@x.com"])  # sent
        result = self._run(_OP.LIST_FOLDERS.value)
        by_name = {f.name: f for f in result.folders}
        self.assertEqual(result.folder_count, 4)
        self.assertEqual(by_name["INBOX"].message_count, 1)
        self.assertEqual(by_name["INBOX"].unread_count, 1)
        self.assertEqual(by_name["SENT"].message_count, 1)
        self.assertEqual(by_name["DRAFTS"].folder_type, EmailFolderType.DRAFTS.value)


# =====================================================================
# Move / Delete / Flags / Metadata
# =====================================================================
class EmailMutationTests(_EmailTestBase):
    def test_move_between_folders(self):
        delivered = self._deliver(subject="Move me")
        result = self._run(
            _OP.MOVE.value, message_id=delivered.message_id, destination_folder="TRASH"
        )
        self.assertEqual(result.source_folder, "INBOX")
        self.assertEqual(result.destination_folder, "TRASH")
        trash = self._run(_OP.READ_FOLDER.value, folder="TRASH")
        self.assertEqual(trash.message_count, 1)

    def test_move_to_invalid_folder_fails(self):
        delivered = self._deliver(subject="x")
        result = self._run(
            _OP.MOVE.value, message_id=delivered.message_id, destination_folder="NOWHERE"
        )
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("invalid destination folder", result.operation_metadata["error"])

    def test_delete_moves_to_trash_then_permanent(self):
        delivered = self._deliver(subject="Bye")
        first = self._run(_OP.DELETE.value, message_id=delivered.message_id)
        self.assertFalse(first.operation_metadata["permanent"])
        # find it in trash and delete again -> permanent
        trash = self._run(_OP.READ_FOLDER.value, folder="TRASH")
        second = self._run(_OP.DELETE.value, message_id=trash.messages[0].message_id)
        self.assertTrue(second.operation_metadata["permanent"])
        self.assertEqual(self._run(_OP.READ_FOLDER.value, folder="TRASH").message_count, 0)

    def test_delete_missing_is_not_found(self):
        self.assertEqual(
            self._run(_OP.DELETE.value, message_id="msg-999").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_mark_read_and_unread(self):
        delivered = self._deliver(subject="x")
        read = self._run(_OP.MARK_READ.value, message_id=delivered.message_id)
        self.assertTrue(read.operation_metadata["is_read"])
        unread = self._run(_OP.MARK_UNREAD.value, message_id=delivered.message_id)
        self.assertFalse(unread.operation_metadata["is_read"])

    def test_star_and_unstar(self):
        delivered = self._deliver(subject="x")
        starred = self._run(_OP.MARK_STARRED.value, message_id=delivered.message_id)
        self.assertTrue(starred.operation_metadata["is_starred"])
        unstarred = self._run(_OP.MARK_UNSTARRED.value, message_id=delivered.message_id)
        self.assertFalse(unstarred.operation_metadata["is_starred"])

    def test_metadata(self):
        self._make_attachment("a.txt", b"hello")
        sent = self._run(
            _OP.SEND.value, subject="Meta", to=["a@x.com", "b@x.com"],
            body_text="body", attachment_paths=["a.txt"],
        )
        result = self._run(_OP.METADATA.value, message_id=sent.message_id)
        meta = result.email_metadata
        self.assertIsInstance(meta, EmailMetadata)
        self.assertEqual(meta.subject, "Meta")
        self.assertEqual(meta.recipient_count, 2)
        self.assertEqual(meta.attachment_count, 1)
        self.assertGreater(meta.size_bytes, 0)

    def test_metadata_missing_is_not_found(self):
        self.assertEqual(
            self._run(_OP.METADATA.value, message_id="msg-999").operation_status,
            _STATUS.NOT_FOUND.value,
        )


# =====================================================================
# Artifacts
# =====================================================================
class EmailArtifactTests(_EmailTestBase):
    def test_send_produces_sent_and_upload_artifacts(self):
        self._make_attachment("a.txt", b"aaa")
        result = self._run(
            _OP.SEND.value, subject="A", to=["a@x.com"], attachment_paths=["a.txt"]
        )
        self.assertEqual(result.artifact.artifact_type, EmailArtifactType.SENT.value)
        self.assertEqual(len(result.attachment_artifacts), 1)
        self.assertEqual(
            result.attachment_artifacts[0].artifact_type,
            EmailArtifactType.UPLOADED_ATTACHMENT.value,
        )

    def test_draft_produces_draft_artifact(self):
        result = self._run(_OP.DRAFT.value, subject="D", body_text="x")
        self.assertEqual(result.artifact.artifact_type, EmailArtifactType.DRAFT.value)

    def test_failed_send_has_no_artifact(self):
        result = self._run(_OP.SEND.value, subject="x", to=["bad"])
        self.assertIsNone(result.artifact)

    def test_artifact_ids_are_deterministic(self):
        manager = EmailArtifactManager()
        self.assertEqual(manager.sent("Hello").artifact_id, manager.sent("Hello").artifact_id)
        self.assertTrue(manager.sent("Hello").artifact_id.startswith("em-sent-"))

    def test_artifact_manager_supports_all_kinds_and_is_stateless(self):
        manager = EmailArtifactManager()
        self.assertEqual(manager.draft("d").artifact_type, "DRAFT")
        self.assertEqual(manager.uploaded_attachment("f", "f").artifact_type, "UPLOADED_ATTACHMENT")
        self.assertEqual(manager.downloaded_attachment("f", "f").artifact_type, "DOWNLOADED_ATTACHMENT")
        self.assertEqual(manager.report("r").artifact_type, "REPORT")
        self.assertEqual(vars(EmailArtifactManager()), {})


# =====================================================================
# Provider independence / ExecutionCapability compliance / bridge
# =====================================================================
class _FakeExecutor(EmailExecutor):
    def __init__(self) -> None:
        self.calls = []

    def perform(self, request, context):
        self.calls.append((request, context))
        return OperationResult(
            operation=request.operation,
            message_id="fake-1",
            success=True,
            operation_status=EmailOperationStatus.SUCCESS.value,
            operation_metadata={"fake": True},
        )


class EmailProviderTests(_EmailTestBase):
    def test_provider_independence_with_injected_executor(self):
        fake = _FakeExecutor()
        capability = EmailCapability(
            executor=fake, staging_root=self.staging, attachment_root=self.attach_dir
        )
        result = capability.run(EmailOperationRequest(operation=_OP.DELETE.value, message_id="m"))
        self.assertTrue(result.operation_metadata["fake"])
        self.assertEqual(len(fake.calls), 1)

    def test_capability_is_execution_capability(self):
        self.assertIsInstance(self.capability, ExecutionCapability)

    def test_local_executor_holds_only_instance_state(self):
        executor = LocalEmailExecutor()
        # fresh mailbox: four empty system folders, no shared/static state
        result = executor.perform(
            EmailOperationRequest(operation=_OP.LIST_FOLDERS.value),
            EmailExecutionContext(None, [], []),
        )
        self.assertEqual(result.folder_count, 4)
        self.assertEqual(sum(f.message_count for f in result.folders), 0)

    def test_results_are_plain_dtos(self):
        result = self._run(_OP.SEND.value, subject="x", to=["a@x.com"])
        self.assertIsInstance(result, SendEmailResult)
        self.assertIsInstance(result, BaseModel)

    def test_execute_bridges_send(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="email",
            capability_inputs={"operation": "SEND", "subject": "Hi", "to": ["a@x.com"], "body_text": "b"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.COMPLETED.value)
        self.assertEqual(result.capability_name, "email")
        self.assertIsNotNone(result.capability_outputs["message_id"])
        self.assertEqual(result.execution_metadata["operation"], "SEND")

    def test_execute_maps_failure(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="email",
            capability_inputs={"operation": "SEND", "subject": "x", "to": ["bad"]},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.FAILED.value)

    def test_execute_outputs_are_json_safe_no_bytes_or_objects(self):
        self._make_attachment("a.bin", b"\x00\xff\x10")
        sent = self._run(_OP.SEND.value, subject="x", to=["a@x.com"], attachment_paths=["a.bin"])
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="email",
            capability_inputs={
                "operation": "DOWNLOAD_ATTACHMENT",
                "message_id": sent.message_id,
                "attachment_filename": "a.bin",
            },
        )
        result = self.capability.execute(request)
        attachment = result.capability_outputs["attachment"]
        # attachment content is base64 str, never raw bytes / model objects
        self.assertIsInstance(attachment["content"], str)
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
class EmailWorkspaceTests(_EmailTestBase):
    def test_current_workspace_staging_dir(self):
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

    def test_cleanup_temporary_workspace_removes_it(self):
        temp = self.capability.create_temporary_workspace()
        path = temp.staging_path
        result = self.capability.cleanup_workspace(temp)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(path))

    def test_cleanup_current_workspace_empties_but_keeps(self):
        self._make_attachment("a.txt", b"x")
        self._run(_OP.SEND.value, subject="x", to=["a@x.com"], attachment_paths=["a.txt"])
        workspace = self.capability.current_workspace()
        self.capability.cleanup_workspace(workspace)
        self.assertTrue(workspace.exists())
        self.assertEqual(list(os.scandir(self.staging)), [])

    def test_workspace_manager_is_stateless(self):
        self.assertEqual(vars(EmailWorkspaceManager()), {})


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class EmailDependencyInjectionTests(unittest.TestCase):
    def test_get_email_capability_returns_capability(self):
        from app.core.dependencies import get_email_capability

        capability = get_email_capability()
        self.assertIsInstance(capability, EmailCapability)
        self.assertIsInstance(capability, ExecutionCapability)

    def test_email_capability_dep_is_wired(self):
        from app.core.dependencies import EmailCapabilityDep

        self.assertIn(EmailCapability, getattr(EmailCapabilityDep, "__args__", ()))

    def test_wired_capability_executes(self):
        from app.core.dependencies import get_email_capability

        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="email",
            capability_inputs={"operation": "LIST_FOLDERS"},
        )
        result = get_email_capability().execute(request)
        self.assertEqual(result.execution_status, "COMPLETED")


# =====================================================================
# Regression — prior seams unchanged
# =====================================================================
class EmailRegressionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
