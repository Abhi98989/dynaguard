'use client';
import {useEffect, useState} from 'react';
import {useToast} from './toast';

type Report = {status: string; coverage: Record<string, number>; findings: Array<{id: string; title: string; severity: string; verification: string}>; executions: Array<{test_id: string; outcome: string; actual: string}>};
type Run = {id: string; mode: string; status: string; stage: string; report: Report | null};

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard'}, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

export default function EnginePanel({projectId}: {projectId: string}) {
  const {showToast} = useToast();
  const [config, setConfig] = useState('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {request('/engine-template').then(v => setConfig(JSON.stringify(v, null, 2))).catch(() => setError('Could not load template'));}, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try { const data = await request<Run[]>(`/projects/${projectId}/engine-runs`); if (active) setRuns(data); }
      catch { if (active) setError('Could not refresh shared engine runs'); }
      if (active) timer = setTimeout(refresh, 1500);
    };
    void refresh();
    return () => {active = false; clearTimeout(timer);};
  }, [projectId]);

  async function start(mode: 'verify' | 'discover') {
    setBusy(true); setError('');
    try {
      await request(`/projects/${projectId}/engine-runs`, {mode, config: JSON.parse(config)});
      showToast(`Engine ${mode} test run started`, 'success');
    } catch (e) {
      const msg = e instanceof SyntaxError ? 'Configuration must be valid JSON' : (e as Error).message;
      setError(msg);
      showToast(msg, 'error');
    } finally {
      setBusy(false);
    }
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true); setError('');
    try {
      const list = Array.from(files);
      if (list.length > 100 || list.reduce((total, f) => total + f.size, 0) > 1500000) throw new Error('Select at most 100 text files totaling 1.5 MB. Use the CLI for larger repositories.');
      const content = await Promise.all(list.map(async f => ({path: f.webkitRelativePath || f.name, content: await f.text()})));
      await request(`/projects/${projectId}/source-review`, {files: content});
      showToast(`${list.length} file(s) uploaded for heuristic source review`, 'success');
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      showToast(msg, 'error');
    } finally {
      setBusy(false);
    }
  }

  function download(run: Run) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(run.report, null, 2)], {type: 'application/json'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `dynaguard-${run.id}.json`; anchor.click(); URL.revokeObjectURL(url);
    showToast(`Downloaded report for run ${run.id.slice(0, 8)}`, 'info');
  }

  return <section>
    <h2>Shared engine · configurable application tests</h2>
    <p>Configure your registered target, identity checks and synthetic resource assertions. This uses the same engine as the terminal CLI.</p>
    <p className="muted">Targets and IP pins must be registered by the deployment owner. Reference worker credentials by environment-variable name; never paste passwords or tokens here.</p>
    {error && <p role="alert" className="error">{error}</p>}
    <label>Project test configuration<textarea aria-label="Project test configuration" rows={18} value={config} onChange={e => setConfig(e.target.value)} style={{width: '100%', fontFamily: 'monospace'}} /></label>
    <div className="row"><button className="primary" disabled={busy} onClick={() => start('verify')}>Verify permissions</button><button disabled={busy} onClick={() => start('discover')}>Discover live pages</button></div>
    <p className="muted">Discovery requires the optional browser worker dependencies and configured discovery_paths. Missing capabilities produce incomplete results.</p>
    <label>Review selected source files<input type="file" multiple disabled={busy} onChange={e => {void upload(e.target.files); e.target.value = '';}} /></label>
    <p className="muted">Selected file contents are sent to this DynaGuard server for heuristic review, then removed from temporary storage. Reports omit source snippets. CLI scans stay local.</p>
    <h3>Shared engine runs</h3>
    {runs.filter(r => r.mode !== 'audit').length === 0 && <p>No shared engine runs yet.</p>}
    {runs.filter(r => r.mode !== 'audit').map(run => <details key={run.id}><summary>{run.mode} · {run.status} · {run.id.slice(0, 8)}</summary><p>{run.stage}</p>
      {['queued', 'running'].includes(run.status) && <button onClick={() => request(`/engine-runs/${run.id}/cancel`, {}).catch(e => setError(e.message))}>Cancel</button>}
      {run.report && <><p>{run.report.findings?.length || 0} findings. Completed describes execution, not a security guarantee.</p><pre>{JSON.stringify(run.report.coverage, null, 2)}</pre>
        {run.report.executions?.map(e => <p key={e.test_id}><strong>{e.test_id}: {e.outcome}</strong> — {e.actual}</p>)}
        {run.report.findings?.map(f => <p key={f.id}>{f.severity} · {f.verification} · {f.title}</p>)}
        <button onClick={() => download(run)}>Download JSON report</button><details><summary>Evidence and limitations</summary><pre>{JSON.stringify(run.report, null, 2)}</pre></details></>}
    </details>)}
  </section>;
}
