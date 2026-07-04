"""Unit tests for the Sprint 12.1 Multimodal Interaction framework (abstraction).

The provider is mocked, so no network, SDK, AI inference, speech recognition/
synthesis, OCR, document parsing, streaming, planner, permission check,
registry, tool execution, or runtime is touched. The tests verify the provider
abstraction, that ``InteractionService`` delegates to the injected provider
exactly once (request forwarded, result returned unchanged, exceptions
propagated), that the service is a stateless, constructor-injected pass-through
that exposes a single public method, the enum vocabulary, the request/result
model contracts (validation + immutability + defaults), and the composition-root
wiring.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_interaction_service
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.interaction import (
    InteractionProvider,
    InteractionRequest,
    InteractionResult,
    InteractionService,
    InteractionType,
)
from app.services.interaction.providers.base import (
    InteractionProvider as BaseInteractionProvider,
)


# =====================================================================
# Provider abstraction
# =====================================================================
class InteractionProviderAbstractionTests(unittest.TestCase):
    def test_provider_is_the_abstract_base(self):
        self.assertIs(InteractionProvider, BaseInteractionProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            InteractionProvider()  # abstract process_interaction not implemented

    def test_process_interaction_is_abstract(self):
        # Sprint 12.1 ships only the contract: the sole method is abstract, so
        # no concrete modality processing is provided here.
        self.assertIn(
            "process_interaction",
            InteractionProvider.__abstractmethods__,
        )

    def test_concrete_subclass_is_instantiable(self):
        class OkProvider(InteractionProvider):
            name = "ok"

            def process_interaction(self, request):
                return InteractionResult(
                    interaction_type=request.interaction_type,
                    normalized_content=request.content,
                )

        provider = OkProvider()
        self.assertIsInstance(provider, InteractionProvider)


# =====================================================================
# InteractionService (provider mocked)
# =====================================================================
class InteractionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = InteractionRequest(
            interaction_type=InteractionType.VOICE,
            content="hello there",
            metadata={"trace": "abc"},
        )
        self.result = InteractionResult(
            interaction_type=InteractionType.VOICE,
            normalized_content="hello there",
            metadata={"lang": "en"},
        )
        self.provider = MagicMock(name="InteractionProvider")
        self.provider.process_interaction.return_value = self.result
        self.service = InteractionService(self.provider)

    def test_delegates_to_provider_exactly_once(self):
        self.service.process_interaction(self.request)
        self.provider.process_interaction.assert_called_once()

    def test_request_forwarded_unchanged(self):
        self.service.process_interaction(self.request)
        self.provider.process_interaction.assert_called_once_with(self.request)
        self.assertIs(
            self.provider.process_interaction.call_args.args[0], self.request
        )

    def test_result_returned_unchanged(self):
        result = self.service.process_interaction(self.request)
        self.assertIs(result, self.result)

    def test_provider_exception_propagates(self):
        self.provider.process_interaction.side_effect = RuntimeError(
            "provider boom"
        )
        with self.assertRaises(RuntimeError):
            self.service.process_interaction(self.request)

    def test_stateless_only_injected_provider(self):
        # No session, repository, cache, runtime, or execution state is held.
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)

    def test_exposes_single_public_method(self):
        # A pure delegator: ``process_interaction`` is the only public method —
        # no runtime, planner, registry, or execution surface is exposed.
        public_methods = {
            name
            for name, attr in vars(InteractionService).items()
            if not name.startswith("_") and callable(attr)
        }
        self.assertEqual(public_methods, {"process_interaction"})


# =====================================================================
# InteractionType (enum vocabulary)
# =====================================================================
class InteractionTypeTests(unittest.TestCase):
    def test_is_str_enum(self):
        self.assertTrue(issubclass(InteractionType, str))
        self.assertEqual(InteractionType.TEXT, "text")

    def test_exact_member_set(self):
        self.assertEqual(
            {member.name for member in InteractionType},
            {"TEXT", "VOICE", "IMAGE", "DOCUMENT"},
        )

    def test_member_values(self):
        self.assertEqual(InteractionType.TEXT.value, "text")
        self.assertEqual(InteractionType.VOICE.value, "voice")
        self.assertEqual(InteractionType.IMAGE.value, "image")
        self.assertEqual(InteractionType.DOCUMENT.value, "document")

    def test_request_accepts_every_modality(self):
        for member in InteractionType:
            request = InteractionRequest(
                interaction_type=member, content="payload"
            )
            self.assertEqual(request.interaction_type, member)

    def test_request_accepts_enum_value_string(self):
        request = InteractionRequest(
            interaction_type="document", content="payload"
        )
        self.assertIs(request.interaction_type, InteractionType.DOCUMENT)

    def test_request_rejects_unknown_modality(self):
        with self.assertRaises(ValidationError):
            InteractionRequest(interaction_type="audio", content="payload")


# =====================================================================
# Models: InteractionRequest validation / InteractionResult immutability
# =====================================================================
class InteractionModelTests(unittest.TestCase):
    def test_request_trims_content(self):
        request = InteractionRequest(
            interaction_type=InteractionType.TEXT, content="  hi there  "
        )
        self.assertEqual(request.content, "hi there")

    def test_request_rejects_empty_content(self):
        with self.assertRaises(ValidationError):
            InteractionRequest(
                interaction_type=InteractionType.TEXT, content=""
            )

    def test_request_rejects_whitespace_content(self):
        with self.assertRaises(ValidationError):
            InteractionRequest(
                interaction_type=InteractionType.TEXT, content="   "
            )

    def test_request_requires_content(self):
        with self.assertRaises(ValidationError):
            InteractionRequest(interaction_type=InteractionType.TEXT)

    def test_request_requires_interaction_type(self):
        with self.assertRaises(ValidationError):
            InteractionRequest(content="hi")

    def test_request_metadata_defaults_empty(self):
        request = InteractionRequest(
            interaction_type=InteractionType.IMAGE, content="ref"
        )
        self.assertEqual(request.metadata, {})

    def test_result_is_immutable(self):
        result = InteractionResult(
            interaction_type=InteractionType.TEXT, normalized_content="hi"
        )
        with self.assertRaises(ValidationError):
            result.normalized_content = "changed"

    def test_result_metadata_defaults_empty(self):
        result = InteractionResult(
            interaction_type=InteractionType.TEXT, normalized_content="hi"
        )
        self.assertEqual(result.metadata, {})

    def test_result_holds_fields(self):
        result = InteractionResult(
            interaction_type=InteractionType.DOCUMENT,
            normalized_content="extracted text",
            metadata={"pages": 3},
        )
        self.assertEqual(result.interaction_type, InteractionType.DOCUMENT)
        self.assertEqual(result.normalized_content, "extracted text")
        self.assertEqual(result.metadata, {"pages": 3})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class InteractionDependencyTests(unittest.TestCase):
    def test_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_interaction_service

        provider = MagicMock(name="InteractionProvider")
        service = get_interaction_service(provider)
        self.assertIsInstance(service, InteractionService)
        self.assertIs(service.provider, provider)

    def test_provider_seam_unfulfilled_until_later_sprint(self):
        # Sprint 12.1 ships only the framework: no concrete provider exists,
        # so the provider composition-root seam intentionally raises.
        from app.core.dependencies import get_interaction_provider

        with self.assertRaises(NotImplementedError):
            get_interaction_provider()


if __name__ == "__main__":
    unittest.main()
