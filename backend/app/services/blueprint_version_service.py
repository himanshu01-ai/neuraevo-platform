"""Blueprint version service: read access to blueprint history.

Read-only orchestration for the version endpoints. Ownership is enforced by
reusing :class:`BlueprintService.get_blueprint` (User -> Employee -> Blueprint
chain). Version *creation* is performed atomically by
:class:`BlueprintApplyService`, not here.
"""

import uuid
from typing import Sequence

from app.models.blueprint_version import BlueprintVersion
from app.models.user import User
from app.repositories.blueprint_version_repository import (
    BlueprintVersionRepository,
)
from app.services.blueprint_service import BlueprintService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlueprintVersionError(Exception):
    """Base class for blueprint-version domain errors."""


class BlueprintVersionNotFoundError(BlueprintVersionError):
    """Raised when a version does not exist for the employee's blueprint."""


class BlueprintVersionService:
    """Read access to an employee's blueprint version history."""

    def __init__(self, session) -> None:
        self.session = session
        self.versions = BlueprintVersionRepository(session)
        # Reused for the User -> Employee -> Blueprint ownership chain.
        self.blueprints = BlueprintService(session)

    def list_versions(
        self, owner: User, employee_id: uuid.UUID
    ) -> Sequence[BlueprintVersion]:
        """List the employee's blueprint versions, oldest first.

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` /
        ``BlueprintNotFoundError`` via the ownership chain.
        """
        blueprint = self.blueprints.get_blueprint(owner, employee_id)
        return self.versions.list_versions(blueprint.id)

    def get_version(
        self, owner: User, employee_id: uuid.UUID, version_id: uuid.UUID
    ) -> BlueprintVersion:
        """Return a single version scoped to the employee's blueprint.

        Raises :class:`BlueprintVersionNotFoundError` if the version does not
        exist or belongs to a different blueprint.
        """
        blueprint = self.blueprints.get_blueprint(owner, employee_id)
        version = self.versions.get_version(version_id)
        if version is None or version.blueprint_id != blueprint.id:
            raise BlueprintVersionNotFoundError(str(version_id))
        return version
