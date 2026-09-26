import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Barres from '../components/Barres.jsx'
import CongesDrh from '../components/CongesDrh.jsx'
import FicheAgent from '../components/FicheAgent.jsx'
import FichesDePoste from '../components/FichesDePoste.jsx'
import FormationsObligatoires from '../components/FormationsObligatoires.jsx'
import Kpi from '../components/Kpi.jsx'
import MediationDrh from '../components/MediationDrh.jsx'
import OffresRecrutement from '../components/OffresRecrutement.jsx'
import Onglets from '../components/Onglets.jsx'
import SyntheseRh from '../components/SyntheseRh.jsx'
import { anciennete, formatDate } from '../lib/format.js'

const STATUTS = { actif: 'Actif', suspendu: 'Suspendu', termine: 'Terminé' }
const TON_STATUT = { actif: 'vert', suspendu: 'orange', termine: 'neutre' }
const DOSSIER_VIDE = { agent: '', poste: '', date_embauche: '', statut: 'actif', notes_rh: '' }
const ONGLETS = [
  { id: 'vue', label: "Vue d'ensemble" },
  { id: 'dossiers', label: 'Dossiers' },
  { id: 'formations', label: 'Formations obligatoires' },
  { id: 'conges', label: 'Congés' },
  { id: 'recrutement', label: 'Recrutement' },
  { id: 'mediation', label: 'Médiation sociale' },
]

export default function RhDashboard() {
  const [onglet, setOnglet] = useState('vue')
  const [filtreStatut, setFiltreStatut] = useState('')
  const [recherche, setRecherche] = useState('')
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [edition, setEdition] = useState(null)
  const [fiche, setFiche] = useState(null)
  const [nouveau, setNouveau] = useState(DOSSIER_VIDE)
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(async () => {
    const [dossiers, agentsSansDossier, scores] = await Promise.all([
      apiFetch('/dossiers-agents/'),
      apiFetch('/dossiers-agents/agents-sans-dossier/'),
      apiFetch('/gamification/agents/'),
    ])
    return { dossiers, agentsSansDossier, scores: scores.agents }
  })

  async function modifier(dossier, champs, confirmation) {
    setMessage({ type: '', texte: '' })
    try {
      await apiFetch(`/dossiers-agents/${dossier.id}/`, { method: 'PATCH', body: champs })
      setMessage({ type: 'success', texte: confirmation })
      setEdition(null)
      await recharger()
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    }
  }

  async function creer(event) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch('/dossiers-agents/', {
        method: 'POST',
        body: { ...nouveau, agent: Number(nouveau.agent) },
      })
      setMessage({ type: 'success', texte: 'Dossier ouvert.' })
      setNouveau(DOSSIER_VIDE)
      await recharger()
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — Ressources humaines">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { dossiers, agentsSansDossier, scores } = data
  const parStatut = (statut) => dossiers.filter((d) => d.statut === statut).length
  const recherchee = recherche.trim().toLowerCase()
  const visibles = dossiers.filter(
    (d) =>
      (!filtreStatut || d.statut === filtreStatut) &&
      (!recherchee || `${d.agent_nom} ${d.poste}`.toLowerCase().includes(recherchee)),
  )
  const dossierOuvert = dossiers.find((d) => d.id === fiche)

  const parPoste = {}
  dossiers
    .filter((d) => d.statut === 'actif')
    .forEach((d) => {
      parPoste[d.poste] = (parPoste[d.poste] || 0) + 1
    })

  return (
    <Layout title="Tableau de bord — Ressources humaines">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <Onglets onglets={ONGLETS} actif={onglet} onChoix={setOnglet} />

      {onglet === 'vue' && (
        <>
          <SyntheseRh />

          <h2 className="section-title">Dossiers</h2>
          <div className="cards-grid">
            <Kpi titre="Agents actifs" valeur={parStatut('actif')} ton="vert" />
            <Kpi titre="Agents suspendus" valeur={parStatut('suspendu')} ton={parStatut('suspendu') ? 'orange' : undefined} />
            <Kpi titre="Dossiers terminés" valeur={parStatut('termine')} />
            <Kpi
              titre="Agents sans dossier"
              valeur={agentsSansDossier.length}
              detail="comptes utilisateurs à rattacher à un dossier"
              ton={agentsSansDossier.length > 0 ? 'orange' : 'vert'}
            />
          </div>

          <h2 className="section-title">Effectif actif par poste</h2>
          <section className="card">
            <Barres
              lignes={Object.entries(parPoste)
                .sort((a, b) => b[1] - a[1])
                .map(([poste, nombre]) => ({ cle: poste, label: poste, valeur: nombre }))}
              vide="Aucun agent actif."
            />
          </section>

          <h2 className="section-title">Scores de gamification par agent</h2>
          <p className="muted">
            Une aide à l&apos;évaluation, à lire avec le contexte de chaque poste : les points mesurent ce que le système voit
            (tickets, trajets, colis, interventions...). Les agents dont le poste n&apos;affiche pas la gamification n&apos;y figurent pas.
          </p>
          {scores.length === 0 ? (
            <p>Aucun score pour le moment.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Poste</th>
                    <th>Niveau</th>
                    <th>Points</th>
                    <th>Badges</th>
                    <th>Missions accomplies</th>
                  </tr>
                </thead>
                <tbody>
                  {scores.map((s) => (
                    <tr key={s.id}>
                      <td>{s.nom}</td>
                      <td>{ROLE_LABELS[s.role] || s.role}</td>
                      <td>
                        {s.niveau.numero} · {s.niveau.nom}
                      </td>
                      <td>{s.points}</td>
                      <td>{s.badges}</td>
                      <td>{s.missions_accomplies}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {onglet === 'dossiers' && (
        <>
          <h2 className="section-title">Dossiers des agents</h2>
          <div className="toolbar">
            <label>
              Statut
              <select value={filtreStatut} onChange={(e) => setFiltreStatut(e.target.value)}>
                <option value="">Tous</option>
                {Object.entries(STATUTS).map(([valeur, label]) => (
                  <option key={valeur} value={valeur}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Recherche
              <input
                type="search"
                placeholder="Nom ou poste"
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
              />
            </label>
          </div>

          {dossierOuvert && <FicheAgent dossier={dossierOuvert} onFermer={() => setFiche(null)} />}

          {visibles.length === 0 ? (
            <p>Aucun dossier ne correspond.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Rôle</th>
                    <th>Poste</th>
                    <th>Embauche</th>
                    <th>Statut</th>
                    <th>Notes RH</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((dossier) => (
                    <tr key={dossier.id}>
                      <td>{dossier.agent_nom}</td>
                      <td>{ROLE_LABELS[dossier.agent_role] || dossier.agent_role}</td>
                      <td>{dossier.poste}</td>
                      <td>
                        {formatDate(dossier.date_embauche)}
                        <br />
                        <span className="muted">{anciennete(dossier.date_embauche)} an(s) d&apos;ancienneté</span>
                      </td>
                      <td>
                        <Badge ton={TON_STATUT[dossier.statut]}>{STATUTS[dossier.statut]}</Badge>
                        <br />
                        <select
                          aria-label={`Statut de ${dossier.agent_nom}`}
                          value={dossier.statut}
                          onChange={(e) =>
                            modifier(dossier, { statut: e.target.value }, `Statut de ${dossier.agent_nom} mis à jour.`)
                          }
                        >
                          {Object.entries(STATUTS).map(([valeur, label]) => (
                            <option key={valeur} value={valeur}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        {edition?.id === dossier.id ? (
                          <>
                            <textarea
                              rows={3}
                              value={edition.notes}
                              onChange={(e) => setEdition({ id: dossier.id, notes: e.target.value })}
                            />
                            <div className="button-row">
                              <button
                                type="button"
                                className="button-small"
                                onClick={() =>
                                  modifier(dossier, { notes_rh: edition.notes }, `Notes de ${dossier.agent_nom} enregistrées.`)
                                }
                              >
                                Enregistrer
                              </button>
                              <button type="button" className="button-secondary button-small" onClick={() => setEdition(null)}>
                                Annuler
                              </button>
                            </div>
                          </>
                        ) : (
                          <>
                            {dossier.notes_rh || <span className="muted">—</span>}{' '}
                            <button
                              type="button"
                              className="button-secondary button-small"
                              onClick={() => setEdition({ id: dossier.id, notes: dossier.notes_rh })}
                            >
                              Modifier
                            </button>
                          </>
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button-secondary button-small"
                          aria-label={`Ouvrir la fiche de ${dossier.agent_nom}`}
                          onClick={() => setFiche(dossier.id)}
                        >
                          Fiche complète
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 className="section-title">Ouvrir un dossier</h2>
          {agentsSansDossier.length === 0 ? (
            <p className="muted">Tous les agents de la compagnie ont déjà un dossier.</p>
          ) : (
            <section className="card">
              <form onSubmit={creer}>
                <div className="form-grid">
                  <label>
                    Agent
                    <select
                      value={nouveau.agent}
                      onChange={(e) => setNouveau({ ...nouveau, agent: e.target.value })}
                      required
                    >
                      <option value="">— Choisir —</option>
                      {agentsSansDossier.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.nom} ({ROLE_LABELS[agent.role] || agent.role})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Poste
                    <input value={nouveau.poste} onChange={(e) => setNouveau({ ...nouveau, poste: e.target.value })} required />
                  </label>
                  <label>
                    Date d&apos;embauche
                    <input
                      type="date"
                      value={nouveau.date_embauche}
                      onChange={(e) => setNouveau({ ...nouveau, date_embauche: e.target.value })}
                      required
                    />
                  </label>
                  <label>
                    Statut
                    <select value={nouveau.statut} onChange={(e) => setNouveau({ ...nouveau, statut: e.target.value })}>
                      {Object.entries(STATUTS).map(([valeur, label]) => (
                        <option key={valeur} value={valeur}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="button-row">
                  <button type="submit" disabled={envoi}>
                    {envoi ? 'Création…' : 'Ouvrir le dossier'}
                  </button>
                </div>
              </form>
            </section>
          )}
        </>
      )}

      {onglet === 'formations' && <FormationsObligatoires />}
      {onglet === 'conges' && <CongesDrh />}
      {onglet === 'recrutement' && (
        <>
          <FichesDePoste />
          <OffresRecrutement />
        </>
      )}
      {onglet === 'mediation' && <MediationDrh />}
    </Layout>
  )
}
