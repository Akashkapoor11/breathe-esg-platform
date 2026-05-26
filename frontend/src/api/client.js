const BASE = import.meta.env.VITE_API_URL || '/api'

function getToken() {
  return localStorage.getItem('access_token')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  // Don't set Content-Type for FormData (let browser set multipart boundary)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    if (options.body && typeof options.body !== 'string') {
      options.body = JSON.stringify(options.body)
    }
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    let err
    try { err = await res.json() } catch { err = { error: res.statusText } }
    throw Object.assign(new Error(err.error || 'Request failed'), { data: err, status: res.status })
  }

  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  if (ct.includes('text/csv')) return res.blob()
  return res
}

export const api = {
  // Auth
  login: (username, password) =>
    request('/auth/login/', { method: 'POST', body: { username, password } }),

  // Dashboard
  stats: () => request('/stats/'),

  // Jobs
  jobs: () => request('/jobs/'),
  uploadFile: (file, sourceType) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('source_type', sourceType)
    return request('/jobs/upload/', { method: 'POST', body: fd })
  },

  // Records
  records: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null))
    ).toString()
    return request(`/records/${qs ? '?' + qs : ''}`)
  },
  record: (id) => request(`/records/${id}/`),
  review: (id, action, note = '') =>
    request(`/records/${id}/review/`, { method: 'POST', body: { action, note } }),
  bulkReview: (ids, action, note = '') =>
    request('/records/bulk-review/', { method: 'POST', body: { ids, action, note } }),
  exportCSV: () => request('/records/export/'),
}
