import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

function Demande({ demande, envoi, onServir, onRefuser }) {
  const [commentaire, setCommentaire] = useState('')
  const suffisant = demande.stock_actuel >= demande.quantite
  return (
    <tr>
      <td>
        <strong>
          {demande.quantite} × {demande.piece_nom}
        </strong>
        <div className="muted">{demande.piece_reference}</div>
      </td>
      <td>
        #{demande.ordre_reparation} — {demande.vehicule_immatriculation}
        <div className="muted">
          {demande.demandeur_nom}, {formatDateHeure(demande.cree_le)}
        </div>
      </td>
      <td>{suffisant ? <Badge ton="vert">En stock : {demande.stock_actuel}</Badge> : <Badge ton="rouge">Stock : {demande.stock_actuel}</Badge>}</td>
      <td>
        <input
          aria-label={`Motif du refus de la demande ${demande.id}`}
          placeholder="Motif (pour refuser)"
          value={commentaire}
          onChange={(e) => setCommentaire(e.target.value)}
        />
      </td>
      <td className="button-row">
        <button type="button" disabled={envoi || !suffisant} onClick={() => onServir(demande)}>
          Servir
        </button>
        <button type="button" className="button-secondary" disabled={envoi} onClick={() => onRefuser(demande, commentaire)}>
          Refuser
        </button>
      </td>
    </tr>
  )
}

/** Les demandes de pièces de l'atelier : le magasinier voit tout de suite si le stock suffit, sert (le stock baisse, la sortie est liée à l'ordre) ou refuse. */
export default function DemandesPiecesMagasin({ onChange }) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data: demandes, error, recharger } = useChargement(() => apiFetch('/demandes-pieces/?statut=demandee'), { intervalleMs: 30000 })

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      if (onChange) await onChange()
      setMessage({ type: 'success', texte: confirmation })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  const servir = (demande) =>
    agir(
      () => apiFetch(`/demandes-pieces/${demande.id}/servir/`, { method: 'POST', body: {} }),
      `${demande.quantite} × ${demande.piece_nom} servi(e) : sortie enregistrée sur l'ordre ${demande.ordre_reparation}, stock mis à jour.`,
    )

  const refuser = (demande, commentaire) =>
    agir(
      () => apiFetch(`/demandes-pieces/${demande.id}/refuser/`, { method: 'POST', body: { commentaire } }),
      `Demande refusée : ${demande.demandeur_nom} en est prévenu.`,
    )

  return (
    <section className="card">
      <h2>
        Demandes de pièces {demandes && demandes.length > 0 && <Badge ton="orange">{demandes.length} à traiter</Badge>}
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
                <th>Pièce</th>
                <th>Ordre</th>
                <th>Stock</th>
                <th>Refus</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {demandes.map((demande) => (
                <Demande key={demande.id} demande={demande} envoi={envoi} onServir={servir} onRefuser={refuser} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
