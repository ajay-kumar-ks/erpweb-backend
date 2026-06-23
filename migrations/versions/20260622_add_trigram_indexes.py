"""add trigram indexes for CRM text search

Revision ID: 20260622_trigram
Revises: 
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260622_trigram'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add pg_trgm extension then create GIN trigram indexes for substring searches
    conn = op.get_bind()
    try:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
    except Exception:
        # Not a Postgres-compatible DB or permission denied
        pass

    try:
        op.execute("CREATE INDEX IF NOT EXISTS idx_leads_title_trgm ON leads USING gin (title gin_trgm_ops);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_leads_assignee_trgm ON leads USING gin (assignee gin_trgm_ops);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_contacts_name_trgm ON contacts USING gin (name gin_trgm_ops);")
    except Exception:
        # Safe fallback: ignore if unsupported
        pass


def downgrade():
    try:
        op.execute("DROP INDEX IF EXISTS idx_leads_title_trgm;")
        op.execute("DROP INDEX IF EXISTS idx_leads_assignee_trgm;")
        op.execute("DROP INDEX IF EXISTS idx_contacts_name_trgm;")
    except Exception:
        pass
