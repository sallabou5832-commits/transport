import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import { formatDateHeure } from '../lib/format.js'

const PORTEES = { les_deux: 'Mon équipe et les chauffeurs en approche', equipe: 'Mon équipe', approche: 'Chauffeurs en approche' }

/**
 * Message direct du chef de gare à son équipe locale et aux conducteurs dont le car arrive à sa gare : il apparaît aussitôt dans leur
 * cloche d'alertes. Sans destinataire (équipe vide, aucun car en route vers la gare), le message n'est pas envoyé.
 */
export default function MessagesGare() {
  const [formulaire, setFormulaire] = useState({ portee: 'les_deux', texte: '' })
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data: messages, error, recharger } = useChargement(() => apiFetch('/messages-directs/'), { intervalleMs: 60000 })

  async function envoyer(event) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      const envoye = await apiFetch('/messages-directs/', { method: 'POST', body: formulaire })
      await recharger()
      setFormulaire({ ...formulaire, texte: '' })
      setMessage({ type: 'success', texte: `Message envoyé à ${envoye.nombre_destinataires} personne(s).` })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card">
      <h2>Message à mon équipe et aux chauffeurs en approche</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={envoyer}>
        <div className="form-grid">
          <label>
            Destinataires du message
            <select value={formulaire.portee} onChange={(e) => setFormulaire({ ...formulaire, portee: e.target.value })}>
              {Object.entries(PORTEES).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Texte du message
            <input value={formulaire.texte} maxLength={500} onChange={(e) => setFormulaire({ ...formulaire, texte: e.target.value })} required />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Envoyer le message
          </button>
        </div>
      </form>
      {messages && messages.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Message</th>
                <th>Destinataires</th>
                <th>Envoyé le</th>
              </tr>
            </thead>
            <tbody>
              {messages.slice(0, 8).map((m) => (
                <tr key={m.id}>
                  <td>{m.texte}</td>
                  <td>
                    {m.portee_libelle} ({m.nombre_destinataires})
                  </td>
                  <td>{formatDateHeure(m.cree_le)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
