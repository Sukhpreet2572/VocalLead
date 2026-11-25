import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../services/api'
import './knowledge.css'

type Status = { provider: string; model: string; ready: boolean; indexed_chunks: number; indexed_documents: number; property_count: number }
type Property = { id: string; name: string; location: string; status: string; amenities: string[]; units: Array<{ configuration: string; price_inr: number; available: number }> }
type Document = { id: string; category: string; chunk_count: number; status: string }
type Search = { candidates: Array<{ property_id: string; name: string; configuration: string; price_inr: number }>; hits: Array<{ text: string; source: string; distance: number }>; duration_ms: number; evidence_available: boolean }

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) throw new Error(`Backend request failed (HTTP ${response.status})`)
  return response.json() as Promise<T>
}

export function Knowledge() {
  const [status, setStatus] = useState<Status | null>(null)
  const [properties, setProperties] = useState<Property[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [query, setQuery] = useState('')
  const [budget, setBudget] = useState('')
  const [configuration, setConfiguration] = useState('')
  const [location, setLocation] = useState('')
  const [result, setResult] = useState<Search | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => { void Promise.all([get<Status>('/knowledge/status'), get<Property[]>('/properties'), get<Document[]>('/knowledge/documents')])
    .then(([s, p, d]) => { setStatus(s); setProperties(p); setDocuments(d) }).catch(() => setError('Knowledge API unavailable. Start the backend.')) }, [])
  const search = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const response = await fetch(`${API_BASE_URL}/knowledge/search`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, max_budget_inr: budget ? Number(budget) : null, configuration: configuration || null, location: location || null }) })
      if (!response.ok) { const body = await response.json(); throw new Error(body?.error?.message || `Search failed (HTTP ${response.status})`) }
      setResult(await response.json() as Search)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Search unavailable') }
    finally { setLoading(false) }
  }
  return <div className="knowledge-page"><div className="page-heading"><div><div className="eyebrow">PROPERTY KNOWLEDGE</div><h1>Knowledge Base</h1><p>Fictional VocaLead Realty demonstration inventory and grounded retrieval.</p></div></div>
    <div className="status-grid"><div className="status-card">Properties<strong>{status?.property_count ?? '—'}</strong></div><div className="status-card">Documents<strong>{status?.indexed_documents ?? '—'}</strong></div><div className="status-card">Indexed chunks<strong>{status?.indexed_chunks ?? '—'}</strong></div><div className="status-card">Vector search<strong>{status ? status.ready ? 'Ready' : 'Not indexed' : 'Checking'}</strong><small>{status?.provider} · {status?.model}</small></div></div>
    <div className="detail-grid"><section className="panel knowledge-section"><h2>Property inventory</h2>{properties.map(item => <article key={item.id}><strong>{item.name}</strong><p>{item.location} · {item.status}</p><p>{item.amenities.join(', ')}</p>{item.units.map(unit => <small key={unit.configuration}>{unit.configuration} · ₹{unit.price_inr.toLocaleString('en-IN')} · {unit.available} units<br /></small>)}</article>)}</section>
    <section className="panel knowledge-section"><h2>Retrieval playground</h2><label>Question<textarea value={query} onChange={event => setQuery(event.target.value)} maxLength={500} placeholder="Which family apartments have a play area?" /></label><label>Maximum budget (INR)<input value={budget} onChange={event => setBudget(event.target.value)} type="number" min="1" /></label><label>Configuration<input value={configuration} onChange={event => setConfiguration(event.target.value)} placeholder="3 BHK" /></label><label>Location<input value={location} onChange={event => setLocation(event.target.value)} placeholder="Gurugram" /></label><button className="button" onClick={() => void search()} disabled={loading || query.trim().length < 3}>{loading ? 'Searching…' : 'Search knowledge'}</button>{error && <p className="error-banner" role="alert">{error}</p>}{result && <div><p>{result.hits.length} source chunks · {result.duration_ms} ms · {result.evidence_available ? 'Evidence found' : 'No sufficient evidence'}</p>{result.candidates.map(item => <p key={item.property_id + item.configuration}>{item.name} · {item.configuration} · ₹{item.price_inr.toLocaleString('en-IN')}</p>)}{result.hits.map((hit, index) => <article key={index}><small>{hit.source} · cosine distance {hit.distance.toFixed(3)}</small><p>{hit.text}</p></article>)}</div>}</section></div>
    <section className="panel knowledge-section"><h2>Document library</h2>{documents.map(item => <p key={item.id}>{item.id} · {item.category} · {item.chunk_count} chunks · {item.status}</p>)}</section></div>
}
