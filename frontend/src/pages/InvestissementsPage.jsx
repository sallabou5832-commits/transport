import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import { formatDateHeure, formatFCFA } from '../lib/format.js'

const VIDE = { type: 'achat_vehicule', libelle: '', montant: '', quantite: '', justification: '' }
const TYPES = { achat_vehicule: 'Achat de véhicules', ouverture_ligne: 'Ouverture de ligne', autre: 'Autre investissement' }
const STATUTS = {
  en_attente: { libelle: 'En attente du PDG', ton: 'orange' },
  valide: { libelle: 'Validé', ton: 'vert' },
  refuse: { libelle: 'Refusé', ton: 'rouge' },
}

/** Demander un investissement (achat de cars, ouverture de ligne…) : le PDG décide, le demandeur suit sa demande. */
export default function InvestissementsPage() {
  const [formulaire, setFormulaire] = useState(VIDE)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data: demandes, error, loading, recharger } = useChargement(() => apiFetch('/investissements/'), { intervalleMs: 60000 })

  async function envoyer(event) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch('/investissements/', {
        method: 'POST',
        body: {
          type: formulaire.type,
          libelle: formulaire.libelle,
          montant: formulaire.montant,
          justification: formulaire.justification,
          quantite: formulaire.quantite === '' ? null : Number(formulaire.quantite),
        },
      })
      await recharger()
      setFormulaire(VIDE)
      setMessage({ type: 'success', texte: 'Demande envoyée : le PDG en est prévenu et décide.' })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Layout title="Investissements">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <section className="card">
        <h2>Nouvelle demande</h2>
        <form onSubmit={envoyer}>
          <div className="form-grid">
            <label>
              Type
              <select value={formulaire.type} onChange={(e) => setFormulaire({ ...formulaire, type: e.target.value })}>
                {Object.entries(TYPES).map(([valeur, libelle]) => (
                  <option key={valeur} value={valeur}>
                    {libelle}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Intitulé
              <input value={formulaire.libelle} onChange={(e) => setFormulaire({ ...formulaire, libelle: e.target.value })} required />
            </label>
            <label>
              Montant (FCFA)
              <input
                type="number"
                min="1"
                step="1"
                value={formulaire.montant}
                onChange={(e) => setFormulaire({ ...formulaire, montant: e.target.value })}
                required
              />
            </label>
            <label>
              Nombre de véhicules (facultatif)
              <input
                type="number"
                min="1"
                step="1"
                value={formulaire.quantite}
                onChange={(e) => setFormulaire({ ...formulaire, quantite: e.target.value })}
              />
            </label>
            <label>
              Justification
              <input
                value={formulaire.justification}
                onChange={(e) => setFormulaire({ ...formulaire, justification: e.target.value })}
              />
            </label>
          </div>
          <div className="button-row">
            <button type="submit" disabled={envoi}>
              Envoyer la demande
            </button>
          </div>
        </form>
      </section>

      <h2 className="section-title">Mes demandes</h2>
      {!demandes ? (
        loading && <p>Chargement…</p>
      ) : demandes.length === 0 ? (
        <p>Aucune demande.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Demande</th>
                <th>Montant</th>
                <th>Envoyée le</th>
                <th>Décision</th>
              </tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <tr key={d.id}>
                  <td>
                    <strong>{d.libelle}</strong>
                    <div className="muted">
                      {d.type_libelle}
                      {d.quantite ? ` — ${d.quantite} véhicule(s)` : ''}
                    </div>
                  </td>
                  <td>{formatFCFA(d.montant)}</td>
                  <td>{formatDateHeure(d.cree_le)}</td>
                  <td>
                    <Badge ton={STATUTS[d.statut].ton}>{STATUTS[d.statut].libelle}</Badge>
                    {d.commentaire_decision && <div className="muted">{d.commentaire_decision}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  )
}
