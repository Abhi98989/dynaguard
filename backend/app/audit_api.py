"""Audit report ingestion and scoped project upload tokens."""
import hashlib
import json
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from .db import Session
from .models import EngineRun, Project, UploadToken, now
from .security import require_admin

router = APIRouter()


def db():
    with Session() as session:
        yield session


def dump(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


class CreateTokenInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.post('/projects/{project_id}/upload-tokens', dependencies=[Depends(require_admin)], status_code=201)
def create_upload_token(project_id: str, body: CreateTokenInput, session=Depends(db)):
    if session.get(Project, project_id) is None:
        raise HTTPException(404, 'Project not found')

    raw_token = 'dgt_' + secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    row = UploadToken(
        project_id=project_id,
        name=body.name.strip(),
        token_sha256=digest
    )
    session.add(row)
    session.commit()

    return {
        'id': row.id,
        'project_id': row.project_id,
        'name': row.name,
        'token': raw_token,
        'created_at': row.created_at.isoformat()
    }


@router.get('/projects/{project_id}/upload-tokens', dependencies=[Depends(require_admin)])
def list_upload_tokens(project_id: str, session=Depends(db)):
    if session.get(Project, project_id) is None:
        raise HTTPException(404, 'Project not found')

    rows = session.scalars(
        select(UploadToken)
        .where(UploadToken.project_id == project_id)
        .order_by(UploadToken.created_at.desc())
    ).all()

    return [{
        'id': r.id,
        'project_id': r.project_id,
        'name': r.name,
        'created_at': r.created_at.isoformat(),
        'last_used_at': r.last_used_at.isoformat() if r.last_used_at else None,
        'revoked_at': r.revoked_at.isoformat() if r.revoked_at else None,
    } for r in rows]


@router.post('/upload-tokens/{token_id}/revoke', dependencies=[Depends(require_admin)])
def revoke_upload_token(token_id: str, session=Depends(db)):
    row = session.get(UploadToken, token_id)
    if not row:
        raise HTTPException(404, 'Token not found')
    row.revoked_at = now()
    session.commit()
    return {'revoked': True, 'id': row.id}


@router.post('/ingest/audit-reports', status_code=201)
async def ingest_audit_report(request: Request, authorization: str = Header(None), session=Depends(db)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Authorization Bearer token required')

    raw_token = authorization[7:].strip()
    token_digest = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    token_row = session.scalar(
        select(UploadToken).where(
            UploadToken.token_sha256 == token_digest,
            UploadToken.revoked_at.is_(None)
        )
    )
    if not token_row:
        raise HTTPException(401, 'Invalid or revoked upload token')

    # Stream body with strict 5MB limit
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 5 * 1024 * 1024:
            raise HTTPException(413, 'Audit report payload exceeds 5 MB limit')

    try:
        data = json.loads(body.decode('utf-8'))
        if not isinstance(data, dict):
            raise ValueError()
        if data.get('schema_version') != 2 or data.get('mode') != 'audit':
            raise ValueError('Invalid audit report schema or mode')
        if not isinstance(data.get('findings'), list) or len(data['findings']) > 5000:
            raise ValueError('Findings list must not exceed 5000 items')
    except (ValueError, KeyError, UnicodeDecodeError):
        raise HTTPException(422, 'Invalid audit report JSON schema') from None

    # Update token last_used_at
    token_row.last_used_at = now()

    # Create EngineRun record bound to the token's project_id
    run_row = EngineRun(
        project_id=token_row.project_id,
        mode='audit',
        status=data.get('status', 'completed'),
        stage='Audit report ingested from CLI',
        config={'uploaded': True, 'stacks': data.get('stacks', [])},
        report=data
    )
    session.add(run_row)
    session.commit()

    return {
        'run_id': run_row.id,
        'project_id': run_row.project_id,
        'status': run_row.status,
        'findings_count': len(data['findings']),
        'summary': data.get('summary', {})
    }
