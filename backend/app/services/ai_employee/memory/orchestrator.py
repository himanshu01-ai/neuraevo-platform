"""Memory Orchestrator (Sprint 16.6 — decide what to remember and retrieve).

Defines :class:`MemoryOrchestrator`, the coordinator of the memory lifecycle. It
follows the locked flow ``AIEmployee -> MemoryOrchestrator -> {MemoryPolicy,
MemoryClassifier, MemoryRetriever, PersistenceManager}`` and coordinates those four
injected collaborators:

    decide      (policy: should it be remembered?  classifier: how important?)
    remember    (if the policy says so: build a record, persist any workflow
                 state through the Persistence Layer, index it)
    recall      (retrieve via deterministic filters)
    forget      (drop a memory)
    update      (replace a memory's content/tags/metadata)
    summarize   (aggregate matching memories)

It coordinates the memory lifecycle only: it never stores memory records itself
(the retriever holds the index), never executes a workflow or capability, never
accesses a repository or database, and always routes durable workflow-state storage
through the injected Sprint 16.5 :class:`PersistenceManager`. There are no
embeddings, vectors, semantic search, or LLM calls. Constructor injection only; its
only mutable state is a deterministic sequence counter — no static, singleton, or
service-locator state. Fully deterministic. Strictly additive to Sprints 1.x–16.5,
whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.memory.classifier import MemoryClassifier
from app.services.ai_employee.memory.models import (
    MemoryCategory,
    MemoryDecision,
    MemoryNotFoundError,
    MemoryQuery,
    MemoryRecord,
    MemorySummary,
)
from app.services.ai_employee.memory.policy import MemoryPolicy
from app.services.ai_employee.memory.retriever import MemoryRetriever
from app.services.ai_employee.persistence.manager import PersistenceManager
from app.services.ai_employee.platform_models import WorkflowInstance


class MemoryOrchestrator:
    """Coordinates the memory lifecycle over policy, classifier, retriever, persistence.

    Constructed with an injected :class:`MemoryPolicy`, :class:`MemoryClassifier`,
    :class:`MemoryRetriever`, and Sprint 16.5 :class:`PersistenceManager`
    (constructor injection; it instantiates none of them). It decides what to
    remember, indexes memories through the retriever, and persists any associated
    workflow state through the Persistence Layer — never storing records itself,
    never touching a repository or database, and never executing a workflow or
    capability. It holds a deterministic sequence counter only.
    """

    def __init__(
        self,
        policy: MemoryPolicy,
        classifier: MemoryClassifier,
        retriever: MemoryRetriever,
        persistence: PersistenceManager,
    ) -> None:
        self.policy = policy
        self.classifier = classifier
        self.retriever = retriever
        self.persistence = persistence
        self._sequence = 0

    # --- decision --------------------------------------------------------
    def decide(
        self,
        category: MemoryCategory,
        content: str = "",
        workflow_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryDecision:
        """Decide whether to remember ``category`` and how important it is.

        Asks the policy (should it be remembered?) and the classifier (how
        important?) and returns an immutable :class:`MemoryDecision`. Nothing is
        stored.
        """
        should_remember = self.policy.should_remember(
            category, content, metadata
        )
        importance = self.classifier.classify(category, content, metadata)
        verdict = "remembered" if should_remember else "skipped"
        return MemoryDecision(
            workflow_id=workflow_id,
            category=category,
            should_remember=should_remember,
            importance=importance,
            reason=(
                f"category {category.value} {verdict} by "
                f"{type(self.policy).__name__}"
            ),
        )

    # --- lifecycle -------------------------------------------------------
    def remember(
        self,
        category: MemoryCategory,
        content: str = "",
        workflow_id: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        workflow_instance: Optional[WorkflowInstance] = None,
    ) -> Optional[MemoryRecord]:
        """Remember information if the policy allows, and return the record (else None).

        Runs :meth:`decide`; if the policy declines, returns ``None`` (nothing is
        stored). Otherwise, when a ``workflow_instance`` is supplied its state is
        persisted through the Persistence Layer (the memory records the resulting
        version), a deterministic :class:`MemoryRecord` is built, and it is indexed
        through the retriever. The orchestrator itself stores nothing and executes
        nothing.
        """
        decision = self.decide(category, content, workflow_id, metadata)
        if not decision.should_remember:
            return None

        sequence = self._next()
        resolved_workflow_id = workflow_id
        persisted_version: Optional[int] = None
        if workflow_instance is not None:
            result = self.persistence.save(workflow_instance)
            persisted_version = result.version
            resolved_workflow_id = workflow_instance.instance_id

        record = MemoryRecord(
            memory_id=(
                f"memory-{resolved_workflow_id or category.value}-{sequence}"
            ),
            workflow_id=resolved_workflow_id,
            category=category,
            importance=decision.importance,
            content=content,
            tags=list(tags or []),
            created_at_sequence=sequence,
            persisted_version=persisted_version,
            metadata=dict(metadata or {}),
        )
        self.retriever.add(record)
        return record

    def recall(self, query: MemoryQuery) -> List[MemoryRecord]:
        """Retrieve remembered records matching ``query`` (deterministic filters)."""
        return self.retriever.retrieve(query)

    def forget(self, memory_id: str) -> bool:
        """Forget the memory with ``memory_id``; return whether it existed."""
        return self.retriever.remove(memory_id)

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryRecord:
        """Update a remembered memory's content/tags/metadata and return it.

        Only the supplied fields change; the rest are preserved. Raises
        :class:`MemoryNotFoundError` when the memory is not remembered.
        """
        existing = self.retriever.get(memory_id)
        if existing is None:
            raise MemoryNotFoundError(f"no such memory: {memory_id}")
        updates: Dict[str, Any] = {}
        if content is not None:
            updates["content"] = content
        if tags is not None:
            updates["tags"] = list(tags)
        if metadata is not None:
            updates["metadata"] = dict(metadata)
        updated = existing.model_copy(update=updates)
        self.retriever.update(updated)
        return updated

    def summarize(
        self, query: Optional[MemoryQuery] = None
    ) -> MemorySummary:
        """Summarise the memories matching ``query`` (deterministic counts).

        Retrieves the matching records and aggregates deterministic counts by
        category and importance. With no query, summarises every remembered memory.
        Nothing is stored or executed.
        """
        query = query or MemoryQuery()
        records = self.retriever.retrieve(query)
        by_category: Dict[str, int] = {}
        by_importance: Dict[str, int] = {}
        for record in records:
            by_category[record.category.value] = (
                by_category.get(record.category.value, 0) + 1
            )
            by_importance[record.importance.value] = (
                by_importance.get(record.importance.value, 0) + 1
            )
        return MemorySummary(
            workflow_id=query.workflow_id,
            total=len(records),
            by_category=by_category,
            by_importance=by_importance,
            memory_ids=[record.memory_id for record in records],
        )

    # --- persistence integration ----------------------------------------
    def persisted_workflow(self, workflow_id: str) -> WorkflowInstance:
        """Load a persisted workflow instance through the Persistence Layer.

        Delegates to the injected :class:`PersistenceManager` — the orchestrator
        never touches a repository or database itself.
        """
        return self.persistence.load(workflow_id)

    # --- helpers ---------------------------------------------------------
    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
