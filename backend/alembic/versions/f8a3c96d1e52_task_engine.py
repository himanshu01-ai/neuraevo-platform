"""Sprint 19: Task Engine

Adds the two tables that make tasks first-class executable work managed by the
Workflow platform: ``tasks`` and ``task_workflow_executions``.

Purely additive:

* Two new tables. No existing table is altered, so every completed domain —
  workflows, execution history, employees — is untouched and the change is
  reversible by dropping them.
* A task's link to a run is a **link table** rather than a ``task_id`` column
  on ``workflow_executions``, precisely so the immutable Sprint 18.10 history
  tables stay exactly as they were. A task's execution history is a join,
  never a copy.

Column choices worth recording:

* ``employee_id`` and ``workflow_id`` are ``SET NULL`` on delete: deleting an
  employee or a workflow retires a collaborator, not the work. The task
  survives, unassigned or unshaped.
* ``execution_id`` is unique — a run is launched by at most one task — and
  cascades with the execution row, so history's own deletion rules keep the
  links honest.
* ``business_id`` (``TSK-1041``) is the id a person quotes, assigned
  sequentially per owner by the service.

Revision ID: f8a3c96d1e52
Revises: e6f2b81c5d47
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8a3c96d1e52"
down_revision: Union[str, Sequence[str], None] = "e6f2b81c5d47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
        sa.Column("business_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("execution_mode", sa.String(length=50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
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
            ["employee_id"], ["employees.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_employee_id", "tasks", ["employee_id"])
    op.create_index("ix_tasks_workflow_id", "tasks", ["workflow_id"])

    op.create_table(
        "task_workflow_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["workflow_executions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", name="uq_task_workflow_execution"),
    )
    op.create_index(
        "ix_task_workflow_executions_task_id",
        "task_workflow_executions",
        ["task_id"],
    )
    op.create_index(
        "ix_task_workflow_executions_execution_id",
        "task_workflow_executions",
        ["execution_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_task_workflow_executions_execution_id",
        table_name="task_workflow_executions",
    )
    op.drop_index(
        "ix_task_workflow_executions_task_id",
        table_name="task_workflow_executions",
    )
    op.drop_table("task_workflow_executions")

    op.drop_index("ix_tasks_workflow_id", table_name="tasks")
    op.drop_index("ix_tasks_employee_id", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
