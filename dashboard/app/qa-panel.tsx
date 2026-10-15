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

const exampleProfile = {
  version: 1,
  project: 'DynaFlow',
  build_id: 'build-v1.0.0',
  capabilities: ['web', 'api', 'database'],
  workflows: [
    {
      id: 'auth.login',
      name: 'User Authentication & Session Lifecycle',
      risk: 'critical',
      roles: ['anonymous', 'user', 'admin'],
      expected_rules: [
        'Valid credentials return HTTP 200 and auth token',
        'Invalid passwords reject with HTTP 401 without user enumeration',
        'Expired or revoked sessions cannot access protected resources'
      ]
    },
    {
      id: 'data.isolation',
      name: 'Multi-Tenant Data Boundary Protection',
      risk: 'critical',
      roles: ['tenant_a_user', 'tenant_b_user'],
      expected_rules: [
        'Tenant A user cannot read, update, or delete Tenant B records',
        'Rejected cross-tenant operations preserve state immutability'
      ]
    }
  ]
};

const exampleSuite = {
  version: 1,
  suite_id: 'dynaflow-core-smoke',
  project: 'DynaFlow',
  build_id: 'build-v1.0.0',
  target_origin: 'http://localhost:8000',
  identities: {
    user: { token: 'mock-user-token-123' },
    admin: { token: 'mock-admin-token-999' }
  },
  api_tests: [
    {
      id: 'api-health',
      name: 'System health probe',
      technique: 'happy_path',
      method: 'GET',
      endpoint: '/health',
      expected_status: 200,
      assertions: [
        { field: 'status', operator: 'equals', expected: 'ok' }
      ]
    },
    {
      id: 'api-neg-empty-input',
      name: 'Reject empty payload without state corruption',
      technique: 'negative',
      method: 'POST',
      endpoint: '/api/v1/items',
      body: { name: '' },
      expected_status: 422,
      assertions: [
        { field: 'detail', operator: 'exists', expected: true }
      ]
    }
  ],
  browser_tests: [
    {
      id: 'browser-landing-page',
      name: 'Landing page render and navigation check',
      technique: 'happy_path',
      start_url: '/',
      actions: [
        { type: 'wait_for', selector: 'body', timeout_ms: 5000 },
        { type: 'assert_visible', selector: 'header' }
      ],
      expected_outcomes: ['Page renders without critical errors', 'Header component visible']
    }
  ]
};

export default function QAPanel({ projectId }: { projectId: string }) {
  const { showToast } = useToast();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [profile, setProfile] = useState(JSON.stringify(exampleProfile, null, 2));
  const [suite, setSuite] = useState(JSON.stringify(exampleSuite, null, 2));
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<'plan' | 'execute'>('execute');

  useEffect(() => {
    fetch('/api/qa/skills')
      .then(async r => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(v => setSkills(v.skills))
      .catch(() => setMessage('Could not load QA catalog'));
  }, []);

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
      const msg = `QA Plan ${run.id.slice(0, 8)} created. ${run.report.coverage.selected_skills} skills selected. No tests executed. Expand in runs list.`;
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
      const cov = run.report?.coverage || {};
      const gate = run.report?.release_gate || {};
      const msg = `QA Execution Run ${run.id.slice(0, 8)}: ${cov.passed || 0} passed, ${cov.failed || 0} failed. Release decision: ${gate.decision || 'unknown'}.`;
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
          <details open>
            <summary>Configure QA Test Suite Contract (API & Browser Workflows)</summary>
            <p className="muted" style={{ fontSize: 13, marginTop: 6 }}>
              Tests executed through this runner evaluate real status codes, JSON field assertions, state immutability invariants, and browser interactions.
            </p>
            <label>
              QA Test Suite JSON
              <textarea
                rows={16}
                value={suite}
                onChange={e => setSuite(e.target.value)}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 13 }}
              />
            </label>
            <button className="primary" disabled={busy} onClick={executeSuite} style={{ marginTop: 8 }}>
              {busy ? 'Executing Test Suite…' : '🚀 Execute QA Test Suite'}
            </button>
          </details>
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
