import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import BesoinRenouvellement from '../components/BesoinRenouvellement.jsx'
import FicheVehicule from '../components/FicheVehicule.jsx'
import FileReparations from '../components/FileReparations.jsx'
import Kpi from '../components/Kpi.jsx'
import PlansEntretien from '../components/PlansEntretien.jsx'
import SuggestionsCommande from '../components/SuggestionsCommande.jsx'
import { formatDate, indexParId, joursRestants } from '../lib/format.js'

export default function TechniqueDashboard() {
  const { data, error, loading, recharger } = useChargement(
    async () => {
      const [vehicules, pieces, assurances, sinistres] = await Promise.all([
        apiFetch('/vehicules/'),
        apiFetch('/pieces/sous-seuil/'),
        apiFetch('/assurances/echeance-proche/'),
        apiFetch('/sinistres/'),
      ])
      return { vehicules, pieces, assurances, sinistres }
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

  const { vehicules, pieces, assurances, sinistres } = data
  const vehiculesParId = indexParId(vehicules)
  const disponibles = vehicules.filter((v) => v.statut === 'disponible' || v.statut === 'en_ligne').length
  const disponibilite = vehicules.length > 0 ? Math.round((disponibles / vehicules.length) * 100) : null
  const parStatut = (statut) => vehicules.filter((v) => v.statut === statut).length
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

      <h2 className="section-title">Réparations</h2>
      <FileReparations onChange={recharger} />

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

      <h2 className="section-title">Entretien préventif et renouvellement</h2>
      <PlansEntretien onChange={recharger} />
      <BesoinRenouvellement />

      <h2 className="section-title">Approvisionnement</h2>
      <SuggestionsCommande />

      <h2 className="section-title">Fiche véhicule</h2>
      <FicheVehicule />
    </Layout>
  )
}
