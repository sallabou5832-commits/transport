import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import Kpi from './Kpi.jsx'
import { formatDate, isoAujourdhui } from '../lib/format.js'
import { ETATS_FORMATION } from '../lib/rh.js'

const POSTES = Object.entries(ROLE_LABELS).filter(([role]) => role !== 'superadmin')
const OBLIGATION_VIDE = { nom: '', roles: [], validite_mois: '', preavis_jours: '60' }
const SESSION_VIDE = { obligation: '', agent: '', date_obtention: '', date_expiration: '', organisme: '', reference: '' }

/**
 * Le suivi des formations et documents obligatoires (sécurité routière OSER, permis, visite médicale…), partagé par le DRH et le QHSE :
 * qui est à jour, qui est à renouveler ou expiré, l'enregistrement d'une session suivie, et le catalogue des obligations par poste.
 * Le DRH, le QHSE et l'agent sont alertés quand une échéance approche (`manage.py generer_alertes`).
 */
export default function FormationsObligatoires() {
  const [etat, setEtat] = useState('')
  const [session, setSession] = useState(SESSION_VIDE)
  const [obligation, setObligation] = useState(OBLIGATION_VIDE)
  const { data, error, recharger } = useChargement(
    async () => {
      const [suivi, obligations] = await Promise.all([apiFetch('/formations-obligatoires/suivi/'), apiFetch('/obligations-formation/')])
      return { suivi, obligations }
    },
    { intervalleMs: 120000 },
  )
  const { agir, envoi, message } = useActions(recharger)

  async function enregistrerSession(event) {
    event.preventDefault()
    const corps = { agent: Number(session.agent), obligation: Number(session.obligation), date_obtention: session.date_obtention }
    for (const champ of ['date_expiration', 'organisme', 'reference']) {
      if (session[champ]) corps[champ] = session[champ]
    }
    if (await agir(() => apiFetch('/formations-suivies/', { method: 'POST', body: corps }), 'Session enregistrée.')) setSession(SESSION_VIDE)
  }

  async function ajouterObligation(event) {
    event.preventDefault()
    const corps = { nom: obligation.nom, roles: obligation.roles, preavis_jours: Number(obligation.preavis_jours) || 60 }
    corps.validite_mois = obligation.validite_mois === '' ? null : Number(obligation.validite_mois)
    if (await agir(() => apiFetch('/obligations-formation/', { method: 'POST', body: corps }), `Obligation « ${obligation.nom} » ajoutée.`)) {
      setObligation(OBLIGATION_VIDE)
    }
  }

  const retirer = (o) => agir(() => apiFetch(`/obligations-formation/${o.id}/`, { method: 'DELETE' }), `Obligation « ${o.nom} » retirée.`)
  const basculerPoste = (role) =>
    setObligation({
      ...obligation,
      roles: obligation.roles.includes(role) ? obligation.roles.filter((r) => r !== role) : [...obligation.roles, role],
    })

  if (!data) return <Alert>{error}</Alert>
  const { suivi, obligations } = data
  const lignes = suivi.lignes.filter((ligne) => !etat || ligne.etat === etat)
  // Les agents qu'une obligation concerne : ceux du suivi, puisque le suivi ne liste que les postes visés.
  const agentsConcernes = [...new Map(suivi.lignes.filter((l) => String(l.obligation) === session.obligation).map((l) => [l.agent, l])).values()]

  function renouveler(ligne) {
    setSession({ ...SESSION_VIDE, obligation: String(ligne.obligation), agent: String(ligne.agent), date_obtention: isoAujourdhui(0) })
  }

  return (
    <div>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <div className="cards-grid">
        <Kpi titre="Expirées" valeur={suivi.resume.expiree} ton={suivi.resume.expiree > 0 ? 'rouge' : 'vert'} />
        <Kpi titre="À renouveler" valeur={suivi.resume.a_renouveler} ton={suivi.resume.a_renouveler > 0 ? 'orange' : 'vert'} />
        <Kpi titre="Manquantes" valeur={suivi.resume.manquante} ton={suivi.resume.manquante > 0 ? 'orange' : 'vert'} />
        <Kpi titre="À jour" valeur={suivi.resume.a_jour} ton="vert" />
      </div>

      <section className="card">
        <h2>Suivi par agent</h2>
        <div className="toolbar">
          <label>
            État
            <select value={etat} onChange={(e) => setEtat(e.target.value)}>
              <option value="">Tous</option>
              {Object.entries(ETATS_FORMATION).map(([valeur, e]) => (
                <option key={valeur} value={valeur}>
                  {e.libelle}
                </option>
              ))}
            </select>
          </label>
        </div>
        {lignes.length === 0 ? (
          <p className="muted">Rien à afficher pour ce filtre.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Formation</th>
                  <th>Valable jusqu&apos;au</th>
                  <th>État</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lignes.map((ligne) => (
                  <tr key={`${ligne.agent}-${ligne.obligation}`} className={['expiree', 'manquante'].includes(ligne.etat) ? 'row-danger' : ''}>
                    <td>
                      {ligne.agent_nom}
                      <div className="muted">{ROLE_LABELS[ligne.agent_role] || ligne.agent_role}</div>
                    </td>
                    <td>{ligne.obligation_nom}</td>
                    <td>
                      {ligne.date_expiration ? formatDate(ligne.date_expiration) : ligne.date_obtention ? 'Sans échéance' : '—'}
                      {ligne.jours_restants !== null && (
                        <div className="muted">{ligne.jours_restants >= 0 ? `dans ${ligne.jours_restants} j` : `échue depuis ${-ligne.jours_restants} j`}</div>
                      )}
                    </td>
                    <td>
                      <Badge ton={ETATS_FORMATION[ligne.etat].ton}>{ETATS_FORMATION[ligne.etat].libelle}</Badge>
                    </td>
                    <td>
                      {ligne.etat !== 'a_jour' && (
                        <button type="button" className="button-secondary button-small" onClick={() => renouveler(ligne)}>
                          Enregistrer une session
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Enregistrer une session suivie</h2>
        <form onSubmit={enregistrerSession}>
          <div className="form-grid">
            <label>
              Formation
              <select value={session.obligation} onChange={(e) => setSession({ ...session, obligation: e.target.value, agent: '' })} required>
                <option value="">— Choisir —</option>
                {obligations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.nom}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Agent
              <select value={session.agent} onChange={(e) => setSession({ ...session, agent: e.target.value })} required>
                <option value="">— Choisir —</option>
                {agentsConcernes.map((l) => (
                  <option key={l.agent} value={l.agent}>
                    {l.agent_nom}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Date de la session
              <input
                type="date"
                max={isoAujourdhui(0)}
                value={session.date_obtention}
                onChange={(e) => setSession({ ...session, date_obtention: e.target.value })}
                required
              />
            </label>
            <label>
              Valable jusqu&apos;au (sinon calculé)
              <input type="date" value={session.date_expiration} onChange={(e) => setSession({ ...session, date_expiration: e.target.value })} />
            </label>
            <label>
              Organisme
              <input value={session.organisme} onChange={(e) => setSession({ ...session, organisme: e.target.value })} />
            </label>
            <label>
              Référence
              <input value={session.reference} onChange={(e) => setSession({ ...session, reference: e.target.value })} />
            </label>
          </div>
          <div className="button-row">
            <button type="submit" disabled={envoi}>
              Enregistrer la session
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2>Catalogue des obligations par poste</h2>
        {obligations.length === 0 ? (
          <p className="muted">Aucune obligation déclarée : ajoutez la sécurité routière, la visite médicale, le permis…</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Obligation</th>
                  <th>Postes concernés</th>
                  <th>Validité</th>
                  <th>Préavis</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {obligations.map((o) => (
                  <tr key={o.id}>
                    <td>{o.nom}</td>
                    <td>{o.roles.map((r) => ROLE_LABELS[r] || r).join(', ')}</td>
                    <td>{o.validite_mois ? `${o.validite_mois} mois` : 'Sans échéance'}</td>
                    <td>{o.preavis_jours} j</td>
                    <td>
                      <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirer(o)}>
                        Retirer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h3>Ajouter une obligation</h3>
        <form onSubmit={ajouterObligation}>
          <div className="form-grid">
            <label>
              Nom de l&apos;obligation
              <input value={obligation.nom} onChange={(e) => setObligation({ ...obligation, nom: e.target.value })} placeholder="Sécurité routière OSER" required />
            </label>
            <label>
              Validité (mois, vide : sans échéance)
              <input type="number" min="1" value={obligation.validite_mois} onChange={(e) => setObligation({ ...obligation, validite_mois: e.target.value })} />
            </label>
            <label>
              Préavis d&apos;alerte (jours)
              <input type="number" min="1" value={obligation.preavis_jours} onChange={(e) => setObligation({ ...obligation, preavis_jours: e.target.value })} />
            </label>
          </div>
          <fieldset className="cases">
            <legend>Postes concernés</legend>
            {POSTES.map(([role, libelle]) => (
              <label key={role}>
                <input type="checkbox" checked={obligation.roles.includes(role)} onChange={() => basculerPoste(role)} />
                {libelle}
              </label>
            ))}
          </fieldset>
          <div className="button-row">
            <button type="submit" disabled={envoi || obligation.roles.length === 0}>
              Ajouter l&apos;obligation
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
