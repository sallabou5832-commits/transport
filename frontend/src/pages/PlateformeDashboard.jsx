import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Kpi from '../components/Kpi.jsx'
import { formatDate, formatFCFA } from '../lib/format.js'

export default function PlateformeDashboard() {
  const { data, error, loading } = useChargement(() => apiFetch('/dashboard/plateforme/'), {
    intervalleMs: 60000,
  })

  if (!data) {
    return (
      <Layout title="Tableau de bord — Plateforme">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { totaux, compagnies } = data

  return (
    <Layout title="Tableau de bord — Plateforme">
      <Alert>{error}</Alert>
      <p className="muted">Toutes les compagnies clientes, situation du {formatDate(data.date)}.</p>

      <div className="cards-grid">
        <Kpi titre="Compagnies" valeur={totaux.compagnies} />
        <Kpi titre="Agents" valeur={totaux.agents} />
        <Kpi titre="Véhicules" valeur={totaux.vehicules} />
        <Kpi titre="Tickets vendus aujourd'hui" valeur={totaux.tickets_du_jour} />
        <Kpi titre="Recettes du jour" valeur={formatFCFA(totaux.recettes_du_jour)} ton="vert" />
      </div>

      <h2 className="section-title">Compagnies</h2>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Compagnie</th>
              <th>Agents</th>
              <th>Gares</th>
              <th>Lignes</th>
              <th>Véhicules</th>
              <th>Départs du jour</th>
              <th>Tickets du jour</th>
              <th>Recettes du jour</th>
              <th>Alertes</th>
            </tr>
          </thead>
          <tbody>
            {compagnies.map((c) => (
              <tr key={c.id}>
                <td>
                  {c.nom}
                  <br />
                  <span className="muted">{c.ville}</span>
                </td>
                <td>{c.agents}</td>
                <td>{c.gares}</td>
                <td>{c.lignes}</td>
                <td>{c.vehicules}</td>
                <td>{c.departs_du_jour}</td>
                <td>{c.tickets_du_jour}</td>
                <td>{formatFCFA(c.recettes_du_jour)}</td>
                <td>
                  {c.vehicules_bloques > 0 && <Badge ton="rouge">{c.vehicules_bloques} bloqué(s)</Badge>}{' '}
                  {c.incidents_ouverts > 0 && <Badge ton="orange">{c.incidents_ouverts} incident(s)</Badge>}
                  {c.vehicules_bloques === 0 && c.incidents_ouverts === 0 && <Badge ton="vert">RAS</Badge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  )
}
