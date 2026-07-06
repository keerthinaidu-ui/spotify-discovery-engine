"""add voc columns

Revision ID: e4dd3c7687e8
Revises: 6b8269d4a8b7
Create Date: 2026-06-30 18:37:38.823828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4dd3c7687e8'
down_revision: Union[str, Sequence[str], None] = '6b8269d4a8b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('feedback_items')]
    
    if 'listening_job' not in columns:
        op.add_column('feedback_items', sa.Column('listening_job', sa.String(length=256), nullable=True))
    if 'desired_outcome' not in columns:
        op.add_column('feedback_items', sa.Column('desired_outcome', sa.String(length=256), nullable=True))
    if 'blocked_goal' not in columns:
        op.add_column('feedback_items', sa.Column('blocked_goal', sa.String(length=256), nullable=True))
    if 'root_cause' not in columns:
        op.add_column('feedback_items', sa.Column('root_cause', sa.Text(), nullable=True))
    if 'user_segment_signals' not in columns:
        op.add_column('feedback_items', sa.Column('user_segment_signals', sa.Text(), nullable=True))
    if 'recommendation_pain_type' not in columns:
        op.add_column('feedback_items', sa.Column('recommendation_pain_type', sa.String(length=128), nullable=True))
    if 'evidence_quote' not in columns:
        op.add_column('feedback_items', sa.Column('evidence_quote', sa.Text(), nullable=True))
        
    indexes = [idx['name'] for idx in inspector.get_indexes('feedback_items')]
    if 'ix_feedback_items_recommendation_pain_type' not in indexes:
        op.create_index(op.f('ix_feedback_items_recommendation_pain_type'), 'feedback_items', ['recommendation_pain_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('feedback_items')]
    indexes = [idx['name'] for idx in inspector.get_indexes('feedback_items')]
    
    if 'ix_feedback_items_recommendation_pain_type' in indexes:
        op.drop_index(op.f('ix_feedback_items_recommendation_pain_type'), table_name='feedback_items')
        
    if 'evidence_quote' in columns:
        op.drop_column('feedback_items', 'evidence_quote')
    if 'recommendation_pain_type' in columns:
        op.drop_column('feedback_items', 'recommendation_pain_type')
    if 'user_segment_signals' in columns:
        op.drop_column('feedback_items', 'user_segment_signals')
    if 'root_cause' in columns:
        op.drop_column('feedback_items', 'root_cause')
    if 'blocked_goal' in columns:
        op.drop_column('feedback_items', 'blocked_goal')
    if 'desired_outcome' in columns:
        op.drop_column('feedback_items', 'desired_outcome')
    if 'listening_job' in columns:
        op.drop_column('feedback_items', 'listening_job')
