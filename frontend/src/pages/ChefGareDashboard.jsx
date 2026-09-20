import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Jauge from '../components/Jauge.jsx'

const STATUT_LABELS = { planifie: 'Planifié', en_cours: 'En cours', termine: 'Terminé' }

export default function ChefGareDashboard() {
  const { user } = useAuth()
  const [gare, setGare] = useState(null)
  const [lignes, setLignes] = useState([])
  const [vehicules, setVehicules] = useState([])
  const [departs, setDeparts] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      apiFetch('/gares/'),
      apiFetch('/lignes/'),
      apiFetch('/vehicules/'),
      apiFetch('/departs/'),
    ])
      .then(([gares, lignesData, vehiculesData, departsData]) => {
        setGare(gares.find((g) => g.chef === user.id) || null)
        setLignes(lignesData)
        setVehicules(vehiculesData)
        setDeparts(departsData)
      })
      .catch((err) => setError(err.message))
  }, [user.id])

  const lignesParId = Object.fromEntries(lignes.map((l) => [l.id, l]))
  const vehiculesParId = Object.fromEntries(vehicules.map((v) => [v.id, v]))

  const departsDeLaGare = gare
    ? departs.filter((d) => lignesParId[d.ligne]?.gare_depart === gare.id)
    : []

  return (
    <Layout title="Tableau de bord — Chef de gare">
      <Alert>{error}</Alert>
      {!gare && !error && <p>Chargement…</p>}
      {gare && (
        <>
          <h2>{gare.nom}</h2>
          {departsDeLaGare.length === 0 ? (
            <p>Aucun départ prévu pour cette gare.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Ligne</th>
                  <th>Date / heure</th>
                  <th>Statut</th>
                  <th>Jauge de remplissage</th>
                </tr>
              </thead>
              <tbody>
                {departsDeLaGare.map((depart) => {
                  const ligne = lignesParId[depart.ligne]
                  const vehicule = vehiculesParId[depart.vehicule]
                  return (
                    <tr key={depart.id}>
                      <td>{ligne?.nom}</td>
                      <td>{new Date(depart.date_heure).toLocaleString('fr-FR')}</td>
                      <td>{STATUT_LABELS[depart.statut] || depart.statut}</td>
                      <td>
                        <Jauge vendues={depart.places_vendues} capacite={vehicule?.capacite} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </>
      )}
    </Layout>
  )
}
