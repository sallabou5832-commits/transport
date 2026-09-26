import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { ROLE_LABELS } from '../auth/roles.js'

/**
 * L'équipe locale de la gare : le chef de gare compose son équipe de guichetiers et de bagagistes. Un agent n'est affecté qu'à
 * une gare à la fois : celui d'une autre gare n'est pas repris d'autorité (c'est le directeur des opérations qui le déplace).
 */
export default function EquipeGare({ gare }) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(async () => {
    const [agents, affectations] = await Promise.all([apiFetch('/affectations-gare/agents-affectables/'), apiFetch('/affectations-gare/')])
    return { agents, affectations }
  })

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      setMessage({ type: 'success', texte: confirmation })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  if (!data) return <Alert>{error}</Alert>

  const affectationDe = Object.fromEntries(data.affectations.map((a) => [a.agent, a]))
  const monEquipe = data.agents.filter((a) => a.gare?.id === gare.id)

  const affecter = (agent) =>
    agir(() => apiFetch('/affectations-gare/', { method: 'POST', body: { agent: agent.id, gare: gare.id } }), `${agent.nom} rejoint l'équipe de ${gare.nom}.`)

  const retirer = (agent) =>
    agir(() => apiFetch(`/affectations-gare/${affectationDe[agent.id].id}/`, { method: 'DELETE' }), `${agent.nom} ne fait plus partie de l'équipe de ${gare.nom}.`)

  return (
    <section className="card">
      <h2>Mon équipe locale</h2>
      <p className="muted">
        {monEquipe.length} agent(s) dans l&apos;équipe de {gare.nom}. Les guichetiers et bagagistes affectés ici vendent et enregistrent pour
        cette gare ; leurs caisses apparaissent dans « Caisses du jour de l&apos;équipe ».
      </p>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {data.agents.length === 0 ? (
        <p className="muted">Aucun guichetier ni bagagiste dans la compagnie.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Poste</th>
                <th>Gare</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.agents.map((agent) => (
                <tr key={agent.id}>
                  <td>{agent.nom}</td>
                  <td>{ROLE_LABELS[agent.role] ?? agent.role}</td>
                  <td>
                    {agent.gare ? (
                      <Badge ton={agent.gare.id === gare.id ? 'vert' : 'neutre'}>{agent.gare.nom}</Badge>
                    ) : (
                      <span className="muted">Sans gare</span>
                    )}
                  </td>
                  <td>
                    {agent.gare?.id === gare.id ? (
                      <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirer(agent)}>
                        Retirer de mon équipe
                      </button>
                    ) : !agent.gare ? (
                      <button type="button" className="button-small" disabled={envoi} onClick={() => affecter(agent)}>
                        Affecter à ma gare
                      </button>
                    ) : (
                      <span className="muted">Affecté à une autre gare</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
