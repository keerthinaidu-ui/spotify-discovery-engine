"""make_raw_id_unique

Revision ID: 4a0e70f072e0
Revises: 7ea4eab3e90a
Create Date: 2026-06-21 20:31:49.814547

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4a0e70f072e0"
down_revision: Union[str, Sequence[str], None] = "7ea4eab3e90a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_feedback_items_raw_id", table_name="feedback_items")
    op.create_index(op.f("ix_feedback_items_raw_id"), "feedback_items", ["raw_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_feedback_items_raw_id", table_name="feedback_items")
    op.create_index(op.f("ix_feedback_items_raw_id"), "feedback_items", ["raw_id"], unique=False)
