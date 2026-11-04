import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import { dashboardPathForRole } from '../auth/roles.js'
import Alert from '../components/Alert.jsx'
import { LABELS_DUREE_SESSION } from '../lib/format.js'

// Les durées proposées quand on coche « Rester connecté » (sans case cochée : 1 jour, comme avant).
const DUREES_LONGUES = ['semaine', 'mois', 'deconnexion']

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  // Décochée à chaque ouverture : sur un poste partagé (guichet), la session ne doit pas rester ouverte par mégarde.
  const [resterConnecte, setResterConnecte] = useState(false)
  const [duree, setDuree] = useState('deconnexion')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user) {
    return <Navigate to={dashboardPathForRole(user.role)} replace />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const me = await login(username, password, resterConnecte ? duree : undefined)
      navigate(dashboardPathForRole(me.role), { replace: true })
    } catch (err) {
      setError(err.message || 'Identifiants invalides.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Transport Coord</h1>
        <p className="login-subtitle">Connexion</p>
        <Alert>{error}</Alert>
        <label>
          Identifiant
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Mot de passe
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <label className="checkbox-ligne">
          <input type="checkbox" checked={resterConnecte} onChange={(e) => setResterConnecte(e.target.checked)} />
          Rester connecté
        </label>
        {resterConnecte && (
          <label>
            Pendant
            <select value={duree} onChange={(e) => setDuree(e.target.value)}>
              {DUREES_LONGUES.map((valeur) => (
                <option key={valeur} value={valeur}>
                  {LABELS_DUREE_SESSION[valeur]}
                </option>
              ))}
            </select>
            <span className="muted">Seulement sur un appareil personnel. Votre compagnie peut limiter cette durée.</span>
          </label>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>
    </div>
  )
}
