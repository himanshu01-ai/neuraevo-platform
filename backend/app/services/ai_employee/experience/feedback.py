"""Feedback manager (Sprint 16.12 — collect structured user feedback).

Defines :class:`FeedbackManager`, which collects and holds an append-only trail of
immutable :class:`FeedbackRecord` s — structured user feedback carrying a rating, a
comment, a :class:`FeedbackCategory`, and the workflow/feature it concerns. It
supports ``submit`` (append a new record), ``history`` (the full trail), and
``summary`` (deterministic aggregate counts and the average rating).

It is a plain in-memory, append-only ledger: existing records are never mutated (each
is a frozen DTO), and it decides, delegates, and executes nothing. It never touches
the Workflow Coordinator, a capability, a repository, a database, an LLM provider, a
thread, or the network. Its only state is the ledger plus a deterministic sequence
counter. Strictly additive to Sprints 1.x–16.11, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.experience.models import (
    FeedbackCategory,
    FeedbackRecord,
)


class FeedbackManager:
    """Append-only ledger of immutable feedback records (ledger only, no execution).

    ``submit`` appends a new immutable :class:`FeedbackRecord` and returns it;
    ``history`` returns the full trail in recording order; and ``summary`` returns
    deterministic aggregates (count, average rating, per-category and per-rating
    counts). It holds the ledger and a deterministic sequence counter — it runs nothing
    and never mutates a record.
    """

    def __init__(self) -> None:
        self._records: List[FeedbackRecord] = []
        self._sequence = 0

    # --- recording -------------------------------------------------------
    def submit(
        self,
        rating: int,
        comment: str = "",
        category: FeedbackCategory = FeedbackCategory.GENERAL,
        workflow: str = "",
        feature: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeedbackRecord:
        """Append and return a new immutable :class:`FeedbackRecord`."""
        sequence = self._next()
        record = FeedbackRecord(
            feedback_id=f"feedback-{sequence}",
            rating=rating,
            comment=comment,
            category=category,
            workflow=workflow,
            feature=feature,
            sequence=sequence,
            feedback_metadata=dict(metadata or {}),
        )
        self._records.append(record)
        return record

    # --- reads -----------------------------------------------------------
    def history(self) -> List[FeedbackRecord]:
        """Return the full feedback trail in deterministic recording order."""
        return list(self._records)

    def summary(self) -> Dict[str, Any]:
        """Return deterministic feedback aggregates (count, average, breakdowns).

        ``count`` is how many records exist; ``average_rating`` is the mean rating
        rounded to two decimals (``0.0`` when empty); ``by_category`` maps each
        category label to a count; and ``by_rating`` maps each rating (1–5) to a count.
        Reads only — it runs nothing.
        """
        count = len(self._records)
        total = sum(record.rating for record in self._records)
        average = round(total / count, 2) if count else 0.0
        by_category: Dict[str, int] = {}
        by_rating: Dict[int, int] = {}
        for record in self._records:
            label = record.category.value
            by_category[label] = by_category.get(label, 0) + 1
            by_rating[record.rating] = by_rating.get(record.rating, 0) + 1
        return {
            "count": count,
            "average_rating": average,
            "by_category": dict(sorted(by_category.items())),
            "by_rating": dict(sorted(by_rating.items())),
        }

    # --- helpers ---------------------------------------------------------
    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
