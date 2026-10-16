'use client';

import { useEffect, useState } from 'react';
import { useToast } from './toast';
import { Button, StatusBadge, EvidenceViewer } from '../components/ui';

type Report = {
  status: string;
  coverage: Record<string, number>;
  findings: Array<{ id: string; title: string; severity: string; verification: string }>;
  executions: Array<{ test_id: string; outcome: string; actual: string }>;
};

type Run = {
  id: string;
  mode: string;
  status: string;
  stage: string;
  report: Report | null;
};

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

export default function EnginePanel({ projectId }: { projectId: string }) {
  const { showToast } = useToast();
  const [config, setConfig] = useState('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    request('/engine-template')
      .then(v => setConfig(JSON.stringify(v, null, 2)))
      .catch(() => setError('Could not load template'));
  }, []);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const data = await request<Run[]>(`/projects/${projectId}/engine-runs`);
        if (active) setRuns(data);
      } catch {
        if (active) setError('Could not refresh shared engine runs');
      }
      if (active) timer = setTimeout(refresh, 2000);
    };
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [projectId]);

  async function start(mode: 'verify' | 'discover') {
    setBusy(true);
    setError('');
    try {
      await request(`/projects/${projectId}/engine-runs`, { mode, config: JSON.parse(config) });
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
    setBusy(true);
    setError('');
    try {
      const list = Array.from(files);
      if (list.length > 100 || list.reduce((total, f) => total + f.size, 0) > 1500000) {
        throw new Error('Select at most 100 text files totaling 1.5 MB. Use the CLI for larger repositories.');
      }
      const content = await Promise.all(
        list.map(async f => ({ path: f.webkitRelativePath || f.name, content: await f.text() }))
      );
      await request(`/projects/${projectId}/source-review`, { files: content });
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
    const url = URL.createObjectURL(new Blob([JSON.stringify(run.report, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `dynaguard-${run.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast(`Downloaded report for run ${run.id.slice(0, 8)}`, 'info');
  }

  return (
    <section>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2>Shared Engine · Configurable Application Tests</h2>
          <p className="muted" style={{ margin: '4px 0 0' }}>
            Configure target assertions, identity checks, and run read-permission validations using the shared engine.
          </p>
        </div>
      </div>

      <div style={{ background: 'var(--surface-muted)', border: '1px solid var(--border)', padding: 12, borderRadius: 'var(--radius-control)', margin: '14px 0', fontSize: 13 }}>
        <strong>Registration & Secret Note:</strong> Targets and IP pins must be registered by the deployment owner. Reference worker credentials by environment-variable name; never paste passwords or private tokens into test configuration.
      </div>

      {error && <p role="alert" className="error">{error}</p>}

      <details open style={{ margin: '14px 0' }}>
        <summary>Project Test Configuration</summary>
        <label htmlFor="shared-engine-config" style={{ marginTop: 8 }}>
          Test Configuration JSON
          <textarea
            id="shared-engine-config"
            aria-label="Project test configuration"
            rows={14}
            value={config}
            onChange={e => setConfig(e.target.value)}
            style={{ width: '100%', fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontSize: 12 }}
          />
        </label>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <Button
            variant="primary"
            disabled={busy}
            loading={busy}
            onClick={() => start('verify')}
          >
            Verify permissions
          </Button>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => start('discover')}
          >
            Discover live pages
          </Button>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Discovery requires optional browser worker dependencies and configured discovery_paths. Missing capabilities produce incomplete results.
        </p>
      </details>

      <details style={{ margin: '14px 0' }}>
        <summary>Review Selected Source Files</summary>
        <p className="muted" style={{ fontSize: 13, margin: '8px 0' }}>
          Upload selected text files (max 100 files, 1.5 MB total) for heuristic pattern review. Files are reviewed on the server and removed from temporary storage.
        </p>
        <label htmlFor="source-review-files">
          Select Source Files
          <input
            id="source-review-files"
            type="file"
            multiple
            disabled={busy}
            onChange={e => {
              void upload(e.target.files);
              e.target.value = '';
            }}
          />
        </label>
      </details>

      <h3 style={{ marginTop: 20 }}>Shared Engine Runs</h3>
      {runs.filter(r => r.mode !== 'audit').length === 0 ? (
        <p className="muted" style={{ margin: '8px 0' }}>No shared engine runs yet.</p>
      ) : (
        <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
          {runs
            .filter(r => r.mode !== 'audit')
            .map(run => (
              <details key={run.id} style={{ margin: 0 }}>
                <summary style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>
                    <strong>Mode: {run.mode}</strong> · ID: <code>{run.id.slice(0, 8)}</code>
                  </span>
                  <StatusBadge status={run.status} label={run.status} />
                </summary>

                <p style={{ fontSize: 13, margin: '8px 0' }}>
                  <strong>Stage: </strong>{run.stage}
                </p>

                {['queued', 'running'].includes(run.status) && (
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => request(`/engine-runs/${run.id}/cancel`, {}).catch(e => setError(e.message))}
                  >
                    Cancel Run
                  </Button>
                )}

                {run.report && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ background: 'var(--surface-muted)', padding: 10, borderRadius: 'var(--radius-control)', marginBottom: 10, fontSize: 13 }}>
                      <strong>{run.report.findings?.length || 0} findings recorded.</strong> "Completed" describes execution status, not a general security certification.
                    </div>

                    {run.report.executions?.map(e => (
                      <div key={e.test_id} className="row" style={{ padding: '6px 0', fontSize: 13 }}>
                        <span>
                          <strong>{e.test_id}</strong>: {e.actual}
                        </span>
                        <StatusBadge status={e.outcome} label={e.outcome} />
                      </div>
                    ))}

                    <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                      <Button size="sm" variant="secondary" onClick={() => download(run)}>
                        Download JSON report
                      </Button>
                    </div>

                    <EvidenceViewer
                      content={run.report}
                      summaryTitle="Raw engine report and coverage metrics"
                    />
                  </div>
                )}
              </details>
            ))}
        </div>
      )}
    </section>
  );
}
