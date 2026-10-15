"""Initial project, policy, run and evidence schema."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None


def identity():
    return [sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)]


def project():
    return sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False, index=True)


def upgrade():
    op.create_table('projects', *identity(), sa.Column('name', sa.String(120), nullable=False))
    op.create_table('environments', *identity(), project(), sa.Column('name', sa.String(120), nullable=False), sa.Column('target', sa.String(255), nullable=False), sa.Column('build_id', sa.String(120), nullable=False))
    op.create_table('credential_references', *identity(), project(), sa.Column('reference', sa.String(120), nullable=False))
    op.create_table('scan_policies', *identity(), project(), sa.Column('environment_id', sa.String(36), sa.ForeignKey('environments.id'), nullable=False), sa.Column('credential_reference_id', sa.String(36), sa.ForeignKey('credential_references.id'), nullable=False), sa.Column('request_limit', sa.Integer(), nullable=False), sa.Column('timeout_seconds', sa.Integer(), nullable=False), sa.Column('test_id', sa.String(120), nullable=False))
    op.create_table('scan_runs', *identity(), project(), sa.Column('policy_id', sa.String(36), sa.ForeignKey('scan_policies.id'), nullable=False), sa.Column('status', sa.String(30), nullable=False, index=True), sa.Column('stage', sa.String(120), nullable=False), sa.Column('snapshot', sa.JSON(), nullable=False), sa.Column('cancel_requested', sa.Boolean(), nullable=False), sa.Column('lease_until', sa.DateTime(timezone=True)), sa.Column('finished_at', sa.DateTime(timezone=True)), sa.Column('retest_of', sa.String(36)))
    op.create_table('test_executions', *identity(), project(), sa.Column('run_id', sa.String(36), sa.ForeignKey('scan_runs.id'), nullable=False, unique=True), sa.Column('test_id', sa.String(120), nullable=False), sa.Column('test_version', sa.String(30), nullable=False), sa.Column('outcome', sa.String(30), nullable=False), sa.Column('expected', sa.Text(), nullable=False), sa.Column('actual', sa.Text(), nullable=False))
    op.create_table('findings', *identity(), project(), sa.Column('run_id', sa.String(36), sa.ForeignKey('scan_runs.id'), nullable=False, unique=True), sa.Column('title', sa.String(255), nullable=False), sa.Column('severity', sa.String(20), nullable=False), sa.Column('verification', sa.String(40), nullable=False), sa.Column('lifecycle', sa.String(40), nullable=False), sa.Column('recommendation', sa.Text(), nullable=False))
    with op.batch_alter_table('scan_runs') as batch:
        batch.create_foreign_key('fk_run_retest', 'findings', ['retest_of'], ['id'])
    op.create_table('evidence', *identity(), project(), sa.Column('run_id', sa.String(36), sa.ForeignKey('scan_runs.id'), nullable=False, unique=True), sa.Column('content', sa.JSON(), nullable=False), sa.Column('sha256', sa.String(64), nullable=False))


def downgrade():
    op.drop_table('evidence')
    with op.batch_alter_table('scan_runs') as batch:
        batch.drop_constraint('fk_run_retest', type_='foreignkey')
    for table in ['findings', 'test_executions', 'scan_runs', 'scan_policies', 'credential_references', 'environments', 'projects']:
        op.drop_table(table)
