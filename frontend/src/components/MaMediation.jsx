import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatDateHeure } from '../lib/format.js'
import { GRAVITES_DOLEANCE, STATUTS_DOLEANCE } from '../lib/rh.js'

const VIDE = { objet: '', description: '', gravite: 'moyenne' }
// Un agent qualifie sa doléance jusqu'à « grave » ; « critique » est une décision du DRH.
const GRAVITES_CHOISISSABLES = ['faible', 'moyenne', 'grave']

/**
 * Le canal de médiation sociale : déposer une doléance et en suivre le traitement. Elle est confidentielle : seuls le déposant et le DRH
 * la lisent. Une doléance grave prévient aussi le responsable juridique d'un risque de litige (sans dire qui l'a déposée).
 */
export default function MaMediation() {
  const [formulaire, setFormulaire] = useState(VIDE)
  const { data, error, recharger } = useChargement(() => apiFetch('/doleances/'), { intervalleMs: 60000 })
  const { agir, envoi, message } = useActions(recharger)

  async function deposer(event) {
    event.preventDefault()
    if (await agir(() => apiFetch('/doleances/', { method: 'POST', body: formulaire }), 'Doléance déposée : le DRH en est informé.')) {
      setFormulaire(VIDE)
    }
  }

  const champ = (nom) => ({ value: formulaire[nom], onChange: (e) => setFormulaire({ ...formulaire, [nom]: e.target.value }) })

  return (
    <section className="card">
      <h2>Médiation sociale</h2>
      <p className="muted">
        Une difficulté avec votre travail, votre rémunération, un collègue ou votre hiérarchie ? Déposez une doléance : elle est lue par le
        DRH seul, qui vous répond ici.
      </p>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      {data && data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Déposée le</th>
                <th>Objet</th>
                <th>État</th>
                <th>Échanges avec le DRH</th>
              </tr>
            </thead>
            <tbody>
              {data.map((doleance) => (
                <tr key={doleance.id}>
                  <td>{formatDate(doleance.cree_le)}</td>
                  <td>
                    {doleance.objet}
                    <div className="muted">Gravité : {GRAVITES_DOLEANCE[doleance.gravite].libelle.toLowerCase()}</div>
                  </td>
                  <td>
                    <Badge ton={STATUTS_DOLEANCE[doleance.statut].ton}>{STATUTS_DOLEANCE[doleance.statut].libelle}</Badge>
                  </td>
                  <td>
                    {doleance.suivis.length === 0 ? (
                      <span className="muted">Pas encore de réponse.</span>
                    ) : (
                      <ul className="motifs">
                        {doleance.suivis.map((suivi) => (
                          <li key={suivi.id}>
                            <span className="muted">{formatDateHeure(suivi.cree_le)} :</span> {suivi.texte}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>Déposer une doléance</h3>
      <form onSubmit={deposer}>
        <div className="form-grid">
          <label>
            Objet
            <input {...champ('objet')} minLength={3} required />
          </label>
          <label>
            Gravité
            <select {...champ('gravite')}>
              {GRAVITES_CHOISISSABLES.map((valeur) => (
                <option key={valeur} value={valeur}>
                  {GRAVITES_DOLEANCE[valeur].libelle}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="grand-champ">
          Ce qui se passe
          <textarea rows={4} {...champ('description')} minLength={10} required />
        </label>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Déposer la doléance
          </button>
        </div>
      </form>
    </section>
  )
}
