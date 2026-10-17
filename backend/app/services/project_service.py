"""Ownership-aware project and immutable-checkpoint domain services."""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError

from app.models.project import Project, ProjectCheckpoint
from app.models.user import User
from app.repositories.project_repository import (
    ProjectCheckpointRepository,
    ProjectRepository,
)
from app.schemas.project import (
    ProjectCheckpointCreate,
    ProjectContextReplacement,
    ProjectCreate,
    ProjectLifecycleChange,
    ProjectMetadataUpdate,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ProjectError(Exception):
    """Base class for project-domain failures."""


class ProjectNotFoundError(ProjectError):
    """The requested project does not exist."""


class ProjectAccessDeniedError(ProjectError):
    """The requested project belongs to another user."""


class ProjectValidationError(ProjectError):
    """The requested state is not a valid project state."""


class ProjectConflictError(ProjectError):
    """The requested mutation conflicts with persisted state."""


class ProjectVersionConflictError(ProjectConflictError):
    """The caller based its mutation on a stale project version."""


class ProjectArchivedError(ProjectConflictError):
    """An archived project was targeted by a write."""


class ProjectCheckpointNotFoundError(ProjectError):
    """The checkpoint does not exist within the owned project."""


class ProjectCheckpointConflictError(ProjectConflictError):
    """A checkpoint idempotency key was reused for different content."""


class ProjectService:
    """Owns project validation, authorization, lifecycle, and transactions."""

    def __init__(self, session) -> None:
        self.session = session
        self.projects = ProjectRepository(session)

    def create_project(self, owner: User, data: ProjectCreate) -> Project:
        project = self.projects.create(
            owner.id,
            name=self._clean_required(data.name, "A project needs a name."),
            objective=self._clean_optional(data.objective),
            technology_stack=self._clean_optional(data.technology_stack),
            repository_reference=self._clean_optional(data.repository_reference),
            constraints=self._clean_optional(data.constraints),
            current_state=self._clean_optional(data.current_state),
        )
        self.session.commit()
        self.session.refresh(project)
        logger.info("User %s created project %s", owner.id, project.id)
        return project

    def get_project(self, owner: User, project_id: uuid.UUID) -> Project:
        project = self.projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(str(project_id))
        if project.user_id != owner.id:
            raise ProjectAccessDeniedError(str(project_id))
        return project

    def list_projects(
        self,
        owner: User,
        *,
        archived: Optional[bool] = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Project]:
        if skip < 0 or limit < 1 or limit > 100:
            raise ProjectValidationError("Invalid project pagination.")
        return self.projects.list_by_user(
            owner.id, archived=archived, skip=skip, limit=limit
        )

    def update_metadata(
        self,
        owner: User,
        project_id: uuid.UUID,
        data: ProjectMetadataUpdate,
    ) -> Project:
        name = self._clean_required(data.name, "A project needs a name.")
        try:
            self.get_project(owner, project_id)
            changed = self.projects.update_if_version(
                owner.id,
                project_id,
                data.expected_version,
                require_archived=False,
                fields={"name": name},
            )
            return self._finish_versioned_write(owner, project_id, changed)
        except Exception:
            self.session.rollback()
            raise

    def replace_approved_context(
        self,
        owner: User,
        project_id: uuid.UUID,
        data: ProjectContextReplacement,
    ) -> Project:
        if data.approved is not True:
            raise ProjectValidationError(
                "Project context must be explicitly approved before it is stored."
            )
        now = datetime.now(timezone.utc)
        fields = {
            "objective": self._clean_required(
                data.objective, "Approved project context needs an objective."
            ),
            "technology_stack": self._clean_optional(data.technology_stack),
            "repository_reference": self._clean_optional(
                data.repository_reference
            ),
            "constraints": self._clean_optional(data.constraints),
            "current_state": self._clean_optional(data.current_state),
            "context_approved_at": now,
        }
        try:
            self.get_project(owner, project_id)
            changed = self.projects.update_if_version(
                owner.id,
                project_id,
                data.expected_version,
                require_archived=False,
                fields=fields,
                increment_context_revision=True,
            )
            return self._finish_versioned_write(owner, project_id, changed)
        except Exception:
            self.session.rollback()
            raise

    def archive_project(
        self,
        owner: User,
        project_id: uuid.UUID,
        data: ProjectLifecycleChange,
    ) -> Project:
        try:
            project = self.get_project(owner, project_id)
            if project.archived_at is not None:
                raise ProjectConflictError("That project is already archived.")
            changed = self.projects.update_if_version(
                owner.id,
                project_id,
                data.expected_version,
                require_archived=False,
                fields={"archived_at": datetime.now(timezone.utc)},
            )
            return self._finish_versioned_write(owner, project_id, changed)
        except Exception:
            self.session.rollback()
            raise

    def restore_project(
        self,
        owner: User,
        project_id: uuid.UUID,
        data: ProjectLifecycleChange,
    ) -> Project:
        try:
            project = self.get_project(owner, project_id)
            if project.archived_at is None:
                raise ProjectConflictError("Only an archived project can be restored.")
            changed = self.projects.update_if_version(
                owner.id,
                project_id,
                data.expected_version,
                require_archived=True,
                fields={"archived_at": None},
            )
            return self._finish_versioned_write(
                owner, project_id, changed, archived_is_read_only=False
            )
        except Exception:
            self.session.rollback()
            raise

    def _finish_versioned_write(
        self,
        owner: User,
        project_id: uuid.UUID,
        changed: bool,
        *,
        archived_is_read_only: bool = True,
    ) -> Project:
        if not changed:
            # Project services own their transaction, matching the existing
            # service convention. End the failed write before inspecting the
            # current row, then also end the read transaction before raising.
            self.session.rollback()
            try:
                project = self.get_project(owner, project_id)
                if archived_is_read_only and project.archived_at is not None:
                    error: ProjectError = ProjectArchivedError(
                        "An archived project is read-only. Restore it first."
                    )
                else:
                    error = ProjectVersionConflictError(
                        "The project changed. Reload it and retry."
                    )
            except Exception:
                self.session.rollback()
                raise
            self.session.rollback()
            raise error
        self.session.commit()
        self.session.expire_all()
        return self.get_project(owner, project_id)

    @staticmethod
    def _clean_required(value: str, message: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ProjectValidationError(message)
        return cleaned

    @staticmethod
    def _clean_optional(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProjectCheckpointService:
    """Creates and reads immutable, owner-scoped resume snapshots."""

    _REQUEST_CONSTRAINT = "uq_checkpoint_request"
    _SEQUENCE_CONSTRAINT = "uq_checkpoint_sequence"
    _SOURCE_MESSAGE_CONSTRAINT = (
        "fk_project_checkpoints_source_message_id_messages"
    )

    def __init__(self, session) -> None:
        self.session = session
        self.projects = ProjectRepository(session)
        self.checkpoints = ProjectCheckpointRepository(session)

    def create_checkpoint(
        self,
        owner: User,
        project_id: uuid.UUID,
        data: ProjectCheckpointCreate,
    ) -> ProjectCheckpoint:
        if data.confirmed is not True:
            raise ProjectValidationError(
                "Saving a checkpoint requires explicit confirmation."
            )
        content = self._validated_content(data)
        request_fingerprint = self._request_fingerprint(
            content, data.source_message_id
        )
        try:
            project = self.projects.get_owned_for_update(owner.id, project_id)
            if project is None:
                self._raise_project_lookup(owner, project_id)

            existing = self.checkpoints.get_by_request(project_id, data.request_id)
            if existing is not None:
                if self._same_request(existing, request_fingerprint):
                    # Commit the read-only unit of work to release the row lock.
                    self.session.commit()
                    return existing
                raise ProjectCheckpointConflictError(
                    "That checkpoint request ID was already used for different content."
                )

            if project.archived_at is not None:
                raise ProjectArchivedError(
                    "An archived project cannot receive new checkpoints."
                )
            if project.version != data.expected_version:
                raise ProjectVersionConflictError(
                    "The project changed. Reload it and retry."
                )
            if project.context_revision < 1 or project.context_approved_at is None:
                raise ProjectValidationError(
                    "Approve project context before saving a checkpoint."
                )
            if data.source_message_id is not None and not (
                self.checkpoints.source_belongs_to_owned_project(
                    data.source_message_id, project.id, owner.id
                )
            ):
                raise ProjectValidationError(
                    "The source message must belong to a conversation in this project."
                )

            checkpoint = self.checkpoints.create(
                project_id=project.id,
                sequence=self.checkpoints.next_sequence(project.id),
                context_revision=project.context_revision,
                context_snapshot=self._context_snapshot(project),
                request_id=data.request_id,
                request_fingerprint=request_fingerprint,
                source_message_id=data.source_message_id,
                **content,
            )
            project.version += 1
            self.session.flush()
            self.session.commit()
            self.session.refresh(checkpoint)
            return checkpoint
        except IntegrityError as exc:
            self.session.rollback()
            constraint = self._constraint_name(exc)
            if constraint == self._REQUEST_CONSTRAINT:
                existing = self.checkpoints.get_by_request(
                    project_id, data.request_id
                )
                if existing is not None and self._same_request(
                    existing, request_fingerprint
                ):
                    self.session.commit()
                    return existing
                self.session.rollback()
                raise ProjectCheckpointConflictError(
                    "That checkpoint request ID was already used for different content."
                ) from exc
            if constraint == self._SEQUENCE_CONSTRAINT:
                raise ProjectCheckpointConflictError(
                    "The checkpoint sequence conflicted with another save. "
                    "Reload the project and retry."
                ) from exc
            if constraint == self._SOURCE_MESSAGE_CONSTRAINT:
                source_exists = (
                    data.source_message_id is not None
                    and self.checkpoints.source_belongs_to_owned_project(
                        data.source_message_id, project_id, owner.id
                    )
                )
                self.session.rollback()
                if not source_exists:
                    raise ProjectValidationError(
                        "The source message no longer belongs to this project."
                    ) from exc
            # The write has been rolled back, but unexpected FK, CHECK, schema,
            # and driver failures retain their original type and diagnostics.
            raise
        except Exception:
            # The service owns this transaction. Always release the project row
            # lock and leave the shared session usable after a rejected save.
            self.session.rollback()
            raise

    def get_checkpoint(
        self,
        owner: User,
        project_id: uuid.UUID,
        checkpoint_id: uuid.UUID,
    ) -> ProjectCheckpoint:
        self._owned_project(owner, project_id)
        checkpoint = self.checkpoints.get_for_project(project_id, checkpoint_id)
        if checkpoint is None:
            raise ProjectCheckpointNotFoundError(str(checkpoint_id))
        return checkpoint

    def list_checkpoints(
        self,
        owner: User,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ProjectCheckpoint]:
        self._owned_project(owner, project_id)
        if skip < 0 or limit < 1 or limit > 100:
            raise ProjectValidationError("Invalid checkpoint pagination.")
        return self.checkpoints.list_for_project(
            project_id, skip=skip, limit=limit
        )

    def latest_checkpoint(
        self, owner: User, project_id: uuid.UUID
    ) -> Optional[ProjectCheckpoint]:
        self._owned_project(owner, project_id)
        return self.checkpoints.latest_for_project(project_id)

    def _owned_project(self, owner: User, project_id: uuid.UUID) -> Project:
        project = self.projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(str(project_id))
        if project.user_id != owner.id:
            raise ProjectAccessDeniedError(str(project_id))
        return project

    def _raise_project_lookup(self, owner: User, project_id: uuid.UUID) -> None:
        self._owned_project(owner, project_id)
        raise ProjectNotFoundError(str(project_id))  # pragma: no cover

    @staticmethod
    def _validated_content(data: ProjectCheckpointCreate) -> dict[str, Optional[str]]:
        content = {
            "decisions": ProjectService._clean_optional(data.decisions),
            "verified_progress": ProjectService._clean_optional(
                data.verified_progress
            ),
            "verification_note": ProjectService._clean_optional(
                data.verification_note
            ),
            "next_steps": ProjectService._clean_optional(data.next_steps),
        }
        if not any(
            content[key]
            for key in ("decisions", "verified_progress", "next_steps")
        ):
            raise ProjectValidationError(
                "A checkpoint needs a decision, verified progress, or next step."
            )
        if content["verified_progress"] and not content["verification_note"]:
            raise ProjectValidationError(
                "Verified progress requires a verification note."
            )
        return content

    @staticmethod
    def _same_request(
        checkpoint: ProjectCheckpoint,
        request_fingerprint: str,
    ) -> bool:
        return hmac.compare_digest(
            checkpoint.request_fingerprint,
            request_fingerprint,
        )

    @staticmethod
    def _request_fingerprint(
        content: dict[str, Optional[str]],
        source_message_id: Optional[uuid.UUID],
    ) -> str:
        payload = {
            **content,
            "source_message_id": (
                str(source_message_id) if source_message_id is not None else None
            ),
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def _constraint_name(cls, exc: IntegrityError) -> Optional[str]:
        diag = getattr(exc.orig, "diag", None)
        name = getattr(diag, "constraint_name", None)
        if name:
            return str(name)
        # SQLite and some test doubles do not expose DB-API diagnostics. This
        # fallback recognizes only the explicitly expected named constraints.
        message = str(exc.orig)
        for expected in (
            cls._REQUEST_CONSTRAINT,
            cls._SEQUENCE_CONSTRAINT,
            cls._SOURCE_MESSAGE_CONSTRAINT,
        ):
            if expected in message:
                return expected
        return None

    @staticmethod
    def _context_snapshot(project: Project) -> dict[str, Optional[str]]:
        return {
            "objective": project.objective,
            "technology_stack": project.technology_stack,
            "repository_reference": project.repository_reference,
            "constraints": project.constraints,
            "current_state": project.current_state,
        }

