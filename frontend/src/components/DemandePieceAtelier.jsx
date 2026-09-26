import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

const STATUTS = {
  demandee: { libelle: 'En attente du magasinier', ton: 'orange' },
  servie: { libelle: 'Servie', ton: 'vert' },
  refusee: { libelle: 'Indisponible', ton: 'rouge' },
  annulee: { libelle: 'Annulée', ton: 'neutre' },
}

/**
 * Demander une pièce au magasinier pour un ordre de réparation : la disponibilité est confirmée tout de suite, le magasinier est
 * prévenu, et la pièce servie est sortie du stock sur l'ordre. `mecanicien` restreint les ordres proposés à ceux d'un intervenant.
 */
export default function DemandePieceAtelier({ mecanicien }) {
  const [formulaire, setFormulaire] = useState({ ordre: '', piece: '', quantite: '1' })
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(
    async () => {
      const [ordres, pieces, demandes] = await Promise.all([apiFetch('/ordres-reparation/'), apiFetch('/pieces/'), apiFetch('/demandes-pieces/')])
      return { ordres, pieces, demandes }
    },
    { intervalleMs: 30000 },
  )

  if (!data) return <Alert>{error}</Alert>

  const ordres = data.ordres.filter((o) => o.statut !== 'termine' && (mecanicien === undefined || o.mecanicien === mecanicien))
  const piece = data.pieces.find((p) => String(p.id) === formulaire.piece)
  const quantite = Number(formulaire.quantite)

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  async function demander(event) {
    event.preventDefault()
    const ok = await agir(
      () =>
        apiFetch('/demandes-pieces/', {
          method: 'POST',
          body: { ordre_reparation: Number(formulaire.ordre), piece: Number(formulaire.piece), quantite },
        }),
      piece && piece.quantite_stock >= quantite
        ? 'Demande envoyée : la pièce est en stock, le magasinier est prévenu.'
        : 'Demande envoyée : le stock ne couvre pas la quantité, le magasinier est prévenu.',
    )
    if (ok) setFormulaire({ ordre: '', piece: '', quantite: '1' })
  }

  const annuler = (demande) => agir(() => apiFetch(`/demandes-pieces/${demande.id}/annuler/`, { method: 'POST', body: {} }), 'Demande annulée.')

  return (
    <section className="card">
      <h2>Demander une pièce au magasinier</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={demander}>
        <div className="form-grid">
          <label>
            Ordre de réparation
            <select value={formulaire.ordre} onChange={(e) => setFormulaire({ ...formulaire, ordre: e.target.value })} required>
              <option value="">— Choisir —</option>
              {ordres.map((o) => (
                <option key={o.id} value={o.id}>
                  #{o.id} — {o.vehicule_immatriculation} — {o.description}
                </option>
              ))}
            </select>
          </label>
          <label>
            Pièce demandée
            <select value={formulaire.piece} onChange={(e) => setFormulaire({ ...formulaire, piece: e.target.value })} required>
              <option value="">— Choisir —</option>
              {data.pieces.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nom} ({p.reference})
                </option>
              ))}
            </select>
          </label>
          <label>
            Quantité demandée
            <input type="number" min="1" value={formulaire.quantite} onChange={(e) => setFormulaire({ ...formulaire, quantite: e.target.value })} required />
          </label>
        </div>
        {piece && (
          <p>
            {piece.quantite_stock >= quantite ? (
              <Badge ton="vert">Disponible : {piece.quantite_stock} en stock</Badge>
            ) : (
              <Badge ton="rouge">Stock insuffisant : {piece.quantite_stock} en stock</Badge>
            )}
          </p>
        )}
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Envoyer la demande
          </button>
        </div>
      </form>

      {data.demandes.length > 0 && (
        <>
          <h2 style={{ marginTop: '1rem' }}>Mes demandes de pièces</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Pièce</th>
                  <th>Ordre</th>
                  <th>Demandée le</th>
                  <th>État</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.demandes.slice(0, 10).map((d) => (
                  <tr key={d.id}>
                    <td>
                      {d.quantite} × {d.piece_nom}
                    </td>
                    <td>
                      #{d.ordre_reparation} — {d.vehicule_immatriculation}
                    </td>
                    <td>{formatDateHeure(d.cree_le)}</td>
                    <td>
                      <Badge ton={STATUTS[d.statut].ton}>{STATUTS[d.statut].libelle}</Badge>
                      {d.commentaire && <div className="muted">{d.commentaire}</div>}
                    </td>
                    <td>
                      {d.statut === 'demandee' && (
                        <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => annuler(d)}>
                          Annuler
                        </button>
                      )}
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
