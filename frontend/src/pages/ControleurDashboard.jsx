import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Jauge from '../components/Jauge.jsx'
import {
  LABELS_GRAVITE,
  LABELS_TYPE_INCIDENT,
  estAujourdhui,
  formatDateHeure,
  indexParId,
} from '../lib/format.js'

const MODES = { especes: 'Espèces', mobile_money: 'Mobile money' }
const INCIDENT_VIDE = { type_incident: 'autre', gravite: 'moyenne', description: '' }

export default function ControleurDashboard() {
  const [departId, setDepartId] = useState('')
  const [recherche, setRecherche] = useState('')
  const [incident, setIncident] = useState(INCIDENT_VIDE)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading } = useChargement(
    async () => {
      const [lignes, departs, vehicules, feuilles, tickets] = await Promise.all([
        apiFetch('/lignes/'),
        apiFetch('/departs/'),
        apiFetch('/vehicules/'),
        apiFetch('/feuilles-de-route/'),
        apiFetch('/tickets/'),
      ])
      return { lignes, departs, vehicules, feuilles, tickets }
    },
    { intervalleMs: 60000 },
  )

  async function signaler(event, depart, feuille) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch('/incidents/', {
        method: 'POST',
        body: {
          feuille_de_route: feuille?.id ?? null,
          vehicule: depart.vehicule,
          chauffeur: depart.chauffeur,
          ...incident,
        },
      })
      setMessage({
        type: 'success',
        texte:
          incident.gravite === 'grave'
            ? 'Infraction grave enregistrée : la direction et le QHSE la voient sur leur tableau de bord.'
            : 'Incident enregistré.',
      })
      setIncident(INCIDENT_VIDE)
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — Contrôleur de ligne">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { lignes, departs, vehicules, feuilles, tickets } = data
  const lignesParId = indexParId(lignes)
  const vehiculesParId = indexParId(vehicules)
  const feuillesParDepart = Object.fromEntries(feuilles.map((f) => [f.depart, f]))

  const aControler = departs
    .filter((d) => estAujourdhui(d.date_heure) && d.statut !== 'termine')
    .sort((a, b) => new Date(a.date_heure) - new Date(b.date_heure))
  const depart = aControler.find((d) => String(d.id) === departId)
  const vehicule = depart ? vehiculesParId[depart.vehicule] : null
  const feuille = depart ? feuillesParDepart[depart.id] : null

  // Un ticket annulé n'est plus un passager : la vérification de charge ne compte que les tickets valides.
  const passagers = depart ? tickets.filter((t) => t.depart === depart.id && t.statut === 'valide') : []
  const recherchee = recherche.trim().toLowerCase()
  const passagersVisibles = passagers.filter(
    (t) => !recherchee || `${t.passager_nom} ${t.passager_telephone}`.toLowerCase().includes(recherchee),
  )
  const ecart = depart ? depart.places_vendues - passagers.length : 0

  return (
    <Layout title="Tableau de bord — Contrôleur de ligne">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <div className="toolbar">
        <label>
          Départ à contrôler
          <select value={departId} onChange={(e) => setDepartId(e.target.value)}>
            <option value="">— Choisir un départ du jour —</option>
            {aControler.map((d) => (
              <option key={d.id} value={d.id}>
                {formatDateHeure(d.date_heure)} — {lignesParId[d.ligne]?.nom}
              </option>
            ))}
          </select>
        </label>
      </div>

      {aControler.length === 0 && <p>Aucun départ à contrôler aujourd&apos;hui.</p>}

      {depart && (
        <>
          <section className="card">
            <h2>{lignesParId[depart.ligne]?.nom}</h2>
            <p>
              Véhicule <strong>{vehicule?.immatriculation}</strong> · chauffeur <strong>{depart.chauffeur_nom}</strong> ·{' '}
              {feuille?.heure_depart_reelle ? (
                <Badge ton="bleu">Parti à {formatDateHeure(feuille.heure_depart_reelle)}</Badge>
              ) : (
                <Badge>Pas encore parti</Badge>
              )}
            </p>
            <h2 style={{ marginTop: '1rem' }}>Vérification de charge</h2>
            <Jauge vendues={depart.places_vendues} capacite={vehicule?.capacite} />
            <p>
              {passagers.length} ticket(s) enregistré(s) pour {depart.places_vendues} place(s) vendue(s){' '}
              {ecart === 0 ? (
                <Badge ton="vert">Cohérent</Badge>
              ) : (
                <Badge ton="rouge">Écart de {Math.abs(ecart)}</Badge>
              )}
            </p>
            <p className="muted">
              Le contrôle d&apos;un ticket déjà utilisé n&apos;est pas encore possible : le serveur n&apos;enregistre pas
              la validation des tickets. Comparez la liste des passagers ci-dessous aux voyageurs à bord.
            </p>
          </section>

          <h2 className="section-title">Liste des passagers</h2>
          <div className="toolbar">
            <label>
              Rechercher
              <input
                type="search"
                placeholder="Nom ou téléphone"
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
              />
            </label>
          </div>
          {passagersVisibles.length === 0 ? (
            <p>Aucun passager.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Passager</th>
                    <th>Téléphone</th>
                    <th>Paiement</th>
                    <th>Vendu le</th>
                  </tr>
                </thead>
                <tbody>
                  {passagersVisibles.map((ticket) => (
                    <tr key={ticket.id}>
                      <td>{ticket.passager_nom}</td>
                      <td>{ticket.passager_telephone}</td>
                      <td>{MODES[ticket.mode_paiement]}</td>
                      <td>{formatDateHeure(ticket.date_vente)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 className="section-title">Signaler une infraction ou un incident</h2>
          <section className="card">
            <form onSubmit={(e) => signaler(e, depart, feuille)}>
              <div className="form-grid">
                <label>
                  Type
                  <select
                    value={incident.type_incident}
                    onChange={(e) => setIncident({ ...incident, type_incident: e.target.value })}
                  >
                    {Object.entries(LABELS_TYPE_INCIDENT).map(([valeur, label]) => (
                      <option key={valeur} value={valeur}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Gravité
                  <select value={incident.gravite} onChange={(e) => setIncident({ ...incident, gravite: e.target.value })}>
                    {Object.entries(LABELS_GRAVITE).map(([valeur, label]) => (
                      <option key={valeur} value={valeur}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Description
                  <input
                    value={incident.description}
                    onChange={(e) => setIncident({ ...incident, description: e.target.value })}
                    required
                  />
                </label>
              </div>
              <div className="button-row">
                <button type="submit" disabled={envoi}>
                  {envoi ? 'Envoi…' : 'Signaler'}
                </button>
              </div>
            </form>
          </section>
        </>
      )}
    </Layout>
  )
}
