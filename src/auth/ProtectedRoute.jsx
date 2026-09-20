import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { dashboardPathForRole } from './roles.js'

export default function ProtectedRoute({ roles, children }) {
  const { user, loading } = useAuth()

  if (loading) return <p className="page-loading">Chargement…</p>
  if (!user) return <Navigate to="/login" replace />

  if (roles && !roles.includes(user.role)) {
    return <Navigate to={dashboardPathForRole(user.role)} replace />
  }

  return children
}
