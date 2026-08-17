"""The platform's one error response shape (Sprint 24 — API hardening).

Every error the API returns — a handled 4xx, a validation 422, or an unexpected
500 — is a JSON body with a ``detail`` field. This module documents that one
contract for OpenAPI and gives the exception handlers a single shape to build, so
a client (and the frontend's one error normaliser) can read every failure the
same way. It changes no behaviour: it names what the API already returns.

``detail`` is a human-readable string for handled errors and a list of
field-level objects for request-validation (422) errors — the two shapes FastAPI
already produces and the frontend already understands.
"""

from typing import List, Union

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """A handled error: one human-readable sentence under ``detail``."""

    detail: str = Field(
        description="A human-readable explanation of what went wrong.",
        examples=["You do not have access to this resource."],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"detail": "The task does not exist."}]
        }
    }


class ValidationErrorItem(BaseModel):
    """One field-level problem in a rejected request body or query."""

    loc: List[Union[str, int]] = Field(
        description="The path to the offending field, e.g. [\"body\", \"name\"].",
        examples=[["body", "name"]],
    )
    msg: str = Field(
        description="What is wrong with that field.",
        examples=["String should have at least 1 character"],
    )
    type: str = Field(
        description="The machine-readable error category.",
        examples=["string_too_short"],
    )


class ValidationErrorResponse(BaseModel):
    """A 422: ``detail`` is the list of field-level problems (FastAPI's shape)."""

    detail: List[ValidationErrorItem]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": [
                        {
                            "loc": ["body", "name"],
                            "msg": "String should have at least 1 character",
                            "type": "string_too_short",
                        }
                    ]
                }
            ]
        }
    }
