import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate } from '../lib/format.js'
import { GRAVITES_DOLEANCE, STATUTS_DOLEANCE } from '../lib/rh.js'

/**
 * Les litiges sociaux : les doléances du canal de médiation du DRH qui ont atteint le seuil de gravité. Le juridique en voit l'objet, le
 * contenu et la gravité, et le poste de l'auteur, pas son identité.
 */
export default function LitigesSociaux() {
  const { data, error } = useChargement(() => apiFetch('/litiges-sociaux/'), { intervalleMs: 120000 })

  return (
    <section className="card">
      <h2>Litiges sociaux signalés</h2>
      <Alert>{error}</Alert>
      {data && (
        <>
          <p className="muted">
            Une doléance de gravité « {GRAVITES_DOLEANCE[data.seuil].libelle.toLowerCase()} » ou plus vous est signalée automatiquement.
          </p>
          {data.litiges.length === 0 ? (
            <p>Aucun litige social signalé.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Objet</th>
                    <th>Origine</th>
                    <th>Gravité</th>
                    <th>Statut</th>
                    <th>Signalé le</th>
                  </tr>
                </thead>
                <tbody>
                  {data.litiges.map((l) => (
                    <tr key={l.id} className={l.gravite === 'critique' && !['resolue', 'sans_suite'].includes(l.statut) ? 'row-danger' : ''}>
                      <td>
                        {l.objet}
                        <div className="muted texte-pre">{l.description}</div>
                      </td>
                      <td>{l.origine === 'syndicat' ? l.syndicat : `Agent : ${ROLE_LABELS[l.auteur_role] || l.auteur_role}`}</td>
                      <td>
                        <Badge ton={GRAVITES_DOLEANCE[l.gravite].ton}>{GRAVITES_DOLEANCE[l.gravite].libelle}</Badge>
                      </td>
                      <td>
                        <Badge ton={STATUTS_DOLEANCE[l.statut].ton}>{STATUTS_DOLEANCE[l.statut].libelle}</Badge>
                      </td>
                      <td>{formatDate(l.litige_signale_le)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
