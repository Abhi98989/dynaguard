"""Separate trusted worker; fixed test catalog, no shell or dashboard-supplied code."""
import asyncio
import hashlib
import json
from datetime import timedelta
from sqlalchemy import select
from . import config
from .db import Session
from .models import ScanRun, TestExecution, Finding, Evidence, now
from .verification import verify
from . import engine_worker


def claim():
    with Session() as session, session.begin():
        run = session.scalar(select(ScanRun).where(ScanRun.status == 'queued').order_by(ScanRun.created_at).with_for_update(skip_locked=True).limit(1))
        if run is None:
            return None
        run.status, run.stage = 'running', 'Worker claimed run'
        run.lease_until = now() + timedelta(seconds=40)
        execution = session.scalar(select(TestExecution).where(TestExecution.run_id == run.id))
        execution.outcome = 'running'
        return run.id, dict(run.snapshot)


def reap():
    # Never automatically retry even this read-only test after an abandoned lease.
    with Session() as session, session.begin():
        for run in session.scalars(select(ScanRun).where(ScanRun.status == 'running', ScanRun.lease_until < now()).with_for_update(skip_locked=True)):
            run.status, run.stage, run.finished_at = 'incomplete', 'Worker lease expired; execution interrupted', now()
            execution = session.scalar(select(TestExecution).where(TestExecution.run_id == run.id))
            execution.outcome, execution.actual = 'incomplete', 'Worker disappeared before committing a result; no pass can be inferred.'


def finish(run_id, outcome, actual, evidence):
    with Session() as session, session.begin():
        run = session.scalar(select(ScanRun).where(ScanRun.id == run_id).with_for_update())
        if run.status != 'running':
            return
        if run.cancel_requested:
            outcome, actual = 'cancelled', 'Worker stopped; result is not a completed test'
        run.status = 'completed' if outcome in {'passed', 'failed'} else outcome
        run.stage, run.finished_at, run.lease_until = actual, now(), None
        execution = session.scalar(select(TestExecution).where(TestExecution.run_id == run_id))
        execution.outcome, execution.actual = outcome, actual
        document = {'test_id': config.TEST_ID, 'test_version': config.TEST_VERSION, 'build_id': run.snapshot['build_id'], 'target': run.snapshot['target'], 'recorded_at': now().isoformat(), **evidence}
        digest = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        session.add(Evidence(project_id=run.project_id, run_id=run.id, content=document, sha256=digest))
        if outcome == 'failed':
            session.add(Finding(project_id=run.project_id, run_id=run.id, title='Cross-owner access to designated synthetic record', recommendation='Enforce record ownership on the server before returning a record. Keep the authorized baseline and cross-owner denial as regression tests.'))
        if run.retest_of:
            original = session.get(Finding, run.retest_of)
            # Keep last conclusive result. Incomplete/cancelled retests remain visible in history.
            if outcome in {'passed', 'failed'}:
                original.lifecycle = 'verified_fixed' if outcome == 'passed' else 'open'


async def execute(run_id, snapshot, transport=None):
    evidence = {'steps': []}

    async def progress(stage):
        with Session() as session, session.begin():
            run = session.get(ScanRun, run_id)
            if run.cancel_requested or run.status != 'running':
                raise asyncio.CancelledError()
            run.stage = stage

    task = asyncio.create_task(verify(snapshot, progress, transport=transport, evidence=evidence))
    try:
        async with asyncio.timeout(snapshot['timeout_seconds'] + 1):
            while not task.done():
                await asyncio.sleep(0.1)
                with Session() as session, session.begin():
                    run = session.get(ScanRun, run_id)
                    if run.cancel_requested or run.status != 'running':
                        task.cancel()
                    else:
                        run.lease_until = now() + timedelta(seconds=40)
            outcome, actual, evidence = await task
    except asyncio.CancelledError:
        outcome, actual = 'cancelled', 'Worker stopped active HTTP work'
    except TimeoutError:
        outcome, actual = 'incomplete', 'Whole-test time limit exceeded'
    except Exception:
        # Do not log exception strings: transport exceptions can contain credentials.
        outcome, actual = 'incomplete', 'Worker could not complete the test'
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    finish(run_id, outcome, actual, evidence)


async def main():
    while True:
        try:
            reap()
            engine_job = engine_worker.claim()
            if engine_job:
                await engine_worker.execute(*engine_job)
            job = claim()
            if job:
                await execute(*job)
            else:
                await asyncio.sleep(0.5)
        except Exception:
            print('Worker control-plane operation failed; retrying without test replay', flush=True)
            await asyncio.sleep(2)


if __name__ == '__main__':
    asyncio.run(main())
