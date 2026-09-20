import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Jauge from '../components/Jauge.jsx'
import { LABELS_DEPART, estAujourdhui, formatHeure, indexParId } from '../lib/format.js'

export default function BagagisteDashboard() {
  const [gareId, setGareId] = useState('')

  const { data, error, loading } = useChargement(
    async () => {
      const [gares, lignes, departs, vehicules] = await Promise.all([
        apiFetch('/gares/'),
        apiFetch('/lignes/'),
        apiFetch('/departs/'),
        apiFetch('/vehicules/'),
      ])
      return { gares, lignes, departs, vehicules }
    },
    { intervalleMs: 60000 },
  )

  if (!data) {
    return (
      <Layout title="Tableau de bord — Bagagiste">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { gares, lignes, departs, vehicules } = data
  const garesParId = indexParId(gares)
  const lignesParId = indexParId(lignes)
  const vehiculesParId = indexParId(vehicules)

  const aCharger = departs
    .filter((d) => estAujourdhui(d.date_heure) && d.statut !== 'termine')
    .filter((d) => !gareId || String(lignesParId[d.ligne]?.gare_depart) === gareId)
    .sort((a, b) => new Date(a.date_heure) - new Date(b.date_heure))

  return (
    <Layout title="Tableau de bord — Bagagiste">
      <Alert type="warning">
        L&apos;enregistrement des bagages et colis (poids, valeur déclarée, code de retrait envoyé au client, suivi de
        statut) n&apos;est pas encore disponible : le serveur n&apos;a pas de module colis. Cette page montre les
        départs à charger aujourd&apos;hui.
      </Alert>
      <Alert>{error}</Alert>

      <div className="toolbar">
        <label>
          Gare de départ
          <select value={gareId} onChange={(e) => setGareId(e.target.value)}>
            <option value="">Toutes les gares</option>
            {gares.map((gare) => (
              <option key={gare.id} value={gare.id}>
                {gare.nom}
              </option>
            ))}
          </select>
        </label>
      </div>

      <h2 className="section-title">Départs à charger aujourd&apos;hui</h2>
      {aCharger.length === 0 ? (
        <p>Aucun départ à charger.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Heure</th>
                <th>Trajet</th>
                <th>Véhicule</th>
                <th>Voyageurs</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {aCharger.map((depart) => {
                const ligne = lignesParId[depart.ligne]
                const vehicule = vehiculesParId[depart.vehicule]
                return (
                  <tr key={depart.id}>
                    <td>{formatHeure(depart.date_heure)}</td>
                    <td>
                      {ligne?.nom}
                      <br />
                      <span className="muted">
                        {garesParId[ligne?.gare_depart]?.nom} → {garesParId[ligne?.gare_arrivee]?.nom}
                      </span>
                    </td>
                    <td>{vehicule?.immatriculation}</td>
                    <td>
                      <Jauge vendues={depart.places_vendues} capacite={vehicule?.capacite} />
                    </td>
                    <td>
                      <Badge ton={depart.statut === 'en_cours' ? 'bleu' : 'neutre'}>
                        {LABELS_DEPART[depart.statut]}
                      </Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  )
}
