import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'

const LABELS_VEHICULE = {
  disponible: 'Disponible',
  en_ligne: 'En ligne',
  en_maintenance: 'En maintenance',
  bloque_securite: 'Bloqué sécurité',
}

const LABELS_GRAVITE = { faible: 'Faible', moyenne: 'Moyenne', grave: 'Grave' }

export default function DirectionDashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/dashboard/direction/')
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <Layout title="Tableau de bord — Direction">
      <Alert>{error}</Alert>
      {!data && !error && <p>Chargement…</p>}
      {data && (
        <div className="cards-grid">
          <section className="card">
            <h2>Véhicules par statut</h2>
            <ul className="stat-list">
              {Object.entries(data.vehicules_par_statut).map(([statut, nombre]) => (
                <li key={statut}>
                  <span>{LABELS_VEHICULE[statut] || statut}</span>
                  <strong>{nombre}</strong>
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h2>Incidents ouverts (7 derniers jours)</h2>
            <ul className="stat-list">
              {Object.entries(data.incidents_ouverts_par_gravite_7_jours).map(([gravite, nombre]) => (
                <li key={gravite}>
                  <span>{LABELS_GRAVITE[gravite] || gravite}</span>
                  <strong>{nombre}</strong>
                </li>
              ))}
            </ul>
          </section>

          <section className="card card-highlight">
            <h2>Recettes du jour</h2>
            <p className="big-number">{Number(data.recettes_du_jour).toLocaleString('fr-FR')} FCFA</p>
          </section>

          <section className="card">
            <h2>Pièces sous seuil d'alerte</h2>
            <p className="big-number">{data.pieces_sous_seuil}</p>
          </section>

          <section className="card">
            <h2>Assurances à échéance proche (&lt; 30 jours)</h2>
            <p className="big-number">{data.assurances_echeance_proche}</p>
          </section>
        </div>
      )}
    </Layout>
  )
}
