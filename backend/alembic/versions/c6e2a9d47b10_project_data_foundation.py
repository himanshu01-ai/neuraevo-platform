"""Project data foundation and optional conversation association.

Adds user-owned projects, immutable resume checkpoints, and a nullable project
reference on conversations. Existing conversations remain valid and are not
backfilled. Deleting a conversation removes its messages; PostgreSQL then sets
checkpoint source-message references to NULL while retaining the checkpoints.

Revision ID: c6e2a9d47b10
Revises: a3f8b7d64c21
Create Date: 2026-10-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6e2a9d47b10"
down_revision: Union[str, Sequence[str], None] = "a3f8b7d64c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create projects/checkpoints and link conversations optionally."""
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("technology_stack", sa.Text(), nullable=True),
        sa.Column("repository_reference", sa.String(length=2048), nullable=True),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("current_state", sa.Text(), nullable=True),
        sa.Column(
            "context_revision", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("context_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
        sa.CheckConstraint(
            "context_revision >= 0", name="ck_projects_context_revision"
        ),
        sa.CheckConstraint("version >= 1", name="ck_projects_version"),
        sa.CheckConstraint(
            "(context_revision = 0 AND context_approved_at IS NULL) OR "
            "(context_revision > 0 AND context_approved_at IS NOT NULL)",
            name="ck_projects_context_approval",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_projects_user_archived_created",
        "projects",
        ["user_id", "archived_at", "created_at"],
    )

    op.add_column("conversations", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_conversations_project_id_projects",
        "conversations",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_conversations_project_id", "conversations", ["project_id"])

    op.create_table(
        "project_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("decisions", sa.Text(), nullable=True),
        sa.Column("verified_progress", sa.Text(), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column("next_steps", sa.Text(), nullable=True),
        sa.Column("context_revision", sa.Integer(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence > 0", name="ck_checkpoints_sequence"),
        sa.CheckConstraint(
            "context_revision > 0", name="ck_checkpoints_context_revision"
        ),
        sa.CheckConstraint(
            "length(trim(coalesce(decisions, ''))) > 0 OR "
            "length(trim(coalesce(verified_progress, ''))) > 0 OR "
            "length(trim(coalesce(next_steps, ''))) > 0",
            name="ck_checkpoints_content",
        ),
        sa.CheckConstraint(
            "length(trim(coalesce(verified_progress, ''))) = 0 OR "
            "length(trim(coalesce(verification_note, ''))) > 0",
            name="ck_checkpoints_verification_note",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_checkpoints_request_fingerprint",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            name="fk_project_checkpoints_source_message_id_messages",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "request_id", name="uq_checkpoint_request"
        ),
        sa.UniqueConstraint(
            "project_id", "sequence", name="uq_checkpoint_sequence"
        ),
    )
    op.create_index(
        "ix_checkpoints_project_created",
        "project_checkpoints",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_project_checkpoints_source_message_id",
        "project_checkpoints",
        ["source_message_id"],
    )


def downgrade() -> None:
    """Remove the project foundation (destructively deletes project data)."""
    op.drop_index(
        "ix_project_checkpoints_source_message_id",
        table_name="project_checkpoints",
    )
    op.drop_index(
        "ix_checkpoints_project_created", table_name="project_checkpoints"
    )
    op.drop_table("project_checkpoints")
    op.drop_index("ix_conversations_project_id", table_name="conversations")
    op.drop_constraint(
        "fk_conversations_project_id_projects",
        "conversations",
        type_="foreignkey",
    )
    op.drop_column("conversations", "project_id")
    op.drop_index("ix_projects_user_archived_created", table_name="projects")
    op.drop_table("projects")

