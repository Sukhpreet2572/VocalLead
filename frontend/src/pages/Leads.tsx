import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../services/api'
import { demoOwner } from '../services/demoOwner'
import './leads.css'

type Lead = { id: string; customer_id: string; customer_display: string; location: string | null; configuration: string | null; max_budget_inr: number | null; score: number; classification: string; sentiment: string; business_signal: string; updated_at: string; recommended_action: string; score_components: Record<string, { points: number; reason: string }>; score_history?: Array<{ previous_score: number; new_score: number; reason: string }> }
type Summary = { total: number; hot: number; warm: number; cold: number; insufficient_information: number }

async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers: { 'Content-Type': 'application/json', 'X-Voice-Owner': demoOwner() }, body: body ? JSON.stringify(body) : undefined })
  if (!response.ok) throw new Error(`Request failed (HTTP ${response.status})`)
  return response.json() as Promise<T>
}
export function Leads() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [items, setItems] = useState<Lead[]>([])
  const [selected, setSelected] = useState<Lead | null>(null)
  const [filter, setFilter] = useState('')
  const [sort, setSort] = useState('updated')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [mode, setMode] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = async () => {
    const [s, list] = await Promise.all([api<Summary>('/leads/summary'), api<{ items: Lead[] }>(`/leads?limit=50${filter ? `&classification=${filter}` : ''}`)])
    setSummary(s); setItems(list.items)
    if (selected) setSelected(await api<Lead>(`/leads/${selected.id}`))
  }
  useEffect(() => { void refresh().catch(() => setError('Lead API unavailable. Start the backend and run migrations.')) }, [filter]) // eslint-disable-line react-hooks/exhaustive-deps
  const create = async () => { setBusy(true); setError(''); try { const lead = await api<Lead>('/leads/demo', 'POST'); setSelected(lead); localStorage.setItem('vocalead-demo-customer', lead.customer_id); await refresh() } catch { setError('Could not create demo customer.') } finally { setBusy(false) } }
  const submit = async () => { if (!selected || !message.trim()) return; setBusy(true); setError(''); try { const result = await api<{ lead: Lead; extraction_mode: string; sentiment_mode: string }>(`/leads/${selected.id}/messages`, 'POST', { message }); setMode(`${result.extraction_mode} · ${result.sentiment_mode}`); setMessage(''); await refresh() } catch { setError('Could not process message.') } finally { setBusy(false) } }
  return <div className="leads-page"><div className="page-heading"><div><div className="eyebrow">CUSTOMER INTELLIGENCE</div><h1>Leads</h1><p>Owner-bound local demo profiles and explainable qualification.</p></div></div>
    <div className="status-grid">{(['total','hot','warm','cold'] as const).map(key => <div className="status-card" key={key}>{key.toUpperCase()}<strong>{summary?.[key] ?? '—'}</strong></div>)}</div>
    <div className="detail-grid"><section className="panel leads-section"><h2>Lead records</h2><label>Classification <select value={filter} onChange={event => setFilter(event.target.value)}><option value="">All</option><option>HOT</option><option>WARM</option><option>COLD</option></select></label><label>Sort <select value={sort} onChange={event => setSort(event.target.value)}><option value="updated">Latest interaction</option><option value="score">Highest score</option><option value="budget">Highest budget</option></select></label><p>{summary?.insufficient_information ?? 0} need more information</p><div className="lead-table-wrap"><table><thead><tr><th>Customer</th><th>Location</th><th>Layout</th><th>Max budget</th><th>Score</th><th>Class</th><th>Sentiment</th><th>Updated</th><th>Action</th></tr></thead><tbody>{[...items].sort((a, b) => sort === 'score' ? b.score - a.score : sort === 'budget' ? (b.max_budget_inr || 0) - (a.max_budget_inr || 0) : Date.parse(b.updated_at) - Date.parse(a.updated_at)).map(item => <tr key={item.id} onClick={() => void api<Lead>(`/leads/${item.id}`).then(setSelected)}><td>{item.customer_display}</td><td>{item.location || '—'}</td><td>{item.configuration || '—'}</td><td>{item.max_budget_inr ? `₹${item.max_budget_inr.toLocaleString('en-IN')}` : '—'}</td><td>{item.score}</td><td>{item.classification}</td><td>{item.sentiment}</td><td>{new Date(item.updated_at).toLocaleDateString()}</td><td>{item.recommended_action}</td></tr>)}</tbody></table></div></section>
    <section className="panel leads-section"><h2>Local intelligence playground</h2><p>Real profile persistence and inventory scoring. Without provider credentials, text extraction and sentiment use limited deterministic phrase rules. Provider output is not verified locally.</p><button className="button" disabled={busy} onClick={() => void create()}>Create demo customer</button>{selected && <><h3>{selected.customer_display}</h3><p>Score {selected.score} · {selected.classification} · {selected.business_signal}</p><p>{selected.recommended_action}</p><label>Sample customer message<textarea value={message} onChange={event => setMessage(event.target.value)} maxLength={1000} placeholder="I want a 3 BHK in Gurugram, max budget 1.2 crore" /></label><button className="button" disabled={busy || message.trim().length < 3} onClick={() => void submit()}>Process final message</button>{mode && <p>Mode: {mode}</p>}<h3>Score components</h3>{Object.entries(selected.score_components || {}).map(([key, value]) => <p key={key}>{key.replaceAll('_',' ')}: {value.points} · {value.reason}</p>)}<h3>Score history</h3>{selected.score_history?.map((entry, index) => <p key={index}>{entry.previous_score} → {entry.new_score}: {entry.reason}</p>)}</>}{error && <p role="alert" className="error-banner">{error}</p>}</section></div></div>
}
