"""Dashboard adapter for the same engine used by the local CLI."""
import json
from pathlib import Path
import tempfile
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from dynaguard.config import ProjectConfig
from dynaguard.source import scan_source
from . import config
from .models import EngineRun, Project
from .security import require_admin
from .db import Session

router = APIRouter(dependencies=[Depends(require_admin)])


def db():
    with Session() as session:
        yield session


def project(session, project_id):
    if session.get(Project, project_id) is None:
        raise HTTPException(404, 'Project not found')


def dump(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


class RunInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['verify', 'discover']
    config: ProjectConfig


def validate_deployment_scope(contract):
    pins = config.targets().get(contract.target.origin)
    if not pins or set(contract.target.pinned_ips) != set(pins):
        raise HTTPException(422, 'Origin and IP pins must match the deployment-owned TARGETS_JSON registry')
    for identity in contract.identities.values():
        for reference in (identity.password_env, identity.token_env):
            if reference and reference != 'FIXTURE_PASSWORD' and not reference.startswith('DYNAGUARD_TEST_'):
                raise HTTPException(422, 'Worker credential references must start with DYNAGUARD_TEST_')


@router.post('/projects/{project_id}/engine-runs', status_code=201)
def create_run(project_id: str, body: RunInput, session=Depends(db)):
    project(session, project_id)
    validate_deployment_scope(body.config)
    row = EngineRun(project_id=project_id, mode=body.mode, config=body.config.model_dump())
    session.add(row)
    session.commit()
    return dump(row)


@router.get('/projects/{project_id}/engine-runs')
def list_runs(project_id: str, session=Depends(db)):
    project(session, project_id)
    return [dump(r) for r in session.scalars(select(EngineRun).where(EngineRun.project_id == project_id).order_by(EngineRun.created_at.desc()).limit(100))]


@router.post('/engine-runs/{run_id}/cancel')
def cancel(run_id: str, session=Depends(db)):
    row = session.scalar(select(EngineRun).where(EngineRun.id == run_id).with_for_update())
    if not row:
        raise HTTPException(404, 'Run not found')
    if row.status in ('queued', 'running'):
        row.cancel_requested = True
        if row.status == 'queued':
            row.status = 'cancelled'
    session.commit()
    return dump(row)


@router.post('/projects/{project_id}/source-review', status_code=201)
async def source_review(project_id: str, request: Request, session=Depends(db)):
    project(session, project_id)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 2 * 1024 * 1024:
            raise HTTPException(413, 'Source upload limit is 2 MiB')
    try:
        files = json.loads(data)['files']
        if not isinstance(files, list) or not 1 <= len(files) <= 100:
            raise ValueError()
        with tempfile.TemporaryDirectory() as directory:
            seen = set()
            for item in files:
                path = Path(item['path'])
                if path.is_absolute() or '..' in path.parts or '\\' in item['path'] or not path.name or str(path) in seen:
                    raise ValueError()
                seen.add(str(path))
                destination = Path(directory) / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(item['content'], encoding='utf-8')
            report = scan_source(directory)
        report['project'] = session.get(Project, project_id).name
    except (ValueError, KeyError, TypeError, OSError):
        raise HTTPException(422, 'Invalid source file upload') from None
    row = EngineRun(project_id=project_id, mode='source', status=report['status'], stage='Source review completed', config={}, report=report)
    session.add(row)
    session.commit()
    return dump(row)


@router.get('/engine-template')
def template():
    from dynaguard.starter import starter
    value = starter()
    registered = config.targets()
    if registered:
        origin = next(iter(registered))
        value['target']['origin'] = origin
        value['target']['pinned_ips'] = registered[origin]
    return value


@router.get('/qa/skills')
def qa_skills():
    from dynaguard.qa import catalog
    return catalog()


from dynaguard.qa import QAProfile, build_plan
from dynaguard.qa_runner import QATestSuite, execute_qa_suite


@router.post('/projects/{project_id}/qa-plan', status_code=201)
def qa_plan(project_id: str, body: QAProfile, session=Depends(db)):
    project(session, project_id)
    try:
        report = build_plan(body)
    except ValueError:
        raise HTTPException(422, 'Unknown or inapplicable QA skill selection') from None
    row = EngineRun(project_id=project_id, mode='qa_plan', status='planned', stage='Plan created; no tests executed; release not evaluated', config=body.model_dump(), report=report)
    session.add(row)
    session.commit()
    return dump(row)


@router.post('/projects/{project_id}/qa-run', status_code=201)
def qa_run(project_id: str, body: QATestSuite, session=Depends(db)):
    project(session, project_id)
    try:
        report = execute_qa_suite(body)
    except Exception as e:
        raise HTTPException(422, f"QA execution failed: {str(e)}") from None
    row = EngineRun(
        project_id=project_id,
        mode='qa_execution',
        status=report.get('status', 'completed'),
        stage=f"QA test suite executed: {report['coverage']['passed']} passed, {report['coverage']['failed']} failed",
        config=body.model_dump(),
        report=report
    )
    session.add(row)
    session.commit()
    return dump(row)
