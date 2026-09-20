import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext.jsx'
import ProtectedRoute from './auth/ProtectedRoute.jsx'
import { DASHBOARD_ROLES, ROLES_GENERIQUES } from './auth/roles.js'
import LoginPage from './pages/LoginPage.jsx'
import DirectionDashboard from './pages/DirectionDashboard.jsx'
import ChefGareDashboard from './pages/ChefGareDashboard.jsx'
import GuichetierDashboard from './pages/GuichetierDashboard.jsx'
import ChauffeurDashboard from './pages/ChauffeurDashboard.jsx'
import MagasinierDashboard from './pages/MagasinierDashboard.jsx'
import ChefAtelierDashboard from './pages/ChefAtelierDashboard.jsx'
import GenericDashboard from './pages/GenericDashboard.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<LoginPage />} />

          <Route
            path="/dashboard/direction"
            element={
              <ProtectedRoute roles={DASHBOARD_ROLES['/dashboard/direction']}>
                <DirectionDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/gare"
            element={
              <ProtectedRoute roles={DASHBOARD_ROLES['/dashboard/gare']}>
                <ChefGareDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/guichetier"
            element={
              <ProtectedRoute roles={DASHBOARD_ROLES['/dashboard/guichetier']}>
                <GuichetierDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/chauffeur"
            element={
              <ProtectedRoute roles={DASHBOARD_ROLES['/dashboard/chauffeur']}>
                <ChauffeurDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/magasinier"
            element={
              <ProtectedRoute roles={DASHBOARD_ROLES['/dashboard/magasinier']}>
                <MagasinierDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/atelier"
            element={
              <ProtectedRoute roles={DASHBOARD_ROLES['/dashboard/atelier']}>
                <ChefAtelierDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/generique"
            element={
              <ProtectedRoute roles={ROLES_GENERIQUES}>
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
