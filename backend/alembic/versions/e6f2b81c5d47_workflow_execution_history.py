"""Sprint 18.10: workflow execution history

Adds the three tables that remember what a run did: ``workflow_executions``,
``workflow_execution_steps`` and ``workflow_execution_logs``.

Purely additive:

* Three new tables. No existing table is altered, so every completed domain is
  untouched and the change is reversible by dropping them.
* Nothing here changes how a workflow runs. These record the Sprint 15.15
  runtime's output; the coordinator does not read them and was not modified.
* History is immutable, which is why no table has an ``updated_at``: a row is
  written when a run ends and never revised. A retry is a *new* execution whose
  ``retry_of_execution_id`` points at the run it repeats, so the original stays
  exactly as it happened.

Two column choices worth recording:

* ``duration_ms`` is stored rather than computed from the two timestamps. It is
  read on every history row, and an integer written once cannot drift with
  timezone handling the way a subtraction across sessions can.
* Outputs, step metadata and artifact descriptors are ``JSON`` rather than
  normalised. Their shape belongs to whichever capability produced them, nothing
  queries inside them, and rows-per-output would buy constraints no reader
  needs. This matches how ``workflows.graph`` is stored, and keeps the model
  portable across the SQLite used by tests and the PostgreSQL used in
  production.

Revision ID: e6f2b81c5d47
Revises: c4e1a7d92f36
Create Date: 2026-07-20 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6f2b81c5d47"
down_revision: Union[str, Sequence[str], None] = "c4e1a7d92f36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("total_step_count", sa.Integer(), nullable=False),
        sa.Column("completed_step_count", sa.Integer(), nullable=False),
        sa.Column("failed_step_id", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("retry_of_execution_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["retry_of_execution_id"], ["workflow_executions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_executions_workflow_id",
        "workflow_executions",
        ["workflow_id"],
    )
    op.create_index(
        "ix_workflow_executions_user_id", "workflow_executions", ["user_id"]
    )
    op.create_index(
        "ix_workflow_executions_retry_of_execution_id",
        "workflow_executions",
        ["retry_of_execution_id"],
    )
    # History is read newest-first, always scoped to one workflow. One composite
    # index serves that listing directly rather than sorting a filtered scan.
    op.create_index(
        "ix_workflow_executions_workflow_started",
        "workflow_executions",
        ["workflow_id", "started_at"],
    )

    op.create_table(
        "workflow_execution_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.String(length=255), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column("step_metadata", sa.JSON(), nullable=False),
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["workflow_executions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_execution_steps_execution_id",
        "workflow_execution_steps",
        ["execution_id"],
    )

    op.create_table(
        "workflow_execution_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("step_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["workflow_executions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_execution_logs_execution_id",
        "workflow_execution_logs",
        ["execution_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_workflow_execution_logs_execution_id", table_name="workflow_execution_logs"
    )
    op.drop_table("workflow_execution_logs")

    op.drop_index(
        "ix_workflow_execution_steps_execution_id",
        table_name="workflow_execution_steps",
    )
    op.drop_table("workflow_execution_steps")

    op.drop_index(
        "ix_workflow_executions_workflow_started", table_name="workflow_executions"
    )
    op.drop_index(
        "ix_workflow_executions_retry_of_execution_id",
        table_name="workflow_executions",
    )
    op.drop_index("ix_workflow_executions_user_id", table_name="workflow_executions")
    op.drop_index(
        "ix_workflow_executions_workflow_id", table_name="workflow_executions"
    )
    op.drop_table("workflow_executions")
