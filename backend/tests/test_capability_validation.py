"""Unit tests for the Sprint 15.5 Capability Validation manager (validation only).

Covers deterministic pre-execution input validation end to end without touching
any network, SDK, AI, dispatcher, concrete capability, or database:

* the immutable :class:`CapabilityValidationRequest` / :class:`CapabilityValidation
  Result` DTOs (defaults, required fields, frozen immutability, tuple errors);
* the :class:`CapabilityValidationManager` itself — empty schema, successful
  validation, single and multiple missing required fields, validated-input copy,
  request non-mutation, deterministic output, provider independence, and stateless
  behaviour;
* the composition-root wiring (``get_capability_validation_manager``,
  ``CapabilityValidationManagerDep``); and
* regression that the Sprint 15.1–15.4 seams and the Sprint 11.2 / 14.3 seams are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_capability_validation
"""

import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.capability_metadata_models import CapabilityMetadata
from app.services.runtime.capability_validation import CapabilityValidationManager
from app.services.runtime.capability_validation_models import (
    CapabilityValidationRequest,
    CapabilityValidationResult,
)


# =====================================================================
# Helpers / in-test doubles (plain data only — never a real capability)
# =====================================================================
def _metadata(input_schema=None, required_permissions=(), **overrides) -> CapabilityMetadata:
    data = dict(
        capability_id="cap-email",
        capability_name="Email",
        capability_description="Send and read email.",
        capability_version="1.0.0",
        capability_category="communication",
        supported_actions=(),
        required_permissions=tuple(required_permissions),
        input_schema=input_schema or {},
        output_schema={},
        metadata={},
    )
    data.update(overrides)
    return CapabilityMetadata(**data)


def _request(input_schema=None, inputs=None, required_permissions=()) -> CapabilityValidationRequest:
    return CapabilityValidationRequest(
        capability_metadata=_metadata(
            input_schema=input_schema, required_permissions=required_permissions
        ),
        capability_inputs=inputs if inputs is not None else {},
    )


def _validate(**kwargs) -> CapabilityValidationResult:
    return CapabilityValidationManager().validate(_request(**kwargs))


# =====================================================================
# CapabilityValidationRequest / Result DTOs
# =====================================================================
class ValidationDtoTests(unittest.TestCase):
    def test_request_defaults(self):
        req = CapabilityValidationRequest(capability_metadata=_metadata())
        self.assertEqual(req.capability_inputs, {})
        self.assertEqual(req.validation_metadata, {})

    def test_request_requires_metadata(self):
        with self.assertRaises(ValidationError):
            CapabilityValidationRequest()

    def test_request_is_immutable(self):
        req = _request(inputs={"a": 1})
        with self.assertRaises(ValidationError):
            req.capability_inputs = {"b": 2}
        with self.assertRaises(ValidationError):
            req.validation_metadata = {"x": 1}

    def test_result_defaults(self):
        res = CapabilityValidationResult(is_valid=True)
        self.assertEqual(res.validation_errors, ())
        self.assertEqual(res.validated_inputs, {})
        self.assertEqual(res.validation_metadata, {})

    def test_result_requires_is_valid(self):
        with self.assertRaises(ValidationError):
            CapabilityValidationResult()

    def test_result_is_immutable(self):
        res = CapabilityValidationResult(is_valid=False, validation_errors=("e",))
        with self.assertRaises(ValidationError):
            res.is_valid = True
        with self.assertRaises(ValidationError):
            res.validation_errors = ()
        with self.assertRaises(ValidationError):
            res.validated_inputs = {"a": 1}

    def test_validation_errors_is_tuple(self):
        res = _validate(input_schema={"to": "string"}, inputs={})
        self.assertIsInstance(res.validation_errors, tuple)


# =====================================================================
# CapabilityValidationManager — behaviour
# =====================================================================
class CapabilityValidationManagerTests(unittest.TestCase):
    # --- empty schema ----------------------------------------------------
    def test_empty_schema_is_always_valid(self):
        res = _validate(input_schema={}, inputs={})
        self.assertTrue(res.is_valid)
        self.assertEqual(res.validation_errors, ())

    def test_empty_schema_valid_even_with_inputs(self):
        res = _validate(input_schema={}, inputs={"anything": 1})
        self.assertTrue(res.is_valid)
        self.assertEqual(res.validation_errors, ())

    # --- successful validation ------------------------------------------
    def test_all_required_keys_present_is_valid(self):
        res = _validate(
            input_schema={"to": "string", "subject": "string"},
            inputs={"to": "a@b.com", "subject": "hi"},
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(res.validation_errors, ())

    def test_extra_inputs_do_not_invalidate(self):
        res = _validate(
            input_schema={"to": "string"},
            inputs={"to": "a@b.com", "extra": 1},
        )
        self.assertTrue(res.is_valid)

    # --- missing required fields ----------------------------------------
    def test_single_missing_field(self):
        res = _validate(
            input_schema={"to": "string", "subject": "string"},
            inputs={"to": "a@b.com"},
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.validation_errors, ("Missing required input: subject",))

    def test_multiple_missing_fields_in_schema_order(self):
        res = _validate(
            input_schema={"to": "string", "subject": "string", "body": "string"},
            inputs={},
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(
            res.validation_errors,
            (
                "Missing required input: to",
                "Missing required input: subject",
                "Missing required input: body",
            ),
        )

    def test_missing_key_count_in_metadata(self):
        res = _validate(
            input_schema={"a": "x", "b": "y", "c": "z"}, inputs={"a": 1}
        )
        self.assertEqual(res.validation_metadata["missing_key_count"], 2)
        self.assertEqual(res.validation_metadata["schema_key_count"], 3)

    def test_required_permissions_surfaced_in_metadata(self):
        res = _validate(
            input_schema={}, inputs={}, required_permissions=("email:send", "email:read")
        )
        self.assertEqual(res.validation_metadata["required_permission_count"], 2)

    # --- validated input copy -------------------------------------------
    def test_validated_inputs_is_a_copy_of_inputs(self):
        inputs = {"to": "a@b.com", "subject": "hi"}
        req = CapabilityValidationRequest(
            capability_metadata=_metadata(input_schema={"to": "string"}),
            capability_inputs=inputs,
        )
        res = CapabilityValidationManager().validate(req)
        self.assertEqual(res.validated_inputs, inputs)
        self.assertIsNot(res.validated_inputs, req.capability_inputs)

    def test_validated_inputs_present_even_when_invalid(self):
        res = _validate(input_schema={"to": "string"}, inputs={"other": 1})
        self.assertFalse(res.is_valid)
        self.assertEqual(res.validated_inputs, {"other": 1})

    def test_mutating_validated_inputs_does_not_touch_request(self):
        req = CapabilityValidationRequest(
            capability_metadata=_metadata(input_schema={"to": "string"}),
            capability_inputs={"to": "a@b.com"},
        )
        res = CapabilityValidationManager().validate(req)
        res.validated_inputs["injected"] = True
        self.assertEqual(req.capability_inputs, {"to": "a@b.com"})

    # --- request non-mutation -------------------------------------------
    def test_validation_does_not_mutate_request(self):
        req = CapabilityValidationRequest(
            capability_metadata=_metadata(
                input_schema={"to": "string"}, required_permissions=("email:send",)
            ),
            capability_inputs={"to": "a@b.com"},
        )
        CapabilityValidationManager().validate(req)
        self.assertEqual(req.capability_inputs, {"to": "a@b.com"})
        self.assertEqual(req.capability_metadata.input_schema, {"to": "string"})
        self.assertEqual(req.capability_metadata.required_permissions, ("email:send",))

    # --- deterministic output -------------------------------------------
    def test_repeated_validation_is_equal(self):
        manager = CapabilityValidationManager()
        req = _request(input_schema={"to": "string"}, inputs={})
        self.assertEqual(manager.validate(req), manager.validate(req))

    def test_independent_managers_agree(self):
        req = _request(input_schema={"to": "string", "b": "y"}, inputs={"to": 1})
        self.assertEqual(
            CapabilityValidationManager().validate(req),
            CapabilityValidationManager().validate(req),
        )

    # --- provider independence ------------------------------------------
    def test_result_is_plain_dtos_only(self):
        res = _validate(input_schema={"to": "string"}, inputs={"to": 1})
        self.assertIsInstance(res, BaseModel)
        self.assertIsInstance(res.validated_inputs, dict)
        self.assertNotIsInstance(res.validated_inputs, BaseModel)

    # --- stateless behaviour --------------------------------------------
    def test_manager_holds_no_state(self):
        self.assertEqual(vars(CapabilityValidationManager()), {})

    def test_manager_exposes_no_execution_surface(self):
        for attr in ("execute", "resolve", "discover", "instantiate", "run"):
            self.assertFalse(hasattr(CapabilityValidationManager, attr))

    def test_managers_are_independent(self):
        req_ok = _request(input_schema={}, inputs={})
        req_bad = _request(input_schema={"x": "y"}, inputs={})
        self.assertTrue(CapabilityValidationManager().validate(req_ok).is_valid)
        self.assertFalse(CapabilityValidationManager().validate(req_bad).is_valid)


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class CapabilityValidationManagerDependencyInjectionTests(unittest.TestCase):
    def test_get_manager_returns_validation_manager(self):
        from app.core.dependencies import get_capability_validation_manager

        manager = get_capability_validation_manager()
        self.assertIsInstance(manager, CapabilityValidationManager)

    def test_wired_manager_validates(self):
        from app.core.dependencies import get_capability_validation_manager

        manager = get_capability_validation_manager()
        res = manager.validate(_request(input_schema={"to": "string"}, inputs={}))
        self.assertFalse(res.is_valid)

    def test_validation_manager_dep_is_wired(self):
        from app.core.dependencies import CapabilityValidationManagerDep

        self.assertIn(
            CapabilityValidationManager,
            getattr(CapabilityValidationManagerDep, "__args__", ()),
        )


# =====================================================================
# Regression — Sprint 15.1–15.4 and prior seams unchanged
# =====================================================================
class CapabilityValidationRegressionTests(unittest.TestCase):
    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)

    def test_sprint_15_2_resolver_seam_unchanged(self):
        from app.core.dependencies import (
            get_capability_registry,
            get_capability_resolver,
        )
        from app.services.runtime.capability_resolver_models import (
            CapabilityResolutionRequest,
        )

        resolver = get_capability_resolver(get_capability_registry())
        self.assertFalse(
            resolver.resolve(
                CapabilityResolutionRequest(capability_id="x")
            ).capability_found
        )

    def test_sprint_15_3_metadata_seam_unchanged(self):
        from app.core.dependencies import (
            get_capability_metadata_manager,
            get_capability_registry,
        )

        manager = get_capability_metadata_manager(get_capability_registry())
        self.assertEqual(manager.snapshot().capability_count, 0)

    def test_sprint_15_4_discovery_seam_unchanged(self):
        from app.core.dependencies import (
            get_capability_discovery_manager,
            get_capability_metadata_manager,
            get_capability_registry,
        )
        from app.services.runtime.capability_discovery_models import (
            CapabilityDiscoveryRequest,
        )

        discovery = get_capability_discovery_manager(
            get_capability_metadata_manager(get_capability_registry())
        )
        self.assertEqual(
            discovery.discover(CapabilityDiscoveryRequest()).capability_count, 0
        )

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_11_tool_registry_seam_unchanged(self):
        from app.core.dependencies import get_tool_registry

        self.assertEqual(get_tool_registry().list_tools(), [])


if __name__ == "__main__":
    unittest.main()
