"""Unit tests for the Sprint 7.3 AI Orchestrator.

Every collaborator is mocked (prompt builder, provider factory, provider), so
no database, network, or real provider is involved. The tests verify that the
orchestrator wires context -> prompt -> provider -> AIResponse correctly,
returns provider-agnostic DTOs, performs no post-processing, and propagates
provider errors.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_ai_orchestrator_service
"""

import unittest
import uuid
from unittest.mock import MagicMock

from app.schemas.ai_response import AIResponse
from app.schemas.prompt_package import (
    PromptMessage,
    PromptMetadata,
    PromptPackage,
)
from app.services.orchestrator.ai_orchestrator_service import (
    AIOrchestratorService,
)
from app.services.permissions import PermissionResult
from app.services.planner import ExecutionPlan, PlanningStep
from app.services.providers import (
    ConversationGenerationError,
    ConversationGenerationTimeoutError,
)
from app.services.tools import ToolExecutionResult


class AIOrchestratorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.package = PromptPackage(
            system_prompt="SYSTEM BLOCK",
            messages=[
                PromptMessage(role="user", content="Hi"),
                PromptMessage(role="assistant", content="Hello!"),
                PromptMessage(role="user", content="What's next?"),
            ],
            language="en",
            metadata=PromptMetadata(
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                memory_count=1,
                message_count=2,
            ),
        )

        # Mocked collaborators.
        self.prompt_builder = MagicMock()
        self.prompt_builder.build.return_value = self.package
        self.provider = MagicMock()
        self.provider.name = "test-provider"
        self.provider.generate_reply.return_value = "Generated reply."
        self.provider_factory = MagicMock()
        self.provider_factory.get_provider.return_value = self.provider

        # Sprint 11.5 agent-execution collaborators (all mocked).
        self.planner = MagicMock(name="PlannerService")
        self.permissions = MagicMock(name="PermissionService")
        self.tool_registry = MagicMock(name="ToolRegistry")
        self.tool_execution = MagicMock(name="ToolExecutionService")

        self.orchestrator = AIOrchestratorService(
            self.prompt_builder,
            self.provider_factory,
            planner=self.planner,
            permissions=self.permissions,
            tool_registry=self.tool_registry,
            tool_execution=self.tool_execution,
        )
        # Context is opaque to the orchestrator (passed straight to the builder).
        self.context = MagicMock(name="RuntimeAIContext")

    def _run(self) -> AIResponse:
        return self.orchestrator.run(self.context)

    # --- happy path / wiring --------------------------------------------
    def test_run_returns_ai_response(self):
        self.assertIsInstance(self._run(), AIResponse)

    def test_builds_prompt_from_context(self):
        self._run()
        self.prompt_builder.build.assert_called_once_with(self.context)

    def test_resolves_provider_from_factory(self):
        self._run()
        self.provider_factory.get_provider.assert_called_once_with()

    def test_calls_provider_with_a_string_prompt(self):
        self._run()
        self.provider.generate_reply.assert_called_once()
        (arg,), _ = self.provider.generate_reply.call_args
        self.assertIsInstance(arg, str)

    def test_content_is_provider_output(self):
        self.assertEqual(self._run().content, "Generated reply.")

    # --- provider-agnostic metadata -------------------------------------
    def test_metadata_provider_name(self):
        self.assertEqual(self._run().metadata.provider, "test-provider")

    def test_metadata_language_from_package(self):
        self.assertEqual(self._run().metadata.language, "en")

    def test_metadata_ids_from_package(self):
        meta = self._run().metadata
        self.assertEqual(meta.employee_id, self.employee_id)
        self.assertEqual(meta.conversation_id, self.conversation_id)

    def test_metadata_prompt_message_count(self):
        self.assertEqual(self._run().metadata.prompt_message_count, 3)

    # --- prompt adapter --------------------------------------------------
    def test_rendered_prompt_contains_system_and_all_messages(self):
        self._run()
        (prompt,), _ = self.provider.generate_reply.call_args
        self.assertIn("SYSTEM BLOCK", prompt)
        self.assertIn("Hi", prompt)
        self.assertIn("Hello!", prompt)
        self.assertIn("What's next?", prompt)

    # --- error propagation ----------------------------------------------
    def test_provider_error_propagates(self):
        self.provider.generate_reply.side_effect = ConversationGenerationError(
            "boom"
        )
        with self.assertRaises(ConversationGenerationError):
            self._run()

    def test_provider_timeout_propagates(self):
        self.provider.generate_reply.side_effect = (
            ConversationGenerationTimeoutError("slow")
        )
        with self.assertRaises(ConversationGenerationTimeoutError):
            self._run()

    # --- no post-processing / no side effects ---------------------------
    def test_content_returned_verbatim_no_post_processing(self):
        self.provider.generate_reply.return_value = "  raw\noutput  "
        self.assertEqual(self._run().content, "  raw\noutput  ")

    def test_orchestrator_holds_only_injected_collaborators(self):
        # No session / repository — orchestration only.
        self.assertEqual(
            set(vars(self.orchestrator)),
            {
                "prompt_builder",
                "provider_factory",
                "planner",
                "permissions",
                "tool_registry",
                "tool_execution",
            },
        )

    def test_reuses_injected_collaborators(self):
        self.assertIs(self.orchestrator.prompt_builder, self.prompt_builder)
        self.assertIs(
            self.orchestrator.provider_factory, self.provider_factory
        )

    def test_single_generation_per_run(self):
        self._run()
        self.assertEqual(self.prompt_builder.build.call_count, 1)
        self.assertEqual(self.provider_factory.get_provider.call_count, 1)
        self.assertEqual(self.provider.generate_reply.call_count, 1)

    def test_run_does_not_touch_agent_collaborators(self):
        self._run()
        self.planner.create_plan.assert_not_called()
        self.permissions.check_permission.assert_not_called()
        self.tool_registry.get_tool.assert_not_called()
        self.tool_execution.execute.assert_not_called()


class AgentExecutionCoreTests(unittest.TestCase):
    """Sprint 11.5 — orchestrator.execute_agent_request coordination."""

    def setUp(self) -> None:
        self.user_request = "Draft and send the weekly update"
        self.steps = [
            PlanningStep(
                tool_name="draft_email",
                arguments={"topic": "weekly"},
                description="Draft the update",
            ),
            PlanningStep(
                tool_name="send_email",
                arguments={"to": "team@example.com"},
                description="Send the update",
            ),
        ]
        self.plan = ExecutionPlan(steps=self.steps)

        self.planner = MagicMock(name="PlannerService")
        self.planner.create_plan.return_value = self.plan
        self.permissions = MagicMock(name="PermissionService")
        self.permissions.check_permission.return_value = PermissionResult(
            approved=True
        )
        self.tool_registry = MagicMock(name="ToolRegistry")
        self.tool_registry.get_tool.side_effect = (
            lambda name: MagicMock(name=f"provider:{name}")
        )
        self.tool_execution = MagicMock(name="ToolExecutionService")
        self._exec_results = [
            ToolExecutionResult(success=True, output="drafted"),
            ToolExecutionResult(success=True, output="sent"),
        ]
        self.tool_execution.execute.side_effect = list(self._exec_results)

        # prompt_builder / provider_factory are unused by the agent path.
        self.orchestrator = AIOrchestratorService(
            MagicMock(name="PromptBuilder"),
            MagicMock(name="ProviderFactory"),
            planner=self.planner,
            permissions=self.permissions,
            tool_registry=self.tool_registry,
            tool_execution=self.tool_execution,
        )

    def _execute(self):
        return self.orchestrator.execute_agent_request(self.user_request)

    # --- happy path: one plan, per-step gate + execute, ordered ----------
    def test_planner_called_exactly_once_with_request(self):
        self._execute()
        self.planner.create_plan.assert_called_once_with(self.user_request)

    def test_permission_checked_once_per_step(self):
        self._execute()
        self.assertEqual(self.permissions.check_permission.call_count, 2)

    def test_registry_lookup_once_per_step(self):
        self._execute()
        self.assertEqual(self.tool_registry.get_tool.call_count, 2)
        looked_up = [
            c.args[0] for c in self.tool_registry.get_tool.call_args_list
        ]
        self.assertEqual(looked_up, ["draft_email", "send_email"])

    def test_execution_once_per_approved_step(self):
        self._execute()
        self.assertEqual(self.tool_execution.execute.call_count, 2)

    def test_returns_results_in_execution_order(self):
        results = self._execute()
        self.assertEqual(results, self._exec_results)
        self.assertEqual([r.output for r in results], ["drafted", "sent"])

    def test_per_step_call_order_registry_then_permission_then_execute(self):
        order = []
        self.tool_registry.get_tool.side_effect = (
            lambda name: order.append(f"registry:{name}")
        )
        self.permissions.check_permission.side_effect = (
            lambda request: order.append(f"permission:{request.tool_name}")
            or PermissionResult(approved=True)
        )
        self.tool_execution.execute.side_effect = (
            lambda request: order.append(f"execute:{request.tool_name}")
            or ToolExecutionResult(success=True)
        )
        self._execute()
        self.assertEqual(
            order,
            [
                "registry:draft_email",
                "permission:draft_email",
                "execute:draft_email",
                "registry:send_email",
                "permission:send_email",
                "execute:send_email",
            ],
        )

    def test_permission_and_execution_receive_step_tool_and_arguments(self):
        self._execute()
        perm_req = self.permissions.check_permission.call_args_list[0].args[0]
        self.assertEqual(perm_req.tool_name, "draft_email")
        self.assertEqual(perm_req.arguments, {"topic": "weekly"})
        exec_req = self.tool_execution.execute.call_args_list[0].args[0]
        self.assertEqual(exec_req.tool_name, "draft_email")
        self.assertEqual(exec_req.arguments, {"topic": "weekly"})

    # --- permission denied: halt immediately -----------------------------
    def test_permission_denied_halts_and_returns_permission_result(self):
        denied = PermissionResult(approved=False, reason="blocked")
        self.permissions.check_permission.return_value = denied
        result = self._execute()
        self.assertIs(result, denied)

    def test_permission_denied_skips_execution_and_remaining_steps(self):
        denied = PermissionResult(approved=False, reason="blocked")
        self.permissions.check_permission.return_value = denied
        self._execute()
        # Halted on step 1: execute never runs, step 2 never checked.
        self.tool_execution.execute.assert_not_called()
        self.assertEqual(self.permissions.check_permission.call_count, 1)
        self.assertEqual(self.tool_registry.get_tool.call_count, 1)

    # --- permission requires confirmation: halt --------------------------
    def test_requires_confirmation_halts_and_returns_result(self):
        confirm = PermissionResult(
            approved=True, requires_user_confirmation=True
        )
        self.permissions.check_permission.return_value = confirm
        result = self._execute()
        self.assertIs(result, confirm)
        self.tool_execution.execute.assert_not_called()
        self.assertEqual(self.permissions.check_permission.call_count, 1)

    # --- unknown tool: registry KeyError propagates ----------------------
    def test_unknown_tool_raises_key_error_and_executes_nothing(self):
        self.tool_registry.get_tool.side_effect = KeyError("draft_email")
        with self.assertRaises(KeyError):
            self._execute()
        self.permissions.check_permission.assert_not_called()
        self.tool_execution.execute.assert_not_called()

    # --- planner exception propagates ------------------------------------
    def test_planner_exception_propagates(self):
        self.planner.create_plan.side_effect = RuntimeError("planner boom")
        with self.assertRaises(RuntimeError):
            self._execute()
        self.tool_registry.get_tool.assert_not_called()
        self.tool_execution.execute.assert_not_called()

    # --- execution exception propagates, later steps skipped -------------
    def test_execution_exception_propagates_and_skips_later_steps(self):
        self.tool_execution.execute.side_effect = RuntimeError("exec boom")
        with self.assertRaises(RuntimeError):
            self._execute()
        # Failed on step 1: step 2 never looked up or checked.
        self.assertEqual(self.tool_registry.get_tool.call_count, 1)
        self.assertEqual(self.permissions.check_permission.call_count, 1)

    # --- empty plan ------------------------------------------------------
    def test_empty_plan_returns_empty_list(self):
        self.planner.create_plan.return_value = ExecutionPlan(steps=[])
        result = self._execute()
        self.assertEqual(result, [])
        self.tool_registry.get_tool.assert_not_called()
        self.permissions.check_permission.assert_not_called()
        self.tool_execution.execute.assert_not_called()

    # --- statelessness ---------------------------------------------------
    def test_stateless_no_state_added_after_execution(self):
        before = set(vars(self.orchestrator))
        self._execute()
        self.assertEqual(set(vars(self.orchestrator)), before)

    def test_repeated_execution_no_accumulation(self):
        first = self._execute()
        self.tool_execution.execute.side_effect = list(self._exec_results)
        second = self._execute()
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)


if __name__ == "__main__":
    unittest.main()
