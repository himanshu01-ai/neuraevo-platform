"""Capability validation manager (Sprint 15.5 — deterministic input validation).

Validates a :class:`CapabilityValidationRequest` against the capability's declared
:class:`CapabilityMetadata` before runtime execution, returning a
:class:`CapabilityValidationResult`. It reads the request only: it never executes,
resolves, or discovers capabilities, never modifies the inputs or metadata, and
never mutates the request. Purely a deterministic check that every required input
schema key is present, surfacing the declared required permissions as descriptors.

Deterministic and offline: no AI, network, clock, UUID, or SDK. Same request ->
identical result. Strictly additive to Sprints 15.1–15.4, whose modules are left
untouched; it knows nothing about any concrete capability (Browser, Email,
Calendar, Python, GitHub, CRM, …).
"""

from typing import Tuple

from app.services.runtime.capability_validation_models import (
    CapabilityValidationRequest,
    CapabilityValidationResult,
)


class CapabilityValidationManager:
    """Validation: (:class:`CapabilityValidationRequest`) -> validation result.

    Stateless — it owns no session, cache, clock, collaborator, or mutable state.
    ``validate`` checks the proposed inputs against the metadata's declared input
    schema (every schema key must be present), copies the inputs out unchanged, and
    reports validity, ordered errors, and deterministic descriptors. It reads the
    request only — it never executes, resolves, discovers, mutates inputs, or
    mutates metadata.
    """

    def validate(
        self, request: CapabilityValidationRequest
    ) -> CapabilityValidationResult:
        """Return a deterministic :class:`CapabilityValidationResult` (read-only).

        An empty input schema always validates. Otherwise every key declared in
        the metadata's ``input_schema`` must be present in ``capability_inputs``;
        each missing key yields one error, in schema-key order. ``validated_inputs``
        is always a fresh copy of the request's inputs (the request is only read,
        never mutated), and ``validation_metadata`` carries deterministic
        descriptors — including the declared required-permission count.
        """
        metadata = request.capability_metadata
        inputs = request.capability_inputs
        schema = metadata.input_schema

        errors: Tuple[str, ...] = tuple(
            f"Missing required input: {key}"
            for key in schema
            if key not in inputs
        )

        return CapabilityValidationResult(
            is_valid=not errors,
            validation_errors=errors,
            validated_inputs=dict(inputs),
            validation_metadata={
                "capability_id": metadata.capability_id,
                "schema_key_count": len(schema),
                "missing_key_count": len(errors),
                "required_permission_count": len(metadata.required_permissions),
            },
        )
