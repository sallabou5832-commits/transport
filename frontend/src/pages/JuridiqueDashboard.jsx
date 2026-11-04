import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import DossierSinistre from '../components/DossierSinistre.jsx'
import EchangesTutelle from '../components/EchangesTutelle.jsx'
import Kpi from '../components/Kpi.jsx'
import LitigesSociaux from '../components/LitigesSociaux.jsx'
import ModelesJuridiquesGestion from '../components/ModelesJuridiquesGestion.jsx'
import Onglets from '../components/Onglets.jsx'
import ReportingJuridique from '../components/ReportingJuridique.jsx'
import TableauConformite from '../components/TableauConformite.jsx'
import {
  LABELS_TYPE_INCIDENT,
  formatDate,
  formatDateHeure,
  indexParId,
  joursRestants,
} from '../lib/format.js'

const STATUTS_SINISTRE = { ouvert: 'Ouvert', en_cours: 'En cours', clos: 'Clos' }
const TON_SINISTRE = { ouvert: 'rouge', en_cours: 'orange', clos: 'vert' }
const SEUIL_RENOUVELLEMENT_JOURS = 30
const ASSURANCE_VIDE = { vehicule: '', compagnie_assurance: '', numero_police: '', date_echeance: '' }
const SINISTRE_VIDE = { vehicule: '', incident: '', description: '' }
const ONGLETS = [
  { id: 'dossiers', label: 'Assurances et sinistres' },
  { id: 'litiges', label: 'Litiges sociaux' },
  { id: 'modeles', label: 'Modèles de documents' },
  { id: 'synthese', label: 'Synthèse pour la Direction' },
  { id: 'tutelle', label: 'Tutelle' },
]

function etatAssurance(assurance) {
  const jours = joursRestants(assurance.date_echeance)
  if (jours < 0) return { ton: 'rouge', label: `Expirée depuis ${-jours} j`, jours }
  if (jours <= SEUIL_RENOUVELLEMENT_JOURS) return { ton: 'orange', label: `Échéance dans ${jours} j`, jours }
  return { ton: 'vert', label: 'À jour', jours }
}

export default function JuridiqueDashboard() {
  const [onglet, setOnglet] = useState('dossiers')
  const [sinistreOuvert, setSinistreOuvert] = useState(null)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [nouvelleAssurance, setNouvelleAssurance] = useState(ASSURANCE_VIDE)
  const [nouveauSinistre, setNouveauSinistre] = useState(SINISTRE_VIDE)
  const [datesRenouvellement, setDatesRenouvellement] = useState({})
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(async () => {
    const [assurances, sinistres, vehicules, incidents] = await Promise.all([
      apiFetch('/assurances/'),
      apiFetch('/sinistres/'),
      apiFetch('/vehicules/'),
      apiFetch('/incidents/'),
    ])
    return { assurances, sinistres, vehicules, incidents }
  })

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      setMessage({ type: 'success', texte: confirmation })
      await recharger()
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  function renouveler(assurance) {
    const date = datesRenouvellement[assurance.id]
    if (!date) return
    return agir(
      () => apiFetch(`/assurances/${assurance.id}/`, { method: 'PATCH', body: { date_echeance: date } }),
      `Police ${assurance.numero_police} renouvelée jusqu'au ${formatDate(date)}.`,
    )
  }

  function supprimer(chemin, libelle) {
    // Pour une saisie erronée : une assurance ou un sinistre encore lié à d'autres données se garde (le serveur dit pourquoi).
    if (!window.confirm(`Supprimer ${libelle} ?`)) return
    agir(() => apiFetch(chemin, { method: 'DELETE' }), `${libelle.charAt(0).toUpperCase()}${libelle.slice(1)} supprimé(e).`)
  }

  async function creerAssurance(event) {
    event.preventDefault()
    const ok = await agir(
      () =>
        apiFetch('/assurances/', {
          method: 'POST',
          body: { ...nouvelleAssurance, vehicule: Number(nouvelleAssurance.vehicule) },
        }),
      'Assurance enregistrée.',
    )
    if (ok) setNouvelleAssurance(ASSURANCE_VIDE)
  }

  async function creerSinistre(event) {
    event.preventDefault()
    const ok = await agir(
      () =>
        apiFetch('/sinistres/', {
          method: 'POST',
          body: {
            description: nouveauSinistre.description,
            vehicule: nouveauSinistre.vehicule ? Number(nouveauSinistre.vehicule) : null,
            incident: nouveauSinistre.incident ? Number(nouveauSinistre.incident) : null,
          },
        }),
      'Sinistre enregistré.',
    )
    if (ok) setNouveauSinistre(SINISTRE_VIDE)
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — Juridique">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { assurances, sinistres, vehicules, incidents } = data
  const vehiculesParId = indexParId(vehicules)
  const incidentsParId = indexParId(incidents)
  const etats = assurances.map(etatAssurance)
  const expirees = etats.filter((e) => e.jours < 0).length
  const aRenouveler = etats.filter((e) => e.jours >= 0 && e.jours <= SEUIL_RENOUVELLEMENT_JOURS).length
  const sinistresActifs = sinistres.filter((s) => s.statut !== 'clos')
  const incidentsRecents = incidents.slice(0, 50)

  return (
    <Layout title="Tableau de bord — Juridique">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <Onglets onglets={ONGLETS} actif={onglet} onChoix={setOnglet} />

      {onglet === 'dossiers' && (
        <>
        <div className="cards-grid">
          <Kpi titre="Assurances expirées" valeur={expirees} ton={expirees > 0 ? 'rouge' : 'vert'} />
          <Kpi
            titre="À renouveler sous 30 jours"
            valeur={aRenouveler}
            ton={aRenouveler > 0 ? 'orange' : 'vert'}
          />
          <Kpi
            titre="Sinistres en cours"
            valeur={sinistresActifs.length}
            detail={`${sinistres.length} au total`}
            ton={sinistresActifs.length > 0 ? 'orange' : 'vert'}
          />
        </div>

        <h2 className="section-title">Assurances de la flotte</h2>
        {assurances.length === 0 ? (
          <p>Aucune assurance enregistrée.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Véhicule</th>
                  <th>Assureur</th>
                  <th>Police</th>
                  <th>Échéance</th>
                  <th>État</th>
                  <th>Renouveler jusqu&apos;au</th>
                </tr>
              </thead>
              <tbody>
                {assurances.map((assurance, i) => (
                  <tr key={assurance.id} className={etats[i].ton === 'rouge' ? 'row-danger' : ''}>
                    <td>{vehiculesParId[assurance.vehicule]?.immatriculation || assurance.vehicule}</td>
                    <td>{assurance.compagnie_assurance}</td>
                    <td>{assurance.numero_police}</td>
                    <td>{formatDate(assurance.date_echeance)}</td>
                    <td>
                      <Badge ton={etats[i].ton}>{etats[i].label}</Badge>
                    </td>
                    <td>
                      <div className="toolbar" style={{ margin: 0 }}>
                        <input
                          type="date"
                          aria-label={`Nouvelle échéance de la police ${assurance.numero_police}`}
                          value={datesRenouvellement[assurance.id] || ''}
                          onChange={(e) =>
                            setDatesRenouvellement({ ...datesRenouvellement, [assurance.id]: e.target.value })
                          }
                        />
                        <button
                          type="button"
                          className="button-small"
                          disabled={envoi || !datesRenouvellement[assurance.id]}
                          onClick={() => renouveler(assurance)}
                        >
                          Renouveler
                        </button>
                        <button
                          type="button"
                          className="button-small button-secondary"
                          disabled={envoi}
                          onClick={() => supprimer(`/assurances/${assurance.id}/`, `la police ${assurance.numero_police}`)}
                        >
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h2 className="section-title">Sinistres</h2>
        {sinistres.length === 0 ? (
          <p>Aucun sinistre enregistré.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Véhicule</th>
                  <th>Description</th>
                  <th>Incident lié</th>
                  <th>Statut</th>
                  <th>Dossier</th>
                </tr>
              </thead>
              <tbody>
                {sinistres.map((sinistre) => {
                  const incident = incidentsParId[sinistre.incident]
                  return (
                    <tr key={sinistre.id}>
                      <td>{formatDateHeure(sinistre.date)}</td>
                      <td>{vehiculesParId[sinistre.vehicule]?.immatriculation || '—'}</td>
                      <td>{sinistre.description}</td>
                      <td>
                        {incident
                          ? `#${incident.id} ${LABELS_TYPE_INCIDENT[incident.type_incident] || ''} — ${incident.chauffeur_nom}`
                          : '—'}
                      </td>
                      <td>
                        <Badge ton={TON_SINISTRE[sinistre.statut]}>{STATUTS_SINISTRE[sinistre.statut]}</Badge>
                        <br />
                        <select
                          aria-label={`Statut du sinistre ${sinistre.id}`}
                          value={sinistre.statut}
                          disabled={envoi}
                          onChange={(e) =>
                            agir(
                              () =>
                                apiFetch(`/sinistres/${sinistre.id}/`, {
                                  method: 'PATCH',
                                  body: { statut: e.target.value },
                                }),
                              `Sinistre #${sinistre.id} : statut mis à jour.`,
                            )
                          }
                        >
                          {Object.entries(STATUTS_SINISTRE).map(([valeur, label]) => (
                            <option key={valeur} value={valeur}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button-secondary button-small"
                          aria-label={`Dossier du sinistre ${sinistre.id}`}
                          onClick={() => setSinistreOuvert(sinistreOuvert === sinistre.id ? null : sinistre.id)}
                        >
                          {sinistreOuvert === sinistre.id ? 'Fermer' : `Pièces (${sinistre.pieces_total})`}
                        </button>
                        {/* Un dossier qui a des pièces jointes se garde : le supprimer effacerait aussi ses pièces. */}
                        {sinistre.pieces_total === 0 && (
                          <>
                            {' '}
                            <button
                              type="button"
                              className="button-secondary button-small"
                              disabled={envoi}
                              onClick={() => supprimer(`/sinistres/${sinistre.id}/`, `le sinistre n° ${sinistre.id}`)}
                            >
                              Supprimer
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {sinistreOuvert && sinistres.find((s) => s.id === sinistreOuvert) && (
          <DossierSinistre key={sinistreOuvert} sinistre={sinistres.find((s) => s.id === sinistreOuvert)} onChange={recharger} />
        )}

        <h2 className="section-title">Enregistrer une assurance</h2>
        <section className="card">
          <form onSubmit={creerAssurance}>
            <div className="form-grid">
              <label>
                Véhicule
                <select
                  value={nouvelleAssurance.vehicule}
                  onChange={(e) => setNouvelleAssurance({ ...nouvelleAssurance, vehicule: e.target.value })}
                  required
                >
                  <option value="">— Choisir —</option>
                  {vehicules.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.immatriculation}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Assureur
                <input
                  value={nouvelleAssurance.compagnie_assurance}
                  onChange={(e) => setNouvelleAssurance({ ...nouvelleAssurance, compagnie_assurance: e.target.value })}
                  required
                />
              </label>
              <label>
                N° de police
                <input
                  value={nouvelleAssurance.numero_police}
                  onChange={(e) => setNouvelleAssurance({ ...nouvelleAssurance, numero_police: e.target.value })}
                  required
                />
              </label>
              <label>
                Échéance
                <input
                  type="date"
                  value={nouvelleAssurance.date_echeance}
                  onChange={(e) => setNouvelleAssurance({ ...nouvelleAssurance, date_echeance: e.target.value })}
                  required
                />
              </label>
            </div>
            <div className="button-row">
              <button type="submit" disabled={envoi}>
                Enregistrer
              </button>
            </div>
          </form>
        </section>

        <h2 className="section-title">Déclarer un sinistre</h2>
        <section className="card">
          <form onSubmit={creerSinistre}>
            <div className="form-grid">
              <label>
                Véhicule
                <select
                  value={nouveauSinistre.vehicule}
                  onChange={(e) => setNouveauSinistre({ ...nouveauSinistre, vehicule: e.target.value })}
                >
                  <option value="">— Aucun —</option>
                  {vehicules.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.immatriculation}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Incident déclaré (optionnel)
                <select
                  value={nouveauSinistre.incident}
                  onChange={(e) => setNouveauSinistre({ ...nouveauSinistre, incident: e.target.value })}
                >
                  <option value="">— Aucun —</option>
                  {incidentsRecents.map((i) => (
                    <option key={i.id} value={i.id}>
                      #{i.id} {LABELS_TYPE_INCIDENT[i.type_incident]} — {formatDateHeure(i.date)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {nouveauSinistre.incident ? 'Description (reprise de l’incident si vide)' : 'Description'}
                <input
                  value={nouveauSinistre.description}
                  onChange={(e) => setNouveauSinistre({ ...nouveauSinistre, description: e.target.value })}
                  required={!nouveauSinistre.incident}
                />
              </label>
            </div>
            <div className="button-row">
              <button type="submit" disabled={envoi}>
                Déclarer
              </button>
            </div>
          </form>
        </section>

        <h2 className="section-title">Conformité réglementaire de la flotte (partagée avec le QHSE)</h2>
        <TableauConformite />
        </>
      )}

      {onglet === 'litiges' && <LitigesSociaux />}
      {onglet === 'modeles' && <ModelesJuridiquesGestion />}
      {onglet === 'synthese' && <ReportingJuridique />}
      {onglet === 'tutelle' && <EchangesTutelle />}
    </Layout>
  )
}
