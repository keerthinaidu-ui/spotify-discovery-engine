"""phase1 csv ingestion

Revision ID: 7ea4eab3e90a
Revises: 730156d05dab
Create Date: 2026-06-21 15:52:28.073339

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7ea4eab3e90a"
down_revision: Union[str, Sequence[str], None] = "730156d05dab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _unique_constraint_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "ingestion_runs"):
        op.create_table(
            "ingestion_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rows_read", sa.Integer(), nullable=False),
            sa.Column("rows_inserted", sa.Integer(), nullable=False),
            sa.Column("rows_skipped", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_ingestion_runs_source"), "ingestion_runs", ["source"], unique=False
        )

    raw_columns = _column_names(inspector, "raw_reviews")
    if "review_id" not in raw_columns:
        op.add_column("raw_reviews", sa.Column("review_id", sa.String(length=64), nullable=False))
    if "country" not in raw_columns:
        op.add_column("raw_reviews", sa.Column("country", sa.String(length=8), nullable=True))

    inspector = sa.inspect(bind)
    index_names = {index["name"] for index in inspector.get_indexes("raw_reviews")}
    if "ix_raw_reviews_review_id" not in index_names:
        op.create_index(
            op.f("ix_raw_reviews_review_id"), "raw_reviews", ["review_id"], unique=False
        )

    unique_names = _unique_constraint_names(sa.inspect(bind), "raw_reviews")
    if "uq_raw_reviews_platform_review_id" not in unique_names:
        with op.batch_alter_table("raw_reviews", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_raw_reviews_platform_review_id",
                ["platform", "review_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "raw_reviews"):
        unique_names = _unique_constraint_names(inspector, "raw_reviews")
        if "uq_raw_reviews_platform_review_id" in unique_names:
            with op.batch_alter_table("raw_reviews", schema=None) as batch_op:
                batch_op.drop_constraint("uq_raw_reviews_platform_review_id", type_="unique")

        index_names = {index["name"] for index in inspector.get_indexes("raw_reviews")}
        if "ix_raw_reviews_review_id" in index_names:
            op.drop_index(op.f("ix_raw_reviews_review_id"), table_name="raw_reviews")

        raw_columns = _column_names(inspector, "raw_reviews")
        if "country" in raw_columns:
            op.drop_column("raw_reviews", "country")
        if "review_id" in raw_columns:
            op.drop_column("raw_reviews", "review_id")

    if _table_exists(inspector, "ingestion_runs"):
        op.drop_index(op.f("ix_ingestion_runs_source"), table_name="ingestion_runs")
        op.drop_table("ingestion_runs")
