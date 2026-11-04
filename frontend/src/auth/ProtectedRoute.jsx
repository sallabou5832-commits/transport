import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { dashboardPathForRole } from './roles.js'

export default function ProtectedRoute({ roles, children }) {
  const { user, loading } = useAuth()
  const { pathname } = useLocation()

  if (loading) return <p className="page-loading">Chargement…</p>
  if (!user) return <Navigate to="/login" replace />
  // Mot de passe provisoire : le serveur refuse tout le reste tant qu'il n'est pas remplacé.
  if (user.doit_changer_mot_de_passe && pathname !== '/parametres') return <Navigate to="/parametres" replace />

  if (roles && !roles.includes(user.role)) {
    return <Navigate to={dashboardPathForRole(user.role)} replace />
  }

  return children
}
