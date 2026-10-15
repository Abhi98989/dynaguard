'use client';

import { useState, useEffect, useCallback } from 'react';
import { useToast } from './toast';

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
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
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
      const match = f.title.toLowerCase().includes(q) ||
        (f.path && f.path.toLowerCase().includes(q)) ||
        f.layer.toLowerCase().includes(q) ||
        f.rule_id.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  return (
    <section>
      <h2>Comprehensive Project Audit & Code Scans</h2>
      <p>
        Perform deep code, dependency, database, and system architecture audits directly from the machine where your code lives.
      </p>

      {/* CLI Upload Token Section */}
      <details open={tokens.length === 0} style={{ marginBottom: 20 }}>
        <summary>CLI Upload Tokens & Setup Instructions</summary>
        <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
          Upload tokens allow the <code>dynaguard</code> CLI to securely upload audit reports without exposing passwords.
        </p>

        <form onSubmit={generateToken} style={{ display: 'flex', gap: 10, maxWidth: 450, margin: '14px 0' }}>
          <input
            placeholder="Token name (e.g., CI/CD or dev-pc)"
            value={newTokenName}
            onChange={e => setNewTokenName(e.target.value)}
            required
            disabled={busy}
          />
          <button className="primary" disabled={busy || !newTokenName.trim()} style={{ flexShrink: 0 }}>
            Generate Token
          </button>
        </form>

        {createdToken && (
          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: 14, borderRadius: 8, margin: '12px 0' }}>
            <strong style={{ color: '#166534' }}>New Upload Token (Save this; it won't be shown again!):</strong>
            <pre style={{ background: 'white', padding: 10, borderRadius: 6, margin: '8px 0', userSelect: 'all' }}>
              {createdToken}
            </pre>
            <small className="muted">To scan and upload from your computer terminal:</small>
            <pre style={{ background: '#1e293b', color: '#f8fafc', padding: 10, borderRadius: 6, margin: '8px 0', overflowX: 'auto' }}>
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
            <strong style={{ fontSize: 13 }}>Active Tokens:</strong>
            {tokens.map(t => (
              <div key={t.id} className="row" style={{ padding: '8px 0', fontSize: 13 }}>
                <div>
                  <strong>{t.name}</strong>
                  <small style={{ color: '#64748b' }}>
                    Created: {new Date(t.created_at).toLocaleDateString()}
                    {t.last_used_at ? ` · Used: ${new Date(t.last_used_at).toLocaleDateString()}` : ' · Never used'}
                    {t.revoked_at && ' · [REVOKED]'}
                  </small>
                </div>
                {!t.revoked_at && (
                  <button onClick={() => revokeToken(t.id)} style={{ padding: '4px 10px', fontSize: 12 }}>
                    Revoke
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </details>

      {/* Audit Runs Section */}
      <h3>Audit Runs ({runs.length})</h3>
      {runs.length === 0 ? (
        <p className="muted">No audit runs ingested yet. Run <code>dynaguard audit</code> on your machine and upload the report.</p>
      ) : (
        <div style={{ display: 'grid', gap: 12, margin: '14px 0' }}>
          {runs.map(run => {
            const sum = run.report?.summary || {};
            const isSelected = selectedRun?.id === run.id;
            return (
              <div
                key={run.id}
                onClick={() => setSelectedRun(isSelected ? null : run)}
                style={{
                  border: isSelected ? '2px solid #0d9488' : '1px solid #e2e8f0',
                  borderRadius: 8,
                  padding: 14,
                  cursor: 'pointer',
                  background: isSelected ? '#f0fdfa' : 'white'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>{run.report?.project || 'Project Audit'}</strong>
                    <span style={{ fontSize: 12, color: '#64748b', marginLeft: 10 }}>
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    {sum.critical ? <span className="badge failed">{sum.critical} critical</span> : null}
                    {sum.high ? <span className="badge failed">{sum.high} high</span> : null}
                    {sum.medium ? <span className="badge incomplete">{sum.medium} med</span> : null}
                    <span className="badge passed">{run.status}</span>
                  </div>
                </div>

                {Array.isArray(run.report?.stacks) && run.report.stacks.length > 0 && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {run.report.stacks.map(st => (
                      <span key={st} style={{ background: '#f1f5f9', color: '#475569', fontSize: 11, padding: '2px 8px', borderRadius: 4 }}>
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
        <div style={{ marginTop: 24, borderTop: '2px solid #e2e8f0', paddingTop: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Audit Report Details</h3>
            <button onClick={() => downloadJson(selectedRun)} style={{ padding: '6px 14px' }}>
              Download JSON Report
            </button>
          </div>

          {/* Severity Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 10, margin: '14px 0' }}>
            <div style={{ padding: 12, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 'bold', color: '#991b1b' }}>{report.summary?.critical || 0}</div>
              <div style={{ fontSize: 12, color: '#7f1d1d' }}>Critical</div>
            </div>
            <div style={{ padding: 12, background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 6, textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 'bold', color: '#be123c' }}>{report.summary?.high || 0}</div>
              <div style={{ fontSize: 12, color: '#881337' }}>High</div>
            </div>
            <div style={{ padding: 12, background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 6, textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 'bold', color: '#b45309' }}>{report.summary?.medium || 0}</div>
              <div style={{ fontSize: 12, color: '#78350f' }}>Medium</div>
            </div>
            <div style={{ padding: 12, background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 6, textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 'bold', color: '#15803d' }}>{(report.summary?.low || 0) + (report.summary?.info || 0)}</div>
              <div style={{ fontSize: 12, color: '#14532d' }}>Low / Info</div>
            </div>
          </div>

          {/* Coverage Table */}
          <details style={{ margin: '14px 0' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Coverage & Tool Verification Matrix ({report.coverage?.length || 0})</summary>
            <table style={{ width: '100%', fontSize: 13, marginTop: 8, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: 8 }}>Scanner / Check</th>
                  <th style={{ padding: 8 }}>Layer</th>
                  <th style={{ padding: 8 }}>Status</th>
                  <th style={{ padding: 8 }}>Coverage Detail</th>
                </tr>
              </thead>
              <tbody>
                {(report.coverage || []).map((c, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: 8 }}><strong>{c.check}</strong></td>
                    <td style={{ padding: 8 }}>{c.layer}</td>
                    <td style={{ padding: 8 }}>
                      <span className={`badge ${c.status === 'checked' ? 'passed' : 'incomplete'}`}>
                        {c.status}
                      </span>
                    </td>
                    <td style={{ padding: 8, color: '#64748b' }}>{c.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          {/* Findings Filter Bar */}
          <div style={{ display: 'flex', gap: 10, margin: '14px 0', alignItems: 'center' }}>
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
                  threatContext = 'Hardcoded credentials in source files or frontend bundles expose admin/service accounts. Anyone with access to the repo or inspecting client JS can extract these credentials and bypass authentication entirely.';
                } else if (isXss) {
                  threatContext = 'Direct HTML injection bypasses React escaping. Malicious actors or stored content can execute arbitrary JavaScript in the victim\'s browser to steal cookies, hijack user sessions, or deface the site.';
                } else if (isDebug) {
                  threatContext = 'Production debug mode exposes interactive debuggers, stack traces, and internal environment configurations to external requests, facilitating further exploitation.';
                } else if (isPrivilege) {
                  threatContext = 'Unrestricted database privileges allow an application breach to escalate into a full database takeover, dumping or deleting data across other tenants and services.';
                } else if (isTls) {
                  threatContext = 'Disabled TLS verification allows Man-in-the-Middle (MitM) attackers on the network to intercept, decrypt, and alter sensitive traffic.';
                }

                return (
                  <div key={f.id} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16, background: '#ffffff', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span className={`badge ${f.severity === 'critical' || f.severity === 'high' ? 'failed' : 'incomplete'}`}>
                          {f.severity.toUpperCase()}
                        </span>
                        <span style={{ fontSize: 11, background: '#e2e8f0', color: '#334155', padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
                          {f.layer.toUpperCase()}
                        </span>
                        <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                          {f.rule_id}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {f.cwe && <span style={{ fontSize: 11, background: '#f1f5f9', color: '#475569', padding: '2px 6px', borderRadius: 4 }}>{f.cwe}</span>}
                        {f.owasp && <span style={{ fontSize: 11, background: '#f1f5f9', color: '#475569', padding: '2px 6px', borderRadius: 4 }}>{f.owasp}</span>}
                      </div>
                    </div>

                    <h4 style={{ margin: '10px 0 6px 0', fontSize: 15, color: '#0f172a' }}>{f.title}</h4>

                    {/* File Location Banner */}
                    {f.path && (
                      <div style={{ fontSize: 12, background: '#f8fafc', border: '1px solid #e2e8f0', padding: '6px 10px', borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'monospace', color: '#0284c7', margin: '6px 0' }}>
                        <span>📍 Location:</span>
                        <strong>{f.path}</strong>
                        {f.line ? <span style={{ background: '#e0f2fe', color: '#0369a1', padding: '1px 6px', borderRadius: 4 }}>Line {f.line}</span> : null}
                      </div>
                    )}

                    {/* Threat & Bypass Scenario */}
                    {threatContext && (
                      <div style={{ fontSize: 13, background: '#fffbeb', border: '1px solid #fef3c7', padding: '10px 12px', borderRadius: 6, margin: '8px 0', color: '#92400e' }}>
                        <strong>⚠️ Threat & Exploitation Vector:</strong>
                        <p style={{ margin: '4px 0 0 0', lineHeight: 1.4 }}>{threatContext}</p>
                      </div>
                    )}

                    {/* Evidence Match */}
                    {f.evidence && f.evidence !== 'Pattern matched; source text and sensitive values omitted.' && (
                      <div style={{ fontSize: 12, background: '#f1f5f9', padding: '8px 10px', borderRadius: 6, margin: '8px 0', color: '#334155', fontFamily: 'monospace' }}>
                        <span style={{ color: '#64748b' }}>Evidence: </span>{f.evidence}
                      </div>
                    )}

                    {/* How to Fix / Remediation */}
                    <div style={{ fontSize: 13, color: '#166534', background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '10px 12px', borderRadius: 6, marginTop: 10 }}>
                      <strong style={{ display: 'block', marginBottom: 4 }}>🛡️ How to Fix / Remediation:</strong>
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
