"""Capability validation models (Sprint 15.5 — immutable validation DTOs).

Provider-independent, immutable request/result shapes for validating a capability
invocation *before* runtime execution. The request pairs the capability's
:class:`CapabilityMetadata` with the proposed inputs; the result reports whether
the inputs satisfy the capability's declared contract — a validity flag, the
ordered validation errors, a copy of the validated inputs, and metadata.

These carry only plain data across the boundary; they describe a validation and
execute nothing — no capability, resolution, discovery, instantiation, dispatch,
network, or SDK lives here, and nothing mutates the request or the metadata.
Strictly additive to Sprints 15.1–15.4, whose modules are left untouched. The DTOs
know nothing about any concrete capability (Browser, Email, Calendar, Python,
GitHub, CRM, …): validation is driven entirely by the supplied metadata.
"""

from typing import Any, Dict, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.capability_metadata_models import CapabilityMetadata


class CapabilityValidationRequest(BaseModel):
    """Immutable request to validate one capability invocation (no execution).

    ``frozen=True`` makes instances immutable. ``capability_metadata`` is the
    :class:`CapabilityMetadata` describing the capability's declared contract
    (input schema, required permissions, …); ``capability_inputs`` are the
    proposed inputs to validate against it; and ``validation_metadata`` carries
    deterministic call-context descriptors and defaults to empty. Building this
    DTO validates and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    capability_metadata: CapabilityMetadata
    capability_inputs: Dict[str, Any] = Field(default_factory=dict)
    validation_metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityValidationResult(BaseModel):
    """Immutable result of validating one capability invocation (no execution).

    ``frozen=True`` makes instances immutable. ``is_valid`` is ``True`` only when
    the inputs satisfy the metadata's declared schema; ``validation_errors`` is
    the immutable tuple of errors in deterministic schema-key order (empty when
    valid); ``validated_inputs`` is always a fresh copy of the request's inputs
    (never the request's own dict); and ``validation_metadata`` carries
    deterministic descriptors only. Producing this DTO executes nothing and never
    mutates the request.
    """

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    validation_errors: Tuple[str, ...] = Field(default_factory=tuple)
    validated_inputs: Dict[str, Any] = Field(default_factory=dict)
    validation_metadata: Dict[str, Any] = Field(default_factory=dict)
