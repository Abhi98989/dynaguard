"""Persistence and cancellation adapter around the shared engine."""
import asyncio
from datetime import timedelta
from sqlalchemy import select
from dynaguard.config import ProjectConfig
from dynaguard.engine import verify
from dynaguard.discovery import discover
from .db import Session
from .models import EngineRun, now
from .engine_api import validate_deployment_scope


def claim():
    with Session() as session, session.begin():
        for row in session.scalars(select(EngineRun).where(EngineRun.status == 'running', EngineRun.lease_until < now()).with_for_update(skip_locked=True)):
            row.status, row.stage = 'incomplete', 'Worker lease expired; no passing result inferred'
        row = session.scalar(select(EngineRun).where(EngineRun.status == 'queued').order_by(EngineRun.created_at).with_for_update(skip_locked=True).limit(1))
        if row is None:
            return None
        row.status, row.stage = 'running', 'Starting shared engine'
        row.lease_until = now() + timedelta(seconds=40)
        return row.id, row.mode, row.config


async def execute(run_id, mode, contract):
    async def progress(stage):
        with Session() as session, session.begin():
            row = session.get(EngineRun, run_id)
            if row.cancel_requested or row.status != 'running':
                raise asyncio.CancelledError()
            row.stage = stage

    task = None
    report = None
    try:
        config = ProjectConfig.model_validate(contract)
        validate_deployment_scope(config)
        task = asyncio.create_task((verify if mode == 'verify' else discover)(config, progress))
        async with asyncio.timeout(config.limits.seconds + 5):
            while not task.done():
                await asyncio.sleep(0.1)
                with Session() as session, session.begin():
                    row = session.get(EngineRun, run_id)
                    if row.cancel_requested or row.status != 'running':
                        task.cancel()
                    else:
                        row.lease_until = now() + timedelta(seconds=40)
            report = await task
            status = report['status']
    except asyncio.CancelledError:
        status = 'cancelled'
    except Exception:
        status = 'incomplete'
    finally:
        if task and not task.done():
            task.cancel()
        if task:
            await asyncio.gather(task, return_exceptions=True)
    with Session() as session, session.begin():
        row = session.scalar(select(EngineRun).where(EngineRun.id == run_id).with_for_update())
        if row.status != 'running':
            return
        row.status = 'cancelled' if row.cancel_requested else status
        row.stage = 'Execution ' + row.status
        row.report = None if row.cancel_requested else report
        row.lease_until = None
