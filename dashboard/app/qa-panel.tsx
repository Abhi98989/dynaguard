'use client';

import { useEffect, useState } from 'react';
import { useToast } from './toast';
import { Button, StatusBadge, EvidenceViewer } from '../components/ui';

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
      if (!response.ok) throw new Error('Check profile schema, workflow IDs and selected skill applicability.');
      const run = await response.json();
      const msg = `QA Plan ${run.id.slice(0, 8)} created with ${run.report.coverage.selected_skills} skills selected. No tests executed.`;
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2>Senior QA Platform · Pre-Release Verification</h2>
          <p className="muted" style={{ margin: '4px 0 0' }}>
            Define business invariants, verify API functional contracts, state immutability, and evaluate release gates.
          </p>
        </div>
      </div>

      {/* Sub-mode selector */}
      <div style={{ display: 'flex', gap: 8, margin: '16px 0' }}>
        <Button
          size="sm"
          variant={activeTab === 'execute' ? 'primary' : 'secondary'}
          onClick={() => setActiveTab('execute')}
        >
          ⚡ Live Test Execution Runner
        </Button>
        <Button
          size="sm"
          variant={activeTab === 'plan' ? 'primary' : 'secondary'}
          onClick={() => setActiveTab('plan')}
        >
          📋 Risk-Based QA Planning ({skills.length} Skills)
        </Button>
      </div>

      {activeTab === 'execute' ? (
        <div>
          {/* Preset Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Target Preset:</span>
            <Button
              size="sm"
              variant={preset === 'hamrobuzz' ? 'primary' : 'ghost'}
              onClick={() => selectPreset('hamrobuzz')}
            >
              HamroBuzz Production (https://hamrobuzz.com)
            </Button>
            <Button
              size="sm"
              variant={preset === 'dynaflow' ? 'primary' : 'ghost'}
              onClick={() => selectPreset('dynaflow')}
            >
              DynaFlow Local (http://127.0.0.1:8010)
            </Button>
            <Button
              size="sm"
              variant={preset === 'custom' ? 'primary' : 'ghost'}
              onClick={() => selectPreset('custom')}
            >
              Custom Suite
            </Button>
          </div>

          <details open>
            <summary>Configure QA Test Suite Contract (API & Browser Workflows)</summary>
            <p className="muted" style={{ fontSize: 13, margin: '8px 0' }}>
              Tests executed through this runner evaluate real status codes, JSON field assertions, state immutability invariants, and browser interactions.
            </p>
            <label htmlFor="qa-suite-json">
              QA Test Suite JSON
              <textarea
                id="qa-suite-json"
                rows={12}
                value={suite}
                onChange={e => {
                  setSuite(e.target.value);
                  setPreset('custom');
                }}
                style={{ width: '100%', fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontSize: 12 }}
              />
            </label>
            <div style={{ marginTop: 10 }}>
              <Button
                variant="primary"
                loading={busy}
                disabled={busy}
                onClick={executeSuite}
              >
                {busy ? 'Executing Live Test Suite…' : 'Execute QA Test Suite'}
              </Button>
            </div>
          </details>

          {/* Execution Report Results Card */}
          {latestReport && (
            <div style={{ marginTop: 20, borderTop: '1px solid var(--border)', paddingTop: 18 }}>
              {/* Release Gate Banner */}
              <div
                style={{
                  padding: 14,
                  borderRadius: 'var(--radius-panel)',
                  marginBottom: 16,
                  background: gate?.decision === 'ready_for_release' ? 'var(--success-bg)' : 'var(--danger-bg)',
                  border: `1px solid ${gate?.decision === 'ready_for_release' ? 'var(--success-border)' : 'var(--danger-border)'}`
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <h3 style={{ margin: 0, color: gate?.decision === 'ready_for_release' ? 'var(--success-text)' : 'var(--danger-text)' }}>
                    {gate?.decision === 'ready_for_release' ? '✓ RELEASE READY: ALL REQUIRED CHECKS PASSED' : '✕ RELEASE REJECTED: CRITICAL DEFECTS DETECTED'}
                  </h3>
                  <StatusBadge status={gate?.decision || 'unknown'} label={gate?.decision?.toUpperCase()} />
                </div>
                <p style={{ margin: '6px 0 0 0', fontSize: 13, color: gate?.decision === 'ready_for_release' ? 'var(--success-text)' : 'var(--danger-text)' }}>
                  {gate?.reason}
                </p>
              </div>

              {/* Statistics Metrics Grid */}
              {cov && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 10, marginBottom: 16 }}>
                  <div style={{ padding: 12, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: 'var(--text)' }}>{cov.planned}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Planned</div>
                  </div>
                  <div style={{ padding: 12, background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: 'var(--success-text)' }}>{cov.passed}</div>
                    <div style={{ fontSize: 11, color: 'var(--success-text)' }}>Passed</div>
                  </div>
                  <div style={{ padding: 12, background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: 'var(--danger-text)' }}>{cov.failed}</div>
                    <div style={{ fontSize: 11, color: 'var(--danger-text)' }}>Failed</div>
                  </div>
                  <div style={{ padding: 12, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: 'var(--radius-control)', textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: 'var(--warning-text)' }}>{cov.incomplete || 0}</div>
                    <div style={{ fontSize: 11, color: 'var(--warning-text)' }}>Incomplete</div>
                  </div>
                </div>
              )}

              {/* Individual Test Executions List */}
              <h3 style={{ marginBottom: 10 }}>Executed Tests & Assertions ({latestReport.executions.length})</h3>
              <div style={{ display: 'grid', gap: 8 }}>
                {latestReport.executions.map(ex => (
                  <div
                    key={ex.test_id}
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-control)',
                      padding: 12,
                      background: ex.outcome === 'passed' ? 'var(--surface)' : 'var(--danger-bg)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <StatusBadge status={ex.outcome} label={ex.outcome.toUpperCase()} />
                        <span style={{ fontSize: 11, background: 'var(--surface-muted)', padding: '2px 6px', borderRadius: 'var(--radius-badge)', fontFamily: 'ui-monospace, monospace' }}>
                          {ex.technique}
                        </span>
                        <strong>{ex.name}</strong>
                      </div>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        {ex.duration_ms} ms
                      </span>
                    </div>

                    <div style={{ fontSize: 13, marginTop: 8, color: ex.outcome === 'passed' ? 'var(--success-text)' : 'var(--danger-text)' }}>
                      <strong>Result: </strong> {ex.actual}
                    </div>

                    {ex.evidence && ex.evidence.length > 0 && (
                      <EvidenceViewer
                        content={ex.evidence}
                        summaryTitle={`View execution trace (${ex.evidence.length} steps)`}
                      />
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
            <div style={{ maxHeight: 280, overflowY: 'auto', marginTop: 10, display: 'grid', gap: 6 }}>
              {skills.map(skill => (
                <details key={skill.id} style={{ margin: 0 }}>
                  <summary style={{ fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>{skill.name}</strong>
                    <StatusBadge status="incomplete" label={skill.implementation} />
                  </summary>
                  <ul style={{ fontSize: 12, marginTop: 6, paddingLeft: 18 }}>
                    {skill.checks.map(c => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                  <p style={{ fontSize: 12, margin: '6px 0 0' }}>
                    <strong>Required Evidence:</strong> {skill.evidence_required}
                  </p>
                </details>
              ))}
            </div>
          </details>

          <details open>
            <summary>Configure QA Profile & Risk Mapping</summary>
            <label htmlFor="qa-profile-json">
              QA Profile JSON
              <textarea
                id="qa-profile-json"
                rows={12}
                value={profile}
                onChange={e => setProfile(e.target.value)}
                style={{ width: '100%', fontFamily: 'ui-monospace, monospace', fontSize: 12 }}
              />
            </label>
            <div style={{ marginTop: 10 }}>
              <Button
                variant="primary"
                loading={busy}
                disabled={busy}
                onClick={plan}
              >
                Create Risk-Ordered QA Plan · Does not run tests
              </Button>
            </div>
          </details>
        </div>
      )}

      {message && (
        <div style={{ marginTop: 14, padding: 12, borderRadius: 'var(--radius-control)', background: 'var(--surface-muted)', border: '1px solid var(--border)' }}>
          <strong>Status: </strong> {message}
        </div>
      )}
    </section>
  );
}
