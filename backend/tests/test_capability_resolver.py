"""Unit tests for the Sprint 15.2 Capability Resolver (resolution only).

Covers deterministic capability resolution end to end without touching any
network, SDK, AI, dispatcher, concrete capability, or database:

* the immutable :class:`CapabilityResolutionRequest` / :class:`CapabilityResolution
  Result` DTOs and the :class:`ResolutionStatus` enum (defaults, required fields,
  frozen immutability, provider independence);
* the :class:`CapabilityResolver` itself — successful resolution (returning the
  exact registered definition), missing capability, empty registry, duplicate
  registry behaviour, deterministic results, registry non-mutation, provider
  independence, and stateless behaviour;
* the composition-root wiring (``get_capability_resolver`` reusing
  ``CapabilityRegistryDep``, ``CapabilityResolverDep``); and
* regression that the Sprint 15.1 registry and the Sprint 11.2 / 14.3 seams are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_capability_resolver
"""

import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.capability_registry import CapabilityRegistry
from app.services.runtime.capability_registry_models import CapabilityDefinition
from app.services.runtime.capability_resolver import CapabilityResolver
from app.services.runtime.capability_resolver_models import (
    CapabilityResolutionRequest,
    CapabilityResolutionResult,
    ResolutionStatus,
)


# =====================================================================
# Helpers / in-test doubles (plain data only — never a real capability)
# =====================================================================
def _definition(**overrides) -> CapabilityDefinition:
    data = dict(
        capability_id="cap-email",
        capability_name="Email",
        capability_description="Send and read email.",
        capability_version="1.0.0",
        capability_category="communication",
        capability_metadata={},
    )
    data.update(overrides)
    return CapabilityDefinition(**data)


def _registry(definitions=None) -> CapabilityRegistry:
    return CapabilityRegistry(definitions or [])


def _request(capability_id: str, **overrides) -> CapabilityResolutionRequest:
    data = dict(capability_id=capability_id, resolution_metadata={})
    data.update(overrides)
    return CapabilityResolutionRequest(**data)


# =====================================================================
# ResolutionStatus enum
# =====================================================================
class ResolutionStatusEnumTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ResolutionStatus.FOUND.value, "FOUND")
        self.assertEqual(ResolutionStatus.NOT_FOUND.value, "NOT_FOUND")

    def test_is_str_enum(self):
        self.assertIsInstance(ResolutionStatus.FOUND, str)


# =====================================================================
# CapabilityResolutionRequest DTO
# =====================================================================
class ResolutionRequestModelTests(unittest.TestCase):
    def test_holds_supplied_data(self):
        req = _request("cap-x", resolution_metadata={"k": "v"})
        self.assertEqual(req.capability_id, "cap-x")
        self.assertEqual(req.resolution_metadata, {"k": "v"})

    def test_metadata_defaults_to_empty_dict(self):
        req = CapabilityResolutionRequest(capability_id="cap-x")
        self.assertEqual(req.resolution_metadata, {})

    def test_capability_id_required(self):
        with self.assertRaises(ValidationError):
            CapabilityResolutionRequest()

    def test_request_is_immutable(self):
        req = _request("cap-x")
        with self.assertRaises(ValidationError):
            req.capability_id = "changed"
        with self.assertRaises(ValidationError):
            req.resolution_metadata = {"mutated": True}


# =====================================================================
# CapabilityResolutionResult DTO
# =====================================================================
class ResolutionResultModelTests(unittest.TestCase):
    def test_defaults(self):
        res = CapabilityResolutionResult(
            capability_found=False, resolution_status="NOT_FOUND"
        )
        self.assertIsNone(res.capability_definition)
        self.assertEqual(res.resolution_metadata, {})

    def test_required_fields(self):
        for missing in ("capability_found", "resolution_status"):
            data = dict(capability_found=True, resolution_status="FOUND")
            data.pop(missing)
            with self.assertRaises(ValidationError):
                CapabilityResolutionResult(**data)

    def test_result_is_immutable(self):
        res = CapabilityResolutionResult(
            capability_found=True,
            capability_definition=_definition(),
            resolution_status="FOUND",
        )
        with self.assertRaises(ValidationError):
            res.capability_found = False
        with self.assertRaises(ValidationError):
            res.capability_definition = None
        with self.assertRaises(ValidationError):
            res.resolution_status = "NOT_FOUND"


# =====================================================================
# CapabilityResolver — behaviour
# =====================================================================
class CapabilityResolverTests(unittest.TestCase):
    # --- successful resolution ------------------------------------------
    def test_found_returns_exact_registered_definition(self):
        defn = _definition(capability_id="cap-a")
        resolver = CapabilityResolver(_registry([defn]))
        result = resolver.resolve(_request("cap-a"))
        self.assertTrue(result.capability_found)
        self.assertEqual(result.resolution_status, "FOUND")
        self.assertEqual(result.resolution_status, ResolutionStatus.FOUND.value)
        # The EXACT registered definition object is returned (identity).
        self.assertIs(result.capability_definition, defn)

    def test_found_result_metadata_is_deterministic(self):
        resolver = CapabilityResolver(_registry([_definition(capability_id="a")]))
        result = resolver.resolve(_request("a"))
        self.assertEqual(
            result.resolution_metadata,
            {"capability_id": "a", "resolution_status": "FOUND"},
        )

    def test_resolves_correct_definition_among_many(self):
        a = _definition(capability_id="a", capability_name="A")
        b = _definition(capability_id="b", capability_name="B")
        c = _definition(capability_id="c", capability_name="C")
        resolver = CapabilityResolver(_registry([a, b, c]))
        self.assertIs(resolver.resolve(_request("b")).capability_definition, b)

    # --- missing capability ---------------------------------------------
    def test_not_found_returns_none_definition(self):
        resolver = CapabilityResolver(_registry([_definition(capability_id="a")]))
        result = resolver.resolve(_request("does-not-exist"))
        self.assertFalse(result.capability_found)
        self.assertIsNone(result.capability_definition)
        self.assertEqual(result.resolution_status, "NOT_FOUND")
        self.assertEqual(
            result.resolution_metadata,
            {"capability_id": "does-not-exist", "resolution_status": "NOT_FOUND"},
        )

    # --- empty registry -------------------------------------------------
    def test_empty_registry_always_not_found(self):
        resolver = CapabilityResolver(_registry())
        result = resolver.resolve(_request("anything"))
        self.assertFalse(result.capability_found)
        self.assertIsNone(result.capability_definition)
        self.assertEqual(result.resolution_status, "NOT_FOUND")

    # --- duplicate registry behaviour -----------------------------------
    def test_resolves_single_definition_after_rejected_duplicate(self):
        first = _definition(capability_id="dup", capability_name="First")
        registry = CapabilityRegistry([first])
        # The registry rejects the duplicate; the resolver then reflects the
        # single, originally-registered definition.
        with self.assertRaises(ValueError):
            registry.register(
                _definition(capability_id="dup", capability_name="Second")
            )
        result = CapabilityResolver(registry).resolve(_request("dup"))
        self.assertTrue(result.capability_found)
        self.assertIs(result.capability_definition, first)
        self.assertEqual(result.capability_definition.capability_name, "First")

    # --- deterministic results ------------------------------------------
    def test_repeated_resolution_is_equal_found(self):
        resolver = CapabilityResolver(_registry([_definition(capability_id="a")]))
        self.assertEqual(
            resolver.resolve(_request("a")), resolver.resolve(_request("a"))
        )

    def test_repeated_resolution_is_equal_not_found(self):
        resolver = CapabilityResolver(_registry([_definition(capability_id="a")]))
        self.assertEqual(
            resolver.resolve(_request("x")), resolver.resolve(_request("x"))
        )

    def test_independent_resolvers_over_equal_registries_agree(self):
        defs = [_definition(capability_id="a")]
        self.assertEqual(
            CapabilityResolver(_registry(defs)).resolve(_request("a")),
            CapabilityResolver(_registry(defs)).resolve(_request("a")),
        )

    # --- registry non-mutation ------------------------------------------
    def test_resolution_does_not_mutate_registry(self):
        registry = _registry([_definition(capability_id="a")])
        before = registry.snapshot()
        resolver = CapabilityResolver(registry)
        resolver.resolve(_request("a"))
        resolver.resolve(_request("missing"))
        self.assertEqual(registry.snapshot(), before)
        self.assertEqual(registry.snapshot().capability_count, 1)

    def test_not_found_does_not_register_the_missing_id(self):
        registry = _registry()
        CapabilityResolver(registry).resolve(_request("ghost"))
        self.assertFalse(registry.has_capability("ghost"))
        self.assertEqual(registry.snapshot().capability_count, 0)

    # --- provider independence ------------------------------------------
    def test_result_is_plain_dtos_only(self):
        resolver = CapabilityResolver(_registry([_definition(capability_id="a")]))
        result = resolver.resolve(_request("a"))
        self.assertIsInstance(result, BaseModel)
        self.assertIsInstance(result.capability_definition, CapabilityDefinition)
        self.assertIsInstance(result.capability_definition, BaseModel)

    # --- stateless behaviour --------------------------------------------
    def test_resolver_holds_only_the_registry(self):
        resolver = CapabilityResolver(_registry())
        self.assertEqual(set(vars(resolver)), {"registry"})

    def test_resolver_exposes_no_execution_surface(self):
        for attr in ("execute", "instantiate", "dispatch", "run", "register"):
            self.assertFalse(hasattr(CapabilityResolver, attr))

    def test_resolvers_are_isolated(self):
        r_full = CapabilityResolver(_registry([_definition(capability_id="a")]))
        r_empty = CapabilityResolver(_registry())
        self.assertTrue(r_full.resolve(_request("a")).capability_found)
        self.assertFalse(r_empty.resolve(_request("a")).capability_found)


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class CapabilityResolverDependencyInjectionTests(unittest.TestCase):
    def test_get_capability_resolver_binds_the_registry(self):
        from app.core.dependencies import (
            get_capability_registry,
            get_capability_resolver,
        )

        registry = get_capability_registry()
        resolver = get_capability_resolver(registry)
        self.assertIsInstance(resolver, CapabilityResolver)
        self.assertIs(resolver.registry, registry)

    def test_default_wired_resolver_resolves_not_found(self):
        from app.core.dependencies import (
            get_capability_registry,
            get_capability_resolver,
        )

        resolver = get_capability_resolver(get_capability_registry())
        self.assertFalse(resolver.resolve(_request("x")).capability_found)

    def test_wired_resolver_over_populated_registry(self):
        from app.core.dependencies import get_capability_resolver

        registry = CapabilityRegistry([_definition(capability_id="a")])
        resolver = get_capability_resolver(registry)
        self.assertTrue(resolver.resolve(_request("a")).capability_found)

    def test_capability_resolver_dep_is_wired(self):
        from app.core.dependencies import CapabilityResolverDep

        self.assertIn(
            CapabilityResolver, getattr(CapabilityResolverDep, "__args__", ())
        )


# =====================================================================
# Regression — Sprint 15.1 and prior seams unchanged
# =====================================================================
class CapabilityResolverRegressionTests(unittest.TestCase):
    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        registry = get_capability_registry()
        self.assertEqual(registry.snapshot().capability_count, 0)
        # Resolving through the resolver never mutates the registry.
        CapabilityResolver(registry).resolve(_request("x"))
        self.assertEqual(registry.snapshot().capability_count, 0)

    def test_sprint_11_tool_registry_seam_unchanged(self):
        from app.core.dependencies import get_tool_registry

        self.assertEqual(get_tool_registry().list_tools(), [])

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_resolution_models_are_distinct_from_registry_models(self):
        self.assertIsNot(CapabilityResolutionResult, CapabilityDefinition)


if __name__ == "__main__":
    unittest.main()
