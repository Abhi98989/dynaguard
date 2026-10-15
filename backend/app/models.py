import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Project(Identity, Base):
    __tablename__ = 'projects'
    name: Mapped[str] = mapped_column(String(120))


class Environment(Identity, Base):
    __tablename__ = 'environments'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    target: Mapped[str] = mapped_column(String(255))
    build_id: Mapped[str] = mapped_column(String(120))


class CredentialReference(Identity, Base):
    __tablename__ = 'credential_references'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    reference: Mapped[str] = mapped_column(String(120), default='fixture/alice')


class ScanPolicy(Identity, Base):
    __tablename__ = 'scan_policies'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    environment_id: Mapped[str] = mapped_column(ForeignKey('environments.id'))
    credential_reference_id: Mapped[str] = mapped_column(ForeignKey('credential_references.id'))
    request_limit: Mapped[int] = mapped_column(Integer, default=8)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15)
    test_id: Mapped[str] = mapped_column(String(120))


class ScanRun(Identity, Base):
    __tablename__ = 'scan_runs'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey('scan_policies.id'))
    status: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    stage: Mapped[str] = mapped_column(String(120), default='Waiting for worker')
    snapshot: Mapped[dict] = mapped_column(JSON)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retest_of: Mapped[str | None] = mapped_column(ForeignKey('findings.id', use_alter=True, name='fk_run_retest'), nullable=True)


class TestExecution(Identity, Base):
    __tablename__ = 'test_executions'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('scan_runs.id'), unique=True)
    test_id: Mapped[str] = mapped_column(String(120))
    test_version: Mapped[str] = mapped_column(String(30))
    outcome: Mapped[str] = mapped_column(String(30), default='pending')
    expected: Mapped[str] = mapped_column(Text)
    actual: Mapped[str] = mapped_column(Text, default='Not executed')


class Finding(Identity, Base):
    __tablename__ = 'findings'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('scan_runs.id'), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(20), default='high')
    verification: Mapped[str] = mapped_column(String(40), default='confirmed_bypass')
    lifecycle: Mapped[str] = mapped_column(String(40), default='open')
    recommendation: Mapped[str] = mapped_column(Text)


class Evidence(Identity, Base):
    __tablename__ = 'evidence'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('scan_runs.id'), unique=True)
    content: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))


class EngineRun(Identity, Base):
    """Versioned shared-engine reports contain many executions and findings per run."""
    __tablename__ = 'engine_runs'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    stage: Mapped[str] = mapped_column(String(160), default='Waiting for worker')
    config: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UploadToken(Identity, Base):
    """Scoped project upload token for CLI report ingestion."""
    __tablename__ = 'upload_tokens'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

