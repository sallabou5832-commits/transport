import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure, LABELS_GRAVITE, LABELS_TYPE_INCIDENT } from '../lib/format.js'

/**
 * Les incidents que le chauffeur a déclarés, du plus récent au plus ancien. Il supprime celui qu'il a déclaré par erreur si le
 * règlement intérieur de sa compagnie le permet (`peutSupprimer`) ; sinon le bouton n'apparaît pas, et le serveur refuserait.
 * `cle` relit la liste après un nouveau signalement.
 */
export default function MesIncidents({ peutSupprimer, cle }) {
  const { data: incidents, error, recharger } = useChargement(() => apiFetch('/incidents/'), { cle })
  const { agir, envoi, message } = useActions(recharger)

  function supprimer(incident) {
    if (!window.confirm(`Supprimer l'incident « ${incident.description} » déclaré par erreur ?`)) return
    agir(() => apiFetch(`/incidents/${incident.id}/`, { method: 'DELETE' }), 'Incident supprimé.')
  }

  // Rien à montrer tant qu'il n'a rien déclaré ; mais la confirmation reste visible après la suppression du dernier.
  if (!incidents || (incidents.length === 0 && !message.texte)) return <Alert>{error}</Alert>

  return (
    <section className="card">
      <h2>Mes incidents déclarés</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {incidents.length === 0 ? (
        <p>Aucun incident déclaré.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Incident</th>
                <th>Gravité</th>
                <th>Suivi</th>
                {peutSupprimer && <th aria-label="Actions" />}
              </tr>
            </thead>
            <tbody>
              {incidents.slice(0, 10).map((incident) => (
                <tr key={incident.id}>
                  <td>{formatDateHeure(incident.date)}</td>
                  <td>
                    {LABELS_TYPE_INCIDENT[incident.type_incident] || incident.type_incident}
                    <div className="muted">{incident.description}</div>
                  </td>
                  <td>{LABELS_GRAVITE[incident.gravite] || incident.gravite}</td>
                  <td>{incident.statut === 'traite' ? <Badge ton="vert">Traité</Badge> : <Badge ton="orange">Ouvert</Badge>}</td>
                  {peutSupprimer && (
                    <td>
                      <button type="button" className="button-small button-secondary" disabled={envoi} onClick={() => supprimer(incident)}>
                        Supprimer
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
