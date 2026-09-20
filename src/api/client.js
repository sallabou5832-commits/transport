const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

function getTokens() {
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  }
}

export function setTokens(access, refresh) {
  localStorage.setItem('access_token', access)
  if (refresh) localStorage.setItem('refresh_token', refresh)
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

async function refreshAccessToken() {
  const { refresh } = getTokens()
  if (!refresh) return null

  const response = await fetch(`${API_BASE_URL}/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
  if (!response.ok) return null

  const data = await response.json()
  setTokens(data.access, null)
  return data.access
}

class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.status = status
    this.data = data
  }
}

export async function apiFetch(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const { access } = getTokens()
    if (access) headers.Authorization = `Bearer ${access}`
  }

  let response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 401 && auth) {
    const newAccess = await refreshAccessToken()
    if (newAccess) {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: { ...headers, Authorization: `Bearer ${newAccess}` },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
    } else {
      clearTokens()
    }
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const message = extractErrorMessage(data) || `Erreur ${response.status}`
    throw new ApiError(message, response.status, data)
  }

  return data
}

function extractErrorMessage(data) {
  if (!data) return null
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return data.join(' ')
  if (data.detail) return data.detail
  const firstKey = Object.keys(data)[0]
  if (!firstKey) return null
  const value = data[firstKey]
  const text = Array.isArray(value) ? value.join(' ') : String(value)
  return firstKey === 'non_field_errors' || firstKey === 'detail' ? text : `${firstKey}: ${text}`
}

export { ApiError, API_BASE_URL }
