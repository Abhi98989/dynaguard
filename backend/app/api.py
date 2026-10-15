import os
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from sqlalchemy import select
from . import config
from .db import Session
from .models import Project, Environment, CredentialReference, ScanPolicy, ScanRun, TestExecution, Finding, Evidence, now
from .security import COOKIE, check_password, rate_limit, require_admin, signer

app = FastAPI(title='DynaGuard local control plane', docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware('http')
async def boundaries(request: Request, call_next):
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        # Custom header cannot be sent by cross-origin forms; no CORS is enabled.
        if request.headers.get('x-dynaguard-client') != 'dashboard':
            return JSONResponse({'detail': 'Required client header missing'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Cross-site request blocked'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # Pydantic's default detail includes submitted values, including passwords.
    return JSONResponse({'detail': 'Invalid request fields'}, status_code=422)


def db():
    with Session() as session:
        yield session


def get(session, model, id):
    row = session.get(model, id)
    if row is None:
        raise HTTPException(404, 'Record not found')
    return row


def dump(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/auth/login')
def login(body: Login, request: Request, response: Response):
    rate_limit(request)
    valid = check_password(body.password)
    if body.username != 'admin' or not valid:
        raise HTTPException(401, 'Invalid administrator credentials')
    response.set_cookie(COOKIE, signer().dumps('administrator'), httponly=True, samesite='strict', secure=os.environ.get('COOKIE_SECURE') == 'true', max_age=28800, path='/')
    return {'username': 'admin'}


@app.post('/auth/logout')
def logout(response: Response):
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}


@app.get('/auth/me', dependencies=[Depends(require_admin)])
def me():
    return {'username': 'admin'}


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r'\S')


@app.get('/projects', dependencies=[Depends(require_admin)])
def projects(session=Depends(db)):
    return [dump(row) for row in session.scalars(select(Project).order_by(Project.created_at.desc()))]


@app.post('/projects', dependencies=[Depends(require_admin)], status_code=201)
def create_project(body: ProjectInput, session=Depends(db)):
    row = Project(name=body.name.strip())
    session.add(row)
    session.flush()
    session.add(CredentialReference(project_id=row.id, reference='fixture/alice'))
    session.commit()
    return dump(row)


@app.get('/targets', dependencies=[Depends(require_admin)])
def allowed_targets():
    return list(config.targets())


class EnvironmentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target: str = Field(max_length=255)
    build_id: str = Field(min_length=1, max_length=120)
    request_limit: int = Field(default=8, ge=4, le=12)
    timeout_seconds: int = Field(default=15, ge=2, le=30)


@app.post('/projects/{project_id}/environments', dependencies=[Depends(require_admin)], status_code=201)
def create_environment(project_id: str, body: EnvironmentInput, session=Depends(db)):
    get(session, Project, project_id)
    if body.target not in config.targets():
        raise HTTPException(422, 'Target is outside the deployment-owned fixture allowlist')
    environment = Environment(project_id=project_id, name=body.name, target=body.target, build_id=body.build_id)
    session.add(environment)
    session.flush()
    credential = session.scalar(select(CredentialReference).where(CredentialReference.project_id == project_id))
    policy = ScanPolicy(project_id=project_id, environment_id=environment.id, credential_reference_id=credential.id, request_limit=body.request_limit, timeout_seconds=body.timeout_seconds, test_id=config.TEST_ID)
    session.add(policy)
    session.commit()
    return {'environment': dump(environment), 'policy': dump(policy)}


@app.get('/projects/{project_id}', dependencies=[Depends(require_admin)])
def project_detail(project_id: str, session=Depends(db)):
    project = get(session, Project, project_id)
    result = {'project': dump(project)}
    for key, model in [('environments', Environment), ('policies', ScanPolicy), ('runs', ScanRun), ('findings', Finding)]:
        result[key] = [dump(row) for row in session.scalars(select(model).where(model.project_id == project_id).order_by(model.created_at.desc()))]
    return result


class RunInput(BaseModel):
    policy_id: str
    retest_of: str | None = None


@app.post('/projects/{project_id}/scan-runs', dependencies=[Depends(require_admin)], status_code=201)
def start_run(project_id: str, body: RunInput, session=Depends(db)):
    get(session, Project, project_id)
    policy = get(session, ScanPolicy, body.policy_id)
    if policy.project_id != project_id:
        raise HTTPException(404, 'Policy not found in project')
    if body.retest_of:
        finding = get(session, Finding, body.retest_of)
        if finding.project_id != project_id:
            raise HTTPException(404, 'Finding not found in project')
    environment = get(session, Environment, policy.environment_id)
    if environment.target not in config.targets():
        raise HTTPException(422, 'Target no longer allowed')
    credential = get(session, CredentialReference, policy.credential_reference_id)
    snapshot = {'target': environment.target, 'build_id': environment.build_id, 'environment_id': environment.id, 'credential_reference': credential.reference, 'request_limit': policy.request_limit, 'timeout_seconds': policy.timeout_seconds, 'test_id': config.TEST_ID, 'test_version': config.TEST_VERSION}
    run = ScanRun(project_id=project_id, policy_id=policy.id, snapshot=snapshot, retest_of=body.retest_of)
    session.add(run)
    session.flush()
    session.add(TestExecution(project_id=project_id, run_id=run.id, test_id=config.TEST_ID, test_version=config.TEST_VERSION, expected='Alice can read record-a. Alice cannot read Bob’s designated record-b. Authorized access still works after denial.'))
    session.commit()
    return dump(run)


@app.get('/scan-runs/{run_id}', dependencies=[Depends(require_admin)])
def run_detail(run_id: str, session=Depends(db)):
    run = get(session, ScanRun, run_id)
    execution = session.scalar(select(TestExecution).where(TestExecution.run_id == run_id))
    evidence = session.scalar(select(Evidence).where(Evidence.run_id == run_id))
    finding = session.scalar(select(Finding).where(Finding.run_id == run_id))
    return {'run': dump(run), 'execution': dump(execution), 'evidence': dump(evidence) if evidence else None, 'finding': dump(finding) if finding else None}


@app.post('/scan-runs/{run_id}/cancel', dependencies=[Depends(require_admin)])
def cancel(run_id: str, session=Depends(db)):
    run = session.scalar(select(ScanRun).where(ScanRun.id == run_id).with_for_update())
    if not run:
        raise HTTPException(404, 'Run not found')
    if run.status not in config.TERMINAL:
        run.cancel_requested = True
        if run.status == 'queued':
            run.status, run.stage, run.finished_at = 'cancelled', 'Cancelled before execution', now()
            execution = session.scalar(select(TestExecution).where(TestExecution.run_id == run_id))
            execution.outcome, execution.actual = 'cancelled', 'No requests executed'
        else:
            run.stage = 'Cancellation requested; waiting for worker acknowledgement'
        session.commit()
    return dump(run)


@app.get('/findings/{finding_id}', dependencies=[Depends(require_admin)])
def finding_detail(finding_id: str, session=Depends(db)):
    finding = get(session, Finding, finding_id)
    return {'finding': dump(finding), 'original': run_detail(finding.run_id, session), 'retests': [run_detail(run.id, session) for run in session.scalars(select(ScanRun).where(ScanRun.retest_of == finding_id).order_by(ScanRun.created_at.desc()))]}


@app.get('/scan-runs/{run_id}/report', dependencies=[Depends(require_admin)])
def report(run_id: str, session=Depends(db)):
    return run_detail(run_id, session)

# New shared-engine endpoints coexist with historical fixture-run endpoints.
from .engine_api import router as engine_router
app.include_router(engine_router)

from .audit_api import router as audit_router
app.include_router(audit_router)

