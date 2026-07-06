"""remove_reddit_table_and_column

Revision ID: ac19da346d3f
Revises: 27a6a2e68447
Create Date: 2026-06-26 23:02:28.318516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac19da346d3f'
down_revision: Union[str, Sequence[str], None] = '27a6a2e68447'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop raw_reddit table
    op.drop_table('raw_reddit')
    
    # 2. Drop subreddit column from feedback_items
    with op.batch_alter_table('feedback_items', schema=None) as batch_op:
        batch_op.drop_column('subreddit')


def downgrade() -> None:
    # 1. Recreate subreddit column in feedback_items
    with op.batch_alter_table('feedback_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subreddit', sa.String(length=128), nullable=True))
        
    # 2. Recreate raw_reddit table
    op.create_table('raw_reddit',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('item_type', sa.String(length=32), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('author', sa.String(length=256), nullable=True),
        sa.Column('subreddit', sa.String(length=128), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('permalink', sa.String(length=1024), nullable=True),
        sa.Column('reddit_id', sa.String(length=32), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_raw_reddit_reddit_id'), 'raw_reddit', ['reddit_id'], unique=False)
