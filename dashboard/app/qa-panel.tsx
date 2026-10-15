'use client';

import { useEffect, useState } from 'react';
import { useToast } from './toast';

type Skill = {
  id: string;
  name: string;
  implementation: string;
  checks: string[];
  evidence_required: string;
  environment: string;
};

type ExecutionResult = {
  test_id: string;
  name: string;
  type: string;
  technique: string;
  outcome: 'passed' | 'failed' | 'blocked' | 'incomplete' | 'skipped';
  actual: string;
  duration_ms: number;
  evidence: Array<{
    step?: string;
    method?: string;
    url?: string;
    status_code?: number;
    duration_ms?: number;
    response_snippet?: unknown;
    action?: string;
    selector?: string;
    value?: string;
  }>;
};

type QAReport = {
  run_id: string;
  project: string;
  build_id: string;
  suite_id: string;
  target_origin: string;
  created_at: string;
  status: string;
  release_gate: {
    decision: 'ready_for_release' | 'rejected' | 'not_evaluated';
    reason: string;
    required_passed: number;
    defects_count: number;
  };
  coverage: {
    planned: number;
    passed: number;
    failed: number;
    blocked: number;
    incomplete: number;
    executed_checks: number;
  };
  executions: ExecutionResult[];
  findings: Array<{
    id: string;
    title: string;
    severity: string;
    recommendation: string;
  }>;
};

const hamrobuzzPreset = {
  version: 1,
  suite_id: 'hamrobuzz-pre-release-suite',
  project: 'HamroBuzz',
  build_id: 'build-prod-2026.10',
  target_origin: 'https://hamrobuzz.com',
  identities: {
    guest: { token: '' }
  },
  api_tests: [
    {
      id: 'hb-system-health',
      name: 'System Health Check Probe',
      technique: 'happy_path',
      method: 'GET',
      endpoint: '/health',
      expected_status: 200,
      assertions: []
    },
    {
      id: 'hb-system-ready',
      name: 'System Readiness Probe',
      technique: 'happy_path',
      method: 'GET',
      endpoint: '/ready',
      expected_status: 200,
      assertions: []
    },
    {
      id: 'hb-api-articles-feed',
      name: 'Public News Articles Feed',
      technique: 'happy_path',
      method: 'GET',
      endpoint: '/api/v1/articles',
      expected_status: 200,
      assertions: []
    },
    {
      id: 'hb-landing-page',
      name: 'English Landing Gateway Render',
      technique: 'happy_path',
      method: 'GET',
      endpoint: '/en',
      expected_status: 200,
      assertions: []
    }
  ],
  browser_tests: []
};

const dynaflowPreset = {
  version: 1,
  suite_id: 'dynaflow-core-smoke',
  project: 'DynaFlow',
  build_id: 'build-v1.0.0',
  target_origin: 'http://127.0.0.1:8010',
  identities: {
    admin: { token: 'mock-admin-token' }
  },
  api_tests: [
    {
      id: 'df-projects-list',
      name: 'Verify project listing availability',
      technique: 'happy_path',
      method: 'GET',
      endpoint: '/projects',
      expected_status: 200,
      assertions: []
    }
  ],
  browser_tests: []
};

const exampleProfile = {
  version: 1,
  project: 'HamroBuzz',
  build_id: 'build-prod-2026.10',
  capabilities: ['web', 'api', 'database'],
  workflows: [
    {
      id: 'news.browse',
      name: 'Public News & Topic Browsing',
      risk: 'critical',
      roles: ['anonymous', 'subscriber'],
      expected_rules: [
        'Articles feed returns HTTP 200 with sanitized content',
        'Direct HTML injections are neutralized before DOM insertion',
        'Localized language endpoints (/en, /ne) load responsive layouts'
      ]
    },
    {
      id: 'cms.drafting',
      name: 'Journalist Article Creation & Media Uploads',
      risk: 'high',
      roles: ['journalist', 'editor', 'admin'],
      expected_rules: [
        'Only authenticated journalists can upload or draft articles',
        'Unauthenticated requests are strictly rejected with HTTP 401'
      ]
    }
  ]
};

export default function QAPanel({ projectId }: { projectId: string }) {
  const { showToast } = useToast();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [preset, setPreset] = useState<'hamrobuzz' | 'dynaflow' | 'custom'>('hamrobuzz');
  const [suite, setSuite] = useState(JSON.stringify(hamrobuzzPreset, null, 2));
  const [profile, setProfile] = useState(JSON.stringify(exampleProfile, null, 2));
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<'execute' | 'plan'>('execute');
  const [latestReport, setLatestReport] = useState<QAReport | null>(null);

  useEffect(() => {
    fetch('/api/qa/skills')
      .then(async r => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(v => setSkills(v.skills))
      .catch(() => setMessage('Could not load QA catalog'));
  }, []);

  function selectPreset(choice: 'hamrobuzz' | 'dynaflow' | 'custom') {
    setPreset(choice);
    if (choice === 'hamrobuzz') {
      setSuite(JSON.stringify(hamrobuzzPreset, null, 2));
    } else if (choice === 'dynaflow') {
      setSuite(JSON.stringify(dynaflowPreset, null, 2));
    }
  }

  async function plan() {
    setBusy(true);
    setMessage('');
    try {
      const response = await fetch(`/api/projects/${projectId}/qa-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard' },
        body: JSON.stringify(JSON.parse(profile))
      });
      if (!response.ok) throw new Error('Check the profile schema, workflow IDs and selected skill applicability.');
      const run = await response.json();
      const msg = `QA Plan ${run.id.slice(0, 8)} created. ${run.report.coverage.selected_skills} skills selected. No tests executed.`;
      setMessage(msg);
      showToast(msg, 'success');
    } catch (error) {
      const err = (error as Error).message;
      setMessage(err);
      showToast(err, 'error');
    } finally {
      setBusy(false);
    }
  }

  async function executeSuite() {
    setBusy(true);
    setMessage('');
    try {
      const parsedSuite = JSON.parse(suite);
      const response = await fetch(`/api/projects/${projectId}/qa-run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard' },
        body: JSON.stringify(parsedSuite)
      });
      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Test execution request failed.');
      }
      const run = await response.json();
      const report: QAReport = run.report;
      setLatestReport(report);

      const cov = report?.coverage || { passed: 0, failed: 0 };
      const gate = report?.release_gate || { decision: 'unknown' };
      const msg = `QA Execution Run ${run.id.slice(0, 8)}: ${cov.passed} passed, ${cov.failed} failed. Release decision: ${gate.decision}.`;
      setMessage(msg);
      showToast(msg, gate.decision === 'ready_for_release' ? 'success' : 'error');
    } catch (error) {
      const err = (error as Error).message;
      setMessage(err);
      showToast(err, 'error');
    } finally {
      setBusy(false);
    }
  }

  const gate = latestReport?.release_gate;
  const cov = latestReport?.coverage;

  return (
    <section>
      <h2>Senior QA Platform · Pre-Release Verification</h2>
      <p>
        Define business invariants, test actual API functional and browser behavior, verify state immutability on negative inputs, and validate release readiness.
      </p>

      {/* Mode Navigation */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <button
          className={activeTab === 'execute' ? 'primary' : ''}
          onClick={() => setActiveTab('execute')}
        >
          ⚡ Live Test Execution Runner
        </button>
        <button
          className={activeTab === 'plan' ? 'primary' : ''}
          onClick={() => setActiveTab('plan')}
        >
          📋 Risk-Based QA Planning (43 Skills)
        </button>
      </div>

      {activeTab === 'execute' ? (
        <div>
          {/* Preset Selector */}
          <div style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Target Preset:</span>
            <button
              style={{ fontSize: 12, padding: '4px 10px', background: preset === 'hamrobuzz' ? '#0d9488' : '#f1f5f9', color: preset === 'hamrobuzz' ? 'white' : '#334155' }}
              onClick={() => selectPreset('hamrobuzz')}
            >
              HamroBuzz Production (https://hamrobuzz.com)
            </button>
            <button
              style={{ fontSize: 12, padding: '4px 10px', background: preset === 'dynaflow' ? '#0d9488' : '#f1f5f9', color: preset === 'dynaflow' ? 'white' : '#334155' }}
              onClick={() => selectPreset('dynaflow')}
            >
              DynaFlow Local (http://127.0.0.1:8010)
            </button>
            <button
              style={{ fontSize: 12, padding: '4px 10px', background: preset === 'custom' ? '#0d9488' : '#f1f5f9', color: preset === 'custom' ? 'white' : '#334155' }}
              onClick={() => selectPreset('custom')}
            >
              Custom Suite
            </button>
          </div>

          <details open style={{ marginBottom: 16 }}>
            <summary>Configure QA Test Suite Contract (API & Browser Workflows)</summary>
            <p className="muted" style={{ fontSize: 13, marginTop: 6 }}>
              Tests executed through this runner evaluate real status codes, JSON field assertions, state immutability invariants, and browser interactions.
            </p>
            <label>
              QA Test Suite JSON
              <textarea
                rows={14}
                value={suite}
                onChange={e => {
                  setSuite(e.target.value);
                  setPreset('custom');
                }}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 13 }}
              />
            </label>
            <button className="primary" disabled={busy} onClick={executeSuite} style={{ marginTop: 8 }}>
              {busy ? 'Executing Live Test Suite…' : '🚀 Execute QA Test Suite'}
            </button>
          </details>

          {/* Execution Report Results Card */}
          {latestReport && (
            <div style={{ marginTop: 20, borderTop: '2px solid #e2e8f0', paddingTop: 18 }}>
              {/* Release Gate Banner */}
              <div
                style={{
                  padding: '14px 18px',
                  borderRadius: 8,
                  marginBottom: 16,
                  background: gate?.decision === 'ready_for_release' ? '#f0fdf4' : '#fef2f2',
                  border: `1px solid ${gate?.decision === 'ready_for_release' ? '#86efac' : '#fca5a5'}`
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0, color: gate?.decision === 'ready_for_release' ? '#166534' : '#991b1b' }}>
                    {gate?.decision === 'ready_for_release' ? '✅ RELEASE READY: ALL CHECKS PASSED' : '❌ RELEASE REJECTED: DEFECTS DETECTED'}
                  </h3>
                  <span className={`badge ${gate?.decision === 'ready_for_release' ? 'passed' : 'failed'}`}>
                    {gate?.decision?.toUpperCase()}
                  </span>
                </div>
                <p style={{ margin: '6px 0 0 0', fontSize: 13, color: gate?.decision === 'ready_for_release' ? '#15803d' : '#b91c1c' }}>
                  {gate?.reason}
                </p>
              </div>

              {/* Statistics Metrics */}
              {cov && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 10, marginBottom: 16 }}>
                  <div style={{ padding: 10, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: '#0f172a' }}>{cov.planned}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>Planned</div>
                  </div>
                  <div style={{ padding: 10, background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: '#15803d' }}>{cov.passed}</div>
                    <div style={{ fontSize: 11, color: '#166534' }}>Passed</div>
                  </div>
                  <div style={{ padding: 10, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: '#dc2626' }}>{cov.failed}</div>
                    <div style={{ fontSize: 11, color: '#991b1b' }}>Failed</div>
                  </div>
                  <div style={{ padding: 10, background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: '#d97706' }}>{cov.incomplete || 0}</div>
                    <div style={{ fontSize: 11, color: '#92400e' }}>Incomplete</div>
                  </div>
                </div>
              )}

              {/* Individual Test Executions List */}
              <h3>Executed Tests & Assertions ({latestReport.executions.length})</h3>
              <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                {latestReport.executions.map(ex => (
                  <div
                    key={ex.test_id}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                      padding: 14,
                      background: ex.outcome === 'passed' ? '#ffffff' : '#fff5f5'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className={`badge ${ex.outcome === 'passed' ? 'passed' : 'failed'}`}>
                          {ex.outcome.toUpperCase()}
                        </span>
                        <span style={{ fontSize: 11, background: '#f1f5f9', padding: '2px 6px', borderRadius: 4, fontFamily: 'monospace' }}>
                          {ex.technique}
                        </span>
                        <strong>{ex.name}</strong>
                      </div>
                      <span style={{ fontSize: 12, color: '#64748b' }}>
                        {ex.duration_ms} ms
                      </span>
                    </div>

                    <div style={{ fontSize: 13, marginTop: 8, color: ex.outcome === 'passed' ? '#15803d' : '#b91c1c' }}>
                      <strong>Result: </strong> {ex.actual}
                    </div>

                    {/* Collapsible Evidence Steps */}
                    {ex.evidence && ex.evidence.length > 0 && (
                      <details style={{ marginTop: 8 }}>
                        <summary style={{ fontSize: 12, color: '#475569', cursor: 'pointer' }}>
                          View Raw Evidence ({ex.evidence.length} steps)
                        </summary>
                        <pre style={{ background: '#0f172a', color: '#f8fafc', padding: 10, borderRadius: 6, fontSize: 11, marginTop: 6, overflowX: 'auto' }}>
                          {JSON.stringify(ex.evidence, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div>
          <details style={{ marginBottom: 14 }}>
            <summary>{skills.length} QA Skill Contracts & Maturity Status</summary>
            <div style={{ maxHeight: 300, overflowY: 'auto', marginTop: 10 }}>
              {skills.map(skill => (
                <details key={skill.id} style={{ marginBottom: 6 }}>
                  <summary style={{ fontSize: 13 }}>
                    <strong>{skill.name}</strong> · <span className="badge incomplete">{skill.implementation}</span>
                  </summary>
                  <ul style={{ fontSize: 12, marginTop: 4 }}>
                    {skill.checks.map(c => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                  <p style={{ fontSize: 12, margin: '4px 0' }}>
                    <strong>Required Evidence:</strong> {skill.evidence_required}
                  </p>
                </details>
              ))}
            </div>
          </details>

          <details open>
            <summary>Configure QA Profile & Risk Mapping</summary>
            <label>
              QA Profile JSON
              <textarea
                rows={14}
                value={profile}
                onChange={e => setProfile(e.target.value)}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 13 }}
              />
            </label>
            <button disabled={busy} onClick={plan} style={{ marginTop: 8 }}>
              Create Risk-Ordered QA Plan · Does not run tests
            </button>
          </details>
        </div>
      )}

      {message && (
        <div style={{ marginTop: 14, padding: 12, borderRadius: 6, background: '#f8fafc', border: '1px solid #cbd5e1' }}>
          <strong>Run Status:</strong> {message}
        </div>
      )}
    </section>
  );
}
