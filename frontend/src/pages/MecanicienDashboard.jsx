import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Layout from '../components/Layout.jsx'
import DemandePieceAtelier from '../components/DemandePieceAtelier.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import { LABELS_VEHICULE, TON_VEHICULE, formatDateHeure, indexParId } from '../lib/format.js'

const STATUT_LABELS = { ouvert: 'Ouvert', en_cours: 'En cours', termine: 'Terminé' }
const TON_STATUT = { ouvert: 'orange', en_cours: 'bleu', termine: 'vert' }

export default function MecanicienDashboard() {
  const { user } = useAuth()
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [minutes, setMinutes] = useState({})
  const [sortie, setSortie] = useState({ ordre: '', piece: '', quantite: '1' })
  const [collegues, setCollegues] = useState({})
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(
    async () => {
      const [ordres, vehicules, pieces, moi, intervenants] = await Promise.all([
        apiFetch('/ordres-reparation/'),
        apiFetch('/vehicules/'),
        apiFetch('/pieces/'),
        // Ce que le règlement intérieur permet au mécanicien : confier son ordre à un collègue, le supprimer.
        apiFetch('/configuration/moi/'),
        apiFetch('/maintenance/intervenants/'),
      ])
      return { ordres, vehicules, pieces, reglement: moi.reglement || {}, intervenants }
    },
    { intervalleMs: 60000 },
  )

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()  // les listes d'abord, le message ensuite
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  function demarrer(ordre) {
    return agir(
      () => apiFetch(`/ordres-reparation/${ordre.id}/`, { method: 'PATCH', body: { statut: 'en_cours' } }),
      `Intervention #${ordre.id} démarrée.`,
    )
  }

  function cloturer(ordre) {
    return agir(
      () =>
        apiFetch(`/ordres-reparation/${ordre.id}/`, {
          method: 'PATCH',
          body: { statut: 'termine', temps_passe_minutes: Number(minutes[ordre.id]) },
        }),
      `Intervention #${ordre.id} clôturée : le régulateur est prévenu dès que le véhicule redevient disponible.`,
    )
  }

  function confier(ordre) {
    const collegue = data.intervenants.find((i) => i.id === Number(collegues[ordre.id]))
    return agir(
      () => apiFetch(`/ordres-reparation/${ordre.id}/`, { method: 'PATCH', body: { mecanicien: collegue.id } }),
      `Intervention #${ordre.id} confiée à ${collegue.nom} : lui et le chef d'atelier sont prévenus.`,
    )
  }

  function supprimer(ordre) {
    if (!window.confirm(`Supprimer l'ordre de réparation #${ordre.id} (${ordre.description}) ?`)) return
    agir(() => apiFetch(`/ordres-reparation/${ordre.id}/`, { method: 'DELETE' }), `Ordre de réparation #${ordre.id} supprimé.`)
  }

  async function sortirPiece(event) {
    event.preventDefault()
    const ok = await agir(
      () =>
        apiFetch('/sorties-pieces/', {
          method: 'POST',
          body: {
            ordre_reparation: Number(sortie.ordre),
            piece: Number(sortie.piece),
            quantite: Number(sortie.quantite),
          },
        }),
      'Pièce sortie du stock et liée à l’ordre de réparation.',
    )
    if (ok) setSortie({ ordre: '', piece: '', quantite: '1' })
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — Mécanicien">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const vehiculesParId = indexParId(data.vehicules)
  const mesOrdres = data.ordres.filter((o) => o.mecanicien === user.id)
  const enCours = mesOrdres.filter((o) => o.statut !== 'termine')
  const termines = mesOrdres.filter((o) => o.statut === 'termine')
  const termineAujourdhui = termines.filter(
    (o) => o.date_cloture && new Date(o.date_cloture).toDateString() === new Date().toDateString(),
  ).length

  return (
    <Layout title="Tableau de bord — Mécanicien">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <p>
        <strong>{enCours.length}</strong> intervention(s) à faire · <strong>{termineAujourdhui}</strong> clôturée(s)
        aujourd&apos;hui
      </p>

      <h2 className="section-title">Mes interventions</h2>
      {enCours.length === 0 && !error && <p>Aucune intervention ne vous est confiée.</p>}
      {enCours.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Véhicule</th>
                <th>Description</th>
                <th>Statut</th>
                <th>Créé le</th>
                <th>Intervention</th>
              </tr>
            </thead>
            <tbody>
              {enCours.map((ordre) => {
                const vehicule = vehiculesParId[ordre.vehicule]
                return (
                  <tr key={ordre.id}>
                    <td>
                      {vehicule?.immatriculation || ordre.vehicule}
                      <br />
                      {vehicule && <Badge ton={TON_VEHICULE[vehicule.statut]}>{LABELS_VEHICULE[vehicule.statut]}</Badge>}
                    </td>
                    <td>{ordre.description}</td>
                    <td>
                      <Badge ton={TON_STATUT[ordre.statut]}>{STATUT_LABELS[ordre.statut]}</Badge>
                    </td>
                    <td>{formatDateHeure(ordre.date_creation)}</td>
                    <td>
                      <div className="toolbar" style={{ margin: 0 }}>
                        {ordre.statut === 'ouvert' && (
                          <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => demarrer(ordre)}>
                            Démarrer
                          </button>
                        )}
                        <input
                          type="number"
                          min="1"
                          placeholder="Temps passé (min)"
                          aria-label={`Temps passé sur l’intervention ${ordre.id}, en minutes`}
                          value={minutes[ordre.id] || ''}
                          onChange={(e) => setMinutes({ ...minutes, [ordre.id]: e.target.value })}
                          style={{ width: '9rem' }}
                        />
                        <button
                          type="button"
                          className="button-small"
                          disabled={envoi || !(Number(minutes[ordre.id]) > 0)}
                          onClick={() => cloturer(ordre)}
                        >
                          Clôturer
                        </button>
                      </div>
                      {(data.reglement.mecanicien_confie_ses_ordres || data.reglement.mecanicien_supprime_ses_ordres) && (
                        <div className="toolbar" style={{ margin: '0.4rem 0 0' }}>
                          {data.reglement.mecanicien_confie_ses_ordres && (
                            <>
                              <select
                                aria-label={`Collègue à qui confier l’intervention ${ordre.id}`}
                                value={collegues[ordre.id] || ''}
                                onChange={(e) => setCollegues({ ...collegues, [ordre.id]: e.target.value })}
                              >
                                <option value="">— Confier à —</option>
                                {data.intervenants
                                  .filter((i) => i.id !== user.id)
                                  .map((i) => (
                                    <option key={i.id} value={i.id}>
                                      {i.nom}
                                    </option>
                                  ))}
                              </select>
                              <button
                                type="button"
                                className="button-secondary button-small"
                                disabled={envoi || !collegues[ordre.id]}
                                onClick={() => confier(ordre)}
                              >
                                Confier
                              </button>
                            </>
                          )}
                          {data.reglement.mecanicien_supprime_ses_ordres && (
                            <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => supprimer(ordre)}>
                              Supprimer
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section-title">Sortir une pièce du stock</h2>
      <section className="card">
        <form onSubmit={sortirPiece}>
          <div className="form-grid">
            <label>
              Ordre de réparation
              <select value={sortie.ordre} onChange={(e) => setSortie({ ...sortie, ordre: e.target.value })} required>
                <option value="">— Choisir —</option>
                {enCours.map((o) => (
                  <option key={o.id} value={o.id}>
                    #{o.id} — {vehiculesParId[o.vehicule]?.immatriculation} — {o.description}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Pièce
              <select value={sortie.piece} onChange={(e) => setSortie({ ...sortie, piece: e.target.value })} required>
                <option value="">— Choisir —</option>
                {data.pieces.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nom} ({p.quantite_stock} en stock)
                  </option>
                ))}
              </select>
            </label>
            <label>
              Quantité
              <input
                type="number"
                min="1"
                value={sortie.quantite}
                onChange={(e) => setSortie({ ...sortie, quantite: e.target.value })}
                required
              />
            </label>
          </div>
          <div className="button-row">
            <button type="submit" disabled={envoi || enCours.length === 0}>
              Enregistrer la sortie
            </button>
          </div>
        </form>
      </section>

      <h2 className="section-title">Demander une pièce</h2>
      <DemandePieceAtelier mecanicien={user.id} />
    </Layout>
  )
}
