"""Synthetic local lab only. Deliberately vulnerable mode must never be exposed."""
import os
import secrets
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
MODE = os.environ.get('FIXTURE_MODE', 'fixed')
PASSWORD = os.environ.get('FIXTURE_PASSWORD', '')
TOKENS = {name: secrets.token_urlsafe(32) for name in ('alice', 'bob')}
RECORDS = {
    'record-a': {'id': 'record-a', 'owner_id': 'alice', 'project_id': 'project-a', 'marker': 'synthetic-alice-731'},
    'record-b': {'id': 'record-b', 'owner_id': 'bob', 'project_id': 'project-b', 'marker': 'synthetic-bob-942'},
}


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


@app.get('/health')
def health():
    return {'status': 'ok', 'build': f'fixture-{MODE}-v1'}


@app.post('/login')
def login(body: Login):
    if not PASSWORD or body.username not in TOKENS or not secrets.compare_digest(body.password, PASSWORD):
        return JSONResponse({'error': 'invalid_credentials'}, status_code=401)
    return {'access_token': TOKENS[body.username], 'user_id': body.username}


@app.get('/records/{record_id}')
def record(record_id: str, authorization: str = Header(default='')):
    user = next((user for user, token in TOKENS.items() if secrets.compare_digest(authorization, f'Bearer {token}')), None)
    if not user:
        return JSONResponse({'error': 'unauthenticated'}, status_code=401)
    record = RECORDS.get(record_id)
    if not record or (MODE != 'vulnerable' and record['owner_id'] != user):
        return JSONResponse({'error': 'forbidden'}, status_code=403)
    return record
