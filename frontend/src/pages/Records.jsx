import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  Search, Filter, CheckCircle, XCircle, Flag, Loader2,
  ChevronLeft, ChevronRight, Download, AlertTriangle
} from 'lucide-react'
import clsx from 'clsx'

const SCOPE_LABELS = { 1: 'S1', 2: 'S2', 3: 'S3' }

function ScopeBadge({ scope }) {
  return <span className={`scope-chip scope-${scope}`}>{SCOPE_LABELS[scope]}</span>
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

export default function Records() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [count, setCount] = useState(0)
  const [selected, setSelected] = useState(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  // Filters
  const [filters, setFilters] = useState({
    scope: searchParams.get('scope') || '',
    status: searchParams.get('status') || '',
    source: searchParams.get('source') || '',
    has_warnings: searchParams.get('has_warnings') || '',
    search: '',
  })

  const PAGE_SIZE = 50

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.records({ ...filters, page })
      setRecords(data.results || data)
      setCount(data.count || (data.results || data).length)
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  useEffect(() => { load() }, [load])

  const setFilter = (key, val) => {
    setFilters(f => ({ ...f, [key]: val }))
    setPage(1)
    setSelected(new Set())
  }

  const toggleSelect = (id, e) => {
    e.stopPropagation()
    setSelected(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const selectAll = () => {
    if (selected.size === records.length) setSelected(new Set())
    else setSelected(new Set(records.map(r => r.id)))
  }

  const bulkAction = async (action) => {
    if (!selected.size) return
    setBulkLoading(true)
    try {
      await api.bulkReview([...selected], action)
      setSelected(new Set())
      load()
    } finally {
      setBulkLoading(false)
    }
  }

  const handleExport = async () => {
    const blob = await api.exportCSV()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'approved_emissions.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)

  return (
    <div className="p-6 fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            Emission Records
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {count.toLocaleString()} records
          </p>
        </div>
        <button onClick={handleExport} className="btn-ghost text-xs">
          <Download size={14} /> Export approved CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }} />
          <input className="input pl-8 text-xs h-8"
            placeholder="Search description, source ref…"
            value={filters.search}
            onChange={e => setFilter('search', e.target.value)} />
        </div>

        <select className="select text-xs h-8" value={filters.scope}
          onChange={e => setFilter('scope', e.target.value)}>
          <option value="">All scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>

        <select className="select text-xs h-8" value={filters.status}
          onChange={e => setFilter('status', e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="flagged">Flagged</option>
        </select>

        <select className="select text-xs h-8" value={filters.source}
          onChange={e => setFilter('source', e.target.value)}>
          <option value="">All sources</option>
          <option value="SAP">SAP</option>
          <option value="UTILITY">Utility</option>
          <option value="TRAVEL">Travel</option>
        </select>

        <select className="select text-xs h-8" value={filters.has_warnings}
          onChange={e => setFilter('has_warnings', e.target.value)}>
          <option value="">Warnings: all</option>
          <option value="true">Has warnings</option>
          <option value="false">Clean</option>
        </select>
      </div>

      {/* Bulk actions bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-3 px-3 py-2 rounded-md text-sm"
          style={{ background: 'rgba(63,185,80,0.08)', border: '1px solid rgba(63,185,80,0.2)' }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            {selected.size} selected
          </span>
          <div className="flex gap-2 ml-2">
            <button onClick={() => bulkAction('approved')} disabled={bulkLoading}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded"
              style={{ background: 'rgba(63,185,80,0.15)', color: 'var(--accent)' }}>
              <CheckCircle size={12} /> Approve all
            </button>
            <button onClick={() => bulkAction('rejected')} disabled={bulkLoading}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded"
              style={{ background: 'rgba(248,81,73,0.1)', color: 'var(--danger)' }}>
              <XCircle size={12} /> Reject all
            </button>
            <button onClick={() => bulkAction('flagged')} disabled={bulkLoading}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded"
              style={{ background: 'rgba(56,139,253,0.1)', color: 'var(--info)' }}>
              <Flag size={12} /> Flag all
            </button>
          </div>
          {bulkLoading && <Loader2 size={13} className="animate-spin ml-auto" />}
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th className="px-3 py-2.5 text-left w-8">
                  <input type="checkbox"
                    checked={selected.size === records.length && records.length > 0}
                    onChange={selectAll}
                    style={{ accentColor: 'var(--accent)' }} />
                </th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>SCOPE</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>DESCRIPTION</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>SOURCE</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>ACTIVITY</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>CO₂e (kg)</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>PERIOD</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>STATUS</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>FLAGS</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-3 py-12 text-center">
                    <Loader2 size={20} className="animate-spin mx-auto" style={{ color: 'var(--text-muted)' }} />
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-3 py-12 text-center text-sm"
                    style={{ color: 'var(--text-muted)' }}>
                    No records match these filters
                  </td>
                </tr>
              ) : records.map(r => (
                <tr key={r.id} className="table-row"
                  onClick={() => navigate(`/records/${r.id}`)}>
                  <td className="px-3 py-2.5" onClick={e => toggleSelect(r.id, e)}>
                    <input type="checkbox" checked={selected.has(r.id)} readOnly
                      style={{ accentColor: 'var(--accent)' }} />
                  </td>
                  <td className="px-3 py-2.5"><ScopeBadge scope={r.scope} /></td>
                  <td className="px-3 py-2.5 max-w-xs">
                    <div className="truncate" style={{ color: 'var(--text-primary)' }}>
                      {r.activity_description}
                    </div>
                    <div className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                      {r.source_ref}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="text-xs mono px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
                      {r.source_type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right mono text-xs"
                    style={{ color: 'var(--text-secondary)' }}>
                    {fmt(r.activity_value_normalized)} {r.activity_unit_normalized}
                  </td>
                  <td className="px-3 py-2.5 text-right mono text-sm font-semibold"
                    style={{ color: 'var(--text-primary)' }}>
                    {fmt(r.co2e_kg)}
                  </td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {r.period_start}
                  </td>
                  <td className="px-3 py-2.5"><StatusBadge status={r.status} /></td>
                  <td className="px-3 py-2.5">
                    {r.has_warnings && (
                      <AlertTriangle size={13} style={{ color: 'var(--warning)' }} />
                    )}
                    {r.is_locked && (
                      <span className="text-xs ml-1" style={{ color: 'var(--text-muted)' }}>🔒</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t"
            style={{ borderColor: 'var(--border)' }}>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Page {page} of {totalPages}
            </div>
            <div className="flex gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="btn-ghost p-1">
                <ChevronLeft size={14} />
              </button>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="btn-ghost p-1">
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
