import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'

/**
 * Les quais d'embarquement d'une gare : les déclarer, fermer un quai en travaux (il reste déclaré sans être proposé), retirer un
 * quai créé par erreur. Le chef de gare tient ceux de sa gare ; la direction, ceux de toutes les gares. `onChange` prévient la page.
 */
export default function QuaisGare({ gare, onChange }) {
  const [nom, setNom] = useState('')
  const { data: quais, error, recharger } = useChargement(() => apiFetch(`/quais/?gare=${gare.id}`), { cle: gare.id })
  const { agir, envoi, message } = useActions(async () => {
    await recharger()
    if (onChange) await onChange()
  })

  async function ajouter(event) {
    event.preventDefault()
    if (await agir(() => apiFetch('/quais/', { method: 'POST', body: { gare: gare.id, nom } }), `Quai « ${nom.trim()} » ajouté.`)) {
      setNom('')
    }
  }

  const basculer = (quai) =>
    agir(
      () => apiFetch(`/quais/${quai.id}/`, { method: 'PATCH', body: { actif: !quai.actif } }),
      quai.actif ? `Quai « ${quai.nom} » fermé : il n'est plus proposé.` : `Quai « ${quai.nom} » rouvert.`,
    )

  const retirer = (quai) => {
    if (!window.confirm(`Retirer le quai « ${quai.nom} » de ${gare.nom} ?`)) return
    agir(() => apiFetch(`/quais/${quai.id}/`, { method: 'DELETE' }), `Quai « ${quai.nom} » retiré.`)
  }

  return (
    <div>
      <h3>Quais de {gare.nom}</h3>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {quais && quais.length === 0 && <p className="muted">Aucun quai déclaré.</p>}
      {quais && quais.length > 0 && (
        <ul className="stat-list">
          {quais.map((quai) => (
            <li key={quai.id}>
              <span>
                {quai.nom} {!quai.actif && <Badge ton="orange">Fermé</Badge>}
              </span>
              <span className="fiche-actions">
                <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => basculer(quai)}>
                  {quai.actif ? 'Fermer' : 'Rouvrir'}
                </button>
                <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirer(quai)}>
                  Retirer
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <form className="toolbar" onSubmit={ajouter}>
        <label>
          Nouveau quai
          <input value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Quai 1, A…" maxLength={50} required />
        </label>
        <button type="submit" disabled={envoi || !nom.trim()}>
          Ajouter le quai
        </button>
      </form>
    </div>
  )
}
