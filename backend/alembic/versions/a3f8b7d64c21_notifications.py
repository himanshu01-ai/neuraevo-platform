"""Notifications: the collaboration inbox

Adds the table behind the reusable notification architecture (Sprint 20D): one
notification delivered to one user. Keyed by an optional polymorphic resource
reference and an optional actor, like the activity timeline, but mutable rather
than append-only — the read/archived/pinned/bookmarked/following/muted flags are
the quick actions the notification center offers.

Purely additive:

* One new table. No existing table is altered, so every completed domain is
  untouched, and the change reverses by dropping it.
* ``user_id`` (the recipient) cascades with the user. ``resource_id`` and
  ``actor_id`` are polymorphic with no foreign key, so a notification serves
  every domain and survives the referenced record.
* ``priority`` reuses the platform's one low/medium/high/urgent scale rather
  than a second vocabulary. ``(user_id, created_at)`` is indexed for the inbox.

Revision ID: a3f8b7d64c21
Revises: f4c8d21e6a95
Create Date: 2026-07-22 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3f8b7d64c21"
down_revision: Union[str, Sequence[str], None] = "f4c8d21e6a95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "description",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=50), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column(
            "read", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "pinned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "bookmarked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "following",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "muted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_id", "notifications", ["user_id"]
    )
    op.create_index(
        "ix_notification_recipient",
        "notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_notification_recipient", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
