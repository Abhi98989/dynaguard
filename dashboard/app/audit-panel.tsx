'use client';

import { useState, useEffect, useCallback } from 'react';
import { useToast } from './toast';
import { Button, StatusBadge } from '../components/ui';

type Token = {
  id: string;
  project_id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

type Finding = {
  id: string;
  rule_id: string;
  tool: string;
  layer: string;
  title: string;
  severity: string;
  confidence: string;
  path: string | null;
  line: number | null;
  cwe: string | null;
  owasp: string | null;
  recommendation: string;
  evidence: string;
  is_new?: boolean;
};

type CoverageItem = {
  check: string;
  layer: string;
  tool: string;
  status: string;
  reason: string;
  items_count?: number;
};

type AuditReport = {
  schema_version: number;
  mode: string;
  project: string;
  created_at: string;
  status: string;
  stacks: string[];
  summary: Record<string, number>;
  by_layer: Record<string, number>;
  coverage: CoverageItem[];
  diff?: { new: number; unchanged: number; fixed: number };
  findings: Finding[];
  suppressed: number;
};

type EngineRun = {
  id: string;
  mode: string;
  status: string;
  stage: string;
  created_at: string;
  report: AuditReport | null;
};

async function req<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  let data: Record<string, unknown> = {};
  try {
    data = await response.json();
  } catch {
    data = { detail: response.statusText || 'Server responded with non-JSON format' };
  }
  if (!response.ok) throw new Error((data.detail as string) || 'Request failed');
  return data as T;
}

export default function AuditPanel({ projectId }: { projectId: string }) {
  const { showToast } = useToast();
  const [tokens, setTokens] = useState<Token[]>([]);
  const [runs, setRuns] = useState<EngineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<EngineRun | null>(null);
  const [newTokenName, setNewTokenName] = useState('');
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);

  const refreshTokens = useCallback(async () => {
    try {
      const data = await req<Token[]>(`/projects/${projectId}/upload-tokens`);
      setTokens(data);
    } catch {
      // ignore token fetch errors
    }
  }, [projectId]);

  const refreshRuns = useCallback(async () => {
    try {
      const data = await req<EngineRun[]>(`/projects/${projectId}/engine-runs`);
      const audits = data.filter(r => r.mode === 'audit');
      setRuns(audits);
      setSelectedRun(prev => {
        if (!prev) return audits[0] || null;
        const updated = audits.find(r => r.id === prev.id);
        return updated || audits[0] || null;
      });
    } catch {
      // ignore run fetch errors
    }
  }, [projectId]);

  useEffect(() => {
    void refreshTokens();
    void refreshRuns();
    const interval = setInterval(() => {
      void refreshRuns();
    }, 3000);
    return () => clearInterval(interval);
  }, [refreshTokens, refreshRuns]);

  async function generateToken(e: React.FormEvent) {
    e.preventDefault();
    if (!newTokenName.trim()) return;
    setBusy(true);
    try {
      const res = await req<{ token: string; name: string }>(`/projects/${projectId}/upload-tokens`, {
        name: newTokenName.trim()
      });
      setCreatedToken(res.token);
      setNewTokenName('');
      await refreshTokens();
      showToast(`Upload token "${res.name}" generated successfully`, 'success');
    } catch (err) {
      showToast((err as Error).message, 'error');
    } finally {
      setBusy(false);
    }
  }

  async function revokeToken(tokenId: string) {
    try {
      await req(`/upload-tokens/${tokenId}/revoke`, {});
      await refreshTokens();
      showToast('Upload token revoked', 'info');
    } catch (err) {
      showToast((err as Error).message, 'error');
    }
  }

  function downloadJson(run: EngineRun) {
    if (!run.report) return;
    const blob = new Blob([JSON.stringify(run.report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dynaguard-audit-${run.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('JSON report downloaded', 'info');
  }

  const report = selectedRun?.report;
  const filteredFindings = (report?.findings || []).filter(f => {
    if (filterSeverity !== 'all' && f.severity !== filterSeverity) return false;
    if (search) {
      const q = search.toLowerCase();
      const match =
        f.title.toLowerCase().includes(q) ||
        (f.path && f.path.toLowerCase().includes(q)) ||
        f.layer.toLowerCase().includes(q) ||
        f.rule_id.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  return (
    <section>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2>Comprehensive Project Audit & Code Scans</h2>
          <p className="muted" style={{ margin: '4px 0 0' }}>
            Perform deep code, dependency, database, and system architecture audits directly from the machine where your code lives.
          </p>
        </div>
      </div>

      {/* CLI Upload Token Section */}
      <details open={tokens.length === 0} style={{ margin: '16px 0' }}>
        <summary>CLI Upload Tokens & Terminal Instructions</summary>
        <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
          Upload tokens allow the local <code>dynaguard</code> CLI to securely upload audit reports without exposing passwords.
        </p>

        <form onSubmit={generateToken} style={{ display: 'flex', gap: 8, maxWidth: 460, margin: '12px 0' }}>
          <input
            placeholder="Token name (e.g. ci-cd or dev-laptop)"
            value={newTokenName}
            onChange={e => setNewTokenName(e.target.value)}
            required
            disabled={busy}
          />
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={busy || !newTokenName.trim()}
            loading={busy}
            style={{ flexShrink: 0 }}
          >
            Generate Token
          </Button>
        </form>

        {createdToken && (
          <div style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)', padding: 14, borderRadius: 'var(--radius-panel)', margin: '12px 0' }}>
            <strong style={{ color: 'var(--success-text)' }}>New Upload Token (Save this; it won't be shown again!):</strong>
            <pre style={{ background: 'white', color: 'var(--text)', border: '1px solid var(--border)', padding: 10, borderRadius: 'var(--radius-control)', margin: '8px 0', userSelect: 'all' }}>
              {createdToken}
            </pre>
            <small className="muted">To scan and upload from your local terminal:</small>
            <pre style={{ background: '#0f172a', color: '#f8fafc', padding: 10, borderRadius: 'var(--radius-control)', margin: '8px 0', overflowX: 'auto' }}>
{`# 1. Run audit
dynaguard audit --path /path/to/your/project --output audit.json

# 2. Upload report
export DYNAGUARD_UPLOAD_TOKEN="${createdToken}"
dynaguard upload --report audit.json --server https://dynaguard.dynamatrixsolution.live`}
            </pre>
          </div>
        )}

        {tokens.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <strong style={{ fontSize: 13 }}>Active Tokens ({tokens.length}):</strong>
            {tokens.map(t => (
              <div key={t.id} className="row" style={{ padding: '6px 0', fontSize: 13 }}>
                <div>
                  <strong>{t.name}</strong>
                  <small style={{ color: 'var(--text-secondary)' }}>
                    Created: {new Date(t.created_at).toLocaleDateString()}
                    {t.last_used_at ? ` · Used: ${new Date(t.last_used_at).toLocaleDateString()}` : ' · Never used'}
                    {t.revoked_at && ' · [REVOKED]'}
                  </small>
                </div>
                {!t.revoked_at && (
                  <Button size="sm" variant="danger" onClick={() => revokeToken(t.id)}>
                    Revoke
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </details>

      {/* Audit Runs Section */}
      <h3 style={{ marginTop: 20 }}>Audit Runs ({runs.length})</h3>
      {runs.length === 0 ? (
        <p className="muted" style={{ margin: '8px 0' }}>
          No audit runs ingested yet. Run <code>dynaguard audit</code> on your machine and upload the report.
        </p>
      ) : (
        <div style={{ display: 'grid', gap: 8, margin: '10px 0' }}>
          {runs.map(run => {
            const sum = run.report?.summary || {};
            const isSelected = selectedRun?.id === run.id;
            return (
              <div
                key={run.id}
                onClick={() => setSelectedRun(isSelected ? null : run)}
                style={{
                  border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-panel)',
                  padding: 12,
                  cursor: 'pointer',
                  background: isSelected ? 'var(--accent-subtle)' : 'var(--surface)',
                  transition: 'all 0.12s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <strong>{run.report?.project || 'Project Audit'}</strong>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 8 }}>
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    {sum.critical ? <StatusBadge status="critical" label={`${sum.critical} critical`} /> : null}
                    {sum.high ? <StatusBadge status="high" label={`${sum.high} high`} /> : null}
                    {sum.medium ? <StatusBadge status="medium" label={`${sum.medium} med`} /> : null}
                    <StatusBadge status="passed" label={run.status} />
                  </div>
                </div>

                {Array.isArray(run.report?.stacks) && run.report.stacks.length > 0 && (
                  <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {run.report.stacks.map(st => (
                      <span key={st} style={{ background: 'var(--surface-muted)', color: 'var(--text-secondary)', fontSize: 11, padding: '2px 6px', borderRadius: 'var(--radius-badge)' }}>
                        {st}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Selected Run Details */}
      {selectedRun && report && (
        <div style={{ marginTop: 24, borderTop: '1px solid var(--border)', paddingTop: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <h3>Audit Report Details</h3>
            <Button size="sm" variant="secondary" onClick={() => downloadJson(selectedRun)}>
              Download JSON Report
            </Button>
          </div>

          {/* Severity Metric Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 10, margin: '14px 0' }}>
            <div style={{ padding: 12, background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: 'var(--danger-text)' }}>{report.summary?.critical || 0}</div>
              <div style={{ fontSize: 11, color: 'var(--danger-text)' }}>Critical</div>
            </div>
            <div style={{ padding: 12, background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: '#be123c' }}>{report.summary?.high || 0}</div>
              <div style={{ fontSize: 11, color: '#be123c' }}>High</div>
            </div>
            <div style={{ padding: 12, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: 'var(--warning-text)' }}>{report.summary?.medium || 0}</div>
              <div style={{ fontSize: 11, color: 'var(--warning-text)' }}>Medium</div>
            </div>
            <div style={{ padding: 12, background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: 'var(--success-text)' }}>{(report.summary?.low || 0) + (report.summary?.info || 0)}</div>
              <div style={{ fontSize: 11, color: 'var(--success-text)' }}>Low / Info</div>
            </div>
          </div>

          {/* Coverage Table */}
          <details style={{ margin: '12px 0' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Coverage & Tool Verification Matrix ({report.coverage?.length || 0})</summary>
            <div style={{ overflowX: 'auto', marginTop: 8 }}>
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: 'var(--surface-muted)', borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: 8 }}>Scanner / Check</th>
                    <th style={{ padding: 8 }}>Layer</th>
                    <th style={{ padding: 8 }}>Status</th>
                    <th style={{ padding: 8 }}>Coverage Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {(report.coverage || []).map((c, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: 8 }}><strong>{c.check}</strong></td>
                      <td style={{ padding: 8 }}>{c.layer}</td>
                      <td style={{ padding: 8 }}>
                        <StatusBadge status={c.status === 'checked' ? 'passed' : 'incomplete'} label={c.status} />
                      </td>
                      <td style={{ padding: 8, color: 'var(--text-secondary)' }}>{c.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          {/* Findings Filter Bar */}
          <div style={{ display: 'flex', gap: 8, margin: '14px 0', alignItems: 'center' }}>
            <input
              placeholder="Search findings by title, file, or rule..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ flex: 1 }}
            />
            <select
              value={filterSeverity}
              onChange={e => setFilterSeverity(e.target.value)}
              style={{ width: 140 }}
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
          </div>

          {/* Findings List */}
          <div style={{ display: 'grid', gap: 10 }}>
            {filteredFindings.length === 0 ? (
              <p className="muted" style={{ padding: 16, textAlign: 'center' }}>No findings match the current filter.</p>
            ) : (
              filteredFindings.map(f => {
                const isCredential = /credential|password|token|secret|key/i.test(f.title + f.rule_id);
                const isXss = /dangerouslySetInnerHTML|xss/i.test(f.title + f.rule_id);
                const isDebug = /debug/i.test(f.title + f.rule_id);
                const isPrivilege = /superuser|privilege|grant/i.test(f.title + f.rule_id);
                const isTls = /tls|ssl|certificate/i.test(f.title + f.rule_id);

                let threatContext = '';
                if (isCredential) {
                  threatContext = 'Hardcoded credentials in source files or bundles expose accounts. Anyone inspecting client JS or repositories can extract credentials and bypass authentication.';
                } else if (isXss) {
                  threatContext = 'Direct HTML injection bypasses React escaping. Stored or reflected content can execute arbitrary JavaScript in the victim’s browser.';
                } else if (isDebug) {
                  threatContext = 'Production debug mode exposes interactive debuggers, internal environment configurations, and stack traces.';
                } else if (isPrivilege) {
                  threatContext = 'Excessive database privileges allow an application vulnerability to escalate into database compromise.';
                } else if (isTls) {
                  threatContext = 'Disabled TLS verification allows network eavesdroppers to intercept, decrypt, or alter sensitive traffic.';
                }

                return (
                  <div key={f.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-panel)', padding: 14, background: 'var(--surface)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <StatusBadge status={f.severity} label={f.severity.toUpperCase()} />
                        <span style={{ fontSize: 11, background: 'var(--surface-muted)', color: 'var(--text)', padding: '2px 6px', borderRadius: 'var(--radius-badge)', fontWeight: 600 }}>
                          {f.layer.toUpperCase()}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'ui-monospace, monospace' }}>
                          {f.rule_id}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {f.cwe && <span style={{ fontSize: 11, background: 'var(--surface-muted)', color: 'var(--text-secondary)', padding: '2px 6px', borderRadius: 'var(--radius-badge)' }}>{f.cwe}</span>}
                        {f.owasp && <span style={{ fontSize: 11, background: 'var(--surface-muted)', color: 'var(--text-secondary)', padding: '2px 6px', borderRadius: 'var(--radius-badge)' }}>{f.owasp}</span>}
                      </div>
                    </div>

                    <h4 style={{ margin: '8px 0 4px', fontSize: 14, color: 'var(--text)' }}>{f.title}</h4>

                    {f.path && (
                      <div style={{ fontSize: 12, background: 'var(--surface-muted)', border: '1px solid var(--border)', padding: '4px 8px', borderRadius: 'var(--radius-control)', display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'ui-monospace, monospace', margin: '4px 0' }}>
                        <span>📍 Location:</span>
                        <strong>{f.path}</strong>
                        {f.line ? <span>(Line {f.line})</span> : null}
                      </div>
                    )}

                    {threatContext && (
                      <div style={{ fontSize: 12, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', padding: '8px 10px', borderRadius: 'var(--radius-control)', margin: '8px 0', color: 'var(--warning-text)' }}>
                        <strong>⚠️ Threat Vector: </strong>
                        <span>{threatContext}</span>
                      </div>
                    )}

                    {f.evidence && f.evidence !== 'Pattern matched; source text and sensitive values omitted.' && (
                      <div style={{ fontSize: 12, background: 'var(--surface-muted)', padding: '6px 8px', borderRadius: 'var(--radius-control)', margin: '6px 0', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Evidence: </span>{f.evidence}
                      </div>
                    )}

                    <div style={{ fontSize: 12, color: 'var(--success-text)', background: 'var(--success-bg)', border: '1px solid var(--success-border)', padding: '8px 10px', borderRadius: 'var(--radius-control)', marginTop: 8 }}>
                      <strong style={{ display: 'block', marginBottom: 2 }}>🛡️ Remediation:</strong>
                      <span>{f.recommendation}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </section>
  );
}
