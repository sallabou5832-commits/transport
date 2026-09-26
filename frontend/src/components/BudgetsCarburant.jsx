import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import { formatFCFA } from '../lib/format.js'
import { jourDuMois, moisCourant } from '../lib/finance.js'

/**
 * Fixer (ou corriger) le budget carburant d'une ligne pour un mois. Une ligne n'a qu'un budget par mois : si elle en a déjà
 * un, le formulaire le reprend et le modifie. La finance et le PDG sont alertés quand la ligne atteint 80 % de son budget, puis
 * au dépassement.
 */
export default function BudgetsCarburant({ onChange }) {
  const [mois, setMois] = useState(moisCourant())
  const [ligne, setLigne] = useState('')
  const [montant, setMontant] = useState('')
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(
    async () => {
      const [lignes, budgets] = await Promise.all([
        apiFetch('/lignes/'),
        apiFetch(`/budgets-carburant/?mois=${jourDuMois(mois || moisCourant())}`),
      ])
      return { lignes, budgets }
    },
    { cle: mois },
  )

  const existant = data?.budgets.find((budget) => String(budget.ligne) === ligne)

  function choisirLigne(valeur) {
    setLigne(valeur)
    const budget = data?.budgets.find((b) => String(b.ligne) === valeur)
    setMontant(budget ? String(Math.round(Number(budget.montant))) : '')
  }

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      if (onChange) await onChange()
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  async function enregistrer(event) {
    event.preventDefault()
    const requete = existant
      ? () => apiFetch(`/budgets-carburant/${existant.id}/`, { method: 'PATCH', body: { montant } })
      : () => apiFetch('/budgets-carburant/', { method: 'POST', body: { ligne: Number(ligne), mois: jourDuMois(mois), montant } })
    const nom = data.lignes.find((l) => String(l.id) === ligne)?.nom
    if (await agir(requete, `Budget carburant de ${nom} ${existant ? 'modifié' : 'fixé'} : ${formatFCFA(montant)}.`)) {
      setLigne('')
      setMontant('')
    }
  }

  const retirer = (budget) => agir(() => apiFetch(`/budgets-carburant/${budget.id}/`, { method: 'DELETE' }), `Budget de ${budget.ligne_nom} retiré.`)

  if (!data) return <Alert>{error}</Alert>

  return (
    <section className="card no-print">
      <h2>Fixer le budget carburant</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={enregistrer}>
        <div className="form-grid">
          <label>
            Mois du budget
            <input type="month" value={mois} onChange={(e) => setMois(e.target.value)} required />
          </label>
          <label>
            Ligne
            <select value={ligne} onChange={(e) => choisirLigne(e.target.value)} required>
              <option value="">— Choisir —</option>
              {data.lignes.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nom}
                </option>
              ))}
            </select>
          </label>
          <label>
            Budget (FCFA)
            <input type="number" min="1" step="1" value={montant} onChange={(e) => setMontant(e.target.value)} required />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi || !ligne || !mois}>
            {existant ? 'Modifier le budget' : 'Fixer le budget'}
          </button>
        </div>
      </form>

      {data.budgets.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Budgets du mois</th>
                <th>Montant</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.budgets.map((budget) => (
                <tr key={budget.id}>
                  <td>{budget.ligne_nom}</td>
                  <td className="montant">{formatFCFA(budget.montant)}</td>
                  <td>
                    <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirer(budget)}>
                      Retirer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
