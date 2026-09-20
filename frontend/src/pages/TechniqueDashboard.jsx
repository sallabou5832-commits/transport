import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Kpi from '../components/Kpi.jsx'
import {
  LABELS_VEHICULE,
  TON_VEHICULE,
  formatDate,
  indexParId,
  joursRestants,
} from '../lib/format.js'

const STATUTS_OR = { ouvert: 'Ouvert', en_cours: 'En cours' }

// Un ordre de réparation est d'autant plus urgent que son véhicule est immobilisé de façon grave.
function urgence(vehicule) {
  if (vehicule?.statut === 'bloque_securite') return { rang: 0, ton: 'rouge', label: 'Critique' }
  if (vehicule?.statut === 'en_maintenance') return { rang: 1, ton: 'orange', label: 'Haute' }
  return { rang: 2, ton: 'neutre', label: 'Normale' }
}

function joursDepuis(iso) {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86400000))
}

export default function TechniqueDashboard() {
  const { data, error, loading } = useChargement(
    async () => {
      const [vehicules, ordres, pieces, assurances, sinistres] = await Promise.all([
        apiFetch('/vehicules/'),
        apiFetch('/ordres-reparation/'),
        apiFetch('/pieces/sous-seuil/'),
        apiFetch('/assurances/echeance-proche/'),
        apiFetch('/sinistres/'),
      ])
      return { vehicules, ordres, pieces, assurances, sinistres }
    },
    { intervalleMs: 60000 },
  )

  if (!data) {
    return (
      <Layout title="Tableau de bord — Technique">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { vehicules, ordres, pieces, assurances, sinistres } = data
  const vehiculesParId = indexParId(vehicules)
  const disponibles = vehicules.filter((v) => v.statut === 'disponible' || v.statut === 'en_ligne').length
  const disponibilite = vehicules.length > 0 ? Math.round((disponibles / vehicules.length) * 100) : null
  const parStatut = (statut) => vehicules.filter((v) => v.statut === statut).length

  const file = ordres
    .filter((o) => o.statut !== 'termine')
    .map((o) => ({ ...o, urgence: urgence(vehiculesParId[o.vehicule]) }))
    .sort(
      (a, b) =>
        a.urgence.rang - b.urgence.rang || new Date(a.date_creation) - new Date(b.date_creation),
    )
  const sinistresActifs = sinistres.filter((s) => s.statut !== 'clos').length

  return (
    <Layout title="Tableau de bord — Technique">
      <Alert>{error}</Alert>

      <div className="cards-grid">
        <Kpi
          titre="Disponibilité de la flotte"
          valeur={disponibilite === null ? '—' : `${disponibilite} %`}
          detail={`${disponibles} véhicule(s) sur ${vehicules.length} peuvent rouler`}
          ton={disponibilite === null ? undefined : disponibilite >= 80 ? 'vert' : disponibilite >= 60 ? 'orange' : 'rouge'}
        />
        <Kpi
          titre="Bloqués par le QHSE"
          valeur={parStatut('bloque_securite')}
          ton={parStatut('bloque_securite') > 0 ? 'rouge' : 'vert'}
        />
        <Kpi titre="En maintenance" valeur={parStatut('en_maintenance')} />
        <Kpi
          titre="Sinistres en cours"
          valeur={sinistresActifs}
          ton={sinistresActifs > 0 ? 'orange' : 'vert'}
        />
      </div>

      <h2 className="section-title">File des réparations (par urgence)</h2>
      {file.length === 0 ? (
        <p>Aucun ordre de réparation en cours.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Urgence</th>
                <th>Véhicule</th>
                <th>Description</th>
                <th>Mécanicien</th>
                <th>Statut</th>
                <th>Ouvert depuis</th>
              </tr>
            </thead>
            <tbody>
              {file.map((ordre) => {
                const vehicule = vehiculesParId[ordre.vehicule]
                return (
                  <tr key={ordre.id} className={ordre.urgence.rang === 0 ? 'row-danger' : ''}>
                    <td>
                      <Badge ton={ordre.urgence.ton}>{ordre.urgence.label}</Badge>
                    </td>
                    <td>
                      {vehicule?.immatriculation || ordre.vehicule}
                      <br />
                      {vehicule && <Badge ton={TON_VEHICULE[vehicule.statut]}>{LABELS_VEHICULE[vehicule.statut]}</Badge>}
                    </td>
                    <td>{ordre.description}</td>
                    <td>{ordre.mecanicien_nom}</td>
                    <td>{STATUTS_OR[ordre.statut]}</td>
                    <td>{joursDepuis(ordre.date_creation)} j</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="cards-grid">
        <section className="card">
          <h2>Pièces sous le seuil d&apos;alerte</h2>
          {pieces.length === 0 ? (
            <p className="muted">Aucune rupture en vue.</p>
          ) : (
            <ul className="stat-list">
              {pieces.map((piece) => (
                <li key={piece.id}>
                  <span>
                    {piece.nom} <span className="muted">({piece.reference})</span>
                  </span>
                  <strong>
                    {piece.quantite_stock} / seuil {piece.seuil_alerte}
                  </strong>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <h2>Assurances à renouveler (30 jours)</h2>
          {assurances.length === 0 ? (
            <p className="muted">Aucune échéance proche.</p>
          ) : (
            <ul className="stat-list">
              {assurances.map((assurance) => {
                const jours = joursRestants(assurance.date_echeance)
                return (
                  <li key={assurance.id}>
                    <span>
                      {vehiculesParId[assurance.vehicule]?.immatriculation || assurance.vehicule} —{' '}
                      {assurance.compagnie_assurance}
                      <br />
                      <span className="muted">Échéance le {formatDate(assurance.date_echeance)}</span>
                    </span>
                    <Badge ton={jours < 0 ? 'rouge' : 'orange'}>
                      {jours < 0 ? `expirée depuis ${-jours} j` : `dans ${jours} j`}
                    </Badge>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>

      <Alert type="warning">
        Entretien préventif (kilométrage, prochaine échéance d&apos;entretien) et rapport de renouvellement de flotte :
        pas encore disponibles, le serveur n&apos;enregistre pas le kilométrage des véhicules.
      </Alert>
    </Layout>
  )
}
