import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import {
  LIBELLES_PAGES_ANNEXES,
  PAGES_ANNEXES,
  PAGES_PARAMETRES,
  POLE_DU_ROLE,
  ROLE_LABELS,
  dashboardPathForRole,
} from '../auth/roles.js'
import { POLES } from '../lib/rh.js'
import AlertesCloche from './AlertesCloche.jsx'
import GamificationBandeau from './GamificationBandeau.jsx'

export default function Layout({ title, children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  // Mot de passe provisoire : rien d'autre n'est accessible tant qu'il n'est pas remplacé (ni menus, ni alertes, ni jeu).
  const provisoire = Boolean(user?.doit_changer_mot_de_passe)
  const annexes = Object.keys(PAGES_ANNEXES).filter((chemin) => PAGES_ANNEXES[chemin].includes(user?.role))
  const parametres = annexes.filter((chemin) => PAGES_PARAMETRES.includes(chemin))
  const nom = user?.first_name || user?.username || ''
  // Chaque pôle a sa couleur (liseré de la barre, titres) : on sait d'un coup d'œil dans quel pôle on travaille.
  const pole = POLE_DU_ROLE[user?.role]

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="layout" data-pole={pole}>
      <header className="topbar">
        <Link to={dashboardPathForRole(user?.role)} className="topbar-marque">
          <span className="topbar-logo" aria-hidden="true">
            TC
          </span>
          <strong>Transport Coord</strong>
        </Link>
        <div className="topbar-user">
          {!provisoire && <AlertesCloche />}
          <span className="topbar-compte">
            <span className="topbar-avatar" aria-hidden="true">
              {nom.charAt(0).toUpperCase()}
            </span>
            <span>
              {nom} — {ROLE_LABELS[user?.role] || user?.role}
            </span>
            {pole && <span className="topbar-pole">{POLES[pole] || 'Plateforme'}</span>}
          </span>
          <button type="button" className="topbar-deconnexion" onClick={handleLogout}>
            Déconnexion
          </button>
        </div>
        {!provisoire && (
          <nav className="topbar-nav" aria-label="Navigation">
            <NavLink to={dashboardPathForRole(user?.role)}>Tableau de bord</NavLink>
            {annexes
              .filter((chemin) => !PAGES_PARAMETRES.includes(chemin))
              .map((chemin) => (
                <NavLink key={chemin} to={chemin}>
                  {LIBELLES_PAGES_ANNEXES[chemin]}
                </NavLink>
              ))}
            {parametres.length > 0 && (
              <details className="topbar-menu">
                <summary>Paramètres</summary>
                <div className="topbar-menu-liste">
                  {parametres.map((chemin) => (
                    <NavLink key={chemin} to={chemin}>
                      {LIBELLES_PAGES_ANNEXES[chemin]}
                    </NavLink>
                  ))}
                </div>
              </details>
            )}
          </nav>
        )}
      </header>
      {!provisoire && <GamificationBandeau />}
      <main className="content">
        {title && <h1 className="page-titre">{title}</h1>}
        {children}
      </main>
    </div>
  )
}
