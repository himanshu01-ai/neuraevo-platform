"""Cache-control dependencies (Sprint 24 — API hardening).

Small, reusable route dependencies for the few endpoints where a caching
directive is a correctness or security concern rather than a default. Attaching
one as a route ``dependencies=[...]`` entry sets the header without changing the
response body, so it is purely additive.
"""

from fastapi import Response


def no_store(response: Response) -> None:
    """Mark a response as non-cacheable (``Cache-Control: no-store``).

    For responses that carry credentials — access/refresh tokens — so no shared
    or browser cache retains them. Header-only; the body is unchanged.
    """
    response.headers["Cache-Control"] = "no-store"
