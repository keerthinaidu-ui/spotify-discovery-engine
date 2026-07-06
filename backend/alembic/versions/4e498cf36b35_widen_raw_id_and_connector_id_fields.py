"""widen_raw_id_and_connector_id_fields

Revision ID: 4e498cf36b35
Revises: 0fdf742ee0bb
Create Date: 2026-06-25 19:34:14.332573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e498cf36b35'
down_revision: Union[str, Sequence[str], None] = '0fdf742ee0bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # feedback_items: raw_id
    with op.batch_alter_table('feedback_items', schema=None) as batch_op:
        batch_op.alter_column('raw_id',
                   existing_type=sa.VARCHAR(length=36),
                   type_=sa.String(length=255),
                   existing_nullable=True)

    # raw_product_hunt_comments: ph_comment_id, ph_post_id
    with op.batch_alter_table('raw_product_hunt_comments', schema=None) as batch_op:
        batch_op.alter_column('ph_comment_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)
        batch_op.alter_column('ph_post_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)

    # raw_product_hunt_posts: ph_post_id
    with op.batch_alter_table('raw_product_hunt_posts', schema=None) as batch_op:
        batch_op.alter_column('ph_post_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)

    # raw_reviews: review_id
    with op.batch_alter_table('raw_reviews', schema=None) as batch_op:
        batch_op.alter_column('review_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)

    # raw_youtube_comments: comment_id, video_id, thread_id, parent_comment_id
    with op.batch_alter_table('raw_youtube_comments', schema=None) as batch_op:
        batch_op.alter_column('comment_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)
        batch_op.alter_column('video_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)
        batch_op.alter_column('thread_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)
        batch_op.alter_column('parent_comment_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=True)

    # raw_youtube_videos: video_id, channel_id
    with op.batch_alter_table('raw_youtube_videos', schema=None) as batch_op:
        batch_op.alter_column('video_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)
        batch_op.alter_column('channel_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=255),
                   existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # raw_youtube_videos
    with op.batch_alter_table('raw_youtube_videos', schema=None) as batch_op:
        batch_op.alter_column('channel_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)
        batch_op.alter_column('video_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)

    # raw_youtube_comments
    with op.batch_alter_table('raw_youtube_comments', schema=None) as batch_op:
        batch_op.alter_column('parent_comment_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=True)
        batch_op.alter_column('thread_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)
        batch_op.alter_column('video_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)
        batch_op.alter_column('comment_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)

    # raw_reviews
    with op.batch_alter_table('raw_reviews', schema=None) as batch_op:
        batch_op.alter_column('review_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)

    # raw_product_hunt_posts
    with op.batch_alter_table('raw_product_hunt_posts', schema=None) as batch_op:
        batch_op.alter_column('ph_post_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)

    # raw_product_hunt_comments
    with op.batch_alter_table('raw_product_hunt_comments', schema=None) as batch_op:
        batch_op.alter_column('ph_post_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)
        batch_op.alter_column('ph_comment_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=False)

    # feedback_items
    with op.batch_alter_table('feedback_items', schema=None) as batch_op:
        batch_op.alter_column('raw_id',
                   existing_type=sa.String(length=255),
                   type_=sa.VARCHAR(length=36),
                   existing_nullable=True)
