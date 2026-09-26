import { useState } from 'react'
import { apiEnvoyer, apiFetch, apiTelecharger } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import { formatDateHeure } from '../lib/format.js'
import { formatTaille } from '../lib/rh.js'

/**
 * Les pièces du dossier d'un sinistre (constat, photos, expertise, courrier de l'assureur) : envoi, téléchargement et retrait. Les
 * fichiers (PDF, images, Word, Excel ; 5 Mo au plus) sont contrôlés par le serveur et ne sont jamais servis par un lien public.
 */
export default function PiecesSinistre({ sinistre, onChange }) {
  const [fichier, setFichier] = useState(null)
  const [libelle, setLibelle] = useState('')
  const [erreurTelechargement, setErreurTelechargement] = useState('')
  const { data, error, recharger } = useChargement(() => apiFetch(`/pieces-sinistre/?sinistre=${sinistre.id}`), { cle: sinistre.id })
  const { agir, envoi, message } = useActions(async () => {
    await recharger()
    if (onChange) await onChange()
  })

  async function joindre(event) {
    event.preventDefault()
    const formulaire = new FormData()
    formulaire.append('sinistre', sinistre.id)
    formulaire.append('fichier', fichier)
    formulaire.append('libelle', libelle)
    if (await agir(() => apiEnvoyer('/pieces-sinistre/', formulaire), `Pièce « ${fichier.name} » jointe au dossier.`)) {
      setFichier(null)
      setLibelle('')
      event.target.reset()
    }
  }

  async function telecharger(piece) {
    setErreurTelechargement('')
    try {
      await apiTelecharger(`/pieces-sinistre/${piece.id}/telecharger/`, piece.nom_fichier)
    } catch (err) {
      setErreurTelechargement(err.message)
    }
  }

  const retirer = (piece) => agir(() => apiFetch(`/pieces-sinistre/${piece.id}/`, { method: 'DELETE' }), `Pièce « ${piece.nom_fichier} » retirée.`)

  return (
    <div>
      <Alert>{error || erreurTelechargement}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {data &&
        (data.length === 0 ? (
          <p className="muted">Aucune pièce jointe à ce dossier.</p>
        ) : (
          <ul className="motifs">
            {data.map((piece) => (
              <li key={piece.id}>
                <strong>{piece.libelle || piece.nom_fichier}</strong>{' '}
                <span className="muted">
                  {piece.libelle ? `${piece.nom_fichier} · ` : ''}
                  {formatTaille(piece.taille)} · ajoutée par {piece.ajoute_par_nom} le {formatDateHeure(piece.cree_le)}
                </span>{' '}
                <button type="button" className="button-secondary button-small" onClick={() => telecharger(piece)}>
                  Télécharger
                </button>{' '}
                <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirer(piece)}>
                  Retirer
                </button>
              </li>
            ))}
          </ul>
        ))}
      <form onSubmit={joindre} className="ligne-fermeture">
        <input
          type="file"
          aria-label={`Fichier à joindre au sinistre ${sinistre.id}`}
          accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
          onChange={(e) => setFichier(e.target.files[0] || null)}
          required
        />
        <input aria-label="Libellé de la pièce" placeholder="Libellé (constat, photo, expertise…)" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
        <button type="submit" disabled={envoi || !fichier}>
          Joindre la pièce
        </button>
      </form>
    </div>
  )
}
