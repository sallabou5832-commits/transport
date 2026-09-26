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

/** Le jeton d'accès courant, pour ce qu'un en-tête `Authorization` ne peut pas faire (le flux de la
 * carte, `useFluxCarte.js`) : un navigateur ne pose pas d'en-tête sur une connexion WebSocket. */
export function getAccessToken() {
  return getTokens().access
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

// `brut` : le corps est envoyé tel quel (un FormData de fichier) et le navigateur pose lui-même l'en-tête Content-Type.
async function envoyer(path, { method = 'GET', body, auth = true, brut = false } = {}) {
  const headers = brut ? {} : { 'Content-Type': 'application/json' }
  if (auth) {
    const { access } = getTokens()
    if (access) headers.Authorization = `Bearer ${access}`
  }
  const corps = body === undefined ? undefined : brut ? body : JSON.stringify(body)

  let response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: corps })

  if (response.status === 401 && auth) {
    const newAccess = await refreshAccessToken()
    if (newAccess) {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: { ...headers, Authorization: `Bearer ${newAccess}` },
        body: corps,
      })
    } else {
      clearTokens()
    }
  }
  return response
}

async function lireJson(response) {
  const isJson = response.headers.get('content-type')?.includes('application/json')
  return isJson ? await response.json().catch(() => null) : null
}

export async function apiFetch(path, options) {
  const response = await envoyer(path, options)
  const data = await lireJson(response)

  if (!response.ok) {
    const message = extractErrorMessage(data) || `Erreur ${response.status}`
    throw new ApiError(message, response.status, data)
  }

  return data
}

/** Envoie un fichier (`FormData`) : pièces jointes des sinistres, fichiers des modèles de documents. */
export async function apiEnvoyer(path, formData) {
  const response = await envoyer(path, { method: 'POST', body: formData, brut: true })
  const data = await lireJson(response)

  if (!response.ok) {
    throw new ApiError(extractErrorMessage(data) || `Erreur ${response.status}`, response.status, data)
  }

  return data
}

/**
 * Télécharge un fichier servi par l'API (export CSV de la finance). Un simple lien ne joindrait pas le jeton d'accès : on
 * récupère donc le fichier avec lui, puis on le dépose dans le navigateur. Le nom vient de l'en-tête de la réponse.
 */
export async function apiTelecharger(path, nomParDefaut = 'export.csv') {
  const response = await envoyer(path)
  if (!response.ok) {
    const data = await lireJson(response)
    throw new ApiError(extractErrorMessage(data) || `Erreur ${response.status}`, response.status, data)
  }
  const nom = /filename="([^"]+)"/.exec(response.headers.get('content-disposition') || '')?.[1] || nomParDefaut
  const url = URL.createObjectURL(await response.blob())
  const lien = document.createElement('a')
  lien.href = url
  lien.download = nom
  lien.click()
  URL.revokeObjectURL(url)
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
