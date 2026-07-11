"""GitHub result models (Sprint 15.14 — immutable result DTOs).

The immutable, provider-independent results of the GitHub capability's operations: a
commit, a repository operation, a branch operation, an issue operation, and the
generic operation (status/stage/unstage/history/tags). Kept in their own module
(mirroring the browser/python/filesystem/email/calendar split); each carries only
plain data — no ``git``/``pygit2``/``GitPython``/GitHub SDK object, no API response,
and no internal storage object crosses this boundary. Strictly additive to Sprints
15.1–15.13.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.github_capability_models import (
    BranchInfo,
    CommitInfo,
    GitHubArtifact,
    IssueInfo,
    RepositoryInfo,
    RepositoryStatus,
    TagInfo,
)


class CreateCommitResult(BaseModel):
    """Immutable result of creating a commit (no git/SDK object exposed).

    ``frozen=True`` makes instances immutable. ``commit_id`` is the created commit's
    deterministic id (``None`` on failure); ``commit`` is the :class:`CommitInfo`;
    ``artifact`` is the ``COMMIT`` :class:`GitHubArtifact`; ``operation_status`` is a
    :class:`GitHubOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    commit_id: Optional[str] = None
    commit: Optional[CommitInfo] = None
    artifact: Optional[GitHubArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class RepositoryResult(BaseModel):
    """Immutable result of a repository operation (no git/SDK object exposed).

    Covers init, clone, open, and metadata. ``frozen=True`` makes instances
    immutable. ``repository`` is the :class:`RepositoryInfo`; ``artifact`` is an
    optional :class:`GitHubArtifact` (a repository ``REPORT``); ``operation_status``
    is a :class:`GitHubOperationStatus` label; and ``operation_metadata`` carries
    plain descriptors.
    """

    model_config = ConfigDict(frozen=True)

    repository: Optional[RepositoryInfo] = None
    artifact: Optional[GitHubArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class BranchResult(BaseModel):
    """Immutable result of a branch operation (no git object exposed).

    Covers create, checkout, delete, and list. ``frozen=True`` makes instances
    immutable. ``branch`` is the single affected :class:`BranchInfo` (``None`` for a
    list); ``branches`` are the listed branches; ``artifact`` is an optional
    ``BRANCH`` :class:`GitHubArtifact`; ``operation_status`` is a
    :class:`GitHubOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    branch: Optional[BranchInfo] = None
    branches: List[BranchInfo] = Field(default_factory=list)
    artifact: Optional[GitHubArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class IssueResult(BaseModel):
    """Immutable result of an issue operation (no SDK object / API response exposed).

    Covers create, update, close, list, and search. ``frozen=True`` makes instances
    immutable. ``issue`` is the single affected :class:`IssueInfo` (``None`` for a
    list/search); ``issues`` are the listed/matched issues; ``match_count`` is the
    tally for a list/search; ``artifact`` is an optional :class:`GitHubArtifact` (an
    ``ISSUE`` or a search ``REPORT``); ``operation_status`` is a
    :class:`GitHubOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    issue: Optional[IssueInfo] = None
    issues: List[IssueInfo] = Field(default_factory=list)
    match_count: int = 0
    artifact: Optional[GitHubArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class OperationResult(BaseModel):
    """Immutable result of a status/stage/history/tag operation (no git object).

    Covers status, stage, unstage, history, create-tag, and list-tags.
    ``frozen=True`` makes instances immutable. ``operation`` is a
    :class:`GitHubOperation` label; ``repository_id`` names the affected repository;
    ``success`` marks a completed operation; ``repository_status`` carries the
    working-tree status for a ``STATUS``/``STAGE``/``UNSTAGE`` request; ``commits``
    are the history for a ``HISTORY`` request; ``tags`` are the listed tags;
    ``tag`` is the created :class:`TagInfo`; ``artifact`` is the
    :class:`GitHubArtifact` recorded for a change; ``operation_status`` is a
    :class:`GitHubOperationStatus` label; and ``operation_metadata`` carries plain
    descriptors.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    repository_id: Optional[str] = None
    success: bool = False
    repository_status: Optional[RepositoryStatus] = None
    commits: List[CommitInfo] = Field(default_factory=list)
    tags: List[TagInfo] = Field(default_factory=list)
    tag: Optional[TagInfo] = None
    artifact: Optional[GitHubArtifact] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)
