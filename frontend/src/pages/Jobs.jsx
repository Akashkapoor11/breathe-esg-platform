import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Loader2, ChevronDown, ChevronRight, FileText } from 'lucide-react'

function statusColor(s) {
  return { COMPLETE: 'var(--accent)', FAILED: 'var(--danger)', PARTIAL: 'var(--warning)', PROCESSING: 'var(--info)', PENDING: 'var(--text-muted)' }[s] || 'var(--text-muted)'
}

export default function Jobs() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    api.jobs().then(d => setJobs(d.results || d)).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
    </div>
  )

  return (
    <div className="p-6 fade-in">
      <div className="mb-5">
        <h1 className="text-xl font-bold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          Ingestion Jobs
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          History of all file uploads and their processing results
        </p>
      </div>

      {jobs.length === 0 ? (
        <div className="card p-12 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
          No jobs yet. <a href="/upload" style={{ color: 'var(--accent)' }}>Upload a file</a> to get started.
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map(job => (
            <div key={job.id} className="card overflow-hidden">
              <div className="flex items-center gap-4 px-4 py-3 cursor-pointer"
                onClick={() => setExpanded(e => e === job.id ? null : job.id)}>
                {expanded === job.id
                  ? <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
                  : <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}

                <FileText size={14} style={{ color: 'var(--text-muted)' }} />

                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                    {job.filename}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {job.source_type_label} · {new Date(job.uploaded_at).toLocaleString()}
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs">
                  <span className="mono" style={{ color: 'var(--accent)' }}>
                    {job.success_count} rows
                  </span>
                  {job.error_count > 0 && (
                    <span className="mono" style={{ color: 'var(--danger)' }}>
                      {job.error_count} errors
                    </span>
                  )}
                  {job.warning_count > 0 && (
                    <span className="mono" style={{ color: 'var(--warning)' }}>
                      {job.warning_count} warnings
                    </span>
                  )}
                  <span className="font-semibold" style={{ color: statusColor(job.status) }}>
                    {job.status}
                  </span>
                </div>
              </div>

              {expanded === job.id && job.processing_log?.length > 0 && (
                <div className="border-t px-4 py-3" style={{ borderColor: 'var(--border)' }}>
                  <div className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
                    PROCESSING LOG
                  </div>
                  <div className="rounded p-2 text-xs mono overflow-y-auto max-h-52 space-y-0.5"
                    style={{ background: 'var(--bg)' }}>
                    {job.processing_log.map((l, i) => (
                      <div key={i}
                        style={{ color: l.level === 'error' ? 'var(--danger)' : l.level === 'warning' ? 'var(--warning)' : 'var(--text-muted)' }}>
                        [{l.level?.toUpperCase() || 'INFO'}] row {l.row}: {l.message}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {expanded === job.id && (!job.processing_log || job.processing_log.length === 0) && (
                <div className="border-t px-4 py-3 text-xs" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                  No log entries for this job.
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
