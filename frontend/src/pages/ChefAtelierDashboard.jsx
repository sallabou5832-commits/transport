import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Layout from '../components/Layout.jsx'
import DemandePieceAtelier from '../components/DemandePieceAtelier.jsx'
import FicheVehicule from '../components/FicheVehicule.jsx'
import FileReparations from '../components/FileReparations.jsx'
import PlansEntretien from '../components/PlansEntretien.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import { LABELS_VEHICULE, TON_VEHICULE, formatDateHeure, indexParId } from '../lib/format.js'

const STATUT_LABELS = { ouvert: 'Ouvert', en_cours: 'En cours', termine: 'Terminé' }
const TON_STATUT = { ouvert: 'orange', en_cours: 'bleu', termine: 'vert' }

export default function ChefAtelierDashboard() {
  const { user } = useAuth()
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [nouveau, setNouveau] = useState({ vehicule: '', description: '' })
  const [minutes, setMinutes] = useState({})
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(async () => {
    const [ordres, vehicules] = await Promise.all([apiFetch('/ordres-reparation/'), apiFetch('/vehicules/')])
    return { ordres, vehicules }
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

  async function ouvrir(event) {
    event.preventDefault()
    // Le mécanicien responsable est celui qui ouvre l'ordre : l'API n'a pas d'annuaire d'agents à proposer.
    // Le serveur ne met en maintenance qu'un véhicule déjà bloqué pour raison de sécurité (PERMISSIONS.md §4).
    const etaitBloque = data.vehicules.find((v) => String(v.id) === nouveau.vehicule)?.statut === 'bloque_securite'
    const ok = await agir(
      () =>
        apiFetch('/ordres-reparation/', {
          method: 'POST',
          body: { vehicule: Number(nouveau.vehicule), description: nouveau.description, mecanicien: user.id },
        }),
      etaitBloque
        ? 'Ordre de réparation ouvert : le véhicule bloqué passe en maintenance.'
        : 'Ordre de réparation ouvert.',
    )
    if (ok) setNouveau({ vehicule: '', description: '' })
  }

  function demarrer(ordre) {
    return agir(
      () => apiFetch(`/ordres-reparation/${ordre.id}/`, { method: 'PATCH', body: { statut: 'en_cours' } }),
      `Intervention #${ordre.id} démarrée.`,
    )
  }

  function cloturer(ordre) {
    const temps = Number(minutes[ordre.id])
    return agir(
      () =>
        apiFetch(`/ordres-reparation/${ordre.id}/`, {
          method: 'PATCH',
          body: { statut: 'termine', temps_passe_minutes: temps },
        }),
      `Intervention #${ordre.id} clôturée : le véhicule est de nouveau disponible pour le régulateur.`,
    )
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — Chef d'atelier">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const vehiculesParId = indexParId(data.vehicules)
  const enCours = data.ordres.filter((o) => o.statut !== 'termine')
  const termines = data.ordres.filter((o) => o.statut === 'termine').slice(0, 5)

  return (
    <Layout title="Tableau de bord — Chef d'atelier">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <h2 className="section-title">Ordres de réparation en cours</h2>
      {enCours.length === 0 && !error && <p>Aucun ordre de réparation en cours.</p>}
      {enCours.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Véhicule</th>
                <th>Description</th>
                <th>Mécanicien</th>
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
                    <td>{ordre.mecanicien_nom}</td>
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
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section-title">Ouvrir un ordre de réparation</h2>
      <section className="card">
        <form onSubmit={ouvrir}>
          <div className="form-grid">
            <label>
              Véhicule
              <select value={nouveau.vehicule} onChange={(e) => setNouveau({ ...nouveau, vehicule: e.target.value })} required>
                <option value="">— Choisir —</option>
                {data.vehicules.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.immatriculation} — {LABELS_VEHICULE[v.statut]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Description de la panne
              <input value={nouveau.description} onChange={(e) => setNouveau({ ...nouveau, description: e.target.value })} required />
            </label>
          </div>
          <div className="button-row">
            <button type="submit" disabled={envoi}>
              Ouvrir l&apos;ordre
            </button>
          </div>
        </form>
      </section>

      {termines.length > 0 && (
        <>
          <h2 className="section-title">Dernières interventions clôturées</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Véhicule</th>
                  <th>Description</th>
                  <th>Clôturé le</th>
                  <th>Temps passé</th>
                </tr>
              </thead>
              <tbody>
                {termines.map((ordre) => (
                  <tr key={ordre.id}>
                    <td>{vehiculesParId[ordre.vehicule]?.immatriculation || ordre.vehicule}</td>
                    <td>{ordre.description}</td>
                    <td>{formatDateHeure(ordre.date_cloture)}</td>
                    <td>{ordre.temps_passe_minutes ? `${ordre.temps_passe_minutes} min` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2 className="section-title">Pilotage de l'atelier</h2>
      <FileReparations onChange={recharger} />
      <DemandePieceAtelier />
      <PlansEntretien onChange={recharger} />
      <FicheVehicule />
    </Layout>
  )
}
