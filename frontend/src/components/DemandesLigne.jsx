import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatDateHeure } from '../lib/format.js'

const ACTIONS = { fermer: 'Fermeture', rouvrir: 'Réouverture' }

function Demande({ demande, envoi, onDecider }) {
  const [commentaire, setCommentaire] = useState('')
  return (
    <tr>
      <td>
        <strong>{ACTIONS[demande.action]}</strong> de {demande.ligne_nom}
        <div className="muted">
          {demande.motif}
          {demande.jusqu_au ? ` — jusqu'au ${formatDate(demande.jusqu_au)}` : ''}
        </div>
      </td>
      <td>
        {demande.demandeur_nom}
        <div className="muted">{formatDateHeure(demande.cree_le)}</div>
      </td>
      <td>
        <input
          aria-label={`Commentaire sur la demande de ${demande.demandeur_nom} pour ${demande.ligne_nom}`}
          placeholder="Commentaire (facultatif)"
          value={commentaire}
          onChange={(e) => setCommentaire(e.target.value)}
        />
      </td>
      <td className="button-row">
        <button type="button" disabled={envoi} onClick={() => onDecider(demande, 'valider', commentaire)}>
          Valider
        </button>
        <button type="button" disabled={envoi} className="button-secondary" onClick={() => onDecider(demande, 'refuser', commentaire)}>
          Refuser
        </button>
      </td>
    </tr>
  )
}

/** Les demandes de fermeture ou de réouverture de ligne (chefs de ligne et de gare) que le directeur des opérations décide. */
export default function DemandesLigne({ onChange, version = 0 }) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data: demandes, error, recharger } = useChargement(() => apiFetch('/changements-ligne/?statut=en_attente'), {
    intervalleMs: 60000,
    cle: version,
  })

  async function decider(demande, decision, commentaire) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch(`/changements-ligne/${demande.id}/decider/`, { method: 'POST', body: { decision, commentaire } })
      await recharger()
      if (onChange) await onChange()
      setMessage({
        type: 'success',
        texte: decision === 'valider' ? 'Demande validée : le changement est appliqué.' : 'Demande refusée : le demandeur en est prévenu.',
      })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card">
      <h2>
        Demandes sur les lignes {demandes && demandes.length > 0 && <Badge ton="orange">{demandes.length} à décider</Badge>}
      </h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {!demandes ? (
        <p>Chargement…</p>
      ) : demandes.length === 0 ? (
        <p className="muted">Aucune demande en attente.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Demande</th>
                <th>Demandeur</th>
                <th>Commentaire</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {demandes.map((demande) => (
                <Demande key={demande.id} demande={demande} envoi={envoi} onDecider={decider} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
