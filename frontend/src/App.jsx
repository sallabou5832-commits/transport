import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext.jsx'
import ProtectedRoute from './auth/ProtectedRoute.jsx'
import { DASHBOARD_ROLES, PAGES_ANNEXES } from './auth/roles.js'
import LoginPage from './pages/LoginPage.jsx'
import AuditPage from './pages/AuditPage.jsx'
import ConfigurationPage from './pages/ConfigurationPage.jsx'
import CadrePage from './pages/CadrePage.jsx'
import PilotagePage from './pages/PilotagePage.jsx'
import InvestissementsPage from './pages/InvestissementsPage.jsx'
import SecretariatPage from './pages/SecretariatPage.jsx'
import NotesPage from './pages/NotesPage.jsx'
import ComptabilitePage from './pages/ComptabilitePage.jsx'
import FinancesPage from './pages/FinancesPage.jsx'
import EspacePage from './pages/EspacePage.jsx'
import ModelesPage from './pages/ModelesPage.jsx'
import SynthesePage from './pages/SynthesePage.jsx'
import DirectionDashboard from './pages/DirectionDashboard.jsx'
import QhseDashboard from './pages/QhseDashboard.jsx'
import ExploitationDashboard from './pages/ExploitationDashboard.jsx'
import ChefGareDashboard from './pages/ChefGareDashboard.jsx'
import ChefLigneDashboard from './pages/ChefLigneDashboard.jsx'
import GuichetierDashboard from './pages/GuichetierDashboard.jsx'
import BagagisteDashboard from './pages/BagagisteDashboard.jsx'
import ChauffeurDashboard from './pages/ChauffeurDashboard.jsx'
import ControleurDashboard from './pages/ControleurDashboard.jsx'
import TechniqueDashboard from './pages/TechniqueDashboard.jsx'
import MagasinierDashboard from './pages/MagasinierDashboard.jsx'
import ChefAtelierDashboard from './pages/ChefAtelierDashboard.jsx'
import MecanicienDashboard from './pages/MecanicienDashboard.jsx'
import RhDashboard from './pages/RhDashboard.jsx'
import FinanceDashboard from './pages/FinanceDashboard.jsx'
import JuridiqueDashboard from './pages/JuridiqueDashboard.jsx'
import PlateformeDashboard from './pages/PlateformeDashboard.jsx'
import GenericDashboard from './pages/GenericDashboard.jsx'

// Une page par route de DASHBOARD_ROLES (auth/roles.js) : les rôles autorisés y sont déclarés une seule fois.
const PAGES = {
  '/dashboard/direction': DirectionDashboard,
  '/dashboard/qhse': QhseDashboard,
  '/dashboard/exploitation': ExploitationDashboard,
  '/dashboard/gare': ChefGareDashboard,
  '/dashboard/ligne': ChefLigneDashboard,
  '/dashboard/guichetier': GuichetierDashboard,
  '/dashboard/bagagiste': BagagisteDashboard,
  '/dashboard/chauffeur': ChauffeurDashboard,
  '/dashboard/controle': ControleurDashboard,
  '/dashboard/technique': TechniqueDashboard,
  '/dashboard/magasinier': MagasinierDashboard,
  '/dashboard/atelier': ChefAtelierDashboard,
  '/dashboard/mecanicien': MecanicienDashboard,
  '/dashboard/rh': RhDashboard,
  '/dashboard/finance': FinanceDashboard,
  '/dashboard/juridique': JuridiqueDashboard,
  '/dashboard/plateforme': PlateformeDashboard,
  '/audit': AuditPage,
  '/configuration': ConfigurationPage,
  '/cadre': CadrePage,
  '/pilotage': PilotagePage,
  '/investissements': InvestissementsPage,
  '/secretariat': SecretariatPage,
  '/comptabilite': ComptabilitePage,
  '/finances': FinancesPage,
  '/espace': EspacePage,
  '/modeles': ModelesPage,
  '/synthese': SynthesePage,
  '/notes': NotesPage,
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<LoginPage />} />

          {Object.entries(PAGES).map(([path, Page]) => (
            <Route
              key={path}
              path={path}
              element={
                <ProtectedRoute roles={DASHBOARD_ROLES[path] ?? PAGES_ANNEXES[path]}>
                  <Page />
                </ProtectedRoute>
              }
            />
          ))}

          <Route
            path="/dashboard/generique"
            element={
              <ProtectedRoute>
                <GenericDashboard />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
