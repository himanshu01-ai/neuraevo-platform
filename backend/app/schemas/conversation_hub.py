"""Pydantic schemas for the user-scoped Conversation hub (Sprint 21).

The hub makes a conversation addressable by its own id — the platform
interaction layer — rather than only through the employee behind it. These DTOs
reuse the existing message shape wherever they can: a turn answers in two
:class:`MessageResponse` objects, because a turn's messages *are* ordinary
conversation messages. Only the cross-employee summary (which carries the owning
employee's name and the thread's last line) is new.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.message import MessageContent, MessageResponse
from app.utils.constants import ConversationStatus, MessageChannel


class ConversationHubCreate(BaseModel):
    """Create a conversation, naming the employee it is with.

    The employee rides in the body (not the path) because the hub is
    user-scoped; ownership of that employee is validated by the reused
    :class:`EmployeeService`.
    """

    employee_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)


class ConversationTurnRequest(BaseModel):
    """One human utterance and the channel it arrived on.

    ``content`` is the text — for a spoken turn, the transcript the browser
    produced. ``channel`` defaults to ``text`` so a typed turn need not send it.
    """

    content: MessageContent
    channel: MessageChannel = MessageChannel.TEXT


class ConversationTurnResponse(BaseModel):
    """Both messages a turn produced: the human's, then the employee's."""

    user_message: MessageResponse
    assistant_message: MessageResponse


class ConversationActionRequest(BaseModel):
    """A confirmed action to carry out for a conversation (Sprint 23).

    Raised after the user approves an action the assistant proposed. ``label`` is
    the action's title (e.g. "Send email", "Create task") and ``summary`` is a
    one-line paraphrase of what was asked. The platform turns the confirmed
    request into a real task, carried by the conversation's employee, so the work
    lands in the workspace rather than being a side effect the conversation
    fabricates.
    """

    label: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=280)


class ConversationActionResponse(BaseModel):
    """The task a confirmed conversation action created."""

    task_id: uuid.UUID
    business_id: str
    name: str
    status: str
    employee_id: Optional[uuid.UUID] = None


class ConversationSummaryResponse(BaseModel):
    """A conversation with the display facts a list or header needs.

    A superset of the existing ``ConversationResponse`` (same real columns) plus
    the owning employee's name, the message count, and the latest message's
    content — assembled server-side so the sidebar renders without a follow-up
    request per row.
    """

    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    title: str
    status: ConversationStatus
    message_count: int
    last_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """A page of the user's conversations with the total behind it."""

    items: list[ConversationSummaryResponse] = Field(default_factory=list)
    total: int
