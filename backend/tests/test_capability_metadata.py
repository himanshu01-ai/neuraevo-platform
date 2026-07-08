"""Unit tests for the Sprint 15.3 Capability Metadata manager (metadata only).

Covers deterministic capability-metadata projection end to end without touching
any network, SDK, AI, dispatcher, concrete capability, or database:

* the immutable :class:`CapabilityMetadata` / :class:`CapabilityMetadataSnapshot`
  DTOs (defaults, required fields, frozen immutability, tuple descriptors,
  provider independence);
* the :class:`CapabilityMetadataManager` itself — empty registry, metadata
  generation (structured-descriptor extraction with empty defaults), insertion
  ordering, one-metadata-per-definition, snapshot immutability and copy-out,
  registry non-mutation, deterministic output, provider independence, and
  stateless behaviour;
* the composition-root wiring (``get_capability_metadata_manager`` reusing
  ``CapabilityRegistryDep``, ``CapabilityMetadataManagerDep``); and
* regression that the Sprint 15.1 registry, Sprint 15.2 resolver, and Sprint
  11.2 / 14.3 seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_capability_metadata
"""

import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.capability_metadata import CapabilityMetadataManager
from app.services.runtime.capability_metadata_models import (
    CapabilityMetadata,
    CapabilityMetadataSnapshot,
)
from app.services.runtime.capability_registry import CapabilityRegistry
from app.services.runtime.capability_registry_models import CapabilityDefinition


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


def _rich_definition(**overrides) -> CapabilityDefinition:
    return _definition(
        capability_metadata={
            "supported_actions": ["send", "read"],
            "required_permissions": ["email:send"],
            "input_schema": {"to": "string"},
            "output_schema": {"message_id": "string"},
            "extra": "kept",
        },
        **overrides,
    )


def _registry(definitions=None) -> CapabilityRegistry:
    return CapabilityRegistry(definitions or [])


def _metadata(**overrides) -> CapabilityMetadata:
    data = dict(
        capability_id="cap-x",
        capability_name="X",
        capability_description="d",
        capability_version="v",
        capability_category="c",
    )
    data.update(overrides)
    return CapabilityMetadata(**data)


# =====================================================================
# CapabilityMetadata DTO
# =====================================================================
class CapabilityMetadataModelTests(unittest.TestCase):
    def test_structured_descriptors_default_to_empty(self):
        meta = _metadata()
        self.assertEqual(meta.supported_actions, ())
        self.assertEqual(meta.required_permissions, ())
        self.assertEqual(meta.input_schema, {})
        self.assertEqual(meta.output_schema, {})
        self.assertEqual(meta.metadata, {})

    def test_actions_and_permissions_are_immutable_tuples(self):
        meta = _metadata(supported_actions=["a", "b"], required_permissions=["p"])
        self.assertEqual(meta.supported_actions, ("a", "b"))
        self.assertEqual(meta.required_permissions, ("p",))
        self.assertIsInstance(meta.supported_actions, tuple)
        self.assertIsInstance(meta.required_permissions, tuple)

    def test_required_identity_fields(self):
        for missing in (
            "capability_id",
            "capability_name",
            "capability_description",
            "capability_version",
            "capability_category",
        ):
            data = dict(
                capability_id="c",
                capability_name="n",
                capability_description="d",
                capability_version="v",
                capability_category="cat",
            )
            data.pop(missing)
            with self.assertRaises(ValidationError):
                CapabilityMetadata(**data)

    def test_metadata_is_immutable(self):
        meta = _metadata(supported_actions=["a"])
        with self.assertRaises(ValidationError):
            meta.capability_id = "changed"
        with self.assertRaises(ValidationError):
            meta.supported_actions = ()
        with self.assertRaises(ValidationError):
            meta.metadata = {"x": 1}

    def test_is_plain_pydantic_dto(self):
        meta = _metadata()
        self.assertIsInstance(meta, BaseModel)
        for attr in ("execute", "resolve", "instantiate"):
            self.assertFalse(hasattr(meta, attr))


# =====================================================================
# CapabilityMetadataSnapshot DTO
# =====================================================================
class CapabilityMetadataSnapshotModelTests(unittest.TestCase):
    def test_defaults_describe_empty_snapshot(self):
        snap = CapabilityMetadataSnapshot()
        self.assertEqual(snap.capabilities, [])
        self.assertEqual(snap.capability_count, 0)
        self.assertEqual(snap.metadata, {})

    def test_snapshot_is_immutable(self):
        snap = CapabilityMetadataSnapshot(
            capabilities=[_metadata()], capability_count=1, metadata={"k": 1}
        )
        with self.assertRaises(ValidationError):
            snap.capability_count = 0
        with self.assertRaises(ValidationError):
            snap.capabilities = []
        with self.assertRaises(ValidationError):
            snap.metadata = {}


# =====================================================================
# CapabilityMetadataManager — behaviour
# =====================================================================
class CapabilityMetadataManagerTests(unittest.TestCase):
    # --- empty registry --------------------------------------------------
    def test_empty_registry_yields_empty_snapshot(self):
        snap = CapabilityMetadataManager(_registry()).snapshot()
        self.assertEqual(snap.capabilities, [])
        self.assertEqual(snap.capability_count, 0)
        self.assertEqual(
            snap.metadata,
            {"capability_count": 0, "metadata_ordering": "insertion"},
        )

    # --- metadata generation --------------------------------------------
    def test_copies_identity_fields_from_definition(self):
        defn = _definition(
            capability_id="cap-cal",
            capability_name="Calendar",
            capability_description="Schedule events.",
            capability_version="2.3",
            capability_category="scheduling",
        )
        meta = CapabilityMetadataManager(_registry([defn])).snapshot().capabilities[0]
        self.assertEqual(meta.capability_id, "cap-cal")
        self.assertEqual(meta.capability_name, "Calendar")
        self.assertEqual(meta.capability_description, "Schedule events.")
        self.assertEqual(meta.capability_version, "2.3")
        self.assertEqual(meta.capability_category, "scheduling")

    def test_extracts_structured_descriptors_from_definition_metadata(self):
        meta = (
            CapabilityMetadataManager(_registry([_rich_definition()]))
            .snapshot()
            .capabilities[0]
        )
        self.assertEqual(meta.supported_actions, ("send", "read"))
        self.assertEqual(meta.required_permissions, ("email:send",))
        self.assertEqual(meta.input_schema, {"to": "string"})
        self.assertEqual(meta.output_schema, {"message_id": "string"})
        # The definition's own metadata is carried through unchanged.
        self.assertEqual(meta.metadata.get("extra"), "kept")

    def test_missing_descriptors_fall_back_to_empty_defaults(self):
        meta = (
            CapabilityMetadataManager(_registry([_definition()]))
            .snapshot()
            .capabilities[0]
        )
        self.assertEqual(meta.supported_actions, ())
        self.assertEqual(meta.required_permissions, ())
        self.assertEqual(meta.input_schema, {})
        self.assertEqual(meta.output_schema, {})

    def test_one_metadata_per_definition(self):
        defs = [_definition(capability_id=str(i)) for i in range(4)]
        snap = CapabilityMetadataManager(_registry(defs)).snapshot()
        self.assertEqual(snap.capability_count, 4)
        self.assertEqual(len(snap.capabilities), 4)
        self.assertEqual(
            sorted(m.capability_id for m in snap.capabilities),
            ["0", "1", "2", "3"],
        )

    # --- insertion ordering ---------------------------------------------
    def test_metadata_follows_registry_insertion_order(self):
        ids = ["zeta", "alpha", "mike", "bravo"]
        registry = _registry()
        for cid in ids:
            registry.register(_definition(capability_id=cid))
        snap = CapabilityMetadataManager(registry).snapshot()
        self.assertEqual([m.capability_id for m in snap.capabilities], ids)

    # --- snapshot immutability / copy-out -------------------------------
    def test_snapshot_is_frozen(self):
        manager = CapabilityMetadataManager(_registry([_definition()]))
        with self.assertRaises(ValidationError):
            manager.snapshot().capability_count = 0

    def test_snapshot_list_is_a_detached_copy(self):
        registry = _registry([_definition(capability_id="a")])
        manager = CapabilityMetadataManager(registry)
        snap = manager.snapshot()
        snap.capabilities.append(_metadata(capability_id="injected"))
        self.assertEqual(manager.snapshot().capability_count, 1)
        self.assertFalse(registry.has_capability("injected"))
        self.assertEqual(registry.snapshot().capability_count, 1)

    def test_each_snapshot_returns_a_new_list_object(self):
        manager = CapabilityMetadataManager(_registry([_definition()]))
        self.assertIsNot(
            manager.snapshot().capabilities, manager.snapshot().capabilities
        )

    # --- registry non-mutation ------------------------------------------
    def test_snapshot_does_not_mutate_registry(self):
        registry = _registry(
            [_definition(capability_id="a"), _rich_definition(capability_id="b")]
        )
        before = registry.snapshot()
        manager = CapabilityMetadataManager(registry)
        manager.snapshot()
        manager.snapshot()
        self.assertEqual(registry.snapshot(), before)
        self.assertEqual(registry.snapshot().capability_count, 2)

    # --- deterministic output -------------------------------------------
    def test_repeated_snapshots_are_equal(self):
        manager = CapabilityMetadataManager(
            _registry([_rich_definition(capability_id="a")])
        )
        self.assertEqual(manager.snapshot(), manager.snapshot())

    def test_independent_managers_over_equal_registries_agree(self):
        defs = [_rich_definition(capability_id="a"), _definition(capability_id="b")]
        self.assertEqual(
            CapabilityMetadataManager(_registry(defs)).snapshot(),
            CapabilityMetadataManager(_registry(defs)).snapshot(),
        )

    # --- provider independence ------------------------------------------
    def test_snapshot_exposes_only_plain_metadata_dtos(self):
        manager = CapabilityMetadataManager(
            _registry([_definition(), _definition(capability_id="b")])
        )
        for entry in manager.snapshot().capabilities:
            self.assertIsInstance(entry, CapabilityMetadata)
            self.assertIsInstance(entry, BaseModel)

    # --- stateless behaviour --------------------------------------------
    def test_manager_holds_only_the_registry(self):
        manager = CapabilityMetadataManager(_registry())
        self.assertEqual(set(vars(manager)), {"registry"})

    def test_manager_exposes_no_execution_surface(self):
        for attr in ("execute", "instantiate", "dispatch", "run", "register"):
            self.assertFalse(hasattr(CapabilityMetadataManager, attr))

    def test_managers_are_isolated(self):
        m_full = CapabilityMetadataManager(_registry([_definition(capability_id="a")]))
        m_empty = CapabilityMetadataManager(_registry())
        self.assertEqual(m_full.snapshot().capability_count, 1)
        self.assertEqual(m_empty.snapshot().capability_count, 0)


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class CapabilityMetadataManagerDependencyInjectionTests(unittest.TestCase):
    def test_get_manager_binds_the_registry(self):
        from app.core.dependencies import (
            get_capability_metadata_manager,
            get_capability_registry,
        )

        registry = get_capability_registry()
        manager = get_capability_metadata_manager(registry)
        self.assertIsInstance(manager, CapabilityMetadataManager)
        self.assertIs(manager.registry, registry)

    def test_default_wired_manager_is_empty(self):
        from app.core.dependencies import (
            get_capability_metadata_manager,
            get_capability_registry,
        )

        manager = get_capability_metadata_manager(get_capability_registry())
        self.assertEqual(manager.snapshot().capability_count, 0)

    def test_wired_manager_over_populated_registry(self):
        from app.core.dependencies import get_capability_metadata_manager

        registry = CapabilityRegistry([_rich_definition(capability_id="a")])
        snap = get_capability_metadata_manager(registry).snapshot()
        self.assertEqual(snap.capability_count, 1)
        self.assertEqual(snap.capabilities[0].supported_actions, ("send", "read"))

    def test_manager_dep_is_wired(self):
        from app.core.dependencies import CapabilityMetadataManagerDep

        self.assertIn(
            CapabilityMetadataManager,
            getattr(CapabilityMetadataManagerDep, "__args__", ()),
        )


# =====================================================================
# Regression — Sprint 15.1/15.2 and prior seams unchanged
# =====================================================================
class CapabilityMetadataRegressionTests(unittest.TestCase):
    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        registry = get_capability_registry()
        self.assertEqual(registry.snapshot().capability_count, 0)
        CapabilityMetadataManager(registry).snapshot()
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
        result = resolver.resolve(CapabilityResolutionRequest(capability_id="x"))
        self.assertFalse(result.capability_found)

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_11_tool_registry_seam_unchanged(self):
        from app.core.dependencies import get_tool_registry

        self.assertEqual(get_tool_registry().list_tools(), [])

    def test_metadata_models_are_distinct_from_definition(self):
        self.assertIsNot(CapabilityMetadata, CapabilityDefinition)


if __name__ == "__main__":
    unittest.main()
