import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, isoAujourdhui } from '../lib/format.js'
import { ETATS_FORMATION, TYPES_CONTRAT, TYPES_MESURE } from '../lib/rh.js'

const CONTRAT_VIDE = { type: 'cdi', date_debut: '', date_fin: '', reference: '', notes: '' }
const EVALUATION_VIDE = () => ({ date: isoAujourdhui(0), note: '4', commentaire: '' })
const MESURE_VIDE = () => ({ date: isoAujourdhui(0), type: 'avertissement', motif: '', duree_jours: '' })

/**
 * Le dossier complet d'un agent tel que le DRH le tient : contrats, évaluations, mesures disciplinaires, formations obligatoires. Les
 * échelons de la hiérarchie lisent la même fiche pour les postes sous leur autorité, sans les notes internes du DRH.
 */
export default function FicheAgent({ dossier, onFermer }) {
  const [contrat, setContrat] = useState(CONTRAT_VIDE)
  const [evaluation, setEvaluation] = useState(EVALUATION_VIDE)
  const [mesure, setMesure] = useState(MESURE_VIDE)
  const { data, error, recharger } = useChargement(() => apiFetch(`/dossiers-agents/${dossier.id}/fiche/`), { cle: dossier.id })
  const { agir, envoi, message } = useActions(recharger)

  async function ajouterContrat(event) {
    event.preventDefault()
    const corps = { ...contrat, agent: dossier.agent, date_fin: contrat.date_fin || null }
    if (await agir(() => apiFetch('/contrats/', { method: 'POST', body: corps }), 'Contrat enregistré.')) setContrat(CONTRAT_VIDE)
  }

  async function ajouterEvaluation(event) {
    event.preventDefault()
    const corps = { ...evaluation, agent: dossier.agent, note: Number(evaluation.note) }
    if (await agir(() => apiFetch('/evaluations/', { method: 'POST', body: corps }), 'Évaluation enregistrée.')) setEvaluation(EVALUATION_VIDE())
  }

  async function ajouterMesure(event) {
    event.preventDefault()
    const corps = { ...mesure, agent: dossier.agent, duree_jours: mesure.duree_jours === '' ? null : Number(mesure.duree_jours) }
    if (await agir(() => apiFetch('/mesures-disciplinaires/', { method: 'POST', body: corps }), 'Mesure enregistrée.')) setMesure(MESURE_VIDE())
  }

  const retirerContrat = (c) => agir(() => apiFetch(`/contrats/${c.id}/`, { method: 'DELETE' }), 'Contrat retiré.')
  const retirerEvaluation = (e) => agir(() => apiFetch(`/evaluations/${e.id}/`, { method: 'DELETE' }), 'Évaluation retirée.')
  const retirerMesure = (m) => agir(() => apiFetch(`/mesures-disciplinaires/${m.id}/`, { method: 'DELETE' }), 'Mesure retirée.')

  // Un champ de formulaire lié à son état : `{...pourContrat('type')}` donne sa valeur et son gestionnaire.
  const lier = (etat, setEtat) => (nom) => ({ value: etat[nom], onChange: (e) => setEtat({ ...etat, [nom]: e.target.value }) })
  const pourContrat = lier(contrat, setContrat)
  const pourEvaluation = lier(evaluation, setEvaluation)
  const pourMesure = lier(mesure, setMesure)

  return (
    <section className="card detail-panneau">
      <div className="button-row">
        <h2>
          Fiche de {dossier.agent_nom} <span className="muted">({ROLE_LABELS[dossier.agent_role] || dossier.agent_role})</span>
        </h2>
        <button type="button" className="button-secondary button-small" onClick={onFermer}>
          Fermer la fiche
        </button>
      </div>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      {data && (
        <>
          <h3>Contrats</h3>
          {data.contrats.length === 0 ? (
            <p className="muted">Aucun contrat enregistré.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Nature</th>
                    <th>Début</th>
                    <th>Fin</th>
                    <th>Référence</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.contrats.map((c) => (
                    <tr key={c.id}>
                      <td>{c.type_libelle}</td>
                      <td>{formatDate(c.date_debut)}</td>
                      <td>{c.date_fin ? formatDate(c.date_fin) : 'Sans terme'}</td>
                      <td>{c.reference || '—'}</td>
                      <td>
                        <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirerContrat(c)}>
                          Retirer
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <form onSubmit={ajouterContrat}>
            <div className="form-grid">
              <label>
                Nature du contrat
                <select {...pourContrat('type')}>
                  {Object.entries(TYPES_CONTRAT).map(([valeur, libelle]) => (
                    <option key={valeur} value={valeur}>
                      {libelle}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Début du contrat
                <input type="date" {...pourContrat('date_debut')} required />
              </label>
              <label>
                Fin du contrat
                <input type="date" {...pourContrat('date_fin')} />
              </label>
              <label>
                Référence du contrat
                <input {...pourContrat('reference')} />
              </label>
            </div>
            <div className="button-row">
              <button type="submit" disabled={envoi}>
                Ajouter le contrat
              </button>
            </div>
          </form>

          <h3>Évaluations</h3>
          {data.evaluations.length === 0 ? (
            <p className="muted">Aucune évaluation.</p>
          ) : (
            <ul className="motifs">
              {data.evaluations.map((e) => (
                <li key={e.id}>
                  {formatDate(e.date)} — <strong>{e.note}/5</strong> par {e.evaluateur_nom}
                  {e.commentaire && ` : ${e.commentaire}`}{' '}
                  <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirerEvaluation(e)}>
                    Retirer
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={ajouterEvaluation}>
            <div className="form-grid">
              <label>
                Date de l&apos;évaluation
                <input type="date" max={isoAujourdhui(0)} {...pourEvaluation('date')} required />
              </label>
              <label>
                Note sur 5
                <select {...pourEvaluation('note')}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Commentaire
                <input {...pourEvaluation('commentaire')} />
              </label>
            </div>
            <div className="button-row">
              <button type="submit" disabled={envoi}>
                Ajouter l&apos;évaluation
              </button>
            </div>
          </form>

          <h3>Discipline</h3>
          {data.mesures.length === 0 ? (
            <p className="muted">Aucune mesure disciplinaire.</p>
          ) : (
            <ul className="motifs">
              {data.mesures.map((m) => (
                <li key={m.id}>
                  {formatDate(m.date)} — <strong>{m.type_libelle}</strong>
                  {m.duree_jours ? ` (${m.duree_jours} j)` : ''} : {m.motif}{' '}
                  <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirerMesure(m)}>
                    Retirer
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={ajouterMesure}>
            <div className="form-grid">
              <label>
                Date de la mesure
                <input type="date" max={isoAujourdhui(0)} {...pourMesure('date')} required />
              </label>
              <label>
                Nature de la mesure
                <select {...pourMesure('type')}>
                  {Object.entries(TYPES_MESURE).map(([valeur, libelle]) => (
                    <option key={valeur} value={valeur}>
                      {libelle}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Durée (jours)
                <input type="number" min="1" {...pourMesure('duree_jours')} />
              </label>
              <label>
                Motif de la mesure
                <input {...pourMesure('motif')} required />
              </label>
            </div>
            <div className="button-row">
              <button type="submit" disabled={envoi}>
                Ajouter la mesure
              </button>
            </div>
          </form>

          <h3>Formations obligatoires</h3>
          {data.formations.length === 0 ? (
            <p className="muted">Aucune formation obligatoire pour ce poste.</p>
          ) : (
            <ul className="motifs">
              {data.formations.map((f) => (
                <li key={f.obligation}>
                  {f.obligation_nom} <Badge ton={ETATS_FORMATION[f.etat].ton}>{ETATS_FORMATION[f.etat].libelle}</Badge>
                  {f.date_expiration && ` jusqu'au ${formatDate(f.date_expiration)}`}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
