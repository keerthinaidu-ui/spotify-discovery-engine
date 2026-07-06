"""add_rating_index_to_feedback_items

Revision ID: 7203be27018f
Revises: 4a0e70f072e0
Create Date: 2026-06-21 23:48:48.752504

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7203be27018f"
down_revision: Union[str, Sequence[str], None] = "4a0e70f072e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        op.f("ix_feedback_items_rating_or_score"),
        "feedback_items",
        ["rating_or_score"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_feedback_items_rating_or_score"), table_name="feedback_items")
