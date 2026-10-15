"""Add shared engine runs without changing historical fixture evidence."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'


def upgrade():
    op.create_table('engine_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('stage', sa.String(160), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('report', sa.JSON(), nullable=True),
        sa.Column('cancel_requested', sa.Boolean(), nullable=False),
        sa.Column('lease_until', sa.DateTime(timezone=True)))
    op.create_index('ix_engine_runs_project_id', 'engine_runs', ['project_id'])
    op.create_index('ix_engine_runs_status', 'engine_runs', ['status'])


def downgrade():
    op.drop_table('engine_runs')
