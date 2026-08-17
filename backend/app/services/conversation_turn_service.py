"""Conversation turn service: one channel-aware exchange.

A "turn" is the unit the interaction layer speaks in: the human says something,
the employee replies. It composes the existing services rather than adding a
second pipeline — :class:`ConversationService` for user-scoped ownership,
:class:`MessageService` to persist the human message, and
:class:`ConversationGenerationService` for the memory-and-blueprint-grounded
reply. The only thing this sprint adds is the channel: the same turn runs
whether the human typed or spoke, and both messages carry the channel it
happened on, so text and voice produce the identical internal message model.

Nothing about voice is special here. A spoken turn is a transcript (text) with
``channel=voice``; speech recognition and synthesis are the browser's, at the
edge. This service never sees audio.
"""

import uuid
from typing import Tuple

from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate
from app.services.conversation_generation_service import (
    ConversationGenerationService,
)
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.utils.constants import MessageChannel, MessageRole
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationTurnService:
    """Runs one human→assistant exchange, returning both persisted messages.

    The generation service is injected (it needs the AI provider); the other
    collaborators are built from the request-scoped session. Each collaborator
    owns its own commit, so a turn is two writes: the human message is saved
    first, then the reply. If generation fails the human message still stands —
    exactly as a chat behaves when a message sends but the reply errors — and a
    retry generates a fresh reply against the same history.
    """

    def __init__(
        self, session, generation: ConversationGenerationService
    ) -> None:
        self.session = session
        self.conversations = ConversationService(session)
        self.messages = MessageService(session)
        self.generation = generation

    def run_turn(
        self,
        owner: User,
        conversation_id: uuid.UUID,
        content: str,
        channel: MessageChannel = MessageChannel.TEXT,
    ) -> Tuple[Message, Message]:
        """Persist the human message, generate the reply, return both.

        Resolves the conversation for ``owner`` (raising
        :class:`ConversationNotFoundError` if it is not theirs), stores the
        human message on the given ``channel``, then asks the reused generation
        service for the employee's reply — which assembles blueprint + memory +
        history for context and persists the assistant message on the same
        channel. Ownership, blueprint, and provider errors propagate unchanged
        from the reused services.
        """
        conversation = self.conversations.get_for_user(owner, conversation_id)

        user_message = self.messages.create_message(
            owner,
            conversation.employee_id,
            conversation_id,
            MessageCreate(
                role=MessageRole.USER, content=content, channel=channel
            ),
        )
        assistant_message = self.generation.generate_reply(
            owner,
            conversation.employee_id,
            conversation_id,
            channel=channel,
        )

        logger.info(
            "User %s ran a %s turn on conversation %s (user %s -> assistant %s)",
            owner.id,
            channel.value,
            conversation_id,
            user_message.id,
            assistant_message.id,
        )
        return user_message, assistant_message
