import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatDateHeure } from '../lib/format.js'

const ASSURANCE = {
  valide: { libelle: 'Valide', ton: 'vert' },
  bientot: { libelle: 'Bientôt échue', ton: 'orange' },
  expiree: { libelle: 'Expirée', ton: 'rouge' },
  absente: { libelle: 'Non enregistrée', ton: 'rouge' },
}
const OBLIGATION = { a_jour: { libelle: 'À jour', ton: 'vert' }, bientot: { libelle: 'Bientôt dû', ton: 'orange' }, en_retard: { libelle: 'En retard', ton: 'rouge' } }
const TRAJET = { 'en cours': 'du trajet en cours', prochain: 'du prochain trajet', dernier: 'du dernier trajet' }

/**
 * Carnet de route numérique du conducteur : les papiers du véhicule qu'il conduit (assurance, contrôle technique, visite), à présenter
 * en cas de contrôle, et ses derniers trajets avec leur ponctualité.
 */
export default function CarnetDeRoute() {
  const { data, error } = useChargement(() => apiFetch('/carnet-de-route/'), { intervalleMs: 300000 })

  if (!data) return <Alert>{error}</Alert>
  const { vehicule, trajets, statistiques } = data

  return (
    <section className="card">
      <h2>Carnet de route</h2>
      <Alert>{error}</Alert>
      {vehicule ? (
        <>
          <p>
            <strong>{vehicule.immatriculation}</strong> — {vehicule.capacite} places · {vehicule.kilometrage.toLocaleString('fr-FR')} km ·{' '}
            <span className="muted">véhicule {TRAJET[vehicule.trajet]}</span>
          </p>
          <ul className="stat-list">
            <li>
              <span>
                Assurance {vehicule.assurance.police ? `(police ${vehicule.assurance.police})` : ''}
                {vehicule.assurance.date_echeance && <span className="muted"> — jusqu&apos;au {formatDate(vehicule.assurance.date_echeance)}</span>}
              </span>
              <Badge ton={ASSURANCE[vehicule.assurance.etat].ton}>{ASSURANCE[vehicule.assurance.etat].libelle}</Badge>
            </li>
            {vehicule.obligations.map((o) => (
              <li key={o.plan}>
                <span>
                  {o.libelle}
                  {o.prochaine_date && <span className="muted"> — prochaine échéance le {formatDate(o.prochaine_date)}</span>}
                </span>
                <Badge ton={OBLIGATION[o.etat].ton}>{OBLIGATION[o.etat].libelle}</Badge>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted">Aucun véhicule ne vous est encore affecté : vos papiers apparaîtront avec votre premier trajet.</p>
      )}

      <h2 style={{ marginTop: '1rem' }}>Mes derniers trajets</h2>
      <p className="muted">
        {statistiques.trajets_30_jours} trajet(s) en 30 jours ·{' '}
        {statistiques.ponctualite_30_jours_pourcent === null ? 'ponctualité —' : `${statistiques.ponctualite_30_jours_pourcent} % à l'heure`} ·{' '}
        {statistiques.incidents_30_jours} incident(s)
      </p>
      {trajets.length === 0 ? (
        <p>Aucun trajet pour le moment.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Prévu</th>
                <th>Ligne</th>
                <th>Véhicule</th>
                <th>État</th>
                <th>Incidents</th>
              </tr>
            </thead>
            <tbody>
              {trajets.slice(0, 10).map((t) => (
                <tr key={t.feuille_de_route}>
                  <td>{formatDateHeure(t.depart_prevu)}</td>
                  <td>{t.ligne}</td>
                  <td>{t.vehicule}</td>
                  <td>
                    {t.en_cours ? (
                      <Badge ton="bleu">En route</Badge>
                    ) : t.arrivee_reelle ? (
                      t.ponctualite === 'en_retard' ? <Badge ton="orange">Arrivé · parti avec {t.retard_minutes} min de retard</Badge> : <Badge ton="vert">Arrivé à l&apos;heure</Badge>
                    ) : (
                      <Badge>À venir</Badge>
                    )}
                  </td>
                  <td>{t.incidents || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
