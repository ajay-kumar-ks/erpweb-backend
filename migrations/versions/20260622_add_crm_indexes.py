"""add crm indexes

Revision ID: 20260622_add_crm_indexes
Revises: 
Create Date: 2026-06-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260622_add_crm_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = getattr(conn.dialect, 'name', '')

    # Prefer concurrent index creation on PostgreSQL to avoid locking
    if dialect == 'postgresql':
        with op.get_context().autocommit_block():
            op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_leads_pipeline_id ON leads (pipeline_id);")
            op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_leads_phase_id ON leads (phase_id);")
            op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_leads_assignee ON leads (assignee);")
            op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_leads_created_at ON leads (created_at);")
            op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_leads_value ON leads (value);")

            op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contacts_status ON contacts (status);")
            op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contacts_company_name ON contacts (company, name);")
    else:
        # Generic fallback for other DBs
        op.create_index('ix_leads_pipeline_id', 'leads', ['pipeline_id'])
        op.create_index('ix_leads_phase_id', 'leads', ['phase_id'])
        op.create_index('ix_leads_assignee', 'leads', ['assignee'])
        op.create_index('ix_leads_created_at', 'leads', ['created_at'])
        op.create_index('ix_leads_value', 'leads', ['value'])

        op.create_index('ix_contacts_status', 'contacts', ['status'])
        op.create_index('ix_contacts_company_name', 'contacts', ['company', 'name'])


def downgrade():
    conn = op.get_bind()
    dialect = getattr(conn.dialect, 'name', '')

    if dialect == 'postgresql':
        with op.get_context().autocommit_block():
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_leads_pipeline_id;")
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_leads_phase_id;")
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_leads_assignee;")
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_leads_created_at;")
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_leads_value;")

            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_contacts_status;")
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_contacts_company_name;")
    else:
        op.drop_index('ix_leads_pipeline_id', table_name='leads')
        op.drop_index('ix_leads_phase_id', table_name='leads')
        op.drop_index('ix_leads_assignee', table_name='leads')
        op.drop_index('ix_leads_created_at', table_name='leads')
        op.drop_index('ix_leads_value', table_name='leads')

        op.drop_index('ix_contacts_status', table_name='contacts')
        op.drop_index('ix_contacts_company_name', table_name='contacts')
