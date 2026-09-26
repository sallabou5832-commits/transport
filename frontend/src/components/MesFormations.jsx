import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate } from '../lib/format.js'
import { ETATS_FORMATION } from '../lib/rh.js'

/** Mes formations et documents obligatoires (permis, visite médicale, sécurité routière…) : ce qui est à jour et ce qui est à renouveler. */
export default function MesFormations() {
  const { user } = useAuth()
  const { data, error } = useChargement(() => apiFetch(`/formations-obligatoires/suivi/?agent=${user.id}`), { intervalleMs: 120000 })

  return (
    <section className="card">
      <h2>Mes formations obligatoires</h2>
      <Alert>{error}</Alert>
      {data &&
        (data.lignes.length === 0 ? (
          <p className="muted">Aucune formation obligatoire n&apos;est prévue pour votre poste.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Formation</th>
                  <th>Suivie le</th>
                  <th>Valable jusqu&apos;au</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {data.lignes.map((ligne) => (
                  <tr key={ligne.obligation} className={['expiree', 'manquante'].includes(ligne.etat) ? 'row-danger' : ''}>
                    <td>{ligne.obligation_nom}</td>
                    <td>{ligne.date_obtention ? formatDate(ligne.date_obtention) : '—'}</td>
                    <td>{ligne.date_expiration ? formatDate(ligne.date_expiration) : 'Sans échéance'}</td>
                    <td>
                      <Badge ton={ETATS_FORMATION[ligne.etat].ton}>{ETATS_FORMATION[ligne.etat].libelle}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </section>
  )
}
