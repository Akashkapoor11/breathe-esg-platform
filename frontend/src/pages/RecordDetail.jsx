import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import {
  ArrowLeft, CheckCircle, XCircle, Flag, AlertTriangle,
  Loader2, Clock, Lock, Database, FileText
} from 'lucide-react'

function Field({ label, value, mono }) {
  return (
    <div>
      <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{label}</div>
      <div className={`text-sm ${mono ? 'mono' : ''}`} style={{ color: 'var(--text-primary)' }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

function Section({ title, icon: Icon, children }) {
  return (
    <div className="card p-4 mb-4">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon size={14} style={{ color: 'var(--text-muted)' }} />}
        <div className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>{title}</div>
      </div>
      {children}
    </div>
  )
}

export default function RecordDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [reviewNote, setReviewNote] = useState('')
  const [actionLoading, setActionLoading] = useState('')

  useEffect(() => {
    api.record(id).then(r => { setRecord(r); setReviewNote(r.review_note || '') })
      .finally(() => setLoading(false))
  }, [id])

  const doReview = async (action) => {
    setActionLoading(action)
    try {
      const updated = await api.review(id, action, reviewNote)
      setRecord(updated)
    } finally {
      setActionLoading('')
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
    </div>
  )

  if (!record) return <div className="p-6">Record not found</div>

  const scopeColors = { 1: '#ff7043', 2: '#42a5f5', 3: '#ab47bc' }
  const statusColors = { pending: '#d29922', approved: '#3fb950', rejected: '#f85149', flagged: '#388bfd' }

  return (
    <div className="p-6 max-w-4xl fade-in">
      {/* Back + header */}
      <button onClick={() => navigate(-1)} className="btn-ghost text-xs mb-4">
        <ArrowLeft size={13} /> Back to records
      </button>

      <div className="flex items-start justify-between mb-5">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className={`scope-chip scope-${record.scope}`}>Scope {record.scope}</span>
            <span className={`badge badge-${record.status}`}>{record.status}</span>
            {record.is_locked && (
              <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                <Lock size={11} /> Locked for audit
              </span>
            )}
          </div>
          <h1 className="text-lg font-semibold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            {record.activity_description}
          </h1>
          <div className="text-xs mt-1 mono" style={{ color: 'var(--text-muted)' }}>
            {record.source_ref}
          </div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold mono" style={{ color: 'var(--accent)' }}>
            {Number(record.co2e_kg).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>kg CO₂e</div>
        </div>
      </div>

      {/* Warnings */}
      {record.warnings?.length > 0 && (
        <div className="rounded-md px-4 py-3 mb-4"
          style={{ background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.2)' }}>
          <div className="flex items-center gap-2 text-xs font-semibold mb-2" style={{ color: 'var(--warning)' }}>
            <AlertTriangle size={13} /> Data quality warnings
          </div>
          <ul className="space-y-1">
            {record.warnings.map((w, i) => (
              <li key={i} className="text-xs" style={{ color: 'var(--text-secondary)' }}>• {w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Activity data */}
        <Section title="ACTIVITY DATA" icon={Database}>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Category" value={record.category?.replace(/_/g, ' ')} />
            <Field label="Period" value={`${record.period_start} → ${record.period_end}`} />
            <Field label="Raw value" value={`${record.activity_value} ${record.activity_unit}`} mono />
            <Field label="Normalized" value={`${Number(record.activity_value_normalized).toLocaleString()} ${record.activity_unit_normalized}`} mono />
          </div>
        </Section>

        {/* Emission factor */}
        <Section title="EMISSION FACTOR" icon={FileText}>
          <div className="grid grid-cols-1 gap-3">
            <Field label="Factor value"
              value={`${record.emission_factor_info?.value} ${record.emission_factor_info?.unit}`}
              mono />
            <Field label="Source" value={record.emission_factor_info?.source} />
          </div>
        </Section>

        {/* Review panel */}
        {!record.is_locked && (
          <Section title="ANALYST REVIEW" icon={CheckCircle}>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-muted)' }}>
                  Note (optional)
                </label>
                <textarea
                  className="input text-xs resize-none"
                  rows={3}
                  placeholder="Add a review note…"
                  value={reviewNote}
                  onChange={e => setReviewNote(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <button onClick={() => doReview('approved')} disabled={!!actionLoading}
                  className="flex-1 flex items-center justify-center gap-1.5 text-xs py-2 rounded-md transition-all"
                  style={{ background: 'rgba(63,185,80,0.12)', color: 'var(--accent)', border: '1px solid rgba(63,185,80,0.2)' }}>
                  {actionLoading === 'approved' ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle size={12} />}
                  Approve
                </button>
                <button onClick={() => doReview('flagged')} disabled={!!actionLoading}
                  className="flex-1 flex items-center justify-center gap-1.5 text-xs py-2 rounded-md transition-all"
                  style={{ background: 'rgba(56,139,253,0.1)', color: 'var(--info)', border: '1px solid rgba(56,139,253,0.2)' }}>
                  {actionLoading === 'flagged' ? <Loader2 size={12} className="animate-spin" /> : <Flag size={12} />}
                  Flag
                </button>
                <button onClick={() => doReview('rejected')} disabled={!!actionLoading}
                  className="flex-1 flex items-center justify-center gap-1.5 text-xs py-2 rounded-md transition-all"
                  style={{ background: 'rgba(248,81,73,0.08)', color: 'var(--danger)', border: '1px solid rgba(248,81,73,0.15)' }}>
                  {actionLoading === 'rejected' ? <Loader2 size={12} className="animate-spin" /> : <XCircle size={12} />}
                  Reject
                </button>
              </div>
            </div>
          </Section>
        )}

        {/* Audit trail */}
        <Section title="AUDIT TRAIL" icon={Clock}>
          <div className="space-y-2">
            {(record.audit_events || []).map((e, i) => (
              <div key={i} className="flex items-start gap-3 text-xs py-1.5"
                style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <div className="flex-1">
                  <span className="font-medium capitalize" style={{ color: 'var(--text-primary)' }}>
                    {e.action}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}> by {e.actor_name || 'system'}</span>
                  {e.note && (
                    <div className="mt-0.5 italic" style={{ color: 'var(--text-muted)' }}>"{e.note}"</div>
                  )}
                </div>
                <div className="mono" style={{ color: 'var(--text-muted)' }}>
                  {new Date(e.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
            {(!record.audit_events || record.audit_events.length === 0) && (
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>No events yet</div>
            )}
          </div>
        </Section>
      </div>

      {/* Raw data */}
      <div className="card p-4">
        <div className="text-xs font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
          RAW SOURCE DATA
        </div>
        <div className="text-xs mono overflow-x-auto rounded p-3"
          style={{ background: 'var(--bg)', color: 'var(--text-secondary)', maxHeight: '220px' }}>
          <pre>{JSON.stringify(record.raw_data, null, 2)}</pre>
        </div>
      </div>
    </div>
  )
}
