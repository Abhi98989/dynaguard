'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import EnginePanel from './engine-panel';
import AuditPanel from './audit-panel';
import QAPanel from './qa-panel';
import { useToast } from './toast';
import {
  HomeIcon,
  PlayIcon,
  AlertTriangleIcon,
  BarChartIcon,
  SettingsIcon,
  EyeIcon,
  EyeOffIcon,
  ChevronRightIcon,
  ChevronDownIcon
} from '../components/icons';

type Project = { id: string; name: string };
type Environment = { id: string; name: string; target: string; build_id: string };
type Policy = { id: string; environment_id: string };
type Run = {
  id: string;
  status: string;
  stage: string;
  created_at: string;
  retest_of: string | null;
  snapshot: { target: string; build_id: string; test_version: string };
};
type Finding = {
  id: string;
  title: string;
  lifecycle: string;
  severity: string;
  recommendation: string;
  verification: string;
  run_id: string;
};
type Detail = {
  project: Project;
  environments: Environment[];
  policies: Policy[];
  runs: Run[];
  findings: Finding[];
};
type Result = {
  run: Run;
  execution: { outcome: string; expected: string; actual: string };
  finding: Finding | null;
  evidence: { content: unknown; sha256: string } | null;
};
type FindingDetail = { finding: Finding; original: Result; retests: Result[] };

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  let result: Record<string, unknown> = {};
  try {
    result = await response.json();
  } catch {
    result = { detail: response.statusText || 'Server responded with non-JSON format' };
  }
  if (!response.ok) throw new Error((result.detail as string) || 'Request failed');
  return result as T;
}

const terminal = new Set(['completed', 'incomplete', 'cancelled']);

function timeAgo(dateString: string): string {
  try {
    const seconds = Math.floor((new Date().getTime() - new Date(dateString).getTime()) / 1000);
    if (seconds < 60) return `${Math.max(1, seconds)}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days > 1 ? 's' : ''} ago`;
  } catch {
    return dateString;
  }
}

export default function Page() {
  const { showToast } = useToast();
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const [currentUser, setCurrentUser] = useState('admin');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState('');
  const [activeNav, setActiveNav] = useState<'overview' | 'all' | 'qa' | 'audit' | 'engine' | 'runs' | 'findings'>('overview');
  const [detail, setDetail] = useState<Detail | null>(null);
  const [targets, setTargets] = useState<string[]>([]);
  const [target, setTarget] = useState('');
  const [selectedEnvId, setSelectedEnvId] = useState('');
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

  const requestSeq = useRef(0);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;


  const refresh = useCallback(async () => {
    const currentSeq = ++requestSeq.current;
    const currentSelected = selectedRef.current;

    const list = await api<Project[]>('/projects');
    if (currentSeq !== requestSeq.current) return;
    setProjects(list);

    // Auto-select first project if none selected yet
    if (!currentSelected && list.length > 0) {
      selectedRef.current = list[0].id;
      setSelected(list[0].id);
    }

    const activeProj = currentSelected || (list[0]?.id || '');
    if (activeProj) {
      const projDetail = await api<Detail>(`/projects/${activeProj}`);
      if (currentSeq !== requestSeq.current || selectedRef.current !== activeProj) return;
      setDetail(projDetail);

      // Auto-select environment if not selected
      if (!selectedEnvId && projDetail.environments.length > 0) {
        setSelectedEnvId(projDetail.environments[0].id);
      }
    }
    if (runId) {
      const runResult = await api<Result>(`/scan-runs/${runId}`);
      if (currentSeq !== requestSeq.current) return;
      setResult(runResult);
    }
    if (findingId) {
      const findingData = await api<FindingDetail>(`/findings/${findingId}`);
      if (currentSeq !== requestSeq.current) return;
      setFinding(findingData);
    }
  }, [runId, findingId, selectedEnvId]);

  useEffect(() => {
    api<{ username?: string }>('/auth/me')
      .then(res => {
        setAuthenticated(true);
        if (res?.username) setCurrentUser(res.username);
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    api<string[]>('/targets')
      .then(list => {
        setTargets(list);
        setTarget(list[0] || '');
      })
      .catch(e => {
        setError(e.message);
        showToast(e.message, 'error');
      });
  }, [authenticated, showToast]);

  useEffect(() => {
    if (!authenticated) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        await refresh();
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
      if (alive) timer = setTimeout(poll, 1500);
    };
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [authenticated, refresh]);

  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError('');
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
      await api('/auth/login', { username: 'admin', password });
      setPassword('');
      setAuthenticated(true);
      setCurrentUser('admin');
      showToast('Signed in successfully', 'success');
    });
  }

  async function scan(policy: string, retest?: string) {
    await action(async () => {
      const run = await api<Run>(`/projects/${selected}/scan-runs`, {
        policy_id: policy,
        retest_of: retest || null
      });
      setResult(null);
      setRunId(run.id);
      await refresh();
      showToast(retest ? 'Retest scan scheduled' : 'Scan run scheduled', 'info');
    });
  }

  function chooseProject(id: string) {
    requestSeq.current++;
    selectedRef.current = id;
    setSelected(id);
    setSelectedEnvId('');
    setDetail(null);
    setRunId('');
    setResult(null);
    setFindingId('');
    setFinding(null);
    setRetestPolicy('');
    setError('');
  }

  // Active project & environment references
  const selectedProject = projects.find(p => p.id === selected) || detail?.project;
  const currentEnv = detail?.environments.find(e => e.id === selectedEnvId) || detail?.environments[0];
  const currentPolicy = currentEnv ? detail?.policies.find(p => p.environment_id === currentEnv.id) : detail?.policies[0];

  // Dynamic metrics computed authoritatively from current real project data
  const passedCount = detail?.runs.filter(r => r.status === 'completed' || r.status === 'passed').length || 0;
  const failedCount = detail?.runs.filter(r => r.status === 'failed').length || 0;
  const notRunCount = Math.max(0, (detail?.environments.length || 0) - (passedCount + failedCount));

  // If not authenticated, render Login Screen
  if (!authenticated) {
    return (
      <div className="login-screen">
        <div className="login-topbar">
          <div className="brand">
            <span className="brand-dyna">Dyna</span>
            <span className="brand-guard">Guard</span>
          </div>
        </div>

        <div className="login-container">
          <div className="login-box">
            <h1 aria-label="Administrator sign in">Sign in</h1>

            {error && (
              <div role="alert" className="error" style={{ marginBottom: 16 }}>
                {error}
              </div>
            )}

            <form onSubmit={login}>
              <div className="login-field">
                <label htmlFor="login-username">Username</label>
                <input
                  id="login-username"
                  className="login-input"
                  value="admin"
                  autoComplete="username"
                  readOnly
                />
              </div>

              <div className="login-field">
                <label htmlFor="login-password">Password</label>
                <div className="password-input-wrapper">
                  <input
                    id="login-password"
                    className="login-input"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    placeholder="••••••••••••"
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowPassword(p => !p)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOffIcon size={18} /> : <EyeIcon size={18} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="login-submit-btn"
                disabled={busy}
              >
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  const activeTabTitle =
    activeNav === 'overview'
      ? 'Overview'
      : activeNav === 'all'
      ? 'All Panels'
      : activeNav === 'qa'
      ? 'Senior QA Platform'
      : activeNav === 'audit'
      ? 'Code Audit'
      : activeNav === 'engine'
      ? 'Shared Engine'
      : activeNav === 'runs'
      ? 'Runs'
      : 'Findings';

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="app-sidebar" aria-label="Main sidebar">
        <div className="sidebar-top">
          <div className="sidebar-brand-wrapper">
            <div className="brand">
              <span className="brand-dyna">Dyna</span>
              <span className="brand-guard">Guard</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="sidebar-nav">
            <button
              className={`nav-item ${activeNav === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveNav('overview')}
            >
              <HomeIcon size={18} />
              <span>Overview</span>
            </button>
            <button
              className={`nav-item ${activeNav === 'all' ? 'active' : ''}`}
              onClick={() => setActiveNav('all')}
            >
              <BarChartIcon size={18} />
              <span>All Panels (Full Stack)</span>
            </button>
            <button
              className={`nav-item ${activeNav === 'qa' ? 'active' : ''}`}
              onClick={() => setActiveNav('qa')}
            >
              <BarChartIcon size={18} />
              <span>Senior QA Platform</span>
            </button>
            <button
              className={`nav-item ${activeNav === 'audit' ? 'active' : ''}`}
              onClick={() => setActiveNav('audit')}
            >
              <AlertTriangleIcon size={18} />
              <span>Project Audit</span>
            </button>
            <button
              className={`nav-item ${activeNav === 'engine' ? 'active' : ''}`}
              onClick={() => setActiveNav('engine')}
            >
              <SettingsIcon size={18} />
              <span>Shared Engine</span>
            </button>
            <button
              className={`nav-item ${activeNav === 'runs' ? 'active' : ''}`}
              onClick={() => setActiveNav('runs')}
            >
              <PlayIcon size={18} />
              <span>Runs ({detail?.runs?.length || 0})</span>
            </button>
            <button
              className={`nav-item ${activeNav === 'findings' ? 'active' : ''}`}
              onClick={() => setActiveNav('findings')}
            >
              <AlertTriangleIcon size={18} />
              <span>Findings ({detail?.findings?.length || 0})</span>
            </button>
          </nav>
        </div>

        {/* Sidebar Footer User Profile */}
        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar" aria-hidden="true">
              {currentUser.slice(0, 2).toUpperCase()}
            </div>
            <span className="user-name">
              {currentUser === 'admin' ? 'Abhishek' : currentUser}
            </span>
          </div>
          <button
            className="signout-link"
            onClick={() =>
              action(async () => {
                await api('/auth/logout', {});
                setAuthenticated(false);
                setDetail(null);
                setResult(null);
                setFinding(null);
                setSelected('');
                showToast('Signed out successfully', 'info');
              })
            }
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main Workspace Pane */}
      <div className="app-main">
        {/* Modern Appbar with Project Switcher, Breadcrumbs, Quick Creator, and Target Environment */}
        <header className="app-header">
          <div className="appbar-left">
            <div className="appbar-project-group">
              <span className="appbar-label">Project:</span>
              <select
                aria-label="Select project"
                value={selected}
                onChange={e => chooseProject(e.target.value)}
                className="appbar-project-select"
              >
                {projects.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
                {projects.length === 0 && <option value="">No projects</option>}
              </select>
            </div>

            <span className="appbar-divider">/</span>
            <strong className="appbar-active-tab">{activeTabTitle}</strong>

            <form
              className="appbar-project-form"
              onSubmit={e => {
                e.preventDefault();
                action(async () => {
                  const project = await api<Project>('/projects', { name: projectName });
                  setProjectName('');
                  chooseProject(project.id);
                  showToast(`Project "${project.name}" created`, 'success');
                });
              }}
            >
              <label htmlFor="new-project-field" className="sr-only">
                New project
              </label>
              <input
                id="new-project-field"
                aria-label="New project"
                value={projectName}
                onChange={e => setProjectName(e.target.value)}
                placeholder="+ New project..."
                maxLength={120}
                className="appbar-new-project-input"
                disabled={busy}
              />
              <button
                type="submit"
                disabled={busy || !projectName.trim()}
                className="appbar-create-project-btn"
              >
                Create project
              </button>
            </form>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {detail?.environments && detail.environments.length > 0 ? (
              <select
                aria-label="Target environment"
                value={selectedEnvId || detail.environments[0]?.id}
                onChange={e => {
                  setSelectedEnvId(e.target.value);
                  const env = detail.environments.find(en => en.id === e.target.value);
                  if (env) showToast(`Switched target: ${env.name}`, 'info');
                }}
                className="env-dropdown-btn"
                style={{ cursor: 'pointer' }}
              >
                {detail.environments.map(env => (
                  <option key={env.id} value={env.id}>
                    Target: {env.name}
                  </option>
                ))}
              </select>
            ) : (
              <button type="button" className="env-dropdown-btn" onClick={() => setActiveNav('overview')}>
                <span>Staging</span>
                <ChevronDownIcon size={14} />
              </button>
            )}
          </div>
        </header>

        {/* Content Pane */}
        <div className="app-content">
          {error && (
            <div role="alert" className="error" style={{ marginBottom: 16 }}>
              {error}
            </div>
          )}

          {/* VIEW: OVERVIEW */}
          {activeNav === 'overview' && (
            <div>
              {/* Header Row */}
              <div className="overview-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <h1>Overview</h1>
                  {/* Accessible heading with project name for Playwright */}
                  <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)', margin: 0 }}>
                    {selectedProject?.name || 'Project'}
                  </h2>
                </div>

                <button
                  className="run-tests-btn"
                  disabled={busy}
                  onClick={() => {
                    if (currentPolicy) {
                      scan(currentPolicy.id);
                    } else if (detail?.policies && detail.policies[0]) {
                      scan(detail.policies[0].id);
                    } else {
                      showToast('Configure a local target environment below to run tests', 'info');
                    }
                  }}
                >
                  Run tests
                </button>
              </div>

              {/* Dynamic Metrics Summary Strip */}
              <div className="metrics-strip">
                <span className="metric-item-passed">
                  <strong>{passedCount}</strong> passed
                </span>
                <span className="metric-divider">|</span>
                <span className="metric-item-failed">
                  <strong>{failedCount}</strong> failed
                </span>
                <span className="metric-divider">|</span>
                <span className="metric-item-notrun">
                  <strong>{notRunCount}</strong> not run
                </span>
                <span className="metric-divider">|</span>
                <span>{detail?.runs && detail.runs.length > 0 ? 'Live data' : '0 checks run'}</span>
              </div>

              {/* Recent Runs Table */}
              <div className="dashboard-section">
                <div className="section-title-row">
                  <h2>Recent runs</h2>
                  <span className="section-action-link" onClick={() => setActiveNav('runs')}>
                    View all ({detail?.runs?.length || 0})
                  </span>
                </div>

                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Test suite</th>
                      <th>Build</th>
                      <th>Status</th>
                      <th>Duration</th>
                      <th>Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail?.runs && detail.runs.length > 0 ? (
                      detail.runs.slice(0, 10).map(run => {
                        const isPass = run.status === 'passed' || run.status === 'completed';
                        const isFail = run.status === 'failed';
                        const isInc = run.status === 'incomplete' || run.status === 'cancelled';
                        const statusClass = isPass ? 'passed' : isFail ? 'failed' : isInc ? 'incomplete' : 'completed';
                        const statusLabel = isPass ? 'Passed' : isFail ? 'Failed' : isInc ? 'Incomplete' : 'Completed';
                        return (
                          <tr
                            key={run.id}
                            className="clickable"
                            onClick={() => {
                              setResult(null);
                              setRunId(run.id);
                            }}
                          >
                            <td>
                              <strong>{run.snapshot?.test_version ? `Permission checks (v${run.snapshot.test_version})` : 'Permission checks'}</strong>
                            </td>
                            <td style={{ color: 'var(--text-secondary)' }}>
                              {run.snapshot?.build_id || 'v1.8.2'}
                            </td>
                            <td>
                              <span className={`status-indicator ${statusClass}`}>
                                <span className="status-dot"></span>
                                {statusLabel}
                              </span>
                            </td>
                            <td style={{ color: 'var(--text-secondary)' }}>32s</td>
                            <td style={{ color: 'var(--text-secondary)' }}>{timeAgo(run.created_at)}</td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', padding: '24px 16px', color: 'var(--text-secondary)' }}>
                          No runs recorded yet for this project. Configure a target below and click &quot;Start scan&quot; or &quot;Run tests&quot;.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Open Findings Table */}
              <div className="dashboard-section">
                <div className="section-title-row">
                  <h2>Open findings</h2>
                  <span className="section-action-link" onClick={() => setActiveNav('findings')}>
                    View all ({detail?.findings?.length || 0})
                  </span>
                </div>

                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 140 }}>Severity</th>
                      <th>Finding</th>
                      <th>Verification</th>
                      <th style={{ width: 40 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail?.findings && detail.findings.length > 0 ? (
                      detail.findings.map(f => {
                        const sevClass =
                          f.severity === 'critical' || f.severity === 'high'
                            ? 'severity-high'
                            : f.severity === 'medium'
                            ? 'severity-medium'
                            : 'severity-low';
                        const verClass =
                          f.lifecycle === 'verified_fixed'
                            ? 'verification-fixed'
                            : f.verification === 'confirmed_bypass' || f.verification === 'Confirmed'
                            ? 'verification-confirmed'
                            : 'verification-review';
                        const verLabel =
                          f.lifecycle === 'verified_fixed'
                            ? 'verified fixed'
                            : f.verification === 'confirmed_bypass'
                            ? 'Confirmed'
                            : f.verification || 'Needs review';
                        return (
                          <tr
                            key={f.id}
                            className="clickable"
                            onClick={() => {
                              setFinding(null);
                              setFindingId(f.id);
                            }}
                          >
                            <td className={sevClass}>
                              {f.severity.charAt(0).toUpperCase() + f.severity.slice(1)}
                            </td>
                            <td>
                              <button
                                type="button"
                                onClick={e => {
                                  e.stopPropagation();
                                  setFinding(null);
                                  setFindingId(f.id);
                                }}
                                style={{
                                  background: 'transparent',
                                  border: 'none',
                                  textAlign: 'left',
                                  padding: 0,
                                  cursor: 'pointer',
                                  font: 'inherit',
                                  color: 'inherit',
                                  fontWeight: 600
                                }}
                              >
                                {f.title}
                                <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 400, color: 'var(--text-secondary)' }}>
                                  ({verLabel})
                                </span>
                              </button>
                            </td>
                            <td className={verClass}>{verLabel}</td>
                            <td className="chevron-cell">
                              <ChevronRightIcon size={16} />
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={4} style={{ textAlign: 'center', padding: '24px 16px', color: 'var(--text-secondary)' }}>
                          No open findings recorded for this project.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Footer */}
              <div className="overview-footer">
                {detail?.runs && detail.runs.length > 0
                  ? `${detail.runs.length} check${detail.runs.length === 1 ? '' : 's'} recorded · ${notRunCount} target${notRunCount === 1 ? '' : 's'} not run`
                  : `Release not evaluated · ${detail?.environments?.length || 0} checks not run`}
              </div>

              {/* Local Target Environments & Interactive Testing Section */}
              <div style={{ marginTop: 36, paddingTop: 24, borderTop: '1px solid var(--border)' }}>
                <h3>Local target environments ({detail?.environments.length || 0})</h3>
                {detail?.environments.map(environment => {
                  const policy = detail.policies.find(p => p.environment_id === environment.id);
                  return (
                    <div className="row" key={environment.id}>
                      <div>
                        <strong>{environment.name}</strong>
                        <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                          {environment.target} · {environment.build_id}
                        </small>
                      </div>
                      <button
                        style={{
                          height: 32,
                          padding: '0 12px',
                          background: 'var(--accent)',
                          color: 'white',
                          border: 'none',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontWeight: 500
                        }}
                        disabled={busy || !policy}
                        onClick={() => scan(policy!.id)}
                      >
                        Start scan
                      </button>
                    </div>
                  );
                })}

                <details open={detail?.environments.length === 0} style={{ marginTop: 16 }}>
                  <summary>Configure a local target</summary>
                  <form
                    style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginTop: 12 }}
                    onSubmit={e => {
                      e.preventDefault();
                      action(async () => {
                        const envName = environmentName;
                        await api(`/projects/${selected}/environments`, {
                          name: environmentName,
                          target,
                          build_id: build
                        });
                        setEnvironmentName('');
                        setBuild('');
                        await refresh();
                        showToast(`Environment "${envName}" configured`, 'success');
                      });
                    }}
                  >
                    <div>
                      <label htmlFor="target-env-name" style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                        Environment name
                      </label>
                      <input
                        id="target-env-name"
                        required
                        value={environmentName}
                        onChange={e => setEnvironmentName(e.target.value)}
                        placeholder="Vulnerable browser fixture"
                        maxLength={120}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label htmlFor="target-allowed-url" style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                        Allowed target
                      </label>
                      <select
                        id="target-allowed-url"
                        value={target}
                        onChange={e => setTarget(e.target.value)}
                        style={{ width: '100%' }}
                      >
                        {targets.map(t => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label htmlFor="target-build-id" style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                        Build identifier
                      </label>
                      <input
                        id="target-build-id"
                        required
                        value={build}
                        onChange={e => setBuild(e.target.value)}
                        placeholder="fixture-vulnerable-v1"
                        maxLength={120}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                      <button
                        type="submit"
                        disabled={busy || !target}
                        style={{
                          height: 38,
                          width: '100%',
                          background: 'var(--surface-muted)',
                          border: '1px solid var(--border-strong)',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontWeight: 500
                        }}
                      >
                        Save target & policy
                      </button>
                    </div>
                  </form>
                </details>
              </div>

              {/* Active Result Inspection */}
              {result && (
                <div style={{ marginTop: 24, padding: 18, border: '1px solid var(--border)', borderRadius: 8, background: '#ffffff' }}>
                  <div className="row" style={{ paddingTop: 0 }}>
                    <h2>
                      Run result <span className={`badge ${result.execution.outcome}`}>{result.execution.outcome}</span>
                    </h2>
                    {!terminal.has(result.run.status) && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          action(async () => {
                            await api(`/scan-runs/${runId}/cancel`, {});
                            await refresh();
                            showToast('Scan run cancelled', 'info');
                          })
                        }
                      >
                        Cancel run
                      </button>
                    )}
                  </div>

                  <p style={{ margin: '8px 0 12px' }}>
                    <strong>Stage: </strong>{result.run.stage}
                  </p>

                  <dl style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px 16px', margin: '12px 0', fontSize: 13 }}>
                    <dt style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Expected</dt>
                    <dd>{result.execution.expected}</dd>
                    <dt style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Actual</dt>
                    <dd style={{ color: result.execution.outcome === 'passed' ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                      {result.execution.actual}
                    </dd>
                    <dt style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Test version / build</dt>
                    <dd>{result.run.snapshot.test_version} / {result.run.snapshot.build_id}</dd>
                  </dl>

                  {result.evidence && (
                    <details>
                      <summary>Masked evidence and integrity hash</summary>
                      <pre>{JSON.stringify(result.evidence.content, null, 2)}</pre>
                      <small style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                        SHA-256 {result.evidence.sha256}
                      </small>
                    </details>
                  )}
                </div>
              )}

              {/* Active Finding Detail & Retest Pane */}
              {finding && (
                <div style={{ marginTop: 24, padding: 18, border: '1px solid var(--border)', borderRadius: 8, background: '#ffffff' }}>
                  <h2>{finding.finding.title}</h2>
                  <dl style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px 16px', margin: '12px 0', fontSize: 13 }}>
                    <dt style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Expected</dt>
                    <dd>{finding.original.execution.expected}</dd>
                    <dt style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Demonstrated behavior</dt>
                    <dd style={{ color: 'var(--danger)', fontWeight: 600 }}>{finding.original.execution.actual}</dd>
                    <dt style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Suggested repair</dt>
                    <dd>{finding.finding.recommendation}</dd>
                  </dl>

                  <details>
                    <summary>Original masked evidence</summary>
                    <pre>{JSON.stringify(finding.original.evidence?.content, null, 2)}</pre>
                  </details>

                  <h3 style={{ marginTop: 16 }}>Retest against a configured build</h3>
                  <div className="row">
                    <select
                      aria-label="Retest environment"
                      value={retestPolicy}
                      onChange={e => setRetestPolicy(e.target.value)}
                      style={{ maxWidth: 280 }}
                    >
                      <option value="">Choose environment</option>
                      {detail?.policies.map(p => (
                        <option key={p.id} value={p.id}>
                          {detail.environments.find(e => e.id === p.environment_id)?.name}
                        </option>
                      ))}
                    </select>
                    <button
                      style={{
                        height: 36,
                        padding: '0 16px',
                        background: 'var(--accent)',
                        color: 'white',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontWeight: 500
                      }}
                      disabled={busy || !retestPolicy}
                      onClick={() => scan(retestPolicy, finding.finding.id)}
                    >
                      Run retest
                    </button>
                  </div>

                  <div style={{ marginTop: 12 }}>
                    {finding.retests.map(retest => (
                      <div key={retest.run.id} className="row">
                        <span>
                          <strong>{retest.run.snapshot.build_id}</strong>
                          <small style={{ display: 'block', color: 'var(--text-secondary)' }}>{retest.execution.actual}</small>
                        </span>
                        <span className={`badge ${retest.execution.outcome}`}>{retest.execution.outcome}</span>
                      </div>
                    ))}
                    {finding.retests.length === 0 && <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>No retest yet.</p>}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* VIEW: RUNS */}
          {activeNav === 'runs' && (
            <div>
              <div className="overview-header">
                <h1>Runs ({detail?.runs.length || 0})</h1>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Test suite</th>
                    <th>Build</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Report</th>
                  </tr>
                </thead>
                <tbody>
                  {detail?.runs.map(run => (
                    <tr
                      key={run.id}
                      className="clickable"
                      onClick={() => {
                        setResult(null);
                        setRunId(run.id);
                        setActiveNav('overview');
                      }}
                    >
                      <td><strong>{run.snapshot?.test_version ? `Permission checks (v${run.snapshot.test_version})` : 'Permission checks'}</strong></td>
                      <td>{run.snapshot?.build_id}</td>
                      <td>
                        <span className={`status-indicator ${run.status === 'completed' || run.status === 'passed' ? 'passed' : run.status === 'failed' ? 'failed' : 'incomplete'}`}>
                          <span className="status-dot"></span>
                          {run.status}
                        </span>
                      </td>
                      <td style={{ color: 'var(--text-secondary)' }}>{timeAgo(run.created_at)}</td>
                      <td>
                        <a href={`/api/scan-runs/${run.id}/report`} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>
                          JSON
                        </a>
                      </td>
                    </tr>
                  ))}
                  {(!detail?.runs || detail.runs.length === 0) && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--text-secondary)' }}>
                        No runs recorded yet. Start a scan from the Overview tab.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* VIEW: FINDINGS */}
          {activeNav === 'findings' && (
            <div>
              <div className="overview-header">
                <h1>Findings ({detail?.findings.length || 0})</h1>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Finding</th>
                    <th>Verification</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {detail?.findings.map(f => (
                    <tr
                      key={f.id}
                      className="clickable"
                      onClick={() => {
                        setFinding(null);
                        setFindingId(f.id);
                        setActiveNav('overview');
                      }}
                    >
                      <td className={f.severity === 'high' || f.severity === 'critical' ? 'severity-high' : f.severity === 'medium' ? 'severity-medium' : 'severity-low'}>
                        {f.severity}
                      </td>
                      <td><strong>{f.title}</strong></td>
                      <td className={f.lifecycle === 'verified_fixed' ? 'verification-fixed' : 'verification-confirmed'}>
                        {f.verification}
                      </td>
                      <td>
                        <span className={`badge ${f.lifecycle}`}>
                          {f.lifecycle.replaceAll('_', ' ')}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {(!detail?.findings || detail.findings.length === 0) && (
                    <tr>
                      <td colSpan={4} style={{ textAlign: 'center', padding: 24, color: 'var(--text-secondary)' }}>
                        No confirmed findings recorded.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* VIEW: ALL PANELS (PREVIOUS FULL STACK CONSOLE) */}
          {activeNav === 'all' && (
            <div style={{ display: 'grid', gap: 24 }}>
              {/* Previous UI Banner */}
              <div className="intro" style={{ margin: 0, padding: '16px 20px', background: 'var(--surface-muted)', borderRadius: 8, border: '1px solid var(--border)' }}>
                <span className="eyebrow" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--accent)' }}>
                  SOURCE REVIEW AND APPLICATION VERIFICATION
                </span>
                <h1 style={{ fontSize: 20, margin: '4px 0 6px', fontWeight: 700 }}>Evidence before conclusions.</h1>
                <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 13 }}>
                  Configure application tests, inspect evidence, and verify repairs.
                </p>
              </div>

              {/* Panel 1: AuditPanel */}
              {selected && <AuditPanel key={'audit-all-' + selected} projectId={selected} />}

              {/* Panel 2: QAPanel */}
              {selected && <QAPanel key={'qa-all-' + selected} projectId={selected} />}

              {/* Panel 3: EnginePanel */}
              {selected && <EnginePanel key={'engine-all-' + selected} projectId={selected} />}

              {/* Panel 4: Local Target Environments */}
              <div className="card" style={{ padding: 20, background: '#ffffff', borderRadius: 8, border: '1px solid var(--border)' }}>
                <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>{detail?.project.name} · legacy fixture pilot</h2>
                <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--text-secondary)' }}>
                  Synthetic Alice → own record → Bob’s record → evidence → retest
                </p>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Local target environments</h3>
                {detail?.environments.map(environment => {
                  const policy = detail.policies.find(p => p.environment_id === environment.id);
                  return (
                    <div className="row" key={environment.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                      <div>
                        <strong>{environment.name}</strong>
                        <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                          {environment.target} · {environment.build_id}
                        </small>
                      </div>
                      <button
                        style={{
                          height: 32,
                          padding: '0 12px',
                          background: 'var(--accent)',
                          color: 'white',
                          border: 'none',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontWeight: 500
                        }}
                        disabled={busy || !policy}
                        onClick={() => scan(policy!.id)}
                      >
                        Start scan
                      </button>
                    </div>
                  );
                })}

                <details open={detail?.environments.length === 0} style={{ marginTop: 16 }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Configure a local target</summary>
                  <form
                    style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginTop: 12 }}
                    onSubmit={e => {
                      e.preventDefault();
                      action(async () => {
                        const envName = environmentName;
                        await api(`/projects/${selected}/environments`, {
                          name: environmentName,
                          target,
                          build_id: build
                        });
                        setEnvironmentName('');
                        setBuild('');
                        await refresh();
                        showToast(`Environment "${envName}" configured`, 'success');
                      });
                    }}
                  >
                    <div>
                      <label htmlFor="target-env-name-all" style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                        Environment name
                      </label>
                      <input
                        id="target-env-name-all"
                        required
                        value={environmentName}
                        onChange={e => setEnvironmentName(e.target.value)}
                        placeholder="Vulnerable fixture"
                        maxLength={120}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label htmlFor="target-allowed-url-all" style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                        Allowed target
                      </label>
                      <select
                        id="target-allowed-url-all"
                        value={target}
                        onChange={e => setTarget(e.target.value)}
                        style={{ width: '100%' }}
                      >
                        {targets.map(t => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label htmlFor="target-build-id-all" style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                        Build identifier
                      </label>
                      <input
                        id="target-build-id-all"
                        required
                        value={build}
                        onChange={e => setBuild(e.target.value)}
                        placeholder="fixture-vulnerable-v1"
                        maxLength={120}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                      <button
                        type="submit"
                        disabled={busy || !target}
                        style={{
                          height: 38,
                          width: '100%',
                          background: 'var(--surface-muted)',
                          border: '1px solid var(--border-strong)',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontWeight: 500
                        }}
                      >
                        Save target & policy
                      </button>
                    </div>
                  </form>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>
                    Fixed ownership test · fixture/alice credential reference · 8 requests maximum · 15 second deadline
                  </p>
                </details>
              </div>

              {/* Panel 5: Scan runs */}
              <div className="card" style={{ padding: 20, background: '#ffffff', borderRadius: 8, border: '1px solid var(--border)' }}>
                <h2 style={{ margin: '0 0 12px', fontSize: 18, fontWeight: 700 }}>Scan runs</h2>
                {detail?.runs.length === 0 && <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>No tests have run yet.</p>}
                {detail?.runs.map(run => (
                  <button
                    className="row run"
                    key={run.id}
                    onClick={() => {
                      setResult(null);
                      setRunId(run.id);
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px 12px',
                      borderRadius: 6,
                      background: 'var(--surface-muted)',
                      border: '1px solid var(--border)',
                      cursor: 'pointer',
                      marginBottom: 8
                    }}
                  >
                    <span>
                      <strong>{run.snapshot?.build_id}</strong>
                      {run.retest_of && ' · retest'}
                      <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                        {new Date(run.created_at).toLocaleString()}
                      </small>
                    </span>
                    <span className={`badge ${run.status}`}>{run.status}</span>
                  </button>
                ))}
              </div>

              {/* Panel 6: Findings */}
              <div className="card" style={{ padding: 20, background: '#ffffff', borderRadius: 8, border: '1px solid var(--border)' }}>
                <h2 style={{ margin: '0 0 12px', fontSize: 18, fontWeight: 700 }}>Findings</h2>
                {detail?.findings.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>No confirmed findings recorded. Check run outcomes for incomplete or untested coverage.</p>
                ) : (
                  detail?.findings.map(f => (
                    <button
                      className="row run"
                      key={f.id}
                      onClick={() => {
                        setFinding(null);
                        setFindingId(f.id);
                      }}
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '10px 12px',
                        borderRadius: 6,
                        background: 'var(--surface-muted)',
                        border: '1px solid var(--border)',
                        cursor: 'pointer',
                        marginBottom: 8
                      }}
                    >
                      <span>
                        <strong>{f.title}</strong>
                        <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                          {f.verification} · {f.severity}
                        </small>
                      </span>
                      <span className={`badge ${f.lifecycle}`}>{f.lifecycle.replaceAll('_', ' ')}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {/* VIEW: QA PLATFORM */}
          {activeNav === 'qa' && (
            <div>
              <div className="overview-header">
                <h1>Senior QA Platform · Pre-Release Verification</h1>
              </div>
              {selected && <QAPanel key={'qa-' + selected} projectId={selected} />}
            </div>
          )}

          {/* VIEW: CODE AUDIT */}
          {activeNav === 'audit' && (
            <div>
              <div className="overview-header">
                <h1>Comprehensive Project Audit & Code Scans</h1>
              </div>
              {selected && <AuditPanel key={'audit-' + selected} projectId={selected} />}
            </div>
          )}

          {/* VIEW: SHARED ENGINE */}
          {activeNav === 'engine' && (
            <div>
              <div className="overview-header">
                <h1>Shared Engine · Configurable Application Tests</h1>
              </div>
              {selected && <EnginePanel key={'engine-' + selected} projectId={selected} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
