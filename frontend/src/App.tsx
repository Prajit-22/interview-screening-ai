import { useEffect, useState } from 'react'
import { request, type Health, type Role, type Session, type Question } from './api'

function Evidence({ q }: { q: Question }) {
  return <details className="evidence"><summary>View retrieval trace & textbook evidence</summary>
    <p><b>Why this question</b><br />{q.rationale}</p>
    {q.evidence_quote && <p><b>Supporting quote</b><br />{q.evidence_quote}</p>}
    <p><b>Resume anchor:</b> {q.plan.anchor} · <b>Difficulty:</b> {q.plan.difficulty}</p>
    <p><b>Retrieval query</b><br /><code>{q.plan.query}</code></p>
    {q.sources.map(s => <blockquote key={s.id} className={q.citation_ids.includes(s.id) ? 'cited' : ''}>
      <small>{s.id} · PDF page {s.page} · fusion {s.score.toFixed(4)} {q.citation_ids.includes(s.id) ? '· cited' : '· retrieved'}</small>
      <p>{s.text}</p><a href={s.url} target="_blank" rel="noreferrer">{s.source}</a>
    </blockquote>)}<small>Page numbers refer to PDF pages, including front matter. Citations trace evidence; they do not prove the model interpreted it correctly.</small>
  </details>
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [roles, setRoles] = useState<Role[]>([])
  const [role, setRole] = useState('ai-ml')
  const [file, setFile] = useState<File | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [restore, setRestore] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([request<Health>('/health'), request<Role[]>('/roles')]).then(([h, r]) => {
      if (active) { setHealth(h); setRoles(r) }
    }).catch(e => { if (active) setError(e.message + ' Start the backend on port 8000.') })
    const id = localStorage.getItem('groundwork-session')
    if (id) request<Session>('/sessions/' + id).then(s => { if (active) setSession(s) }).catch(() => { if (active) localStorage.removeItem('groundwork-session') })
    return () => { active = false }
  }, [])

  function remember(s: Session) { setSession(s); localStorage.setItem('groundwork-session', s.id) }
  async function act(fn: () => Promise<void>) {
    if (busy) return
    setBusy(true); setError('')
    try { await fn() } catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong') }
    finally { setBusy(false) }
  }
  const current = session?.questions.find(q => q.answer === null)
  const answered = session?.questions.filter(q => q.answer !== null).length ?? 0
  const complete = session?.status === 'complete'

  return <div className="shell">
    <header><a className="brand" href="/">◈ <span>groundwork<span className="brand-small">CANDIDATE SCREENING</span></span></a>
      <span className="status"><i className={health?.status === 'ready' ? 'online' : ''} />{health?.status === 'ready' ? 'Knowledge index ready' : 'Connecting to API'}</span></header>
    <main><div className="intro"><div><p className="eyebrow">RESUME → RETRIEVAL → INTERVIEW</p><h1>{complete ? 'A record worth reviewing.' : session ? 'Go beyond the definition.' : 'Interview the experience.\nGround it in the book.'}</h1>
      <p className="subtitle">{session ? `${session.role} · ${session.profile.difficulty} questions` : 'A resume-aware technical interview, with a source behind every question.'}</p></div>
      <div className="mode-card"><span className="eyebrow">GENERATION MODE</span><strong>{(session?.mode ?? health?.mode) === 'llm' ? 'Model-powered' : 'Practice scaffold'}</strong>
        <small>{(session?.mode ?? health?.mode) === 'llm' ? health?.model : 'No API key needed. Not LLM-generated.'}</small></div></div>
    <nav className="steps" aria-label="Interview stages">{['Candidate profile', 'Grounded interview', 'Session review'].map((s, i) => <div key={s} className={(complete ? 2 : session ? 1 : 0) === i ? 'active' : ''}><span>0{i + 1}</span>{s}</div>)}</nav>
    {error && <div className="error" role="alert">{error}</div>}
    {health?.error && <div className="error" role="alert">{health.error}</div>}
    {!session ? <div className="entry-grid"><section className="panel"><p className="eyebrow">01 / CANDIDATE ENTRY</p><h2>Start with your resume</h2><p className="muted">Text-based PDF or TXT · up to 2 MB · maximum 10 PDF pages</p>
      <form onSubmit={e => { e.preventDefault(); act(async () => {
        if (!file) throw new Error('Choose a resume first')
        if (file.size > 2 * 1024 * 1024) throw new Error('Resume must be smaller than 2 MB')
        const data = new FormData(); data.append('resume', file); data.append('role', role)
        remember(await request<Session>('/sessions', { method: 'POST', body: data }))
      }) }}><label className="upload"><span className="upload-icon">↑</span><b>{file?.name ?? 'Choose a resume'}</b><span>We extract skills, project context and a difficulty hint.</span><input type="file" accept=".pdf,.txt" aria-label="Resume file" onChange={e => setFile(e.target.files?.[0] ?? null)} disabled={busy} required /></label>
        <label className="field">Target role<select value={role} onChange={e => setRole(e.target.value)} disabled={busy}>{roles.map(r => <option value={r.id} key={r.id}>{r.name}</option>)}</select></label>
        <button className="primary" disabled={busy || !file || health?.status !== 'ready'}>{busy ? 'Retrieving context & generating questions…' : 'Build my interview →'}</button>
      </form><p className="fine">Resume bytes are discarded after parsing. Extracted profile and session records stay in local SQLite until deleted. No candidate data is sent to a model in practice mode; model mode sends extracted profile and textbook passages to your configured endpoint.</p>
    </section><aside><section className="panel book"><p className="eyebrow">THE KNOWLEDGE BASE</p><div className="book-art"><span>THE HUNDRED-PAGE</span><strong>Machine<br />Learning<br />Book</strong><span>ANDRIY BURKOV</span></div><p>One primary textbook. Page-aware chunks. Hybrid retrieval.</p><div className="stat"><b>{health?.chunks ?? '—'}</b><span>indexed passages with page citations</span></div><p className="fine">Backend role focuses on ML serving and data pipelines, not general backend trivia. Source content stays on this machine.</p></section>
      <details className="panel restore"><summary>Restore a session from its ID</summary><label className="field">Session ID<input value={restore} onChange={e => setRestore(e.target.value)} /></label><button disabled={busy || !restore} onClick={() => act(async () => remember(await request<Session>('/sessions/' + restore.trim())))}>Restore</button></details></aside></div> : <>
      <div className="session-grid"><aside className="panel profile"><p className="eyebrow">EXTRACTED PROFILE</p><h2>Your interview context</h2><div className="tags">{session.profile.skills.length ? session.profile.skills.map(s => <span key={s}>{s}</span>) : <span>No known skills detected</span>}</div>
        <p className="muted">{session.profile.difficulty_basis}. This is a planning heuristic, not an assessment.</p>
        <p className="eyebrow">SESSION CONTINUITY</p><progress value={answered} max={session.questions.length} /><p>{answered} / {session.questions.length} answers saved</p><small className="session-id">{session.id}</small><p className="fine">Treat the session ID as a private access token. Refreshing this page restores your saved answers.</p>
        <button disabled={busy} onClick={() => { localStorage.removeItem('groundwork-session'); setSession(null); setAnswer(''); setError('') }}>Start another interview</button>
        <button className="delete" disabled={busy} onClick={() => { if (confirm('Delete this session and all its answers permanently?')) act(async () => { await request('/sessions/' + session.id, { method: 'DELETE' }); localStorage.removeItem('groundwork-session'); setSession(null) }) }}>Delete this session</button>
      </aside><section className="interview">
      {!complete && current && <section className="panel question"><div className="question-head"><p className="eyebrow">QUESTION {current.number.toString().padStart(2, '0')} / {session.questions.length.toString().padStart(2, '0')}</p><span className="pill">{current.citation_ids.length} source{current.citation_ids.length === 1 ? '' : 's'}</span></div><h2>{current.text}</h2><p className="muted">{current.focus}</p><Evidence q={current} />
        <form onSubmit={e => { e.preventDefault(); act(async () => {
          remember(await request<Session>('/sessions/' + session.id + '/answers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_id: current.id, answer }) })); setAnswer('')
        }) }}><label className="field">Your answer<textarea value={answer} onChange={e => setAnswer(e.target.value)} placeholder="Explain your reasoning, then connect it to something you have built." maxLength={10000} rows={7} disabled={busy} required /></label><div className="answer-actions"><small>{answer.trim().split(/\s+/).filter(Boolean).length} words · saved on submit</small><button className="primary" disabled={busy || !answer.trim()}>{busy ? 'Saving…' : current.number === session.questions.length ? 'Save & review session →' : 'Save answer & continue →'}</button></div></form></section>}
      {complete && session.summary && <section className="panel review"><p className="eyebrow">03 / SESSION REVIEW</p><h2>Interview complete</h2><p>All answers are saved. This is an auditable record, not an automated hiring decision.</p><div className="metrics"><div><strong>{session.summary.answered}</strong><span>answered questions</span></div><div><strong>{session.summary.total_words}</strong><span>words in responses</span></div></div><h3>Topics explored</h3><ul>{session.summary.topics.map((t, i) => <li key={i}>{t}</li>)}</ul><p className="fine">{session.summary.note}</p>{session.summary.short_responses.length > 0 && <p className="notice">Answers {session.summary.short_responses.join(', ')} were shorter than 25 words. Consider expanding the reasoning; short does not mean incorrect.</p>}<p>{session.summary.next_step}</p><button onClick={() => { const blob = new Blob([JSON.stringify(session, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `interview-${session.id}.json`; a.click(); URL.revokeObjectURL(url) }}>Export full trace as JSON ↓</button></section>}
      {answered > 0 && <section className="history"><h3>Saved responses</h3>{session.questions.filter(q => q.answer !== null).map(q => <details className="panel" key={q.id}><summary>Question {q.number} · {q.focus}</summary><h3>{q.text}</h3><p className="saved-answer">{q.answer}</p><Evidence q={q} /></details>)}</section>}
      </section></div></>}
    <footer><span>Groundwork · evidence before judgement</span><span>React + FastAPI + SQLite · textbook-grounded RAG</span></footer></main>
  </div>
}
