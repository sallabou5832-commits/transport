import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import Alert from './Alert.jsx'
import PiecesSinistre from './PiecesSinistre.jsx'
import { formatDateHeure } from '../lib/format.js'

/** Le dossier d'un sinistre : suivi auprès de l'assureur (référence, montants estimé et indemnisé) et pièces jointes. */
export default function DossierSinistre({ sinistre, onChange }) {
  const [suivi, setSuivi] = useState({
    reference_assureur: sinistre.reference_assureur || '',
    montant_estime: sinistre.montant_estime ? String(Math.round(Number(sinistre.montant_estime))) : '',
    montant_indemnise: sinistre.montant_indemnise ? String(Math.round(Number(sinistre.montant_indemnise))) : '',
  })
  const { agir, envoi, message } = useActions(onChange)

  async function enregistrer(event) {
    event.preventDefault()
    const corps = {
      reference_assureur: suivi.reference_assureur,
      montant_estime: suivi.montant_estime === '' ? null : suivi.montant_estime,
      montant_indemnise: suivi.montant_indemnise === '' ? null : suivi.montant_indemnise,
    }
    await agir(() => apiFetch(`/sinistres/${sinistre.id}/`, { method: 'PATCH', body: corps }), 'Suivi du sinistre enregistré.')
  }

  const champ = (nom) => ({ value: suivi[nom], onChange: (e) => setSuivi({ ...suivi, [nom]: e.target.value }) })

  return (
    <section className="card detail-panneau">
      <h3>
        Dossier du sinistre #{sinistre.id} <span className="muted">— {formatDateHeure(sinistre.date)}</span>
      </h3>
      <p>{sinistre.description}</p>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={enregistrer}>
        <div className="form-grid">
          <label>
            Référence chez l&apos;assureur
            <input {...champ('reference_assureur')} />
          </label>
          <label>
            Montant estimé (FCFA)
            <input type="number" min="0" step="1" {...champ('montant_estime')} />
          </label>
          <label>
            Montant indemnisé (FCFA)
            <input type="number" min="0" step="1" {...champ('montant_indemnise')} />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Enregistrer le suivi
          </button>
        </div>
      </form>
      <h4>Pièces jointes</h4>
      <PiecesSinistre sinistre={sinistre} onChange={onChange} />
    </section>
  )
}
