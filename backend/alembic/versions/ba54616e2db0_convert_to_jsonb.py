"""convert_to_jsonb

Revision ID: ba54616e2db0
Revises: e4dd3c7687e8
Create Date: 2026-06-30 19:31:15.278865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ba54616e2db0'
down_revision: Union[str, Sequence[str], None] = 'e4dd3c7687e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if we are running against PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        import json
        
        # 1. Mandatory Data Audit & Repair before altering columns
        def audit_and_repair(connection, table, column):
            rows = connection.execute(sa.text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL")).fetchall()
            malformed_count = 0
            total_count = len(rows)
            if total_count == 0:
                return
            
            for row_id, val in rows:
                if not val:
                    continue
                if isinstance(val, (dict, list)):
                    continue
                try:
                    json.loads(val)
                except Exception:
                    # Attempt heuristic repair by replacing single quotes with double quotes
                    cleaned_val = val.strip()
                    try:
                        repaired_str = cleaned_val.replace("'", '"')
                        json.loads(repaired_str)
                        connection.execute(
                            sa.text(f"UPDATE {table} SET {column} = :val WHERE id = :id"),
                            {"val": repaired_str, "id": row_id}
                        )
                        continue
                    except Exception:
                        pass
                    
                    # Unrepairable rows: nullify to prevent type conversion crash (quarantine log printed)
                    malformed_count += 1
                    connection.execute(
                        sa.text(f"UPDATE {table} SET {column} = NULL WHERE id = :id"),
                        {"id": row_id}
                    )
                    print(f"[AUDIT WARNING] Malformed JSON in {table}.{column} for ID {row_id} was unrepairable and nullified. Original: {val!r}")
            
            if malformed_count > 0:
                error_rate = malformed_count / total_count
                print(f"[AUDIT] Column {table}.{column} completed with {malformed_count} malformed rows. Error rate: {error_rate:.2%}")
                if error_rate > 0.01:
                    raise Exception(f"Migration aborted: Column {table}.{column} malformed rate ({error_rate:.2%}) exceeds 1.0% limit.")

        # Run mandatory audit on all JSON columns
        connection = bind.connect() if hasattr(bind, 'connect') else bind
        audit_and_repair(connection, 'feedback_items', 'topics')
        audit_and_repair(connection, 'feedback_items', 'unmet_needs')
        audit_and_repair(connection, 'feedback_items', 'user_segment_signals')
        audit_and_repair(connection, 'feedback_items', 'analysis_evidence')
        audit_and_repair(connection, 'analysis_results', 'payload_json')

        # 2. Type Conversion with USING clause and default/null handling
        op.alter_column('feedback_items', 'topics',
                        type_=postgresql.JSONB(astext_type=sa.Text()),
                        postgresql_using="topics::jsonb",
                        nullable=True)
        op.alter_column('feedback_items', 'unmet_needs',
                        type_=postgresql.JSONB(astext_type=sa.Text()),
                        postgresql_using="unmet_needs::jsonb",
                        nullable=True)
        op.alter_column('feedback_items', 'user_segment_signals',
                        type_=postgresql.JSONB(astext_type=sa.Text()),
                        postgresql_using="user_segment_signals::jsonb",
                        nullable=True)
        op.alter_column('feedback_items', 'analysis_evidence',
                        type_=postgresql.JSONB(astext_type=sa.Text()),
                        postgresql_using="analysis_evidence::jsonb",
                        nullable=True)
        op.alter_column('analysis_results', 'payload_json',
                        type_=postgresql.JSONB(astext_type=sa.Text()),
                        postgresql_using="payload_json::jsonb",
                        nullable=True)

        # 2. Manual GIN Index creation (whole-column indexes for containment queries)
        op.execute("CREATE INDEX ix_feedback_items_topics_gin ON feedback_items USING gin (topics)")
        op.execute("CREATE INDEX ix_feedback_items_unmet_needs_gin ON feedback_items USING gin (unmet_needs)")
        op.execute("CREATE INDEX ix_feedback_items_user_segment_signals_gin ON feedback_items USING gin (user_segment_signals)")
        op.execute("CREATE INDEX ix_feedback_items_analysis_evidence_gin ON feedback_items USING gin (analysis_evidence)")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # 1. Drop Manual GIN Indexes
        op.execute("DROP INDEX IF EXISTS ix_feedback_items_topics_gin")
        op.execute("DROP INDEX IF EXISTS ix_feedback_items_unmet_needs_gin")
        op.execute("DROP INDEX IF EXISTS ix_feedback_items_user_segment_signals_gin")
        op.execute("DROP INDEX IF EXISTS ix_feedback_items_analysis_evidence_gin")

        # 2. Revert JSONB columns back to TEXT using USING clause
        op.alter_column('feedback_items', 'topics',
                        type_=sa.Text(),
                        postgresql_using="topics::text")
        op.alter_column('feedback_items', 'unmet_needs',
                        type_=sa.Text(),
                        postgresql_using="unmet_needs::text")
        op.alter_column('feedback_items', 'user_segment_signals',
                        type_=sa.Text(),
                        postgresql_using="user_segment_signals::text")
        op.alter_column('feedback_items', 'analysis_evidence',
                        type_=sa.Text(),
                        postgresql_using="analysis_evidence::text")
        op.alter_column('analysis_results', 'payload_json',
                        type_=sa.Text(),
                        postgresql_using="payload_json::text")
