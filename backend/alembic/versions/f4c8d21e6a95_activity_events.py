"""Activity events: the platform activity timeline

Adds the append-only timeline behind the Collaboration Platform (Sprint 20C):
one record that something happened to a collaborated resource. It is the
cross-domain counterpart to ``employee_activity_events`` — same append-only
discipline and per-subject ``sequence`` ordinal — but keyed polymorphically by
``resource_type`` + ``resource_id`` so a single timeline serves conversations,
tasks, workflows, and memory.

Purely additive:

* One new table. No existing table is altered, so every completed domain is
  untouched, and the change reverses by dropping it.
* No foreign keys: ``resource_id`` is polymorphic, and ``actor_id`` must survive
  the actor being deleted — an audit row is written once and never rewritten.
* ``owner_user_id`` is denormalised from the resource owner at write time and
  indexed, so the per-user feed is one read rather than a fan-out across every
  domain. ``(resource_type, resource_id, sequence)`` is indexed for the
  per-resource timeline.

Revision ID: f4c8d21e6a95
Revises: e2a9c4f16b73
Create Date: 2026-07-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4c8d21e6a95"
down_revision: Union[str, Sequence[str], None] = "e2a9c4f16b73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activity_resource",
        "activity_events",
        ["resource_type", "resource_id", "sequence"],
    )
    op.create_index("ix_activity_owner", "activity_events", ["owner_user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_activity_owner", table_name="activity_events")
    op.drop_index("ix_activity_resource", table_name="activity_events")
    op.drop_table("activity_events")
