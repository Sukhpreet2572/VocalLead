import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../services/api'
import { demoOwner } from '../services/demoOwner'
import './appointments.css'

type Lead = { id: string; customer_display: string; configuration: string | null; location: string | null }
type Property = { id: string; name: string; location: string; status: string }
type Slot = { start_at: string; end_at: string; local_display: string; availability_provider: string }
type Proposal = { id: string; property_id: string; property_name?: string; start_at: string; expires_at: string; status: string }
type Appointment = { id: string; customer_display: string; property_name: string; start_at: string; timezone: string; status: string; booking_provider: string; calendar_sync_status: string; crm_sync_status: string; operations: Array<{ type: string; status: string; failure_code: string | null }> }
type CRM = { id: string; lifecycle_status: string; provider: string; sync_status: string; last_synced_at: string | null; failure_code: string | null }
type Summary = { upcoming: number; confirmed: number; cancelled: number; pending_sync: number; failed_sync: number }
type Activity = { event_type: string; appointment_id: string | null; created_at: string; details: Record<string, unknown> }

async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers: { 'Content-Type': 'application/json', 'X-Voice-Owner': demoOwner() }, body: body ? JSON.stringify(body) : undefined })
  if (!response.ok) { const result = await response.json().catch(() => null); throw new Error(result?.error?.message || `Request failed (HTTP ${response.status})`) }
  return response.json() as Promise<T>
}

export function Appointments() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [properties, setProperties] = useState<Property[]>([])
  const [items, setItems] = useState<Appointment[]>([])
  const [crm, setCrm] = useState<CRM[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [activity, setActivity] = useState<Activity[]>([])
  const [leadId, setLeadId] = useState('')
  const [propertyId, setPropertyId] = useState('')
  const [day, setDay] = useState('')
  const [slots, setSlots] = useState<Slot[]>([])
  const [slot, setSlot] = useState('')
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [pending, setPending] = useState<Proposal[]>([])
  const [idempotency, setIdempotency] = useState('')
  const [result, setResult] = useState<Appointment | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = async () => {
    const [a, c, s, events, proposals] = await Promise.all([api<{ items: Appointment[] }>('/appointments?limit=50'), api<{ items: CRM[] }>('/crm/records?limit=50'), api<Summary>('/appointments/summary'), api<{ items: Activity[] }>('/appointments/activity?limit=12'), api<{ items: Proposal[] }>('/appointments/proposals?limit=20')])
    setItems(a.items); setCrm(c.items); setSummary(s); setActivity(events.items); setPending(proposals.items)
  }
  useEffect(() => { void Promise.all([api<{ items: Lead[] }>('/leads?limit=100'), api<Property[]>('/properties')])
    .then(([l, p]) => { setLeads(l.items); setProperties(p) }).catch(() => setError('Start the backend and run migrations.')); void refresh().catch(() => setError('Appointments API unavailable.')) }, [])
  const run = async (operation: () => Promise<void>) => { setBusy(true); setError(''); try { await operation() } catch (caught) { setError(caught instanceof Error ? caught.message : 'Operation failed') } finally { setBusy(false) } }
  const findSlots = () => void run(async () => { setProposal(null); setResult(null); setSlot(''); const response = await api<{ slots: Slot[] }>(`/appointments/availability?property_id=${encodeURIComponent(propertyId)}&day=${day}`); setSlots(response.slots) })
  const propose = () => void run(async () => { const created = await api<Proposal>('/appointments/proposals', 'POST', { lead_id: leadId, property_id: propertyId, start_at: slot }); setProposal(created); setIdempotency(crypto.randomUUID()); setResult(null) })
  const confirm = () => void run(async () => { if (!proposal) return; const booked = await api<Appointment>('/appointments/confirm', 'POST', { proposal_id: proposal.id, idempotency_key: idempotency, explicit_confirmation: true }); setResult(booked); setProposal(null); await refresh(); if (propertyId && day) { const response = await api<{ slots: Slot[] }>(`/appointments/availability?property_id=${encodeURIComponent(propertyId)}&day=${day}`); setSlots(response.slots) } })
  const cancel = (id: string) => void run(async () => { await api(`/appointments/${id}/cancel`, 'POST'); await refresh() })
  const retry = (id: string) => void run(async () => { await api(`/crm/records/${id}/sync`, 'POST'); await refresh() })
  const retryCalendar = (id: string) => void run(async () => { await api(`/appointments/${id}/sync`, 'POST'); await refresh() })
  const reconcileCalendar = (id: string) => void run(async () => { await api(`/appointments/${id}/reconcile`, 'POST'); await refresh() })
  return <div className="appointments-page"><div className="page-heading"><div><div className="eyebrow">BUSINESS AUTOMATION</div><h1>Appointments</h1><p>Local site visits: Tuesday–Sunday, 10:00–17:00 IST. External sync is shown separately.</p></div></div>
    <div className="status-grid">{(['upcoming','confirmed','cancelled','pending_sync','failed_sync'] as const).map(key => <div className="status-card" key={key}>{key.replaceAll('_',' ').toUpperCase()}<strong>{summary?.[key] ?? '—'}</strong></div>)}</div>
    <div className="detail-grid"><section className="panel appointments-section"><h2>Book a site visit</h2><p>Choose an owned demo lead, property and date. A slot is reserved only after you review and confirm a proposal.</p><label>Customer<select value={leadId} onChange={event => setLeadId(event.target.value)}><option value="">Select lead</option>{leads.map(lead => <option key={lead.id} value={lead.id}>{lead.customer_display} · {lead.configuration || 'No layout'} · {lead.location || 'No location'}</option>)}</select></label><label>Property<select value={propertyId} onChange={event => { setPropertyId(event.target.value); setSlots([]); setProposal(null) }}><option value="">Select property</option>{properties.map(item => <option key={item.id} value={item.id}>{item.name} · {item.location}</option>)}</select></label><label>Date<input type="date" value={day} onChange={event => { setDay(event.target.value); setSlots([]); setProposal(null) }} /></label><button className="button" disabled={busy || !propertyId || !day} onClick={findSlots}>Check actual availability</button>{slots.length === 0 && <p>No slots loaded or available for this date.</p>}{slots.length > 0 && <label>Available slot<select value={slot} onChange={event => setSlot(event.target.value)}><option value="">Select a time</option>{slots.map(item => <option key={item.start_at} value={item.start_at}>{item.local_display}</option>)}</select></label>}<button className="button" disabled={busy || !leadId || !slot} onClick={propose}>Review proposal</button>{proposal && <div className="proposal"><h3>Confirm this proposal</h3><p>{properties.find(item => item.id === proposal.property_id)?.name} · {new Date(proposal.start_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST</p><p>Expires {new Date(proposal.expires_at).toLocaleTimeString('en-IN')}</p><button className="button" disabled={busy} onClick={confirm}>Yes, confirm this booking</button></div>}{result && <p role="status">Booking {result.id}: {result.status}. Calendar {result.calendar_sync_status}; CRM {result.crm_sync_status}.</p>}{error && <p className="error-banner" role="alert">{error}</p>}</section>
    <section className="panel appointments-section"><h2>Local CRM status</h2>{crm.length === 0 ? <p>No CRM records yet. Confirm a local appointment to create one.</p> : crm.map(item => <article key={item.id}><strong>{item.lifecycle_status}</strong><p>{item.provider} · {item.sync_status} · {item.last_synced_at ? new Date(item.last_synced_at).toLocaleString() : 'Never synced'}</p>{item.failure_code && <small>{item.failure_code}</small>}{item.provider === 'hubspot' && item.sync_status === 'FAILED' && <button className="button" disabled={busy} onClick={() => retry(item.id)}>Retry CRM sync</button>}</article>)}</section></div>
    <section className="panel appointments-section"><h2>Pending proposals</h2><p>Voice agent proposals appear here for your explicit review. They expire after five minutes.</p><button className="button" disabled={busy} onClick={() => void run(refresh)}>Refresh proposals</button>{pending.length === 0 ? <p>No pending proposals.</p> : pending.map(item => <article key={item.id}><strong>{item.property_name || item.property_id}</strong><p>{new Date(item.start_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST · Expires {new Date(item.expires_at).toLocaleTimeString('en-IN')}</p><button className="button" onClick={() => { setProposal(item); setIdempotency(crypto.randomUUID()); setResult(null) }}>Review and confirm</button></article>)}</section>
    <section className="panel appointments-section"><h2>Appointments</h2>{items.length === 0 ? <p>No appointments yet.</p> : <div className="appointment-table-wrap"><table><thead><tr><th>ID</th><th>Customer</th><th>Property</th><th>Time (IST)</th><th>Status</th><th>Provider</th><th>Calendar</th><th>CRM</th><th>Actions</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.id.slice(0,8)}</td><td>{item.customer_display}</td><td>{item.property_name}</td><td>{new Date(item.start_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}</td><td>{item.status}</td><td>{item.booking_provider}</td><td>{item.calendar_sync_status}</td><td>{item.crm_sync_status}</td><td>{item.status !== 'CANCELLED' && <button disabled={busy} onClick={() => cancel(item.id)}>Cancel</button>}{item.booking_provider === 'google' && item.operations.some(op => op.status === 'RECONCILE_REQUIRED') && <button disabled={busy} onClick={() => reconcileCalendar(item.id)}>Reconcile calendar</button>}{item.booking_provider === 'google' && item.calendar_sync_status === 'FAILED' && item.operations.some(op => op.status === 'FAILED') && <button disabled={busy} onClick={() => retryCalendar(item.id)}>Retry calendar</button>}</td></tr>)}</tbody></table></div>}</section>
    <section className="panel appointments-section"><h2>Recent business activity</h2>{activity.length === 0 ? <p>No activity yet.</p> : activity.map((event, index) => <p key={`${event.created_at}-${index}`}>{new Date(event.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} · {event.event_type.replaceAll('_', ' ')}{event.appointment_id ? ` · ${event.appointment_id.slice(0,8)}` : ''}</p>)}</section></div>
}
