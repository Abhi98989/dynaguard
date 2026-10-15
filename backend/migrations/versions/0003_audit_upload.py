"""Add upload tokens for CLI audit ingestion."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'


def upgrade():
    op.create_table('upload_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('token_sha256', sa.String(64), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_upload_tokens_project_id', 'upload_tokens', ['project_id'])
    op.create_index('ix_upload_tokens_token_sha256', 'upload_tokens', ['token_sha256'], unique=True)


def downgrade():
    op.drop_table('upload_tokens')
