import { Fragment, useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Jauge from '../components/Jauge.jsx'
import Kpi from '../components/Kpi.jsx'
import DemandeLigne from '../components/DemandeLigne.jsx'
import VehiculesAtelier from '../components/VehiculesAtelier.jsx'
import PlanificationDepart from '../components/PlanificationDepart.jsx'
import {
  LABELS_DEPART,
  LABELS_VEHICULE,
  TON_VEHICULE,
  estAujourdhui,
  formatDateHeure,
  formatHeure,
  indexParId,
} from '../lib/format.js'
import { retardMinutes, statutFeuille } from '../lib/ponctualite.js'

const VEHICULES_INDISPONIBLES = ['bloque_securite', 'en_maintenance']

function etatDepart(feuille, maintenant) {
  if (!feuille) return { ton: 'neutre', label: 'Sans feuille de route' }
  if (feuille.heure_arrivee_reelle) return { ton: 'vert', label: 'Arrivé' }
  const statut = statutFeuille(feuille, maintenant)
  if (feuille.heure_depart_reelle) {
    return statut === 'a_l_heure'
      ? { ton: 'vert', label: `Parti à ${formatHeure(feuille.heure_depart_reelle)}` }
      : { ton: 'orange', label: `Parti avec ${retardMinutes(feuille, maintenant)} min de retard` }
  }
  return statut === 'en_retard'
    ? { ton: 'rouge', label: `Non parti (+${retardMinutes(feuille, maintenant)} min)` }
    : { ton: 'neutre', label: 'En attente' }
}

export default function ChefLigneDashboard() {
  const [ligneId, setLigneId] = useState('')
  const [reaffectation, setReaffectation] = useState(null)
  const [message, setMessage] = useState({ type: '', texte: '' })

  const { data, error, loading, recharger } = useChargement(
    async () => {
      const [lignes, departs, vehicules, feuilles] = await Promise.all([
        apiFetch('/lignes/'),
        apiFetch('/departs/'),
        apiFetch('/vehicules/'),
        apiFetch('/feuilles-de-route/'),
      ])
      return { lignes, departs, vehicules, feuilles }
    },
    { intervalleMs: 60000 },
  )

  async function ouvrirReaffectation(depart) {
    setMessage({ type: '', texte: '' })
    setReaffectation({
      departId: depart.id,
      vendues: depart.places_vendues,
      chargement: true,
      options: null,
      vehicule: '',
      chauffeur: '',
      heure: '',
      erreur: '',
    })
    try {
      const options = await apiFetch(`/departs/${depart.id}/remplacants-possibles/`)
      setReaffectation((r) => ({ ...r, chargement: false, options }))
    } catch (err) {
      setReaffectation((r) => ({ ...r, chargement: false, erreur: err.message }))
    }
  }

  async function appliquer() {
    const corps = {}
    if (reaffectation.vehicule) corps.vehicule = Number(reaffectation.vehicule)
    if (reaffectation.chauffeur) corps.chauffeur = Number(reaffectation.chauffeur)
    if (reaffectation.heure) corps.date_heure = new Date(reaffectation.heure).toISOString()
    if (Object.keys(corps).length === 0) return
    try {
      await apiFetch(`/departs/${reaffectation.departId}/`, { method: 'PATCH', body: corps })
      setMessage({ type: 'success', texte: 'Départ réaffecté.' })
      setReaffectation(null)
      await recharger()
    } catch (err) {
      setReaffectation((r) => ({ ...r, erreur: err.message }))
    }
  }

  async function supprimer(depart) {
    // Correction d'une erreur de planning : le serveur refuse un départ qui a des tickets ou qui a démarré.
    if (!window.confirm('Supprimer ce départ planifié ? Sa feuille de route sera supprimée aussi.')) return
    setMessage({ type: '', texte: '' })
    try {
      await apiFetch(`/departs/${depart.id}/`, { method: 'DELETE' })
      setMessage({ type: 'success', texte: 'Départ supprimé.' })
      await recharger()
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    }
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — Chef de ligne">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { lignes, departs, vehicules, feuilles } = data
  const maintenant = new Date()
  const lignesParId = indexParId(lignes)
  const vehiculesParId = indexParId(vehicules)
  const feuillesParDepart = Object.fromEntries(feuilles.map((f) => [f.depart, f]))

  const departsLigne = departs.filter((d) => !ligneId || String(d.ligne) === ligneId)
  const departsDuJour = departsLigne.filter((d) => estAujourdhui(d.date_heure))
  const lignesAffichees = departsLigne
    .filter((d) => estAujourdhui(d.date_heure) || (new Date(d.date_heure) > maintenant && d.statut !== 'termine'))
    .sort((a, b) => new Date(a.date_heure) - new Date(b.date_heure))

  const feuillesDuJour = departsDuJour.map((d) => feuillesParDepart[d.id]).filter(Boolean)
  const arrives = feuillesDuJour.filter((f) => f.heure_arrivee_reelle).length
  const retardCumule = feuillesDuJour
    .filter((f) => statutFeuille(f, maintenant) === 'en_retard')
    .reduce((somme, f) => somme + retardMinutes(f, maintenant), 0)
  const enCirculation = departsDuJour.filter((d) => d.statut === 'en_cours').length
  const sansVehicule = lignesAffichees.filter(
    (d) =>
      d.statut === 'planifie' &&
      !feuillesParDepart[d.id]?.heure_depart_reelle &&
      VEHICULES_INDISPONIBLES.includes(vehiculesParId[d.vehicule]?.statut),
  )

  return (
    <Layout title="Tableau de bord — Chef de ligne">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <div className="toolbar">
        <label>
          Ligne
          <select value={ligneId} onChange={(e) => setLigneId(e.target.value)}>
            <option value="">Toutes les lignes</option>
            {lignes.map((ligne) => (
              <option key={ligne.id} value={ligne.id}>
                {ligne.nom}
              </option>
            ))}
          </select>
        </label>
        <span className="muted">Actualisé chaque minute.</span>
      </div>

      {sansVehicule.length > 0 && (
        <Alert type="warning">
          {sansVehicule.length} départ(s) prévu(s) avec un véhicule indisponible : réaffectation nécessaire.
        </Alert>
      )}

      <div className="cards-grid">
        <Kpi
          titre="Rotations effectuées"
          valeur={`${arrives} / ${departsDuJour.length}`}
          detail="départs du jour arrivés à destination"
        />
        <Kpi
          titre="Retard cumulé"
          valeur={`${retardCumule} min`}
          detail="sur les départs du jour en retard"
          ton={retardCumule > 0 ? 'orange' : 'vert'}
        />
        <Kpi
          titre="Cars en circulation"
          valeur={`${enCirculation} / ${departsDuJour.length}`}
          detail="en cours, sur les départs prévus aujourd'hui"
        />
        <Kpi
          titre="Véhicules indisponibles"
          valeur={sansVehicule.length}
          detail="sur des départs à venir"
          ton={sansVehicule.length > 0 ? 'rouge' : 'vert'}
        />
      </div>

      <h2 className="section-title">Départs du jour et à venir</h2>
      {lignesAffichees.length === 0 ? (
        <p>Aucun départ.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Heure</th>
                <th>Ligne</th>
                <th>Véhicule</th>
                <th>Chauffeur</th>
                <th>Remplissage</th>
                <th>État</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lignesAffichees.map((depart) => {
                const vehicule = vehiculesParId[depart.vehicule]
                const feuille = feuillesParDepart[depart.id]
                const etat = etatDepart(feuille, maintenant)
                const modifiable = depart.statut === 'planifie' && !feuille?.heure_depart_reelle
                const indisponible = VEHICULES_INDISPONIBLES.includes(vehicule?.statut)
                return (
                  <Fragment key={depart.id}>
                    <tr className={modifiable && indisponible ? 'row-danger' : ''}>
                      <td>
                        {formatDateHeure(depart.date_heure)}
                        <br />
                        <span className="muted">{LABELS_DEPART[depart.statut]}</span>
                      </td>
                      <td>{lignesParId[depart.ligne]?.nom}</td>
                      <td>
                        {vehicule?.immatriculation}
                        <br />
                        {vehicule && <Badge ton={TON_VEHICULE[vehicule.statut]}>{LABELS_VEHICULE[vehicule.statut]}</Badge>}
                      </td>
                      <td>{depart.chauffeur_nom}</td>
                      <td>
                        <Jauge
                          vendues={depart.places_vendues}
                          capacite={vehicule?.capacite}
                          reservees={depart.places_reservees}
                        />
                      </td>
                      <td>
                        <Badge ton={etat.ton}>{etat.label}</Badge>
                      </td>
                      <td>
                        {modifiable && (
                          <div className="button-row" style={{ margin: 0 }}>
                            <button
                              type="button"
                              className="button-secondary button-small"
                              onClick={() => ouvrirReaffectation(depart)}
                            >
                              Réaffecter
                            </button>
                            <button
                              type="button"
                              className="button-secondary button-small"
                              onClick={() => supprimer(depart)}
                            >
                              Supprimer
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {reaffectation?.departId === depart.id && (
                      <tr>
                        <td colSpan={7}>
                          <div className="reaffectation">
                            {reaffectation.chargement && <p>Recherche de remplaçants disponibles…</p>}
                            <Alert>{reaffectation.erreur}</Alert>
                            {reaffectation.options && (
                              <>
                                <p className="muted">
                                  Suggestions : véhicules disponibles assez grands et sans autre départ proche,
                                  chauffeurs libres. Laissez « inchangé » ce que vous ne remplacez pas.
                                </p>
                                <div className="form-grid">
                                  <label>
                                    Nouveau véhicule
                                    <select
                                      value={reaffectation.vehicule}
                                      onChange={(e) => setReaffectation({ ...reaffectation, vehicule: e.target.value })}
                                    >
                                      <option value="">— inchangé —</option>
                                      {reaffectation.options.vehicules.map((v) => (
                                        <option key={v.id} value={v.id}>
                                          {v.immatriculation} ({v.capacite} places)
                                        </option>
                                      ))}
                                    </select>
                                  </label>
                                  <label>
                                    Nouveau chauffeur
                                    <select
                                      value={reaffectation.chauffeur}
                                      onChange={(e) => setReaffectation({ ...reaffectation, chauffeur: e.target.value })}
                                    >
                                      <option value="">— inchangé —</option>
                                      {reaffectation.options.chauffeurs.map((c) => (
                                        <option key={c.id} value={c.id}>
                                          {c.nom}
                                        </option>
                                      ))}
                                    </select>
                                  </label>
                                  <label>
                                    Nouvelle heure (décaler le départ)
                                    <input
                                      type="datetime-local"
                                      value={reaffectation.heure}
                                      onChange={(e) => setReaffectation({ ...reaffectation, heure: e.target.value })}
                                    />
                                  </label>
                                </div>
                                {reaffectation.heure && reaffectation.vendues > 0 && (
                                  <Alert type="warning">
                                    {reaffectation.vendues} ticket(s) déjà vendu(s) pour l’heure actuelle : prévenez les
                                    voyageurs, aucun message n’est envoyé automatiquement.
                                  </Alert>
                                )}
                                {reaffectation.options.vehicules.length === 0 && (
                                  <Alert type="warning">
                                    Aucun véhicule disponible pour ce créneau : pénurie à signaler au directeur des
                                    opérations.
                                  </Alert>
                                )}
                              </>
                            )}
                            <div className="button-row">
                              <button
                                type="button"
                                disabled={!reaffectation.vehicule && !reaffectation.chauffeur && !reaffectation.heure}
                                onClick={appliquer}
                              >
                                Appliquer
                              </button>
                              <button type="button" className="button-secondary" onClick={() => setReaffectation(null)}>
                                Annuler
                              </button>
                            </div>
                          </div>
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

      <PlanificationDepart lignes={lignes} onPlanifie={recharger} />

      <h2 className="section-title">Véhicules à l'atelier</h2>
      <VehiculesAtelier />

      <h2 className="section-title">Fermer ou rouvrir une ligne</h2>
      <DemandeLigne />
    </Layout>
  )
}
