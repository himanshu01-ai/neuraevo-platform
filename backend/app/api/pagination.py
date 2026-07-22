"""Shared, bounded pagination parameters (Sprint 24 — API hardening).

A single dependency for the ``skip``/``limit`` offset pagination the list
endpoints use, so the bounds are declared in one place rather than re-typed (or,
as on some endpoints before this, forgotten). It keeps the existing parameter
names — ``skip`` and ``limit`` — so it is a drop-in for the endpoints that spelled
them out inline, with no change to the request or response contract.

The bounds are the production-safety point: ``skip`` cannot be negative (which
previously reached the database and failed as a 500), and ``limit`` is capped so
one request cannot ask for an unbounded page. Out-of-range input now gets a clear
422, consistent with the endpoints that already declared these bounds.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

#: The page size used when the caller does not specify one.
DEFAULT_PAGE_SIZE = 50

#: The largest page a single request may ask for.
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class Pagination:
    """A validated offset/limit window."""

    skip: int
    limit: int


def pagination_params(
    skip: int = Query(
        default=0,
        ge=0,
        description="Number of items to skip for pagination.",
    ),
    limit: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Maximum items to return (1–{MAX_PAGE_SIZE}).",
    ),
) -> Pagination:
    """Resolve validated ``skip``/``limit`` query parameters into a window."""
    return Pagination(skip=skip, limit=limit)


#: Annotated dependency alias, used the same way as the other ``...Dep`` aliases.
PaginationDep = Annotated[Pagination, Depends(pagination_params)]
