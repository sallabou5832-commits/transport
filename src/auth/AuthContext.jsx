import { createContext, useContext, useEffect, useState } from 'react'
import { apiFetch, clearTokens, setTokens } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const access = localStorage.getItem('access_token')
    if (!access) {
      setLoading(false)
      return
    }
    apiFetch('/auth/me/')
      .then(setUser)
      .catch(() => {
        clearTokens()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  async function login(username, password) {
    const tokens = await apiFetch('/auth/login/', {
      method: 'POST',
      body: { username, password },
      auth: false,
    })
    setTokens(tokens.access, tokens.refresh)
    const me = await apiFetch('/auth/me/')
    setUser(me)
    return me
  }

  function logout() {
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth doit être utilisé à l’intérieur de AuthProvider')
  return context
}
