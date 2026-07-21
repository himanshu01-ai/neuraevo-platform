"""Collaboration participants: the reusable collaboration core

Adds the one table the Collaboration Platform (Sprint 20) is built on: a
participant on a shared resource. It is polymorphic over the resource —
``resource_type`` + ``resource_id`` name a conversation, task, workflow, or
memory — so a single table serves every domain and a future domain joins by
naming a new resource type, never a new table.

Purely additive:

* One new table. No existing table is altered, so every completed domain —
  Conversations, Tasks, Workflows, Memory and the rest — is untouched, and the
  change reverses by dropping it.
* ``resource_id`` deliberately carries **no** foreign key: the referenced table
  varies by ``resource_type``, and the four owning models are frozen. Ownership
  is read back through each resource's existing chain at access time, not
  enforced here.

Constraint choices worth recording:

* Two nullable identity columns, ``user_id`` and ``employee_id``, each cascading
  with its parent, plus a check constraint that exactly one is set and matches
  ``participant_type``. That employee column is what lets an AI employee join a
  resource on the same footing as a person.
* A unique constraint per identity (``uq_collab_participant_user`` /
  ``…_employee``) keeps a user or employee a participant at most once per
  resource. NULLs are distinct in SQLite and PostgreSQL, so an employee row
  never collides on the user constraint and vice versa.
* ``ix_collab_participant_resource`` indexes the ``(resource_type,
  resource_id)`` pair — listing a resource's participants is the hot read.

Revision ID: d7b2f4a1c908
Revises: b9d4f27c6e13
Create Date: 2026-07-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7b2f4a1c908"
down_revision: Union[str, Sequence[str], None] = "b9d4f27c6e13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "collaboration_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("participant_type", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["added_by_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_type",
            "resource_id",
            "user_id",
            name="uq_collab_participant_user",
        ),
        sa.UniqueConstraint(
            "resource_type",
            "resource_id",
            "employee_id",
            name="uq_collab_participant_employee",
        ),
        sa.CheckConstraint(
            "(participant_type = 'user' AND user_id IS NOT NULL "
            "AND employee_id IS NULL) OR "
            "(participant_type = 'employee' AND employee_id IS NOT NULL "
            "AND user_id IS NULL)",
            name="ck_collab_participant_identity",
        ),
    )
    op.create_index(
        "ix_collaboration_participants_user_id",
        "collaboration_participants",
        ["user_id"],
    )
    op.create_index(
        "ix_collaboration_participants_employee_id",
        "collaboration_participants",
        ["employee_id"],
    )
    op.create_index(
        "ix_collab_participant_resource",
        "collaboration_participants",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_collab_participant_resource",
        table_name="collaboration_participants",
    )
    op.drop_index(
        "ix_collaboration_participants_employee_id",
        table_name="collaboration_participants",
    )
    op.drop_index(
        "ix_collaboration_participants_user_id",
        table_name="collaboration_participants",
    )
    op.drop_table("collaboration_participants")
