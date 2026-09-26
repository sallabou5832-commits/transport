import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, isoAujourdhui } from '../lib/format.js'
import { STATUTS_CONGE, TYPES_CONGE } from '../lib/rh.js'

const VIDE = { type: 'annuel', debut: '', fin: '', motif: '' }

/**
 * Mes congés : la demande (le DRH la valide après avoir vu l'effet sur l'effectif disponible) et le suivi de mes demandes. Ouvert à
 * tout poste ; un arrêt maladie se déclare après coup, tout autre congé se demande avant.
 */
export default function MesConges() {
  const { user } = useAuth()
  const [formulaire, setFormulaire] = useState(VIDE)
  const { data, error, recharger } = useChargement(() => apiFetch(`/conges/?agent=${user.id}`), { intervalleMs: 60000 })
  const { agir, envoi, message } = useActions(recharger)

  async function demander(event) {
    event.preventDefault()
    if (await agir(() => apiFetch('/conges/', { method: 'POST', body: formulaire }), 'Demande envoyée : le DRH va la traiter.')) {
      setFormulaire(VIDE)
    }
  }

  const annuler = (conge) => agir(() => apiFetch(`/conges/${conge.id}/annuler/`, { method: 'POST', body: {} }), 'Demande annulée.')
  const champ = (nom) => ({ value: formulaire[nom], onChange: (e) => setFormulaire({ ...formulaire, [nom]: e.target.value }) })
  const aujourdhui = isoAujourdhui(0)

  return (
    <section className="card">
      <h2>Mes congés</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      {data &&
        (data.length === 0 ? (
          <p className="muted">Vous n&apos;avez fait aucune demande.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Nature</th>
                  <th>Du</th>
                  <th>Au</th>
                  <th>Durée</th>
                  <th>État</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.map((conge) => (
                  <tr key={conge.id}>
                    <td>{conge.type_libelle}</td>
                    <td>{formatDate(conge.debut)}</td>
                    <td>{formatDate(conge.fin)}</td>
                    <td>{conge.jours} j</td>
                    <td>
                      <Badge ton={STATUTS_CONGE[conge.statut].ton}>{STATUTS_CONGE[conge.statut].libelle}</Badge>
                      {conge.motif_decision && <div className="muted">{conge.motif_decision}</div>}
                    </td>
                    <td>
                      {['en_attente', 'approuve'].includes(conge.statut) && conge.fin >= aujourdhui && (
                        <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => annuler(conge)}>
                          Annuler
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      <h3>Demander un congé</h3>
      <form onSubmit={demander}>
        <div className="form-grid">
          <label>
            Nature du congé
            <select {...champ('type')}>
              {Object.entries(TYPES_CONGE).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Premier jour
            <input type="date" {...champ('debut')} min={formulaire.type === 'maladie' ? undefined : aujourdhui} required />
          </label>
          <label>
            Dernier jour
            <input type="date" {...champ('fin')} min={formulaire.debut || undefined} required />
          </label>
          <label>
            Motif (facultatif)
            <input {...champ('motif')} />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Envoyer la demande
          </button>
        </div>
      </form>
    </section>
  )
}
