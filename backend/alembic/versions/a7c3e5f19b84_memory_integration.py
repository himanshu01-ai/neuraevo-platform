"""Memory integration: link memories to tasks and workflows

Adds the two link tables that make an existing memory a shared platform
resource — referenced by tasks and workflows — without duplicating its content
or altering its ownership:

* ``task_memory_links``     — which memories a task references.
* ``workflow_memory_links`` — which memories a workflow references.

Purely additive:

* Two new tables. No existing table is altered, so the Sprint 2 Memory Engine,
  the Task Engine, workflows and every other completed domain are untouched, and
  the change is reversible by dropping them.
* Each is a **link table** referencing existing ``memories`` rows rather than a
  ``task_id``/``workflow_id`` column on ``memories`` — the association is a join,
  never a copy, and the frozen memory row keeps its single ``employee_id`` owner.

Column choices worth recording:

* ``memory_id`` cascades with the memory, and ``task_id``/``workflow_id`` cascade
  with the task/workflow: a link never outlives either end, and removing a link
  destroys neither the memory nor the task/workflow.
* A unique constraint on each pair keeps a memory referenced at most once per
  task/workflow, so attaching an already-linked memory is a no-op.

Revision ID: a7c3e5f19b84
Revises: f8a3c96d1e52
Create Date: 2026-07-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c3e5f19b84"
down_revision: Union[str, Sequence[str], None] = "f8a3c96d1e52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "task_memory_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("memory_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["memories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "memory_id", name="uq_task_memory_link"),
    )
    op.create_index(
        "ix_task_memory_links_task_id", "task_memory_links", ["task_id"]
    )
    op.create_index(
        "ix_task_memory_links_memory_id", "task_memory_links", ["memory_id"]
    )

    op.create_table(
        "workflow_memory_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("memory_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["memories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "memory_id", name="uq_workflow_memory_link"
        ),
    )
    op.create_index(
        "ix_workflow_memory_links_workflow_id",
        "workflow_memory_links",
        ["workflow_id"],
    )
    op.create_index(
        "ix_workflow_memory_links_memory_id",
        "workflow_memory_links",
        ["memory_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_workflow_memory_links_memory_id", table_name="workflow_memory_links"
    )
    op.drop_index(
        "ix_workflow_memory_links_workflow_id",
        table_name="workflow_memory_links",
    )
    op.drop_table("workflow_memory_links")

    op.drop_index(
        "ix_task_memory_links_memory_id", table_name="task_memory_links"
    )
    op.drop_index(
        "ix_task_memory_links_task_id", table_name="task_memory_links"
    )
    op.drop_table("task_memory_links")
