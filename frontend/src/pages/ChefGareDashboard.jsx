import { Fragment, useState } from 'react'
import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Jauge from '../components/Jauge.jsx'
import CaissesDuJour from '../components/CaissesDuJour.jsx'
import ColisDeLaGare from '../components/ColisDeLaGare.jsx'
import DemandeLigne from '../components/DemandeLigne.jsx'
import EquipeGare from '../components/EquipeGare.jsx'
import FicheGare from '../components/FicheGare.jsx'
import ImportVentes from '../components/ImportVentes.jsx'
import MessagesGare from '../components/MessagesGare.jsx'
import QuaisGare from '../components/QuaisGare.jsx'
import SanteGare from '../components/SanteGare.jsx'
import { formatDateHeure, formatFCFA, indexParId } from '../lib/format.js'

const STATUT_LABELS = { planifie: 'Planifié', en_cours: 'En cours', termine: 'Terminé' }
const MODES = { especes: 'Espèces', mobile_money: 'Mobile money' }
const MOTIF_MIN = 5

export default function ChefGareDashboard() {
  const { user } = useAuth()
  const [ouvert, setOuvert] = useState(null)
  const [motifs, setMotifs] = useState({})
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(async () => {
    const [gares, lignes, vehicules, departs, tickets] = await Promise.all([
      apiFetch('/gares/'),
      apiFetch('/lignes/'),
      apiFetch('/vehicules/'),
      apiFetch('/departs/'),
      apiFetch('/tickets/'),
    ])
    return { gare: gares.find((g) => g.chef === user.id) || null, lignes, vehicules, departs, tickets }
  })

  async function annuler(ticket) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch(`/tickets/${ticket.id}/annuler/`, { method: 'POST', body: { motif: motifs[ticket.id] } })
      setMessage({
        type: 'success',
        texte: `Ticket de ${ticket.passager_nom} annulé : la place est libérée et la vente sort des recettes.`,
      })
      setMotifs({ ...motifs, [ticket.id]: '' })
      await recharger()
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  if (!data?.gare) {
    return (
      <Layout title="Tableau de bord — Chef de gare">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
        {!loading && !error && <p>Aucune gare ne vous est rattachée : demandez à l’administrateur de vous désigner chef de gare.</p>}
      </Layout>
    )
  }

  const { gare, lignes, vehicules, departs, tickets } = data
  const lignesParId = indexParId(lignes)
  const vehiculesParId = indexParId(vehicules)
  const departsDeLaGare = departs.filter((d) => lignesParId[d.ligne]?.gare_depart === gare.id)

  return (
    <Layout title="Tableau de bord — Chef de gare">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <h2>{gare.nom}</h2>

      <SanteGare />

      <h2 className="section-title">Caisses du jour de l&apos;équipe</h2>
      <CaissesDuJour equipe />

      <EquipeGare gare={gare} />

      <MessagesGare />

      <ColisDeLaGare gare={gare} />

      <ImportVentes />

      <h2 className="section-title">Départs de la gare</h2>

      {departsDeLaGare.length === 0 ? (
        <p>Aucun départ prévu pour cette gare.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Ligne</th>
                <th>Date / heure</th>
                <th>Statut</th>
                <th>Jauge de remplissage</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {departsDeLaGare.map((depart) => {
                const vehicule = vehiculesParId[depart.vehicule]
                const ticketsDuDepart = tickets.filter((t) => t.depart === depart.id)
                return (
                  <Fragment key={depart.id}>
                    <tr>
                      <td>{lignesParId[depart.ligne]?.nom}</td>
                      <td>{formatDateHeure(depart.date_heure)}</td>
                      <td>{STATUT_LABELS[depart.statut] || depart.statut}</td>
                      <td>
                        <Jauge vendues={depart.places_vendues} capacite={vehicule?.capacite} reservees={depart.places_reservees} />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button-secondary button-small"
                          onClick={() => setOuvert(ouvert === depart.id ? null : depart.id)}
                        >
                          Tickets ({ticketsDuDepart.length})
                        </button>
                      </td>
                    </tr>
                    {ouvert === depart.id && (
                      <tr>
                        <td colSpan={5}>
                          {ticketsDuDepart.length === 0 ? (
                            <p className="muted">Aucun ticket sur ce départ.</p>
                          ) : (
                            <>
                              <p className="muted">
                                Un ticket vendu ne se modifie pas. Pour corriger une erreur, annulez-le avec un motif : la
                                place est libérée, la vente sort des recettes et l’annulation est tracée.
                              </p>
                              <table className="table">
                                <thead>
                                  <tr>
                                    <th>Passager</th>
                                    <th>Prix</th>
                                    <th>Paiement</th>
                                    <th>Statut</th>
                                    <th>Annulation</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {ticketsDuDepart.map((ticket) => (
                                    <tr key={ticket.id} className={ticket.statut === 'annule' ? 'row-alerte' : ''}>
                                      <td>
                                        {ticket.passager_nom}
                                        <br />
                                        <span className="muted">{ticket.passager_telephone}</span>
                                      </td>
                                      <td>{formatFCFA(ticket.prix)}</td>
                                      <td>{MODES[ticket.mode_paiement]}</td>
                                      <td>
                                        {ticket.statut === 'annule' ? (
                                          <Badge ton="rouge">Annulé</Badge>
                                        ) : (
                                          <Badge ton="vert">Valide</Badge>
                                        )}
                                      </td>
                                      <td>
                                        {ticket.statut === 'annule' ? (
                                          <span className="muted">
                                            {ticket.motif_annulation} — {formatDateHeure(ticket.annule_le)}
                                          </span>
                                        ) : (
                                          <div className="toolbar" style={{ margin: 0 }}>
                                            <input
                                              placeholder="Motif de l’annulation"
                                              aria-label={`Motif d’annulation du ticket de ${ticket.passager_nom}`}
                                              value={motifs[ticket.id] || ''}
                                              onChange={(e) => setMotifs({ ...motifs, [ticket.id]: e.target.value })}
                                            />
                                            <button
                                              type="button"
                                              className="button-small"
                                              disabled={envoi || (motifs[ticket.id] || '').trim().length < MOTIF_MIN}
                                              onClick={() => annuler(ticket)}
                                            >
                                              Annuler le ticket
                                            </button>
                                          </div>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section-title">Fermer ou rouvrir une ligne</h2>
      <DemandeLigne />

      <h2 className="section-title">Fiche de la gare</h2>
      <section className="card">
        <p className="muted">Adresse, téléphone et horaires de votre gare, et ses quais d&apos;embarquement.</p>
        <FicheGare key={gare.id} gare={gare} onEnregistre={recharger} />
        <QuaisGare gare={gare} />
      </section>
    </Layout>
  )
}
