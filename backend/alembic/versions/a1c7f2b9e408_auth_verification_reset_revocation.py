"""Sprint 18.1A: email verification, password reset, token revocation, avatar

Adds the authentication columns to ``users``. Existing rows are preserved and
backfilled so no current user is locked out or nagged:

* ``email_verified`` is set to ``true`` for every pre-existing row — those
  accounts were created before verification existed, so treating them as
  unverified would regress them. New rows default to ``false``.
* ``token_epoch`` starts at ``0``, which is also the value assumed for tokens
  minted before this sprint, so already-issued JWTs stay valid.

Revision ID: a1c7f2b9e408
Revises: d59e7bedf3fa
Create Date: 2026-07-18 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c7f2b9e408"
down_revision: Union[str, Sequence[str], None] = "d59e7bedf3fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("avatar_url", sa.String(length=1024), nullable=True))

    # --- Email verification ---------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verification_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Password reset --------------------------------------------------
    op.add_column(
        "users", sa.Column("password_reset_hash", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Reset tokens are looked up by digest, so the column is indexed.
    op.create_index(
        op.f("ix_users_password_reset_hash"),
        "users",
        ["password_reset_hash"],
        unique=False,
    )

    # --- Token revocation ------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "token_epoch", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )

    # Grandfather existing accounts as verified — they predate verification.
    op.execute(
        "UPDATE users SET email_verified = true, email_verified_at = now() "
        "WHERE email_verified = false"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "token_epoch")
    op.drop_index(op.f("ix_users_password_reset_hash"), table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_hash")
    op.drop_column("users", "verification_expires_at")
    op.drop_column("users", "verification_token_hash")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "avatar_url")
