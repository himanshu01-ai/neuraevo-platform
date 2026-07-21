"""Collaboration shares: secure share links

Adds the table behind the sharing architecture (Sprint 20B): a redeemable,
secure link that grants participation in a resource. Polymorphic over the
resource in the same way as ``collaboration_participants`` — ``resource_type`` +
``resource_id`` name any collaborated resource, with no foreign key to the four
frozen owning tables.

Purely additive:

* One new table. No existing table is altered, so every completed domain is
  untouched, and the change reverses by dropping it.
* Only the SHA-256 ``token_hash`` is stored, never the token — the same stance
  the ``users`` table takes with verification and reset tokens. A unique
  constraint on the hash lets a redeemer be resolved by hashing the presented
  token.
* Revocation and expiry are timestamps, not a delete, so a link's history
  survives for the activity timeline. ``created_by_user_id`` cascades with the
  user.

Revision ID: e2a9c4f16b73
Revises: d7b2f4a1c908
Create Date: 2026-07-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2a9c4f16b73"
down_revision: Union[str, Sequence[str], None] = "d7b2f4a1c908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "collaboration_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_collab_share_token"),
    )
    op.create_index(
        "ix_collaboration_shares_created_by_user_id",
        "collaboration_shares",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_collab_share_resource",
        "collaboration_shares",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_collab_share_resource", table_name="collaboration_shares"
    )
    op.drop_index(
        "ix_collaboration_shares_created_by_user_id",
        table_name="collaboration_shares",
    )
    op.drop_table("collaboration_shares")
