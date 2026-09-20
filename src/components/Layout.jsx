import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'

const ROLE_LABELS = {
  pdg: 'PDG',
  secretaire_general: 'Secrétaire général',
  qhse: 'QHSE',
  directeur_exploitation: 'Directeur exploitation',
  chef_gare: 'Chef de gare',
  chef_ligne: 'Chef de ligne',
  guichetier: 'Guichetier',
  bagagiste: 'Bagagiste',
  chauffeur_principal: 'Chauffeur principal',
  chauffeur_relais: 'Chauffeur relais',
  controleur_ligne: 'Contrôleur de ligne',
  directeur_technique: 'Directeur technique',
  magasinier: 'Magasinier',
  chef_atelier: "Chef d'atelier",
  drh: 'DRH',
  directeur_financier: 'Directeur financier',
  responsable_juridique: 'Responsable juridique',
  superadmin: 'Super administrateur',
}

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
