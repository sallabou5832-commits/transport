import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import { formatFCFA } from '../lib/format.js'

/**
 * Le solde de caisse de départ : la trésorerie part de ce montant, auquel s'ajoutent les recettes (billets et fret) et se
 * retranchent les dépenses saisies. Réservé à la finance.
 */
export default function SoldeInitial({ onChange }) {
  const { data, error, recharger } = useChargement(() => apiFetch('/finance/configuration/'))
  const [saisie, setSaisie] = useState('')
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  async function enregistrer(event) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      const reglage = await apiFetch('/finance/configuration/', { method: 'PUT', body: { solde_initial: saisie } })
      await recharger()
      if (onChange) await onChange()
      setSaisie('')
      setMessage({ type: 'success', texte: `Solde de départ fixé à ${formatFCFA(reglage.solde_initial)}.` })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card no-print">
      <h2>Solde de caisse de départ</h2>
      <p className="muted">
        La trésorerie part de ce montant ; s&apos;y ajoutent les recettes et s&apos;en retranchent les dépenses saisies.
        {data && ` Actuellement : ${formatFCFA(data.solde_initial)}.`}
      </p>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={enregistrer} className="ligne-fermeture">
        <input
          type="number"
          step="1"
          aria-label="Nouveau solde de départ (FCFA)"
          placeholder="Nouveau solde de départ (FCFA)"
          value={saisie}
          onChange={(e) => setSaisie(e.target.value)}
          required
        />
        <button type="submit" disabled={envoi || saisie === ''}>
          Enregistrer le solde
        </button>
      </form>
    </section>
  )
}
