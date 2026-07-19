"""Sprint 18.3: workflow persistence domain

Adds the ``workflows`` table — the first persistence for authored workflows.
The frontend builder has existed since Sprint 17.5 against a mock adapter;
this is the backend that will replace it.

Purely additive:

* One new table. No existing table is altered, so every completed domain is
  untouched and the change is reversible by dropping it.
* The graph is one JSON column rather than node/edge tables. The builder reads
  and writes whole graphs, nothing queries inside the document, and node shape
  is still the frontend's authoring vocabulary — normalising now would add
  joins and constraints with no consumer.
* ``employee_assignments.workflow_id`` is deliberately *not* given a foreign
  key here. It is a ``String(255)`` holding caller-supplied identifiers (the
  current callers pass values like ``'wfl_1'``), so a constraint against
  ``workflows.id`` would reject existing rows and require both a type change
  and a data migration on a completed domain. That belongs in its own sprint,
  once assignments actually reference workflows created through this API.

Revision ID: c4e1a7d92f36
Revises: b3d914ac7f52
Create Date: 2026-07-19 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e1a7d92f36"
down_revision: Union[str, Sequence[str], None] = "b3d914ac7f52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=50), nullable=False, server_default="draft"
        ),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    # Every read path filters by owner, so the ownership column is indexed —
    # the same shape as ``employees.user_id``.
    op.create_index(
        op.f("ix_workflows_user_id"), "workflows", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_workflows_user_id"), table_name="workflows")
    op.drop_table("workflows")
