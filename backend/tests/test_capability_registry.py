"""Unit tests for the Sprint 15.1 Capability Registry (catalogue only).

Covers the central capability catalogue end to end without touching any network,
SDK, AI, dispatcher, concrete capability, or database:

* the immutable :class:`CapabilityDefinition` / :class:`CapabilityRegistrySnapshot`
  DTOs (defaults, required fields, frozen immutability, provider independence);
* the :class:`CapabilityRegistry` itself — empty registry, registration,
  duplicate rejection, lookup by id, insertion ordering, snapshot immutability
  and copy-out semantics, deterministic behaviour, stateless public behaviour,
  and the guarantee that it never executes, resolves, or instantiates a
  capability;
* the composition-root wiring (``get_capability_definitions``,
  ``get_capability_registry``, ``CapabilityRegistryDep``); and
* regression that the Sprint 11.2 tool registry and Sprint 14.3 execution
  capability seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_capability_registry
"""

import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.capability_registry import CapabilityRegistry
from app.services.runtime.capability_registry_models import (
    CapabilityDefinition,
    CapabilityRegistrySnapshot,
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


# =====================================================================
# CapabilityDefinition DTO
# =====================================================================
class CapabilityDefinitionModelTests(unittest.TestCase):
    def test_holds_supplied_plain_data(self):
        defn = _definition(
            capability_id="cap-x",
            capability_name="X",
            capability_description="does x",
            capability_version="2.1",
            capability_category="general",
            capability_metadata={"k": "v"},
        )
        self.assertEqual(defn.capability_id, "cap-x")
        self.assertEqual(defn.capability_name, "X")
        self.assertEqual(defn.capability_description, "does x")
        self.assertEqual(defn.capability_version, "2.1")
        self.assertEqual(defn.capability_category, "general")
        self.assertEqual(defn.capability_metadata, {"k": "v"})

    def test_metadata_defaults_to_empty_dict(self):
        defn = CapabilityDefinition(
            capability_id="c",
            capability_name="n",
            capability_description="d",
            capability_version="v",
            capability_category="cat",
        )
        self.assertEqual(defn.capability_metadata, {})

    def test_required_fields_are_required(self):
        # Every descriptor except metadata is required.
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
                CapabilityDefinition(**data)

    def test_definition_is_immutable(self):
        defn = _definition()
        with self.assertRaises(ValidationError):
            defn.capability_id = "changed"
        with self.assertRaises(ValidationError):
            defn.capability_metadata = {"mutated": True}

    def test_definition_is_a_plain_pydantic_dto(self):
        # Provider independence: a definition is plain data, not a provider/SDK
        # object, and exposes no execute/validate/resolve behaviour.
        defn = _definition()
        self.assertIsInstance(defn, BaseModel)
        for attr in ("execute", "validate_request", "resolve", "instantiate"):
            self.assertFalse(hasattr(defn, attr))


# =====================================================================
# CapabilityRegistrySnapshot DTO
# =====================================================================
class CapabilityRegistrySnapshotModelTests(unittest.TestCase):
    def test_defaults_describe_an_empty_registry(self):
        snap = CapabilityRegistrySnapshot()
        self.assertEqual(snap.capabilities, [])
        self.assertEqual(snap.capability_count, 0)
        self.assertEqual(snap.registry_metadata, {})

    def test_snapshot_is_immutable(self):
        snap = CapabilityRegistrySnapshot(
            capabilities=[_definition()],
            capability_count=1,
            registry_metadata={"capability_count": 1},
        )
        with self.assertRaises(ValidationError):
            snap.capability_count = 99
        with self.assertRaises(ValidationError):
            snap.capabilities = []
        with self.assertRaises(ValidationError):
            snap.registry_metadata = {}


# =====================================================================
# CapabilityRegistry — behaviour
# =====================================================================
class CapabilityRegistryTests(unittest.TestCase):
    # --- empty registry --------------------------------------------------
    def test_initial_registry_is_empty(self):
        registry = CapabilityRegistry()
        snap = registry.snapshot()
        self.assertEqual(snap.capabilities, [])
        self.assertEqual(snap.capability_count, 0)
        self.assertFalse(registry.has_capability("anything"))

    def test_empty_constructor_variants(self):
        self.assertEqual(CapabilityRegistry(None).snapshot().capability_count, 0)
        self.assertEqual(CapabilityRegistry([]).snapshot().capability_count, 0)

    # --- registration ----------------------------------------------------
    def test_register_adds_definition(self):
        registry = CapabilityRegistry()
        defn = _definition(capability_id="cap-1")
        registry.register(defn)
        self.assertTrue(registry.has_capability("cap-1"))
        self.assertIs(registry.get_capability("cap-1"), defn)

    def test_constructor_registers_all_definitions(self):
        a = _definition(capability_id="a")
        b = _definition(capability_id="b")
        registry = CapabilityRegistry([a, b])
        self.assertTrue(registry.has_capability("a"))
        self.assertTrue(registry.has_capability("b"))
        self.assertEqual(registry.snapshot().capability_count, 2)

    # --- duplicate rejection --------------------------------------------
    def test_register_duplicate_id_raises_value_error(self):
        registry = CapabilityRegistry([_definition(capability_id="dup")])
        with self.assertRaises(ValueError):
            registry.register(
                _definition(capability_id="dup", capability_name="Other")
            )

    def test_duplicate_in_constructor_raises_value_error(self):
        with self.assertRaises(ValueError):
            CapabilityRegistry(
                [
                    _definition(capability_id="dup"),
                    _definition(capability_id="dup"),
                ]
            )

    def test_rejected_duplicate_does_not_overwrite(self):
        first = _definition(capability_id="dup", capability_name="First")
        registry = CapabilityRegistry([first])
        with self.assertRaises(ValueError):
            registry.register(
                _definition(capability_id="dup", capability_name="Second")
            )
        # The original registration is preserved untouched.
        self.assertIs(registry.get_capability("dup"), first)
        self.assertEqual(registry.snapshot().capability_count, 1)

    # --- lookup ----------------------------------------------------------
    def test_get_capability_returns_registered_immutable_definition(self):
        defn = _definition(capability_id="cap-look")
        registry = CapabilityRegistry([defn])
        got = registry.get_capability("cap-look")
        self.assertIs(got, defn)
        with self.assertRaises(ValidationError):
            got.capability_name = "mutated"

    def test_get_capability_unknown_raises_key_error(self):
        registry = CapabilityRegistry([_definition(capability_id="known")])
        with self.assertRaises(KeyError):
            registry.get_capability("unknown")

    def test_has_capability_true_and_false(self):
        registry = CapabilityRegistry([_definition(capability_id="here")])
        self.assertTrue(registry.has_capability("here"))
        self.assertFalse(registry.has_capability("absent"))

    # --- insertion ordering ---------------------------------------------
    def test_snapshot_preserves_insertion_order(self):
        # Ids deliberately not in sorted order to prove order is insertion,
        # never alphabetical.
        ids = ["zeta", "alpha", "mike", "bravo"]
        registry = CapabilityRegistry()
        for cid in ids:
            registry.register(_definition(capability_id=cid))
        self.assertEqual(
            [d.capability_id for d in registry.snapshot().capabilities], ids
        )

    def test_constructor_order_is_preserved(self):
        ids = ["3", "1", "2"]
        registry = CapabilityRegistry([_definition(capability_id=i) for i in ids])
        self.assertEqual(
            [d.capability_id for d in registry.snapshot().capabilities], ids
        )

    # --- snapshot immutability / copy-out -------------------------------
    def test_snapshot_count_matches_registered(self):
        registry = CapabilityRegistry(
            [_definition(capability_id=str(i)) for i in range(3)]
        )
        snap = registry.snapshot()
        self.assertEqual(snap.capability_count, 3)
        self.assertEqual(len(snap.capabilities), 3)

    def test_snapshot_is_frozen(self):
        registry = CapabilityRegistry([_definition()])
        with self.assertRaises(ValidationError):
            registry.snapshot().capability_count = 0

    def test_snapshot_list_is_a_detached_copy(self):
        registry = CapabilityRegistry([_definition(capability_id="a")])
        snap = registry.snapshot()
        # Mutating the returned list must not affect the registry.
        snap.capabilities.append(_definition(capability_id="injected"))
        self.assertFalse(registry.has_capability("injected"))
        self.assertEqual(registry.snapshot().capability_count, 1)

    def test_each_snapshot_returns_a_new_list_object(self):
        registry = CapabilityRegistry([_definition()])
        self.assertIsNot(
            registry.snapshot().capabilities, registry.snapshot().capabilities
        )

    def test_prior_snapshot_unaffected_by_later_registration(self):
        registry = CapabilityRegistry([_definition(capability_id="a")])
        snap = registry.snapshot()
        registry.register(_definition(capability_id="b"))
        # The already-taken snapshot is an immutable point-in-time view.
        self.assertEqual(snap.capability_count, 1)
        self.assertEqual([d.capability_id for d in snap.capabilities], ["a"])
        self.assertEqual(registry.snapshot().capability_count, 2)

    # --- deterministic behaviour ----------------------------------------
    def test_repeated_snapshots_are_equal(self):
        registry = CapabilityRegistry(
            [_definition(capability_id="a"), _definition(capability_id="b")]
        )
        self.assertEqual(registry.snapshot(), registry.snapshot())

    def test_registry_metadata_is_deterministic(self):
        registry = CapabilityRegistry(
            [_definition(capability_id="a"), _definition(capability_id="b")]
        )
        meta = registry.snapshot().registry_metadata
        self.assertEqual(
            meta, {"capability_count": 2, "registry_ordering": "insertion"}
        )
        # Identical across calls — no timestamps, uuids, or other nondeterminism.
        self.assertEqual(
            registry.snapshot().registry_metadata,
            registry.snapshot().registry_metadata,
        )

    def test_same_registrations_yield_equal_snapshots(self):
        defs = [_definition(capability_id="a"), _definition(capability_id="b")]
        self.assertEqual(
            CapabilityRegistry(defs).snapshot(),
            CapabilityRegistry(defs).snapshot(),
        )

    # --- provider independence ------------------------------------------
    def test_snapshot_exposes_only_plain_definition_dtos(self):
        registry = CapabilityRegistry([_definition(), _definition(capability_id="b")])
        for entry in registry.snapshot().capabilities:
            self.assertIsInstance(entry, CapabilityDefinition)
            self.assertIsInstance(entry, BaseModel)

    # --- stateless public behaviour -------------------------------------
    def test_reads_do_not_mutate_state(self):
        registry = CapabilityRegistry([_definition(capability_id="a")])
        before = registry.snapshot()
        registry.get_capability("a")
        registry.has_capability("a")
        registry.has_capability("missing")
        registry.snapshot()
        self.assertEqual(registry.snapshot(), before)

    def test_registries_are_isolated_no_global_state(self):
        r1 = CapabilityRegistry()
        r2 = CapabilityRegistry()
        r1.register(_definition(capability_id="only-in-r1"))
        self.assertTrue(r1.has_capability("only-in-r1"))
        self.assertFalse(r2.has_capability("only-in-r1"))

    def test_registry_holds_only_its_definitions_map(self):
        registry = CapabilityRegistry([_definition()])
        self.assertEqual(set(vars(registry)), {"_definitions"})

    def test_registry_exposes_no_execution_surface(self):
        # Catalogue only: it never executes, resolves, or instantiates.
        for attr in ("execute", "resolve", "instantiate", "dispatch", "run"):
            self.assertFalse(hasattr(CapabilityRegistry, attr))

    def test_input_list_not_mutated(self):
        original = [_definition(capability_id="a"), _definition(capability_id="b")]
        snapshot_of_input = list(original)
        registry = CapabilityRegistry(original)
        registry.register(_definition(capability_id="c"))
        self.assertEqual(original, snapshot_of_input)
        self.assertEqual(registry.snapshot().capability_count, 3)


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class CapabilityRegistryDependencyInjectionTests(unittest.TestCase):
    def test_get_capability_definitions_is_empty(self):
        from app.core.dependencies import get_capability_definitions

        self.assertEqual(get_capability_definitions(), [])

    def test_get_capability_registry_default_is_empty(self):
        from app.core.dependencies import get_capability_registry

        registry = get_capability_registry()
        self.assertIsInstance(registry, CapabilityRegistry)
        self.assertEqual(registry.snapshot().capability_count, 0)

    def test_get_capability_registry_with_injected_definitions(self):
        from app.core.dependencies import get_capability_registry

        registry = get_capability_registry(
            [_definition(capability_id="a"), _definition(capability_id="b")]
        )
        self.assertIsInstance(registry, CapabilityRegistry)
        self.assertTrue(registry.has_capability("a"))
        self.assertTrue(registry.has_capability("b"))

    def test_capability_registry_dep_is_wired(self):
        from app.core.dependencies import CapabilityRegistryDep

        # Annotated[CapabilityRegistry, Depends(get_capability_registry)]
        self.assertIn(CapabilityRegistry, getattr(CapabilityRegistryDep, "__args__", ()))


# =====================================================================
# Regression — prior sprints unchanged
# =====================================================================
class CapabilityRegistryRegressionTests(unittest.TestCase):
    def test_sprint_11_tool_registry_seam_unchanged(self):
        from app.core.dependencies import get_tool_registry
        from app.services.tools.registry import ToolRegistry

        registry = get_tool_registry()
        self.assertIsInstance(registry, ToolRegistry)
        self.assertEqual(registry.list_tools(), [])

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_runtime_capability_modules_still_import(self):
        # The new module lives beside the Sprint 14 runtime modules without
        # colliding with them.
        from app.services.runtime.execution_capability_models import (
            CapabilityExecutionRequest,
        )
        from app.services.runtime.capability_registry_models import (
            CapabilityDefinition as _CD,
        )

        self.assertIsNot(CapabilityExecutionRequest, _CD)


if __name__ == "__main__":
    unittest.main()
