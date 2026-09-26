import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

const RECOMMANDATIONS = { a_renouveler: { libelle: 'À renouveler', ton: 'rouge' }, a_surveiller: { libelle: 'À surveiller', ton: 'orange' } }

/**
 * Rapport de besoin de renouvellement de la flotte, généré à la demande pour la Direction Générale : un véhicule y figure dès qu'il
 * atteint un seuil d'usure (kilométrage, réparations ou immobilisation sur 12 mois) ; deux seuils atteints = à renouveler.
 */
export default function BesoinRenouvellement() {
  const { data, error } = useChargement(() => apiFetch('/maintenance/besoin-renouvellement/'), { intervalleMs: 300000 })

  if (!data) return <Alert>{error}</Alert>

  return (
    <section className="card">
      <h2>Renouvellement de la flotte</h2>
      <Alert>{error}</Alert>
      <p className="muted">
        Seuils : {data.criteres.kilometrage.toLocaleString('fr-FR')} km, {data.criteres.ordres_12_mois} réparations et{' '}
        {data.criteres.jours_immobilise_12_mois} jours d&apos;immobilisation sur 12 mois. Rapport du {formatDateHeure(data.genere_le)}.
      </p>
      {data.vehicules.length === 0 ? (
        <p>Aucun véhicule n&apos;atteint ces seuils ({data.flotte} véhicule(s) dans la flotte).</p>
      ) : (
        <>
          <p>
            <Badge ton="rouge">{data.a_renouveler} à renouveler</Badge> <Badge ton="orange">{data.a_surveiller} à surveiller</Badge>{' '}
            sur {data.flotte} véhicule(s).
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Véhicule</th>
                  <th>Compteur</th>
                  <th>Réparations (12 mois)</th>
                  <th>Immobilisé (12 mois)</th>
                  <th>Motifs</th>
                  <th>Recommandation</th>
                </tr>
              </thead>
              <tbody>
                {data.vehicules.map((v) => (
                  <tr key={v.id} className={v.recommandation === 'a_renouveler' ? 'row-danger' : ''}>
                    <td>{v.immatriculation}</td>
                    <td>{v.kilometrage.toLocaleString('fr-FR')} km</td>
                    <td>{v.ordres_12_mois}</td>
                    <td>{v.jours_immobilise_12_mois} j</td>
                    <td>
                      <ul className="motifs">
                        {v.raisons.map((raison) => (
                          <li key={raison}>{raison}</li>
                        ))}
                      </ul>
                    </td>
                    <td>
                      <Badge ton={RECOMMANDATIONS[v.recommandation].ton}>{RECOMMANDATIONS[v.recommandation].libelle}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
