import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatDateHeure } from '../lib/format.js'

const VIDE = { ligne: '', motif: '', jusqu_au: '' }
const STATUTS = {
  en_attente: { libelle: 'En attente', ton: 'orange' },
  valide: { libelle: 'Validée', ton: 'vert' },
  refuse: { libelle: 'Refusée', ton: 'rouge' },
}

/**
 * Demander au directeur des opérations de fermer (route coupée, grève…) ou de rouvrir une ligne. Le terrain voit la situation
 * avant la direction : c'est lui qui demande, la direction décide.
 */
export default function DemandeLigne() {
  const [formulaire, setFormulaire] = useState(VIDE)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(
    async () => {
      const [lignes, demandes] = await Promise.all([apiFetch('/lignes/'), apiFetch('/changements-ligne/')])
      return { lignes, demandes }
    },
    { intervalleMs: 60000 },
  )

  if (!data) return <Alert>{error}</Alert>

  const { lignes, demandes } = data
  const ligne = lignes.find((l) => String(l.id) === formulaire.ligne)
  const fermee = ligne?.est_fermee ?? false

  async function envoyer(event) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch(`/lignes/${formulaire.ligne}/changement/`, {
        method: 'POST',
        body: {
          action: fermee ? 'rouvrir' : 'fermer',
          motif: formulaire.motif,
          ...(!fermee && formulaire.jusqu_au ? { jusqu_au: formulaire.jusqu_au } : {}),
        },
      })
      await recharger()
      setFormulaire(VIDE)
      setMessage({ type: 'success', texte: 'Demande envoyée : le directeur des opérations en est prévenu et décide.' })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card">
      <h2>Demander la fermeture ou la réouverture d’une ligne</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={envoyer}>
        <div className="form-grid">
          <label>
            Ligne concernée
            <select value={formulaire.ligne} onChange={(e) => setFormulaire({ ...formulaire, ligne: e.target.value })} required>
              <option value="">— Choisir —</option>
              {lignes.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nom}
                  {l.est_fermee ? ' (fermée)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label>
            Motif de la demande
            <input value={formulaire.motif} onChange={(e) => setFormulaire({ ...formulaire, motif: e.target.value })} required />
          </label>
          {ligne && !fermee && (
            <label>
              Dernier jour de fermeture (facultatif)
              <input
                type="date"
                value={formulaire.jusqu_au}
                min={new Date().toISOString().slice(0, 10)}
                onChange={(e) => setFormulaire({ ...formulaire, jusqu_au: e.target.value })}
              />
            </label>
          )}
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi || !ligne}>
            {fermee ? 'Demander la réouverture' : 'Demander la fermeture'}
          </button>
        </div>
      </form>

      {demandes.length > 0 && (
        <>
          <h2 style={{ marginTop: '1rem' }}>Mes demandes</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Ligne</th>
                  <th>Demande</th>
                  <th>Envoyée le</th>
                  <th>Décision</th>
                </tr>
              </thead>
              <tbody>
                {demandes.slice(0, 8).map((demande) => (
                  <tr key={demande.id}>
                    <td>{demande.ligne_nom}</td>
                    <td>
                      {demande.action === 'fermer' ? 'Fermeture' : 'Réouverture'} — {demande.motif}
                      {demande.jusqu_au ? ` (jusqu'au ${formatDate(demande.jusqu_au)})` : ''}
                    </td>
                    <td>{formatDateHeure(demande.cree_le)}</td>
                    <td>
                      <Badge ton={STATUTS[demande.statut].ton}>{STATUTS[demande.statut].libelle}</Badge>
                      {demande.commentaire_decision && <div className="muted">{demande.commentaire_decision}</div>}
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
