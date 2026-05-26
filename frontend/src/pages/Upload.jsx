import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Upload as UploadIcon, CheckCircle, AlertTriangle, X, Loader2, FileText } from 'lucide-react'
import clsx from 'clsx'

const SOURCE_TYPES = [
  {
    value: 'SAP',
    label: 'SAP Fuel & Procurement',
    desc: 'ALV CSV export from MM transactions (ME2M, ME80FN, ZMM_*). Handles MANDT, WERKS, MENGE, MEINS. German headers OK.',
    scope: 'Scope 1',
    scopeClass: 'scope-1',
    accept: '.csv,.txt',
  },
  {
    value: 'UTILITY',
    label: 'Utility Electricity',
    desc: 'Portal CSV export from DISCOM account portal (BSES, MSEDCL, BESCOM, TATA, TNEB, etc.). One row per billing period per meter.',
    scope: 'Scope 2',
    scopeClass: 'scope-2',
    accept: '.csv',
  },
  {
    value: 'TRAVEL',
    label: 'Corporate Travel',
    desc: 'Concur or Navan expense report CSV. Supports flights (IATA codes), hotel nights, ground transport. Distance computed if missing.',
    scope: 'Scope 3',
    scopeClass: 'scope-3',
    accept: '.csv',
  },
]

export default function Upload() {
  const navigate = useNavigate()
  const [sourceType, setSourceType] = useState('SAP')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const selected = SOURCE_TYPES.find(s => s.value === sourceType)

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    setResult(null)
    setError('')
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [])

  const onDragOver = (e) => { e.preventDefault(); setDragging(true) }
  const onDragLeave = () => setDragging(false)

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const job = await api.uploadFile(file, sourceType)
      setResult(job)
      setFile(null)
    } catch (err) {
      setError(err.data?.error || err.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-2xl fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          Upload Data
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
          Upload a file to ingest and normalize into emission records.
        </p>
      </div>

      {/* Source type selector */}
      <div className="mb-5">
        <div className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>SOURCE TYPE</div>
        <div className="grid grid-cols-3 gap-2">
          {SOURCE_TYPES.map(s => (
            <button key={s.value}
              onClick={() => setSourceType(s.value)}
              className={clsx('card p-3 text-left transition-all', {
                'border-opacity-100': sourceType === s.value
              })}
              style={sourceType === s.value ? {
                borderColor: 'var(--accent-dim)',
                background: 'rgba(63,185,80,0.05)'
              } : {}}>
              <div className="flex items-center justify-between mb-1.5">
                <span className={`scope-chip ${s.scopeClass}`}>{s.scope}</span>
                {sourceType === s.value && <CheckCircle size={13} style={{ color: 'var(--accent)' }} />}
              </div>
              <div className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                {s.label}
              </div>
            </button>
          ))}
        </div>
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>{selected?.desc}</p>
      </div>

      {/* Drop zone */}
      {!result && (
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          className={clsx('drop-zone rounded-lg p-8 text-center mb-4 cursor-pointer', { active: dragging })}
          onClick={() => document.getElementById('file-input').click()}>
          <input id="file-input" type="file" className="hidden"
            accept={selected?.accept}
            onChange={e => handleFile(e.target.files[0])} />

          {file ? (
            <div className="flex items-center justify-center gap-3">
              <FileText size={20} style={{ color: 'var(--accent)' }} />
              <div>
                <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{file.name}</div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {(file.size / 1024).toFixed(1)} KB
                </div>
              </div>
              <button onClick={(e) => { e.stopPropagation(); setFile(null) }}
                className="ml-2 p-1 rounded" style={{ color: 'var(--text-muted)' }}>
                <X size={14} />
              </button>
            </div>
          ) : (
            <div>
              <UploadIcon size={28} className="mx-auto mb-3" style={{ color: 'var(--text-muted)' }} />
              <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Drop a CSV file here
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                or click to browse · {selected?.accept}
              </div>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 text-sm px-3 py-2 rounded-md mb-4"
          style={{ background: 'rgba(248,81,73,0.08)', color: 'var(--danger)', border: '1px solid rgba(248,81,73,0.15)' }}>
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!result && (
        <button onClick={handleSubmit} disabled={!file || loading}
          className="btn-primary w-full justify-center py-2.5"
          style={{ opacity: (!file || loading) ? 0.5 : 1 }}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <UploadIcon size={14} />}
          {loading ? 'Processing…' : 'Upload & Process'}
        </button>
      )}

      {/* Result */}
      {result && (
        <div className="card p-4 fade-in">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle size={16} style={{ color: 'var(--accent)' }} />
            <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Upload complete
            </div>
            <span className={`badge badge-${result.status === 'COMPLETE' ? 'approved' : 'pending'} ml-auto`}>
              {result.status}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 mb-4 text-center">
            {[
              { label: 'Records created', value: result.success_count, color: 'var(--accent)' },
              { label: 'Parse errors', value: result.error_count, color: result.error_count > 0 ? 'var(--danger)' : 'var(--text-muted)' },
              { label: 'With warnings', value: result.warning_count, color: result.warning_count > 0 ? 'var(--warning)' : 'var(--text-muted)' },
            ].map(s => (
              <div key={s.label} className="rounded-md p-2" style={{ background: 'var(--surface-2)' }}>
                <div className="text-xl font-bold mono" style={{ color: s.color }}>{s.value}</div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{s.label}</div>
              </div>
            ))}
          </div>

          {result.processing_log?.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>PROCESSING LOG</div>
              <div className="rounded p-2 text-xs mono overflow-y-auto max-h-40 space-y-1"
                style={{ background: 'var(--bg)' }}>
                {result.processing_log.slice(0, 30).map((l, i) => (
                  <div key={i}
                    style={{ color: l.level === 'error' ? 'var(--danger)' : l.level === 'warning' ? 'var(--warning)' : 'var(--text-muted)' }}>
                    [{l.level?.toUpperCase()}] row {l.row}: {l.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <button onClick={() => navigate('/records')} className="btn-primary flex-1 justify-center">
              Review records →
            </button>
            <button onClick={() => setResult(null)} className="btn-ghost">
              Upload another
            </button>
          </div>
        </div>
      )}

      {/* Sample data note */}
      {!result && !file && (
        <div className="mt-6 text-xs p-3 rounded-md" style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
          <div className="font-semibold mb-1">Expected file formats:</div>
          <div>• <strong>SAP:</strong> ALV CSV with MANDT, WERKS, MATNR, MAKTX, MENGE, MEINS, BLDAT columns (comma or semicolon delimited, German headers OK)</div>
          <div>• <strong>Utility:</strong> Portal CSV with account number, meter ID, billing period dates, usage kWh columns</div>
          <div>• <strong>Travel:</strong> Concur/Navan CSV with trip ID, travel date, type (FLIGHT/HOTEL/CAR), origin/destination IATA codes, cabin class, nights</div>
        </div>
      )}
    </div>
  )
}
