import { createContext, useContext, useEffect, useState } from 'react'
import { apiFetch, clearTokens, setTokens, surSessionExpiree } from '../api/client.js'

const AuthContext = createContext(null)

const aUnJeton = () => Boolean(localStorage.getItem('access_token'))

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Sans jeton, il n'y a rien à charger : l'état est connu d'emblée (pas de `setState` dans l'effet).
  const [loading, setLoading] = useState(aUnJeton)

  useEffect(() => {
    if (!aUnJeton()) return
    apiFetch('/auth/me/')
      .then(setUser)
      .catch(() => {
        clearTokens()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  // Session finie pour de bon (jeton de renouvellement refusé, compte suspendu) : retour à la connexion, sans attendre un
  // rechargement de la page.
  useEffect(() => surSessionExpiree(() => setUser(null)), [])

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
