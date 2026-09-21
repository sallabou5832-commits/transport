import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import { PAGES_ANNEXES, ROLE_LABELS, dashboardPathForRole } from '../auth/roles.js'

export default function Layout({ title, children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="layout">
      <header className="topbar">
        <div>
          <strong>Transport Coord</strong>
          <span className="topbar-title">{title}</span>
        </div>
        <div className="topbar-user">
          <nav className="topbar-nav" aria-label="Navigation">
            <Link to={dashboardPathForRole(user?.role)}>Tableau de bord</Link>
            {PAGES_ANNEXES['/audit'].includes(user?.role) && <Link to="/audit">Journal d&apos;audit</Link>}
          </nav>
          <span>
            {user?.first_name || user?.username} — {ROLE_LABELS[user?.role] || user?.role}
          </span>
          <button type="button" onClick={handleLogout}>
            Déconnexion
          </button>
        </div>
      </header>
      <main className="content">{children}</main>
    </div>
  )
}
