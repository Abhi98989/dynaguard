"""Strict, data-only project contracts. No commands or inline credentials."""
import ipaddress
from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


def safe_path(value):
    p = urlsplit(value)
    if not value.startswith('/') or value.startswith('//') or p.scheme or p.netloc or p.fragment:
        raise ValueError('Use an origin-relative path without a fragment')
    if any(c in value for c in ('\\', '\r', '\n', '\x00')) or '%' in p.path or '..' in p.path.split('/'):
        raise ValueError('Encoded or ambiguous paths are not supported')
    return value


class Check(Strict):
    path: str
    expected: dict[str, str | int | bool] = Field(min_length=1, max_length=20)
    _path = field_validator('path')(safe_path)


class Identity(Strict):
    kind: Literal['anonymous', 'bearer', 'json_login'] = 'anonymous'
    token_env: str | None = None
    login_path: str | None = None
    username: str | None = None
    username_field: str = 'username'
    password_field: str = 'password'
    password_env: str | None = None
    token_field: str = 'access_token'
    session: Literal['bearer', 'cookie'] = 'bearer'
    auth_check: Check | None = None

    @model_validator(mode='after')
    def valid_identity(self):
        if self.kind != 'anonymous' and not self.auth_check:
            raise ValueError('Authenticated identities require an auth_check')
        if self.kind == 'bearer' and not self.token_env:
            raise ValueError('Bearer identities require token_env')
        if self.kind == 'json_login':
            if not all((self.login_path, self.username, self.password_env)):
                raise ValueError('JSON login requires path, username and password_env')
            safe_path(self.login_path)
        return self


class PermissionTest(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,80}$')
    title: str = Field(min_length=1, max_length=160)
    authorized_identity: str
    probe_identity: str
    resource: Check
    severity: Literal['medium', 'high', 'critical'] = 'high'
    recommendation: str = 'Enforce server-side authorization for this resource and retain this test as a regression check.'


class Target(Strict):
    origin: str
    pinned_ips: list[str] = Field(min_length=1, max_length=16)
    allowed_paths: list[str] = Field(min_length=1, max_length=100)
    allow_private: bool = False

    @model_validator(mode='after')
    def valid_target(self):
        p = urlsplit(self.origin)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.path not in ('', '/') or p.query or p.fragment:
            raise ValueError('Target must be an HTTP(S) origin')
        self.origin = self.origin.rstrip('/')
        for value in self.pinned_ips:
            ip = ipaddress.ip_address(value)
            if ip.is_link_local or ip.is_multicast or ip.is_unspecified or (not self.allow_private and not ip.is_global):
                raise ValueError('Private addresses need allow_private; link-local/multicast/unspecified addresses are prohibited')
        for value in self.allowed_paths:
            safe_path(value)
            if '?' in value:
                raise ValueError('Allowed paths must omit query strings')
        return self


class Limits(Strict):
    requests: int = Field(default=100, ge=1, le=1000)
    seconds: int = Field(default=120, ge=1, le=600)
    response_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    pages: int = Field(default=10, ge=1, le=50)


class ProjectConfig(Strict):
    version: Literal[1] = 1
    project: str = Field(min_length=1, max_length=120)
    build_id: str = Field(min_length=1, max_length=120)
    target: Target
    identities: dict[str, Identity] = Field(min_length=1, max_length=20)
    tests: list[PermissionTest] = Field(default_factory=list, max_length=100)
    limits: Limits = Field(default_factory=Limits)
    discovery_paths: list[str] = Field(default_factory=list, max_length=50)
    discovery_identity: str | None = None

    @model_validator(mode='after')
    def references(self):
        if len({t.id for t in self.tests}) != len(self.tests):
            raise ValueError('Test IDs must be unique')
        for test in self.tests:
            if test.authorized_identity not in self.identities or test.probe_identity not in self.identities:
                raise ValueError('Test identity not defined')
            if test.authorized_identity == test.probe_identity:
                raise ValueError('Use distinct authorized and probe identities')
            if self.identities[test.authorized_identity].kind == 'anonymous':
                raise ValueError('The authorized baseline must use an authenticated identity')
        for path in self.discovery_paths:
            safe_path(path)
        if self.discovery_identity and self.discovery_identity not in self.identities:
            raise ValueError('Discovery identity not defined')
        return self
