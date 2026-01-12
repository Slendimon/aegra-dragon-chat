"""Fix assistant index config size limit

Revision ID: 8f3a2b1c4d5e
Revises: d042a0ca1cb5
Create Date: 2026-01-12 17:09:59.000000

This migration fixes the issue where the idx_assistant_user_graph_config index
fails when the config JSONB field is too large (exceeds btree maximum row size).

The solution is to use a functional index with MD5 hash of the config instead
of indexing the config directly. This maintains uniqueness while avoiding size limits.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "8f3a2b1c4d5e"
down_revision = "d042a0ca1cb5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace idx_assistant_user_graph_config with functional index using MD5 hash."""
    # Drop the existing index that includes config directly
    op.execute(
        sa.text("DROP INDEX IF EXISTS idx_assistant_user_graph_config")
    )
    
    # Create a functional unique index using MD5 hash of config
    # This avoids the btree row size limit while maintaining uniqueness
    # JSONB normalizes key order internally, so config::text is consistent
    op.execute(
        sa.text("""
            CREATE UNIQUE INDEX idx_assistant_user_graph_config 
            ON assistant (user_id, graph_id, md5(config::text))
        """)
    )


def downgrade() -> None:
    """Revert to the original index with config directly (may fail if config is too large)."""
    # Drop the functional index
    op.execute(
        sa.text("DROP INDEX IF EXISTS idx_assistant_user_graph_config")
    )
    
    # Recreate the original index (may fail if config values are too large)
    op.create_index(
        "idx_assistant_user_graph_config",
        "assistant",
        ["user_id", "graph_id", "config"],
        unique=True,
    )
