"""Message channel: make voice a first-class conversation channel

Adds one nullable-safe column, ``messages.channel``, recording the channel a
message happened on (``text`` or ``voice``). Voice is an interface over the same
Conversation domain — a spoken turn is transcribed and stored as an ordinary
message tagged with its channel — so no new table, no new relationship, and no
change to any existing column is needed.

Purely additive and backwards compatible:

* The column is ``NOT NULL`` with a server default of ``'text'``, so every
  message written before voice existed reads as typed and the migration needs
  no data backfill step of its own.
* Nothing about conversations, the AI pipeline, memory, tasks or workflows
  changes; dropping the column fully reverses the change.

Revision ID: b9d4f27c6e13
Revises: a7c3e5f19b84
Create Date: 2026-07-21 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9d4f27c6e13"
down_revision: Union[str, Sequence[str], None] = "a7c3e5f19b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "messages",
        sa.Column(
            "channel",
            sa.String(length=50),
            server_default="text",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("messages", "channel")
