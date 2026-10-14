"""PostgreSQL-backed integration test for the canonical conversation turn.

Runs only in the dedicated CI step with a disposable PostgreSQL service and an
explicit NEURAEVO_POSTGRES_INTEGRATION=1 opt-in. No live model credentials are
used: the conversation provider is replaced with a deterministic test double,
while database sessions, ownership checks, Blueprint context, message writes,
and the FastAPI turn route remain real.
"""

import os
import unittest
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.dependencies import get_conversation_provider_factory, get_current_user
from app.main import app
from app.models import Blueprint, Conversation, Employee, Message, User


class _FakeConversationProvider:
    name = "postgres-integration-test"

    def generate_reply(self, prompt: str) -> str:
        if not prompt.strip():
            raise AssertionError("Conversation prompt must not be empty.")
        return "PostgreSQL integration reply"


class _FakeConversationProviderFactory:
    def __init__(self) -> None:
        self.provider = _FakeConversationProvider()

    def get_provider(self) -> _FakeConversationProvider:
        return self.provider


@unittest.skipUnless(
    os.environ.get("NEURAEVO_POSTGRES_INTEGRATION") == "1",
    "Run only in the dedicated PostgreSQL integration CI step.",
)
class ConversationPostgresIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        if not settings.DATABASE_URL:
            self.fail("DATABASE_URL must point to the disposable PostgreSQL test database.")
        self.engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        self.owner_id = uuid.uuid4()
        self.other_owner_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.blueprint_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.owner = SimpleNamespace(id=self.owner_id)
        self.provider_factory = _FakeConversationProviderFactory()
        self.previous_overrides = dict(app.dependency_overrides)

        with self.SessionLocal() as session:
            session.add_all(
                [
                    User(
                        id=self.owner_id,
                        email=f"ci-{self.owner_id.hex}@example.test",
                        hashed_password="not-a-real-password-hash",
                        full_name="Conversation Integration Owner",
                    ),
                    User(
                        id=self.other_owner_id,
                        email=f"ci-{self.other_owner_id.hex}@example.test",
                        hashed_password="not-a-real-password-hash",
                        full_name="Conversation Integration Other Owner",
                    ),
                ]
            )
            session.flush()
            session.add(
                Employee(
                    id=self.employee_id,
                    user_id=self.owner_id,
                    name="Integration Assistant",
                    role="assistant",
                    description="Test-only employee",
                )
            )
            session.flush()
            session.add(
                Blueprint(
                    id=self.blueprint_id,
                    employee_id=self.employee_id,
                    vision="Give concise, accurate project assistance.",
                    communication_style="Clear and direct.",
                    personality_traits="Careful and practical.",
                    goals="Answer project questions.",
                    constraints="Do not make unsupported claims.",
                    preferences="Use test fixtures only.",
                )
            )
            session.add(
                Conversation(
                    id=self.conversation_id,
                    employee_id=self.employee_id,
                    title="PostgreSQL integration",
                    status="active",
                )
            )
            session.commit()

        app.dependency_overrides[get_current_user] = lambda: self.owner
        app.dependency_overrides[
            get_conversation_provider_factory
        ] = lambda: self.provider_factory

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)
        if hasattr(self, "SessionLocal"):
            with self.SessionLocal() as session:
                for user_id in (self.owner_id, self.other_owner_id):
                    user = session.get(User, user_id)
                    if user is not None:
                        session.delete(user)
                session.commit()
            self.engine.dispose()

    def test_turn_persists_messages_and_enforces_owner_scope(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/conversations/{self.conversation_id}/turn",
                json={"content": "Help me investigate a project issue.", "channel": "text"},
            )
            self.assertEqual(response.status_code, 201, response.text)
            body = response.json()
            self.assertEqual(body["user_message"]["content"], "Help me investigate a project issue.")
            self.assertEqual(body["assistant_message"]["content"], "PostgreSQL integration reply")

            with self.SessionLocal() as session:
                rows = session.scalars(
                    select(Message).where(Message.conversation_id == self.conversation_id)
                ).all()
                self.assertEqual(len(rows), 2)
                self.assertEqual({row.role for row in rows}, {"user", "assistant"})
                self.assertEqual(
                    {row.content for row in rows},
                    {
                        "Help me investigate a project issue.",
                        "PostgreSQL integration reply",
                    },
                )

            # The same conversation must be indistinguishable from a missing one
            # when accessed as a different user.
            self.owner = SimpleNamespace(id=self.other_owner_id)
            denied = client.post(
                f"/api/v1/conversations/{self.conversation_id}/turn",
                json={"content": "Should not be stored.", "channel": "text"},
            )
            self.assertEqual(denied.status_code, 404, denied.text)

            with self.SessionLocal() as session:
                count = session.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.conversation_id == self.conversation_id)
                )
                self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
