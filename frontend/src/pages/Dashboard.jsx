import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { AlertTriangle, CheckCircle, Clock, TrendingUp, Database, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const SCOPE_COLORS = { scope_1: '#ff7043', scope_2: '#42a5f5', scope_3: '#ab47bc' }
const SCOPE_LABELS = { scope_1: 'Scope 1', scope_2: 'Scope 2', scope_3: 'Scope 3' }
const STATUS_COLORS = { pending: '#d29922', approved: '#3fb950', rejected: '#f85149', flagged: '#388bfd' }

function StatCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{label}</div>
        <div className="w-7 h-7 rounded-md flex items-center justify-center"
          style={{ background: `${color}1a` }}>
          <Icon size={15} style={{ color }} />
        </div>
      </div>
      <div className="text-2xl font-bold mono" style={{ color: 'var(--text-primary)' }}>{value}</div>
      {sub && <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{sub}</div>}
    </div>
  )
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs">
      <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{payload[0].name}</div>
      <div style={{ color: 'var(--text-secondary)' }}>{Number(payload[0].value).toLocaleString()} kg CO₂e</div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.stats().then(setStats).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
    </div>
  )

  if (!stats) return null

  const scopeData = Object.entries(stats.scope_breakdown)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ name: SCOPE_LABELS[k] || k, value: Math.round(v), color: SCOPE_COLORS[k] }))

  const categoryData = Object.entries(stats.category_breakdown)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([k, v]) => ({
      name: k.replace(/_/g, ' ').replace(/business travel /i, ''),
      value: Math.round(v)
    }))

  const statusData = Object.entries(stats.status_counts)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ name: k, value: v, color: STATUS_COLORS[k] || '#666' }))

  const totalKg = stats.total_co2e_kg
  const totalT = (totalKg / 1000).toFixed(2)

  return (
    <div className="p-6 fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          Emissions Dashboard
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
          Acme Manufacturing Pvt. Ltd. · Reporting Year 2024
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          icon={TrendingUp}
          label="Total CO₂e"
          value={`${Number(totalT).toLocaleString()} t`}
          sub="tonnes CO₂ equivalent"
          color="var(--accent)"
        />
        <StatCard
          icon={Clock}
          label="Pending Review"
          value={stats.pending_review}
          sub="records awaiting analyst"
          color="var(--warning)"
        />
        <StatCard
          icon={AlertTriangle}
          label="With Warnings"
          value={stats.records_with_warnings}
          sub="flagged data quality issues"
          color="var(--danger)"
        />
        <StatCard
          icon={CheckCircle}
          label="Approved"
          value={stats.status_counts.approved || 0}
          sub="ready for audit"
          color="var(--accent)"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* Scope breakdown */}
        <div className="card p-4">
          <div className="text-xs font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>
            EMISSIONS BY SCOPE
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={scopeData} cx="50%" cy="50%" innerRadius={48} outerRadius={72}
                dataKey="value" paddingAngle={3}>
                {scopeData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {scopeData.map((d, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                  <span style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                </div>
                <span className="mono" style={{ color: 'var(--text-primary)' }}>
                  {d.value.toLocaleString()} kg
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Category breakdown bar chart */}
        <div className="card p-4 md:col-span-2">
          <div className="text-xs font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>
            EMISSIONS BY CATEGORY (kg CO₂e)
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryData} layout="vertical"
              margin={{ top: 0, right: 20, left: 80, bottom: 0 }}>
              <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }}
                axisLine={false} tickLine={false} width={80} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="value" fill="var(--accent-dim)" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Status + recent jobs row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Review status */}
        <div className="card p-4">
          <div className="text-xs font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>
            REVIEW STATUS
          </div>
          <div className="space-y-2">
            {statusData.map(d => (
              <div key={d.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                  <span className="capitalize" style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                </div>
                <span className="mono text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {d.value}
                </span>
              </div>
            ))}
          </div>
          <button onClick={() => navigate('/records?status=pending')}
            className="btn-ghost w-full justify-center text-xs mt-4">
            Review pending →
          </button>
        </div>

        {/* Recent jobs */}
        <div className="card p-4 md:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              RECENT INGESTION JOBS
            </div>
            <button onClick={() => navigate('/jobs')} className="text-xs" style={{ color: 'var(--accent)' }}>
              View all
            </button>
          </div>
          <div className="space-y-2">
            {(stats.recent_jobs || []).map(job => (
              <div key={job.id} className="flex items-center justify-between text-xs py-1.5"
                style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <div>
                  <div className="font-medium truncate max-w-xs" style={{ color: 'var(--text-primary)' }}>
                    {job.filename}
                  </div>
                  <div style={{ color: 'var(--text-muted)' }}>
                    {job.source_type_label} · {new Date(job.uploaded_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="flex items-center gap-3 ml-3">
                  <span style={{ color: 'var(--accent)' }}>{job.success_count} rows</span>
                  {job.error_count > 0 && (
                    <span style={{ color: 'var(--danger)' }}>{job.error_count} errors</span>
                  )}
                  <span className={`badge badge-${job.status.toLowerCase() === 'complete' ? 'approved' : 'pending'}`}>
                    {job.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
