import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'

const STATUT_LABELS = { ouvert: 'Ouvert', en_cours: 'En cours', termine: 'Terminé' }

export default function ChefAtelierDashboard() {
  const [ordres, setOrdres] = useState([])
  const [vehicules, setVehicules] = useState({})
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([apiFetch('/ordres-reparation/'), apiFetch('/vehicules/')])
      .then(([ordresData, vehiculesData]) => {
        setOrdres(ordresData.filter((o) => o.statut !== 'termine'))
        setVehicules(Object.fromEntries(vehiculesData.map((v) => [v.id, v])))
      })
      .catch((err) => setError(err.message))
  }, [])

  return (
    <Layout title="Tableau de bord — Chef d'atelier">
      <Alert>{error}</Alert>
      {ordres.length === 0 && !error && <p>Aucun ordre de réparation en cours.</p>}
      {ordres.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Véhicule</th>
              <th>Description</th>
              <th>Statut</th>
              <th>Créé le</th>
            </tr>
          </thead>
          <tbody>
            {ordres.map((ordre) => (
              <tr key={ordre.id}>
                <td>{vehicules[ordre.vehicule]?.immatriculation || ordre.vehicule}</td>
                <td>{ordre.description}</td>
                <td>{STATUT_LABELS[ordre.statut] || ordre.statut}</td>
                <td>{new Date(ordre.date_creation).toLocaleString('fr-FR')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Layout>
  )
}
