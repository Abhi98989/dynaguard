'use client';

import EnginePanel from './engine-panel';
import AuditPanel from './audit-panel';
import QAPanel from './qa-panel';
import { useToast } from './toast';

import { FormEvent, useCallback, useEffect, useState } from 'react';

type Project = {id: string; name: string};
type Environment = {id: string; name: string; target: string; build_id: string};
type Policy = {id: string; environment_id: string};
type Run = {id: string; status: string; stage: string; created_at: string; retest_of: string | null; snapshot: {target: string; build_id: string; test_version: string}};
type Finding = {id: string; title: string; lifecycle: string; severity: string; recommendation: string; verification: string; run_id: string};
type Detail = {project: Project; environments: Environment[]; policies: Policy[]; runs: Run[]; findings: Finding[]};
type Result = {run: Run; execution: {outcome: string; expected: string; actual: string}; finding: Finding | null; evidence: {content: unknown; sha256: string} | null};
type FindingDetail = {finding: Finding; original: Result; retests: Result[]};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard'}, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || 'Request failed');
  return result;
}

const terminal = new Set(['completed', 'incomplete', 'cancelled']);

export default function Page() {
  const { showToast } = useToast();
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const [password, setPassword] = useState('');
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<Detail | null>(null);
  const [targets, setTargets] = useState<string[]>([]);
  const [target, setTarget] = useState('');
  const [projectName, setProjectName] = useState('');
  const [environmentName, setEnvironmentName] = useState('');
  const [build, setBuild] = useState('');
  const [runId, setRunId] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [findingId, setFindingId] = useState('');
  const [finding, setFinding] = useState<FindingDetail | null>(null);
  const [retestPolicy, setRetestPolicy] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const list = await api<Project[]>('/projects');
    setProjects(list);
    if (selected) setDetail(await api<Detail>(`/projects/${selected}`));
    if (runId) setResult(await api<Result>(`/scan-runs/${runId}`));
    if (findingId) setFinding(await api<FindingDetail>(`/findings/${findingId}`));
  }, [selected, runId, findingId]);

  useEffect(() => {api('/auth/me').then(() => setAuthenticated(true)).catch(() => {}).finally(() => setChecking(false));}, []);
  useEffect(() => {
    if (!authenticated) return;
    api<string[]>('/targets').then(list => {setTargets(list); setTarget(list[0] || '');}).catch(e => {
      setError(e.message);
      showToast(e.message, 'error');
    });
  }, [authenticated, showToast]);
  useEffect(() => {
    if (!authenticated) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {await refresh();} catch (e) {
        if (alive) {
          setError((e as Error).message);
        }
      }
      if (alive) timer = setTimeout(poll, 1000);
    };
    void poll();
    return () => {alive = false; clearTimeout(timer);};
  }, [authenticated, refresh]);

  async function action(work: () => Promise<void>) {
    setBusy(true); setError('');
    try {
      await work();
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      showToast(msg, 'error');
    } finally {
      setBusy(false);
    }
  }
  async function login(event: FormEvent) {
    event.preventDefault();
    await action(async () => {
      await api('/auth/login', {username: 'admin', password});
      setPassword('');
      setAuthenticated(true);
      showToast('Signed in successfully', 'success');
    });
  }
  async function scan(policy: string, retest?: string) {
    await action(async () => {
      const run = await api<Run>(`/projects/${selected}/scan-runs`, {policy_id: policy, retest_of: retest || null});
      setResult(null);
      setRunId(run.id);
      await refresh();
      showToast(retest ? 'Retest scan run scheduled' : 'Scan run scheduled', 'info');
    });
  }
  function chooseProject(id: string) {
    setSelected(id); setDetail(null); setRunId(''); setResult(null); setFindingId(''); setFinding(null); setRetestPolicy('');
  }

  return <main>
    <header><div><strong className="brand">DynaGuard</strong><span className="muted">Dynamatrix / internal validation</span></div>{authenticated && <button onClick={() => action(async () => {await api('/auth/logout', {}); setAuthenticated(false); setDetail(null); setResult(null); setFinding(null); showToast('Signed out successfully', 'info');})}>Sign out</button>}</header>
    <div className="intro"><span className="eyebrow">SOURCE REVIEW AND APPLICATION VERIFICATION</span><h1>Evidence before conclusions.</h1><p>Configure application tests, inspect evidence, and verify repairs.</p></div>
    {error && <div role="alert" className="error">{error}</div>}
    {checking ? <p>Checking session…</p> : !authenticated ? <section className="login"><h2>Administrator sign in</h2><form onSubmit={login}><label>Username<input value="admin" autoComplete="username" readOnly /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password" /></label><button disabled={busy} className="primary">Sign in</button></form><p className="muted">Use the administrator password created during local setup.</p></section> : <div className="workspace">
      <aside><h2>Projects</h2>{projects.length === 0 && <p className="muted">Create a project to begin.</p>}{projects.map(project => <button className={`project ${selected === project.id ? 'selected' : ''}`} key={project.id} onClick={() => chooseProject(project.id)}>{project.name}</button>)}<form onSubmit={e => {e.preventDefault(); action(async () => {const project = await api<Project>('/projects', {name: projectName}); setProjectName(''); chooseProject(project.id); showToast(`Project "${project.name}" created`, 'success');});}}><label>New project<input value={projectName} onChange={e => setProjectName(e.target.value)} placeholder="DynaFlow local pilot" required maxLength={120} /></label><button disabled={busy || !projectName.trim()}>Create project</button></form></aside>
      <div className="content">{!selected ? <section><h2>Start with a synthetic project</h2><p>Create a project, configure the vulnerable and fixed targets, then start the ownership test.</p><p className="muted">Coverage: one designated-record permission test. No real products have been scanned.</p></section> : !detail ? <p>Loading project…</p> : <>
        <AuditPanel key={'audit-' + selected} projectId={selected} />
        <QAPanel key={'qa-' + selected} projectId={selected} />
        <EnginePanel key={selected} projectId={selected} /><section><h2>{detail.project.name} · legacy fixture pilot</h2><p className="muted">Synthetic Alice → own record → Bob’s record → evidence → retest</p><h3>Local target environments</h3>{detail.environments.map(environment => {const policy = detail.policies.find(p => p.environment_id === environment.id); return <div className="row" key={environment.id}><div><strong>{environment.name}</strong><small>{environment.target} · {environment.build_id}</small></div><button disabled={busy || !policy} onClick={() => scan(policy!.id)}>Start scan</button></div>;})}
          <details open={detail.environments.length === 0}><summary>Configure a local target</summary><form className="grid" onSubmit={e => {e.preventDefault(); action(async () => {const envName = environmentName; await api(`/projects/${selected}/environments`, {name: environmentName, target, build_id: build}); setEnvironmentName(''); setBuild(''); await refresh(); showToast(`Environment "${envName}" configured`, 'success');});}}><label>Environment name<input required value={environmentName} onChange={e => setEnvironmentName(e.target.value)} placeholder="Vulnerable fixture" maxLength={120}/></label><label>Allowed target<select value={target} onChange={e => setTarget(e.target.value)}>{targets.map(t => <option key={t}>{t}</option>)}</select></label><label>Build identifier<input required value={build} onChange={e => setBuild(e.target.value)} placeholder="fixture-vulnerable-v1" maxLength={120}/></label><button disabled={busy || !target}>Save target & policy</button></form><p className="muted">Fixed ownership test · fixture/alice credential reference · 8 requests maximum · 15 second deadline</p></details>
        </section>
        <section><h2>Scan runs</h2>{detail.runs.length === 0 && <p className="muted">No tests have run yet.</p>}{detail.runs.map(run => <button className="row run" key={run.id} onClick={() => {setResult(null); setRunId(run.id);}}><span>{run.snapshot.build_id}{run.retest_of && ' · retest'}<small>{new Date(run.created_at).toLocaleString()}</small></span><span className={`badge ${run.status}`}>{run.status}</span></button>)}</section>
        {result && <section aria-live="polite"><div className="row"><h2>Run result <span className={`badge ${result.execution.outcome}`}>{result.execution.outcome}</span></h2>{!terminal.has(result.run.status) && <button disabled={busy} onClick={() => action(async () => {await api(`/scan-runs/${runId}/cancel`, {}); await refresh(); showToast('Scan run cancelled', 'info');})}>Cancel run</button>}</div><p>{result.run.stage}</p><dl><dt>Expected</dt><dd>{result.execution.expected}</dd><dt>Actual</dt><dd>{result.execution.actual}</dd><dt>Test version / build</dt><dd>{result.run.snapshot.test_version} / {result.run.snapshot.build_id}</dd></dl>{result.evidence && <details><summary>Masked evidence and integrity hash</summary><pre>{JSON.stringify(result.evidence.content, null, 2)}</pre><small className="hash">SHA-256 {result.evidence.sha256}</small></details>}<a href={`/api/scan-runs/${runId}/report`} target="_blank" rel="noreferrer">Open JSON report</a></section>}
        <section><h2>Findings</h2>{detail.findings.length === 0 ? <p className="muted">No confirmed findings recorded. Check run outcomes for incomplete or untested coverage.</p> : detail.findings.map(f => <button className="row run" key={f.id} onClick={() => {setFinding(null); setFindingId(f.id);}}><span>{f.title}<small>{f.verification} · {f.severity}</small></span><span className={`badge ${f.lifecycle}`}>{f.lifecycle.replaceAll('_', ' ')}</span></button>)}</section>
        {finding && <section><h2>{finding.finding.title}</h2><dl><dt>Expected</dt><dd>{finding.original.execution.expected}</dd><dt>Demonstrated behavior</dt><dd>{finding.original.execution.actual}</dd><dt>Suggested repair</dt><dd>{finding.finding.recommendation}</dd></dl><details><summary>Original masked evidence</summary><pre>{JSON.stringify(finding.original.evidence?.content, null, 2)}</pre></details><h3>Retest against a configured build</h3><div className="row"><select aria-label="Retest environment" value={retestPolicy} onChange={e => setRetestPolicy(e.target.value)}><option value="">Choose environment</option>{detail.policies.map(p => <option key={p.id} value={p.id}>{detail.environments.find(e => e.id === p.environment_id)?.name}</option>)}</select><button disabled={busy || !retestPolicy} onClick={() => scan(retestPolicy, finding.finding.id)}>Run retest</button></div>{finding.retests.map(retest => <div key={retest.run.id} className="row"><span>{retest.run.snapshot.build_id}<small>{retest.execution.actual}</small></span><span className={`badge ${retest.execution.outcome}`}>{retest.execution.outcome}</span></div>)}{finding.retests.length === 0 && <p className="muted">No retest yet.</p>}</section>}
      </>}</div>
    </div>}
    <footer>Results apply only to configured checks and targets. Untested components are not certified secure.</footer>
  </main>;
}
