"""Unit tests for the Sprint 15.4 Capability Discovery manager (discovery only).

Covers deterministic capability discovery end to end without touching any network,
SDK, AI, dispatcher, concrete capability, or database:

* the immutable :class:`CapabilityDiscoveryRequest` / :class:`CapabilityDiscovery
  Result` DTOs (optional search fields, defaults, frozen immutability);
* the :class:`CapabilityDiscoveryManager` itself — empty snapshot, discover-all,
  category / supported-action / permission filtering, multi-filter intersection,
  insertion ordering, snapshot non-mutation, fresh immutable collections,
  deterministic output, provider independence, and stateless behaviour;
* the composition-root wiring (``get_capability_discovery_manager`` reusing
  ``CapabilityMetadataManagerDep``, ``CapabilityDiscoveryManagerDep``); and
* regression that the Sprint 15.1–15.3 seams and the Sprint 11.2 / 14.3 seams are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_capability_discovery
"""

import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.capability_discovery import CapabilityDiscoveryManager
from app.services.runtime.capability_discovery_models import (
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResult,
)
from app.services.runtime.capability_metadata import CapabilityMetadataManager
from app.services.runtime.capability_metadata_models import CapabilityMetadata
from app.services.runtime.capability_registry import CapabilityRegistry
from app.services.runtime.capability_registry_models import CapabilityDefinition


# =====================================================================
# Helpers / in-test doubles (plain data only — never a real capability)
# =====================================================================
def _definition(
    cid, category="communication", actions=(), permissions=()
) -> CapabilityDefinition:
    meta = {}
    if actions:
        meta["supported_actions"] = list(actions)
    if permissions:
        meta["required_permissions"] = list(permissions)
    return CapabilityDefinition(
        capability_id=cid,
        capability_name=cid.title(),
        capability_description=f"{cid} capability",
        capability_version="1.0.0",
        capability_category=category,
        capability_metadata=meta,
    )


# Fixture capabilities, in a deliberate (non-sorted) insertion order.
def _fixture_definitions():
    return [
        _definition(
            "email",
            category="communication",
            actions=["send", "read"],
            permissions=["email:send"],
        ),
        _definition(
            "calendar",
            category="scheduling",
            actions=["create", "list"],
            permissions=["cal:write"],
        ),
        _definition(
            "browser",
            category="web",
            actions=["open", "click"],
            permissions=["net:access"],
        ),
        _definition(
            "crm",
            category="communication",
            actions=["send"],
            permissions=["crm:write"],
        ),
    ]


def _manager(definitions=None) -> CapabilityDiscoveryManager:
    registry = CapabilityRegistry(definitions or [])
    return CapabilityDiscoveryManager(CapabilityMetadataManager(registry))


def _fixture_manager() -> CapabilityDiscoveryManager:
    return _manager(_fixture_definitions())


def _request(**overrides) -> CapabilityDiscoveryRequest:
    return CapabilityDiscoveryRequest(**overrides)


def _ids(result: CapabilityDiscoveryResult):
    return [m.capability_id for m in result.discovered_capabilities]


# =====================================================================
# CapabilityDiscoveryRequest DTO
# =====================================================================
class DiscoveryRequestModelTests(unittest.TestCase):
    def test_all_search_fields_optional_default_none(self):
        req = CapabilityDiscoveryRequest()
        self.assertIsNone(req.capability_category)
        self.assertIsNone(req.supported_action)
        self.assertIsNone(req.required_permission)
        self.assertEqual(req.discovery_metadata, {})

    def test_holds_supplied_data(self):
        req = _request(
            capability_category="web",
            supported_action="open",
            required_permission="net:access",
            discovery_metadata={"k": "v"},
        )
        self.assertEqual(req.capability_category, "web")
        self.assertEqual(req.supported_action, "open")
        self.assertEqual(req.required_permission, "net:access")
        self.assertEqual(req.discovery_metadata, {"k": "v"})

    def test_request_is_immutable(self):
        req = _request(capability_category="web")
        with self.assertRaises(ValidationError):
            req.capability_category = "communication"
        with self.assertRaises(ValidationError):
            req.discovery_metadata = {"x": 1}


# =====================================================================
# CapabilityDiscoveryResult DTO
# =====================================================================
class DiscoveryResultModelTests(unittest.TestCase):
    def test_defaults(self):
        res = CapabilityDiscoveryResult()
        self.assertEqual(res.discovered_capabilities, [])
        self.assertEqual(res.capability_count, 0)
        self.assertEqual(res.discovery_metadata, {})

    def test_result_is_immutable(self):
        res = CapabilityDiscoveryResult(capability_count=0)
        with self.assertRaises(ValidationError):
            res.capability_count = 5
        with self.assertRaises(ValidationError):
            res.discovered_capabilities = []
        with self.assertRaises(ValidationError):
            res.discovery_metadata = {}


# =====================================================================
# CapabilityDiscoveryManager — behaviour
# =====================================================================
class CapabilityDiscoveryManagerTests(unittest.TestCase):
    # --- empty metadata snapshot ----------------------------------------
    def test_empty_snapshot_discovers_nothing(self):
        result = _manager().discover(_request())
        self.assertEqual(result.discovered_capabilities, [])
        self.assertEqual(result.capability_count, 0)
        self.assertEqual(
            result.discovery_metadata,
            {
                "capability_count": 0,
                "total_capabilities": 0,
                "discovery_ordering": "insertion",
            },
        )

    # --- discover all ---------------------------------------------------
    def test_empty_request_discovers_all(self):
        result = _fixture_manager().discover(_request())
        self.assertEqual(_ids(result), ["email", "calendar", "browser", "crm"])
        self.assertEqual(result.capability_count, 4)

    # --- category filtering ---------------------------------------------
    def test_category_exact_match(self):
        result = _fixture_manager().discover(_request(capability_category="communication"))
        self.assertEqual(_ids(result), ["email", "crm"])

    def test_category_no_match_is_empty(self):
        result = _fixture_manager().discover(_request(capability_category="nope"))
        self.assertEqual(_ids(result), [])
        self.assertEqual(result.capability_count, 0)

    def test_category_is_exact_not_substring(self):
        result = _fixture_manager().discover(_request(capability_category="comm"))
        self.assertEqual(_ids(result), [])

    # --- supported action filtering -------------------------------------
    def test_supported_action_filter(self):
        result = _fixture_manager().discover(_request(supported_action="send"))
        self.assertEqual(_ids(result), ["email", "crm"])

    def test_supported_action_single_match(self):
        result = _fixture_manager().discover(_request(supported_action="open"))
        self.assertEqual(_ids(result), ["browser"])

    # --- permission filtering -------------------------------------------
    def test_required_permission_filter(self):
        result = _fixture_manager().discover(_request(required_permission="email:send"))
        self.assertEqual(_ids(result), ["email"])

    def test_required_permission_no_match(self):
        result = _fixture_manager().discover(_request(required_permission="absent"))
        self.assertEqual(_ids(result), [])

    # --- multiple-filter intersection -----------------------------------
    def test_multiple_filters_must_all_match(self):
        result = _fixture_manager().discover(
            _request(capability_category="communication", supported_action="send")
        )
        self.assertEqual(_ids(result), ["email", "crm"])

    def test_multiple_filters_intersection_empties_when_conflicting(self):
        result = _fixture_manager().discover(
            _request(capability_category="web", supported_action="send")
        )
        self.assertEqual(_ids(result), [])

    def test_all_three_filters_together(self):
        result = _fixture_manager().discover(
            _request(
                capability_category="communication",
                supported_action="send",
                required_permission="email:send",
            )
        )
        self.assertEqual(_ids(result), ["email"])

    # --- insertion ordering ---------------------------------------------
    def test_output_preserves_metadata_insertion_order(self):
        # crm registered last but shares the category; order must stay email->crm.
        result = _fixture_manager().discover(_request(capability_category="communication"))
        self.assertEqual(_ids(result), ["email", "crm"])

    # --- snapshot non-mutation ------------------------------------------
    def test_discovery_does_not_mutate_metadata_or_registry(self):
        registry = CapabilityRegistry(_fixture_definitions())
        metadata_manager = CapabilityMetadataManager(registry)
        before = metadata_manager.snapshot()
        manager = CapabilityDiscoveryManager(metadata_manager)
        manager.discover(_request(capability_category="communication"))
        manager.discover(_request())
        self.assertEqual(metadata_manager.snapshot(), before)
        self.assertEqual(registry.snapshot().capability_count, 4)

    # --- fresh immutable collections ------------------------------------
    def test_each_discovery_returns_a_fresh_list(self):
        manager = _fixture_manager()
        r1 = manager.discover(_request())
        r2 = manager.discover(_request())
        self.assertIsNot(r1.discovered_capabilities, r2.discovered_capabilities)

    def test_mutating_result_list_does_not_affect_manager(self):
        manager = _fixture_manager()
        result = manager.discover(_request(capability_category="communication"))
        result.discovered_capabilities.clear()
        self.assertEqual(
            _ids(manager.discover(_request(capability_category="communication"))),
            ["email", "crm"],
        )

    # --- deterministic output -------------------------------------------
    def test_repeated_discovery_is_equal(self):
        manager = _fixture_manager()
        self.assertEqual(
            manager.discover(_request(supported_action="send")),
            manager.discover(_request(supported_action="send")),
        )

    def test_independent_managers_over_equal_definitions_agree(self):
        defs = _fixture_definitions()
        self.assertEqual(
            _manager(defs).discover(_request(capability_category="web")),
            _manager(defs).discover(_request(capability_category="web")),
        )

    # --- provider independence ------------------------------------------
    def test_discovered_items_are_plain_metadata_dtos(self):
        result = _fixture_manager().discover(_request())
        for entry in result.discovered_capabilities:
            self.assertIsInstance(entry, CapabilityMetadata)
            self.assertIsInstance(entry, BaseModel)

    # --- stateless behaviour --------------------------------------------
    def test_manager_holds_only_the_metadata_manager(self):
        self.assertEqual(set(vars(_manager())), {"metadata_manager"})

    def test_manager_exposes_no_execution_surface(self):
        for attr in ("execute", "resolve", "instantiate", "dispatch", "run"):
            self.assertFalse(hasattr(CapabilityDiscoveryManager, attr))

    def test_managers_are_isolated(self):
        full = _fixture_manager()
        empty = _manager()
        self.assertEqual(full.discover(_request()).capability_count, 4)
        self.assertEqual(empty.discover(_request()).capability_count, 0)


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class CapabilityDiscoveryManagerDependencyInjectionTests(unittest.TestCase):
    def test_get_manager_binds_the_metadata_manager(self):
        from app.core.dependencies import (
            get_capability_discovery_manager,
            get_capability_metadata_manager,
            get_capability_registry,
        )

        metadata_manager = get_capability_metadata_manager(get_capability_registry())
        manager = get_capability_discovery_manager(metadata_manager)
        self.assertIsInstance(manager, CapabilityDiscoveryManager)
        self.assertIs(manager.metadata_manager, metadata_manager)

    def test_default_wired_manager_discovers_nothing(self):
        from app.core.dependencies import (
            get_capability_discovery_manager,
            get_capability_metadata_manager,
            get_capability_registry,
        )

        manager = get_capability_discovery_manager(
            get_capability_metadata_manager(get_capability_registry())
        )
        self.assertEqual(manager.discover(_request()).capability_count, 0)

    def test_wired_manager_over_populated_registry(self):
        from app.core.dependencies import get_capability_discovery_manager

        metadata_manager = CapabilityMetadataManager(
            CapabilityRegistry(_fixture_definitions())
        )
        manager = get_capability_discovery_manager(metadata_manager)
        self.assertEqual(
            _ids(manager.discover(_request(capability_category="scheduling"))),
            ["calendar"],
        )

    def test_discovery_manager_dep_is_wired(self):
        from app.core.dependencies import CapabilityDiscoveryManagerDep

        self.assertIn(
            CapabilityDiscoveryManager,
            getattr(CapabilityDiscoveryManagerDep, "__args__", ()),
        )


# =====================================================================
# Regression — Sprint 15.1–15.3 and prior seams unchanged
# =====================================================================
class CapabilityDiscoveryRegressionTests(unittest.TestCase):
    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        registry = get_capability_registry()
        self.assertEqual(registry.snapshot().capability_count, 0)

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

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_11_tool_registry_seam_unchanged(self):
        from app.core.dependencies import get_tool_registry

        self.assertEqual(get_tool_registry().list_tools(), [])


if __name__ == "__main__":
    unittest.main()
