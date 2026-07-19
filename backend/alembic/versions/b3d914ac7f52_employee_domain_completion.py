"""Sprint 18.2A: employee configuration, capabilities, permissions, activity, assignments

Adds first-class configuration columns to ``employees`` and the four tables the
completed domain needs. Existing employees are preserved and backfilled:

* Configuration columns are added with server defaults, so every existing row
  gets a valid, conservative configuration (balanced autonomy, professional
  tone, sequential execution, medium priority, approval required).
* ``status`` is untouched. Every existing row already holds ``'draft'``, which
  is a member of the new ``EmployeeStatus`` vocabulary, so no value migration
  is needed and no employee changes state.
* ``archived_at`` and ``deleted_at`` start null — nothing is retroactively
  archived or deleted.
* No column is dropped and no data is rewritten, so the change is reversible.

Revision ID: b3d914ac7f52
Revises: a1c7f2b9e408
Create Date: 2026-07-19 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3d914ac7f52"
down_revision: Union[str, Sequence[str], None] = "a1c7f2b9e408"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Configuration on employees --------------------------------------
    op.add_column(
        "employees",
        sa.Column(
            "autonomy", sa.String(length=50), nullable=False, server_default="balanced"
        ),
    )
    op.add_column(
        "employees",
        sa.Column(
            "tone", sa.String(length=50), nullable=False, server_default="professional"
        ),
    )
    op.add_column(
        "employees",
        sa.Column(
            "execution_mode",
            sa.String(length=50),
            nullable=False,
            server_default="sequential",
        ),
    )
    op.add_column(
        "employees",
        sa.Column(
            "priority", sa.String(length=50), nullable=False, server_default="medium"
        ),
    )
    op.add_column(
        "employees",
        sa.Column(
            "require_approval", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "employees",
        sa.Column("accent", sa.String(length=50), nullable=False, server_default="slate"),
    )
    op.add_column(
        "employees",
        sa.Column("glyph", sa.String(length=50), nullable=False, server_default="bot"),
    )

    # --- Lifecycle timestamps --------------------------------------------
    op.add_column(
        "employees",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Every list query filters on this, so it is indexed.
    op.create_index(
        op.f("ix_employees_deleted_at"), "employees", ["deleted_at"], unique=False
    )

    # --- Capabilities -----------------------------------------------------
    op.create_table(
        "employee_capabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "capability", name="uq_employee_capability"),
    )
    op.create_index(
        op.f("ix_employee_capabilities_employee_id"),
        "employee_capabilities",
        ["employee_id"],
        unique=False,
    )

    # --- Permissions ------------------------------------------------------
    op.create_table(
        "employee_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=50), nullable=False),
        sa.Column(
            "level", sa.String(length=50), nullable=False, server_default="blocked"
        ),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "permission", name="uq_employee_permission"),
    )
    op.create_index(
        op.f("ix_employee_permissions_employee_id"),
        "employee_permissions",
        ["employee_id"],
        unique=False,
    )

    # --- Activity ---------------------------------------------------------
    op.create_table(
        "employee_activity_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_activity_events_employee_id"),
        "employee_activity_events",
        ["employee_id"],
        unique=False,
    )

    # --- Assignments ------------------------------------------------------
    op.create_table(
        "employee_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column(
            "priority", sa.String(length=50), nullable=False, server_default="medium"
        ),
        sa.Column(
            "execution_mode",
            sa.String(length=50),
            nullable=False,
            server_default="sequential",
        ),
        sa.Column("dependency_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id", "workflow_id", name="uq_employee_assignment_workflow"
        ),
    )
    op.create_index(
        op.f("ix_employee_assignments_employee_id"),
        "employee_assignments",
        ["employee_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_employee_assignments_employee_id"), table_name="employee_assignments"
    )
    op.drop_table("employee_assignments")

    op.drop_index(
        op.f("ix_employee_activity_events_employee_id"),
        table_name="employee_activity_events",
    )
    op.drop_table("employee_activity_events")

    op.drop_index(
        op.f("ix_employee_permissions_employee_id"), table_name="employee_permissions"
    )
    op.drop_table("employee_permissions")

    op.drop_index(
        op.f("ix_employee_capabilities_employee_id"), table_name="employee_capabilities"
    )
    op.drop_table("employee_capabilities")

    op.drop_index(op.f("ix_employees_deleted_at"), table_name="employees")
    op.drop_column("employees", "deleted_at")
    op.drop_column("employees", "archived_at")
    op.drop_column("employees", "glyph")
    op.drop_column("employees", "accent")
    op.drop_column("employees", "require_approval")
    op.drop_column("employees", "priority")
    op.drop_column("employees", "execution_mode")
    op.drop_column("employees", "tone")
    op.drop_column("employees", "autonomy")

