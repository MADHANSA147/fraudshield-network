import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, Building2, Check, ChevronDown,
  CircleHelp, CreditCard, Database, FileCheck2, Fingerprint, FlaskConical, Layers3,
  LayoutDashboard, LockKeyhole, Menu, Network, Play, Plus, ShieldCheck, SlidersHorizontal,
  Square, Terminal, X, XCircle, Zap } from 'lucide-react'
import './style.css'
import './dark.css'

type Json = Record<string, any>
type Page = 'Overview' | 'Institutions' | 'Training runs' | 'Evidence lab' | 'Release review' | 'Model registry' | 'Usage & billing'
const pages: [Page, React.ElementType][] = [['Overview', LayoutDashboard], ['Institutions', Building2],
  ['Training runs', Activity], ['Evidence lab', FlaskConical], ['Release review', FileCheck2],
  ['Model registry', Layers3], ['Usage & billing', CreditCard]]
const activeStates = ['QUEUED', 'PREPARING', 'TRAINING', 'VALIDATING', 'EVALUATING_ATTACKS']
const statusLabel = (s: string) => s?.toLowerCase().replaceAll('_', ' ') || 'pending'
const number = (n: number) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(n)
const pct = (n: number | null | undefined) => n == null ? '—' : (n * 100).toFixed(1) + '%'
const date = (t: number) => new Date(t * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
class ApiError extends Error { constructor(message: string, public status: number) { super(message) } }
async function api(path: string, body?: unknown, extra: Record<string, string> = {}) {
  const res = await fetch('/api' + path, { method: body === undefined ? 'GET' : 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...extra }, body: body === undefined ? undefined : JSON.stringify(body) })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'The request could not be completed. Please try again.', res.status)
  return data
}
function Badge({ status }: { status: string }) {
  const tone = ['PASS', 'RELEASED', 'DEMO_READY', 'COMPLETE', 'ENROLLED'].includes(status) ? 'green' :
    ['BLOCKED', 'FAILED', 'BUDGET_BLOCKED'].includes(status) ? 'red' : activeStates.includes(status) ? 'blue' : 'amber'
  return <span className={'badge ' + tone}><span/>{statusLabel(status)}</span>
}
function App() {
  const [workspace, setWorkspace] = useState<Json | null>(null)
  const [page, setPage] = useState<Page>('Overview')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [modal, setModal] = useState(false)
  const [mobile, setMobile] = useState(false)
  useEffect(() => {
    if (!modal) return
    const previous = document.activeElement as HTMLElement | null
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), input, select, [tabindex="0"]') || [])
    focusable()[0]?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) setModal(false)
      if (event.key !== 'Tab') return
      const items = focusable(), first = items[0], last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = overflow; previous?.focus() }
  }, [modal, busy])
  const [selected, setSelected] = useState<Json | null>(null)
  const [usage, setUsage] = useState<Json | null>(null)
  const [reference, setReference] = useState<Json[]>([])
  const [events, setEvents] = useState<Json[]>([])
  const [name, setName] = useState('Northstar Consortium')
  const [plan, setPlan] = useState({ name: 'Collaborative fraud detector', epsilon_cap: 4, rounds: 3,
    local_steps: 12, capacity: 2048, batch_size: 128, seed: 42, learning_rate: .1, positive_weight: 5 })
  const refresh = async () => {
    try { setWorkspace(await api('/workspace')) } catch (e) {
      if (e instanceof ApiError && e.status === 401) setWorkspace(null)
      else setError((e as Error).message)
    }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, [])
  const runs: Json[] = workspace?.runs || []
  const active = runs.find(r => activeStates.includes(r.status))
  useEffect(() => {
    if (!active) return
    const timer = setInterval(async () => {
      try {
        await refresh()
        if (selected?.id === active.id) setSelected(await api('/runs/' + active.id))
      } catch (e) { setError((e as Error).message) }
    }, 3000)
    return () => clearInterval(timer)
  }, [active?.id, selected?.id])
  useEffect(() => {
    if (!selected || !activeStates.includes(selected.status)) return
    const stream = new EventSource('/api/runs/' + selected.id + '/events', { withCredentials: true })
    stream.onmessage = e => setEvents(old => [...old.slice(-99), JSON.parse(e.data)])
    stream.onerror = () => stream.close()
    return () => stream.close()
  }, [selected?.id])
  useEffect(() => {
    if (workspace && page === 'Usage & billing') api('/usage').then(setUsage).catch(e => setError(e.message))
    if (workspace && page === 'Evidence lab') api('/reference-benchmark').then(report => setReference((report.results || []).map((r: Json) => ({
      id: r.run_id, plan: { name: 'Public study · seed ' + r.seed + ' · ε cap ' + r.planned_epsilon },
      comparison: { epsilon: r.epsilon, metrics: r.metrics },
    })))).catch(e => setError(e.message))
  }, [page, workspace?.tenant.id])
  async function act(action: () => Promise<void>) {
    setBusy(true); setError('')
    try { await action() } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  async function openRun(run: Json, target: Page = 'Training runs') {
    await act(async () => { setSelected(await api('/runs/' + run.id)); setEvents([]); setPage(target) })
  }
  const released = runs.filter(r => r.status === 'RELEASED')
  const completed = runs.filter(r => ['EVIDENCE_READY', 'RELEASED'].includes(r.status))
  const evidence = selected?.evidence
  const metrics = evidence?.public_evaluation?.aggregate
  const decision = selected?.decision
  const subtitles: Record<Page, string> = {
    'Overview': 'Collaborate on fraud detection. Keep control of your data and every model release.',
    'Institutions': 'Three independent data custodians. One approved training contract.',
    'Training runs': 'Follow training, secure aggregation, and cumulative privacy expenditure.',
    'Evidence lab': 'Measure the trade-off. Separate public benchmarks from protected validation.',
    'Release review': 'Every approval binds the exact model and its evidence.',
    'Model registry': 'Only approved, integrity-verified models are available for distribution.',
    'Usage & billing': 'Transparent platform usage. Your transaction volumes stay private.',
  }
  if (loading) return <div className="boot"><ShieldCheck size={40}/><p>Opening your workspace…</p></div>
  if (!workspace) return <main className="welcome">
    <div className="welcome-brand"><ShieldCheck/> FRAUDSHIELD <span>NETWORK</span></div>
    <div className="welcome-grid"><section><div className="eyebrow">PRIVATE DATA. COLLECTIVE INTELLIGENCE.</div>
      <h1>Train together.<br/><em>Keep data local.</em></h1>
      <p className="welcome-copy">A shared fraud model. Three independent institutions. Every release accountable to a privacy budget and measured evidence.</p>
      <div className="welcome-features"><span><LockKeyhole size={17}/> Local data custody</span><span><Fingerprint size={17}/> Record-level privacy</span><span><FileCheck2 size={17}/> Evidence-bound release</span></div>
    </section><section className="welcome-card"><div className="icon-box"><Network size={25}/></div><h2>Your consortium starts here</h2>
      <p>Explore the complete workflow with generated public transaction fixtures.</p>
      <form onSubmit={e => { e.preventDefault(); act(async () => { await api('/demo/session', { name }); await refresh() }) }}>
        <label>Workspace name<input value={name} onChange={e => setName(e.target.value)} minLength={3} maxLength={80} required/></label>
        <button className="primary full" disabled={busy}>{busy ? 'Creating workspace…' : 'Open demo workspace'}<ArrowRight size={17}/></button>
      </form><div className="small-note"><ShieldCheck size={16}/><span>No bank data. No payment required. Each workspace has its own session and records.</span></div>
      {error && <div className="inline-error">{error}</div>}</section></div>
    <footer>FraudShield Network <span>Research-grounded. Evidence-first.</span></footer>
  </main>
  return <div className="shell">
    <aside className={mobile ? 'sidebar open' : 'sidebar'}>
      <a className="brand" href="#" onClick={e => { e.preventDefault(); setPage('Overview') }}><span className="brand-icon"><ShieldCheck size={23}/></span><span>FraudShield<small>CONSORTIUM PLATFORM</small></span></a>
      <div className="workspace-switch"><span className="avatar">N</span><div>{workspace.tenant.name}<small>Consortium workspace</small></div><ChevronDown size={15}/></div>
      <div className="nav-label">WORKSPACE</div><nav>{pages.map(([label, Icon], i) => <React.Fragment key={label}>{i === 6 && <div className="nav-divider"/>}
        <button className={page === label ? 'nav active' : 'nav'} onClick={() => { setPage(label); setMobile(false) }}><Icon size={18}/>{label}{label === 'Training runs' && active && <span className="live-dot"/>}</button></React.Fragment>)}</nav>
      <div className="sidebar-bottom"><div className="trust-note"><ShieldCheck size={18}/><div>Privacy by construction<small>Explicit guarantees. Visible limits.</small></div></div>
        <button className="profile" onClick={() => act(async () => { await api('/logout', {}); setWorkspace(null) })}><span className="avatar small">AD</span><div>Demo administrator<small>Sign out of workspace</small></div><ArrowUpRight size={16}/></button></div>
    </aside><div className="main-shell">
      <header className="topbar"><div><button className="mobile-menu" onClick={() => setMobile(!mobile)} aria-label="Toggle navigation"><Menu/></button><span className="breadcrumb">Workspace <span>/</span> <strong>{page}</strong></span></div>
        <div className="topbar-right"><span className="environment"><span/> PUBLIC DATA SANDBOX</span><button className="help" aria-label="About this demo" onClick={() => setNotice('Real Opacus training and Flower SecAgg+ on generated public fixtures. No real-bank, customer-level, or production security claim.')}><CircleHelp size={19}/></button><span className="avatar small">AD</span></div></header>
      <main className="content"><div className="page-heading"><div><div className="eyebrow">{page === 'Overview' ? 'YOUR COLLABORATIVE DEFENSE NETWORK' : 'FRAUDSHIELD WORKSPACE'}</div><h1>{page === 'Overview' ? 'Stronger models. Shared trust.' : page}</h1><p>{subtitles[page]}</p></div>
        <button className="primary" disabled={!!active} onClick={() => setModal(true)}><Plus size={17}/>{active ? 'Training in progress' : 'New training run'}</button></div>
        {page === 'Overview' && <>
          <div className="stats-grid"><Stat label="Connected institutions" value="03" detail="Independent worker processes" icon={Building2}/>
            <Stat label="Training runs" value={String(runs.length).padStart(2, '0')} detail={completed.length + ' with measured evidence'} icon={Activity}/>
            <Stat label="Approved models" value={String(released.length).padStart(2, '0')} detail="Release gates enforced" icon={ShieldCheck}/>
            <Stat label="Privacy unit" value="1 record" detail="Transaction-level · (ε, δ)-DP" icon={Fingerprint}/></div>
          <div className="overview-grid"><section className="panel network-panel"><PanelTitle eyebrow="CONSORTIUM NETWORK" title="Intelligence moves. Data stays." extra={<span className="muted tiny">3 institution workers</span>}/>
            <div className="network-visual"><div className="network-line"/><div className="coordinator"><ShieldCheck size={29}/><strong>FraudShield</strong><small>Secure aggregation</small></div>
              <div className="institution-nodes">{workspace.institutions.map((i: Json, index: number) => <div className="network-node" key={i.slug}><div className="node-wire"/><div className={'node-symbol node-' + index}><Building2 size={22}/><span><LockKeyhole size={10}/></span></div><strong>{i.name}</strong><small>Records stay local</small><span className="node-state"><span/>{active ? 'Participating' : 'Demo ready'}</span></div>)}</div></div>
            <div className="network-foot"><LockKeyhole size={15}/><span>Only masked, differentially private updates enter aggregation.</span></div>
          </section><section className="panel protocol-panel"><div className="eyebrow">THE RELEASE CONTRACT</div><h2>Trust is a process.<br/>Make it inspectable.</h2><p>Every candidate must pass the same evidence checks.</p>
            {[['01', 'Respect the budget', 'Durable accounting before private operations.'], ['02', 'Measure what matters', 'Fraud recall, false alerts, and attack controls.'], ['03', 'Release with evidence', 'Signed manifests and owner approvals.']].map(([n, t, d]) => <div className="contract-step" key={n}><span>{n}</span><div><strong>{t}</strong><small>{d}</small></div></div>)}
            <button className="text-button" onClick={() => setPage('Release review')}>Explore release controls <ArrowRight size={16}/></button></section></div>
          <RunTable runs={runs.slice(0, 5)} onOpen={openRun} onNew={() => setModal(true)}/>
          <div className="disclosure"><FlaskConical size={18}/><div><strong>An honest engineering sandbox</strong><span>Generated public fixtures, not PaySim or real-bank results. Local isolation assumes a trusted host. Confidential releases require secure RNG and institution deployment.</span></div></div>
        </>}
        {page === 'Institutions' && <><div className="institution-cards">{workspace.institutions.map((i: Json, index: number) => <section className="panel institution-card" key={i.slug}>
          <div className={'node-symbol node-' + index}><Building2 size={25}/></div><h2>{i.name}</h2><p>{i.region}</p><Badge status={i.status}/>
          <dl><div><dt>Data custody</dt><dd>Institution-local</dd></div><div><dt>Privacy unit</dt><dd>Transaction record</dd></div><div><dt>Aggregation weight</dt><dd>Equal · 1.0</dd></div><div><dt>Local ledger</dt><dd>Persistent SQLite</dd></div></dl>
          <button className="secondary full" disabled={busy} onClick={() => act(async () => { const r = await api('/institutions/' + i.slug + '/enrollment', {}); setNotice('One-time enrollment token for ' + i.name + ' (10 minutes): ' + r.token) })}><Fingerprint size={15}/>Generate enrollment token</button>
        </section>)}</div><section className="panel schema-panel"><PanelTitle eyebrow="APPROVED DATA CONTRACT" title="A fixed, pre-transaction feature schema"/><div className="feature-list">{workspace.schema.features.map((f: string) => <code key={f}>{f}</code>)}</div><p className="muted">No central dataset upload. No post-transaction balances, account identities, or fraud flags in model inputs.</p></section></>}
        {page === 'Training runs' && <><RunTable runs={runs} onOpen={openRun} onNew={() => setModal(true)}/>{selected && <section className="panel run-detail"><PanelTitle eyebrow={'RUN ' + selected.id.slice(0, 8)} title={selected.plan.name} extra={<Badge status={selected.status}/>}/>
          <div className="run-progress"><div style={{ width: (selected.status === 'EVIDENCE_READY' || selected.status === 'RELEASED' ? 100 : Math.max(3, (selected.round || 0) / selected.plan.rounds * 75)) + '%' }}/></div>
          <div className="detail-grid"><div><small>Current stage</small><strong>{selected.stage}</strong></div><div><small>Rounds</small><strong>{selected.round || 0} / {selected.plan.rounds}</strong></div><div><small>Run ε allowance</small><strong>{selected.plan.epsilon_cap}</strong></div><div><small>Communication</small><strong>{number((selected.wire_bytes || 0) / 1024)} KB</strong></div></div>
          {selected.error && <div className="inline-error">{selected.error}</div>}<div className="run-actions">{activeStates.includes(selected.status) ? <button className="secondary" onClick={() => act(async () => { await api('/runs/' + selected.id + '/cancel', {}); setNotice('Cancellation requested. Committed privacy spend is retained.') })}><Square size={13}/>Cancel future work</button> : selected.evidence && <button className="primary" onClick={() => setPage('Evidence lab')}>Explore evidence<ArrowRight size={16}/></button>}</div>
          {!!events.length && <div className="event-log"><div><Terminal size={15}/>Allowlisted run events</div>{events.slice(-8).map((e, i) => <p key={i}><time>{new Date(e.created * 1000).toLocaleTimeString()}</time><span>{e.payload.stage || statusLabel(e.kind)}</span></p>)}</div>}
        </section>}</>}
        {page === 'Evidence lab' && <><CandidatePicker completed={completed} selected={selected} onSelect={r => openRun(r, 'Evidence lab')}/>{evidence ? <>
          <div className="stats-grid"><Stat label="PR-AUC" value={metrics?.pr_auc?.toFixed(3) || '—'} detail="Public held-out fixture" icon={Activity}/><Stat label="Fraud recall" value={pct(metrics?.recall)} detail="At frozen development threshold" icon={Zap}/><Stat label="False alerts / 1,000" value={metrics?.false_alerts_per_1000?.toFixed(1) || '—'} detail="Legitimate public transactions" icon={SlidersHorizontal}/><Stat label="Spent ε · worst institution" value={Math.max(...evidence.receipts.map((r: Json) => r.payload.epsilon)).toFixed(2)} detail={'δ = ' + selected?.plan.delta} icon={Fingerprint}/></div>
          <div className="overview-grid"><section className="panel"><PanelTitle eyebrow="MEASURED RESULTS" title="Institution-level performance"/><div className="table-scroll"><table><thead><tr><th>Institution</th><th>PR-AUC</th><th>Recall</th><th>FPR</th></tr></thead><tbody>{Object.entries(evidence.public_evaluation.institutions).map(([k, m]: [string, any]) => <tr key={k}><td>{k}</td><td>{m.pr_auc?.toFixed(3)}</td><td>{pct(m.recall)}</td><td>{pct(m.fpr)}</td></tr>)}</tbody></table></div><div className="panel-note">Public engineering fixture. No real-bank performance claim.</div></section>
          <section className="panel"><PanelTitle eyebrow="PRIVATE VALIDATION" title="Protected counts, visible uncertainty"/><Badge status={evidence.private_validation.denominators_supported ? 'COMPLETE' : 'INCONCLUSIVE'}/><div className="interval-row"><span>Recall interval</span><strong>{evidence.private_validation.recall_interval.map(pct).join(' – ')}</strong></div><div className="interval-row"><span>FPR interval</span><strong>{evidence.private_validation.fpr_interval.map(pct).join(' – ')}</strong></div><p className="muted">OpenDP count releases. Bounds include privacy noise and sampling uncertainty.</p></section></div>
          <Comparison runs={completed}/>
          <section className="panel"><PanelTitle eyebrow="PUBLIC BASELINES & ABLATIONS" title="Compare the training mechanisms"/><div className="table-scroll"><table><thead><tr><th>Method</th><th>PR-AUC</th><th>Recall</th><th>FPR</th></tr></thead><tbody>{Object.entries(evidence.baselines).filter(([k]) => k !== 'local').map(([k, v]: [string, any]) => { const m = v.metrics || v; return <tr key={k}><td>{statusLabel(k)}</td><td>{m.pr_auc?.toFixed(3)}</td><td>{pct(m.recall)}</td><td>{pct(m.fpr)}</td></tr> })}</tbody></table></div><p className="muted">Public-data reference experiments. DP ablations are independent public simulations; they do not reset a protected dataset budget.</p></section>
          <section className="panel"><PanelTitle eyebrow="ATTACK EVALUATION" title="A failed attack is not a privacy proof" extra={<Badge status={evidence.attacks.membership.status}/>}/><div className="detail-grid"><div><small>Loss attack ROC-AUC</small><strong>{evidence.attacks.membership.loss_attack?.roc_auc.toFixed(3) || '—'}</strong></div><div><small>Shadow likelihood ROC-AUC</small><strong>{evidence.attacks.membership.shadow_likelihood_attack?.roc_auc.toFixed(3) || '—'}</strong></div><div><small>Positive-control ROC-AUC</small><strong>{evidence.attacks.membership.positive_control?.roc_auc.toFixed(3) || '—'}</strong></div><div><small>Membership attacker observes</small><strong>Candidate model scores</strong></div></div><p className="muted">{evidence.attacks.membership.scope || evidence.attacks.membership.reason}</p></section>
          <button className="secondary" onClick={() => { const blob = new Blob([JSON.stringify(evidence, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'fraudshield-evidence.json'; a.click(); URL.revokeObjectURL(url) }}><ArrowDownToLine size={16}/>Export actual evidence</button>
        </> : <Empty icon={FlaskConical} title="Evidence begins with an experiment" text="Complete a training run to see actual performance, privacy expenditure, and attack results."/>}{!!reference.length && <Comparison runs={reference} reference/>}</>}
        {page === 'Release review' && <><CandidatePicker completed={completed} selected={selected} onSelect={r => openRun(r, 'Release review')}/>{decision ? <div className="release-layout"><section className="panel"><PanelTitle eyebrow="RELEASE POLICY · VERSION 1" title="Every check has a reason" extra={<Badge status={decision.status}/>}/><div className="gate-list">{decision.checks.map((c: Json) => <div className="gate-row" key={c.name}><span className={'gate-icon ' + (c.status === 'PASS' ? 'pass' : 'fail')}>{c.status === 'PASS' ? <Check size={17}/> : c.status === 'INCONCLUSIVE' ? <CircleHelp size={17}/> : <X size={17}/>}</span><div><strong>{c.name}</strong><small>{c.reason}</small></div><Badge status={c.status}/></div>)}</div></section>
          <section className="panel approval-panel"><div className="eyebrow">INSTITUTION APPROVALS</div><h2>Bound to this candidate.</h2><p>Changing the model or evidence invalidates its approvals.</p>{workspace.institutions.map((i: Json) => <div className="approval-row" key={i.slug}><span>{i.name}</span><button className={selected?.approvals?.includes(i.slug) ? 'approved-button' : 'secondary compact'} disabled={busy || selected?.status === 'RELEASED' || selected?.approvals?.includes(i.slug)} onClick={() => act(async () => { await api('/runs/' + selected?.id + '/approve/' + i.slug, {}); setSelected(await api('/runs/' + selected?.id)); await refresh() })}>{selected?.approvals?.includes(i.slug) ? <><Check size={14}/>Approved</> : 'Approve'}</button></div>)}
            <div className="small-note"><CircleHelp size={16}/><span>Demo approvals simulate institution owners and are recorded as simulated.</span></div><button className="primary full" disabled={busy || decision.status !== 'PASS' || selected?.status === 'RELEASED'} onClick={() => act(async () => { await api('/runs/' + selected?.id + '/release', {}); setSelected(await api('/runs/' + selected?.id)); await refresh(); setPage('Model registry') })}><ShieldCheck size={17}/>Release approved model</button><code className="hash">{decision.evidence_digest}</code></section></div>
          : <Empty icon={FileCheck2} title="No candidate to review yet" text="The release gate is enforced on measured evidence. Start a run, then review every decision here."/>}</>}
        {page === 'Model registry' && <>{released.length ? <section className="panel"><PanelTitle eyebrow="APPROVED MODELS" title="Ready for institution-local inference"/>{released.map(r => <div className="registry-row" key={r.id}><div className="icon-box"><ShieldCheck/></div><div><strong>{r.plan.name}</strong><small>{r.id} · {date(r.updated)}</small></div><a className="primary" href={'/api/runs/' + r.id + '/bundle'}><ArrowDownToLine size={16}/>Verified bundle</a></div>)}</section> : <Empty icon={Layers3} title="A registry built on earned trust" text="No model has passed all release requirements yet. Blocked candidates stay in Evidence lab and cannot be downloaded as approved models."/>}
          <section className="panel schema-panel"><PanelTitle eyebrow="ARTIFACT CONTRACT" title="More than a weights file"/><div className="feature-list">{['model.safetensors','feature_schema.json','threshold.json','privacy_statement.json','evaluation.json','attack_report.json','manifest.json','manifest.signature.json'].map(f => <code key={f}>{f}</code>)}</div><p className="muted">Ed25519 signatures bind artifacts and approvals. They establish integrity, not regulatory certification.</p></section></>}
        {page === 'Usage & billing' && <div className="billing-layout"><section className="panel plan-card"><div className="eyebrow">CONSORTIUM PILOT</div><h2>One shared workspace.<br/>Three independent institutions.</h2><div className="price">$499<span>/ month</span></div><p>Illustrative pricing hypothesis · sandbox only</p><ul>{['3 institution connectors', 'Managed training and evidence workflow', 'Signed model registry', 'Transparent compute metering'].map(t => <li key={t}><Check size={16}/>{t}</li>)}</ul><button className="primary full" disabled={busy || !usage?.billing_configured} onClick={() => act(async () => { const r = await api('/billing/checkout', {}); window.location.assign(r.url) })}>Open sandbox checkout<ArrowUpRight size={16}/></button><small>{usage?.billing_configured ? 'Stripe test mode. No real charges.' : 'Checkout disabled until Stripe test credentials are configured.'}</small></section>
          <section className="panel"><PanelTitle eyebrow="ACTUAL WORKSPACE USAGE" title="Meter the infrastructure, not the records"/><div className="usage-line"><span>Training runs</span><strong>{usage?.runs || 0} / {usage?.run_quota || 20}</strong></div><div className="usage-line"><span>Worker elapsed time</span><strong>{number((usage?.compute_seconds || 0) / 60)} min</strong></div><div className="usage-line"><span>Protocol traffic</span><strong>{number((usage?.wire_bytes || 0) / 1024)} KB</strong></div><div className="usage-line"><span>Transaction telemetry</span><strong>Not collected</strong></div><div className="disclosure"><Database size={18}/><div><strong>Local inference stays local</strong><span>No per-transaction billing or central transaction upload.</span></div></div></section></div>}
        <footer className="page-footer"><span>FraudShield Network <b>·</b> Privacy-governed collaboration</span><span><LockKeyhole size={12}/> Public-data engineering demonstration</span></footer>
      </main></div>
    {(error || notice) && <div className={'toast ' + (error ? 'error' : '')} role="alert"><div>{error ? <XCircle size={19}/> : <CircleHelp size={19}/>}</div><p>{error || notice}</p><button aria-label="Dismiss" onClick={() => { setError(''); setNotice('') }}><X size={18}/></button></div>}
    {modal && <div className="modal-backdrop" onClick={() => !busy && setModal(false)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="new-run-title" onClick={e => e.stopPropagation()}><button className="modal-close" aria-label="Close" onClick={() => setModal(false)}><X/></button><div className="eyebrow">NEW COLLABORATIVE EXPERIMENT</div><h2 id="new-run-title">Define the training contract.</h2><p>The same approved plan goes to all three institution workers.</p>
      <form onSubmit={e => { e.preventDefault(); act(async () => { const r = await api('/runs', { ...plan, mode: 'public_fixture' }, { 'Idempotency-Key': crypto.randomUUID() }); setModal(false); await refresh(); setSelected(await api('/runs/' + r.id)); setPage('Training runs') }) }}>
        <label>Run name<input value={plan.name} onChange={e => setPlan({ ...plan, name: e.target.value })} minLength={3} maxLength={100} required/></label>
        <label>Training protocol<select value={plan.capacity === 8192 ? 'research' : 'smoke'} onChange={e => setPlan(e.target.value === 'research' ? { ...plan, capacity: 8192, rounds: 5, local_steps: 100, learning_rate: .5, positive_weight: 1, seed: 242 } : { ...plan, capacity: 2048, rounds: 3, local_steps: 12, learning_rate: .1, positive_weight: 5, seed: 42 })}><option value="smoke">Quick pipeline check · generated public fixture</option><option value="research">Frozen public-development settings · longer experiment</option></select></label>
        <label>New-run privacy allowance<span className="label-detail">δ = 10⁻⁶ · includes 0.5 for validation · lifetime cap ε = 8</span></label>
        <div className="budget-options">{[2,4,8].map(epsilon => <button type="button" key={epsilon} className={plan.epsilon_cap === epsilon ? 'selected' : ''} onClick={() => setPlan({ ...plan, epsilon_cap: epsilon })}><span>ε = {epsilon}</span><small>{epsilon === 2 ? 'Tighter budget' : epsilon === 4 ? 'Middle comparison' : 'Larger budget'}</small></button>)}</div>
        <div className="form-grid"><label>Federated rounds<input type="number" min={1} max={20} value={plan.rounds} onChange={e => setPlan({ ...plan, rounds: +e.target.value })} required/></label><label>Local steps / round<input type="number" min={1} max={200} value={plan.local_steps} onChange={e => setPlan({ ...plan, local_steps: +e.target.value })} required/></label></div>
        <div className="small-note"><LockKeyhole size={18}/><span>Real DP-SGD + SecAgg+. Generated public fixtures. Existing dataset expenditure is retained across runs.</span></div><button className="primary full" disabled={busy}><Play size={16}/>{busy ? 'Submitting approved plan…' : 'Start training'}</button>
      </form></section></div>}
  </div>
}
function Stat({ label, value, detail, icon: Icon }: { label: string, value: string, detail: string, icon: React.ElementType }) {
  return <section className="stat"><div><span>{label}</span><Icon size={17}/></div><strong>{value}</strong><small>{detail}</small></section>
}
function Comparison({ runs, reference = false }: { runs: Json[], reference?: boolean }) {
  const points = runs.filter(r => Number.isFinite(r.comparison?.epsilon) && Number.isFinite(r.comparison?.metrics?.pr_auc))
  const maxX = Math.max(8, ...points.map(r => r.comparison.epsilon))
  return <section className="panel"><PanelTitle eyebrow={reference ? "RECORDED PUBLIC REFERENCE STUDIES" : "PRIVACY–UTILITY COMPARISON"} title={reference ? "Three seeds. Three budget profiles." : "Measured experiments, visible trade-offs"}/>{points.length ? <>
    <svg className="comparison-chart" viewBox="0 0 720 250" role="img" aria-label="Scatter plot of measured epsilon versus public PR-AUC" style={{ width: '100%', maxHeight: 300 }}>
      {[0,.25,.5,.75,1].map(y => <g key={y}><line x1="55" x2="680" y1={210-y*180} y2={210-y*180} stroke="#e4e9e4"/><text x="42" y={214-y*180} textAnchor="end" fill="#68786e" fontSize="11">{y}</text></g>)}
      {[0,2,4,6,8].map(x => <text key={x} x={55+x/maxX*625} y="229" textAnchor="middle" fill="#68786e" fontSize="11">{x}</text>)}
      <text x="370" y="248" textAnchor="middle" fill="#68786e" fontSize="11">Cumulative ε · smaller is a tighter bound</text>
      <text x="55" y="17" fill="#68786e" fontSize="11">Public PR-AUC</text>
      {points.map(r => <circle key={r.id} cx={55+r.comparison.epsilon/maxX*625} cy={210-r.comparison.metrics.pr_auc*180} r="6" fill="#28604e" stroke="#fff" strokeWidth="2"><title>{r.plan.name + ': ε ' + r.comparison.epsilon.toFixed(3) + ', PR-AUC ' + r.comparison.metrics.pr_auc.toFixed(3)}</title></circle>)}
    </svg><p className="muted">{reference ? 'Actual generated-fixture experiments recorded by the CLI benchmark. Independent public studies, not this workspace’s training history or real-bank results. Release decisions remain tied to measured utility and privacy evidence.' : 'Each point is a completed run. Settings, seeds and cumulative histories can differ; this plot alone does not establish a causal trend. The CLI benchmark holds the comparison protocol fixed.'}</p>
    </> : <p className="muted">Complete experiments to populate the comparison. No estimated performance is displayed.</p>}</section>
}
function PanelTitle({ eyebrow, title, extra }: { eyebrow: string, title: string, extra?: React.ReactNode }) {
  return <div className="panel-title"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2></div>{extra}</div>
}
function Empty({ icon: Icon, title, text }: { icon: React.ElementType, title: string, text: string }) {
  return <section className="panel empty"><div className="empty-icon"><Icon size={27}/></div><h2>{title}</h2><p>{text}</p></section>
}
function CandidatePicker({ completed, selected, onSelect }: { completed: Json[], selected: Json | null, onSelect: (r: Json) => void }) {
  return <div className="candidate-picker"><label>Evidence candidate<select value={selected?.id || ''} onChange={e => { const r = completed.find(r => r.id === e.target.value); if (r) onSelect(r) }}><option value="">Select a completed experiment</option>{completed.map(r => <option key={r.id} value={r.id}>{r.plan.name} · {r.id.slice(0, 8)}</option>)}</select></label><span><FlaskConical size={15}/> Public synthetic engineering results</span></div>
}
function RunTable({ runs, onOpen, onNew }: { runs: Json[], onOpen: (r: Json) => void, onNew: () => void }) {
  return <section className="panel runs-panel"><PanelTitle eyebrow="EXPERIMENT HISTORY" title="Training runs" extra={<span className="muted tiny">{runs.length} experiments</span>}/>
    {runs.length ? <div className="table-scroll"><table><thead><tr><th>Experiment</th><th>Run ε allowance</th><th>Rounds</th><th>Status</th><th>Created</th><th/></tr></thead><tbody>{runs.map(r => <tr key={r.id} onClick={() => onOpen(r)}><td><button className="table-link" onClick={e => { e.stopPropagation(); onOpen(r) }}><span className="run-icon"><Activity size={16}/></span><span>{r.plan.name}<small>{r.id.slice(0, 8)} · public fixture</small></span></button></td><td className="mono">ε {r.plan.epsilon_cap}</td><td>{r.round || 0} / {r.plan.rounds}</td><td><Badge status={r.status}/></td><td className="muted tiny">{date(r.created)}</td><td><ArrowUpRight size={16}/></td></tr>)}</tbody></table></div> :
    <div className="empty-runs"><div className="empty-icon"><Activity size={24}/></div><div><h3>Your first shared model starts here.</h3><p>Launch an experiment to measure the privacy–performance trade-off.</p></div><button className="secondary" onClick={onNew}>Create first run<ArrowRight size={15}/></button></div>}
  </section>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
