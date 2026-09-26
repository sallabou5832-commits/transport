import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate } from '../lib/format.js'

const VIDE = {
  vehicule: '', libelle: '', periodicite_jours: '', periodicite_km: '', duree_estimee_heures: '4', derniere_date: '', dernier_km: '', reglementaire: false,
}
const ETATS = { a_jour: { libelle: 'À jour', ton: 'vert' }, bientot: { libelle: 'Bientôt dû', ton: 'orange' }, en_retard: { libelle: 'En retard', ton: 'rouge' } }

function reste(echeance) {
  const morceaux = []
  if (echeance.jours_restants !== null) {
    morceaux.push(echeance.jours_restants >= 0 ? `${echeance.jours_restants} j` : `${-echeance.jours_restants} j de retard`)
  }
  if (echeance.km_restants !== null) {
    morceaux.push(echeance.km_restants >= 0 ? `${echeance.km_restants.toLocaleString('fr-FR')} km` : `${(-echeance.km_restants).toLocaleString('fr-FR')} km de dépassement`)
  }
  return morceaux.join(' / ')
}

function Kilometrage({ vehicule, envoi, onReleve }) {
  const [km, setKm] = useState('')
  return (
    <tr>
      <td>{vehicule.immatriculation}</td>
      <td>{vehicule.kilometrage.toLocaleString('fr-FR')} km</td>
      <td>
        <form
          className="ligne-fermeture"
          onSubmit={(event) => {
            event.preventDefault()
            onReleve(vehicule, km).then((ok) => ok && setKm(''))
          }}
        >
          <input
            type="number"
            min="0"
            aria-label={`Nouveau kilométrage de ${vehicule.immatriculation}`}
            placeholder="Nouveau relevé"
            value={km}
            onChange={(e) => setKm(e.target.value)}
          />
          <button type="submit" className="button-secondary button-small" disabled={envoi || km === ''}>
            Relever
          </button>
        </form>
      </td>
    </tr>
  )
}

/**
 * L'entretien préventif : les plans par échéance (les retards d'abord), leur déclaration (en jours et/ou en kilomètres) et le
 * relevé du kilométrage des véhicules. Quand une échéance approche, l'atelier est prévenu et l'ordre de réparation s'ouvre tout
 * seul (`manage.py generer_alertes`).
 */
export default function PlansEntretien({ onChange }) {
  const [formulaire, setFormulaire] = useState(VIDE)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(
    async () => {
      const [plans, vehicules] = await Promise.all([apiFetch('/plans-entretien/echeances/'), apiFetch('/vehicules/')])
      return { plans, vehicules }
    },
    { intervalleMs: 60000 },
  )

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      if (onChange) await onChange()
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  async function declarer(event) {
    event.preventDefault()
    const corps = {
      vehicule: Number(formulaire.vehicule),
      libelle: formulaire.libelle,
      duree_estimee_heures: Number(formulaire.duree_estimee_heures) || 4,
      reglementaire: formulaire.reglementaire,
    }
    for (const champ of ['periodicite_jours', 'periodicite_km', 'dernier_km']) {
      if (formulaire[champ] !== '') corps[champ] = Number(formulaire[champ])
    }
    if (formulaire.derniere_date) corps.derniere_date = formulaire.derniere_date
    if (await agir(() => apiFetch('/plans-entretien/', { method: 'POST', body: corps }), `Plan « ${formulaire.libelle} » déclaré.`)) {
      setFormulaire(VIDE)
    }
  }

  const releverKm = (vehicule, km) =>
    agir(
      () => apiFetch(`/vehicules/${vehicule.id}/`, { method: 'PATCH', body: { kilometrage: Number(km) } }),
      `Kilométrage de ${vehicule.immatriculation} relevé.`,
    )

  const fait = (plan) =>
    agir(() => apiFetch(`/plans-entretien/${plan.id}/realise/`, { method: 'POST', body: {} }), `Entretien « ${plan.libelle} » noté comme fait : le plan repart de zéro.`)

  if (!data) return <Alert>{error}</Alert>
  const { plans, vehicules } = data

  return (
    <section className="card">
      <h2>Entretien préventif</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {plans.length === 0 ? (
        <p className="muted">Aucun plan d&apos;entretien déclaré.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Véhicule</th>
                <th>Entretien</th>
                <th>Prochaine échéance</th>
                <th>Reste</th>
                <th>État</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => (
                <tr key={plan.id} className={plan.echeance.etat === 'en_retard' ? 'row-danger' : ''}>
                  <td>{plan.vehicule_immatriculation}</td>
                  <td>
                    {plan.libelle} {plan.reglementaire && <Badge ton="bleu">Réglementaire</Badge>}
                    <div className="muted">
                      {[plan.periodicite_jours && `tous les ${plan.periodicite_jours} j`, plan.periodicite_km && `tous les ${plan.periodicite_km.toLocaleString('fr-FR')} km`]
                        .filter(Boolean)
                        .join(' ou ')}
                    </div>
                  </td>
                  <td>
                    {plan.echeance.prochaine_date ? formatDate(plan.echeance.prochaine_date) : ''}
                    {plan.echeance.prochain_km ? ` ${plan.echeance.prochain_km.toLocaleString('fr-FR')} km` : ''}
                  </td>
                  <td>{reste(plan.echeance)}</td>
                  <td>
                    <Badge ton={ETATS[plan.echeance.etat].ton}>{ETATS[plan.echeance.etat].libelle}</Badge>
                  </td>
                  <td>
                    <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => fait(plan)}>
                      Fait
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 style={{ marginTop: '1rem' }}>Déclarer un plan d&apos;entretien</h2>
      <form onSubmit={declarer}>
        <div className="form-grid">
          <label>
            Véhicule du plan
            <select value={formulaire.vehicule} onChange={(e) => setFormulaire({ ...formulaire, vehicule: e.target.value })} required>
              <option value="">— Choisir —</option>
              {vehicules.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.immatriculation}
                </option>
              ))}
            </select>
          </label>
          <label>
            Entretien
            <input value={formulaire.libelle} onChange={(e) => setFormulaire({ ...formulaire, libelle: e.target.value })} placeholder="Vidange, contrôle technique…" required />
          </label>
          <label>
            Tous les (jours)
            <input type="number" min="1" value={formulaire.periodicite_jours} onChange={(e) => setFormulaire({ ...formulaire, periodicite_jours: e.target.value })} />
          </label>
          <label>
            Tous les (km)
            <input type="number" min="1" value={formulaire.periodicite_km} onChange={(e) => setFormulaire({ ...formulaire, periodicite_km: e.target.value })} />
          </label>
          <label>
            Durée estimée (heures)
            <input type="number" min="1" value={formulaire.duree_estimee_heures} onChange={(e) => setFormulaire({ ...formulaire, duree_estimee_heures: e.target.value })} />
          </label>
          <label>
            Dernier entretien (date)
            <input type="date" value={formulaire.derniere_date} onChange={(e) => setFormulaire({ ...formulaire, derniere_date: e.target.value })} />
          </label>
          <label>
            Kilométrage au dernier entretien
            <input type="number" min="0" value={formulaire.dernier_km} onChange={(e) => setFormulaire({ ...formulaire, dernier_km: e.target.value })} />
          </label>
          <label className="checkbox-ligne">
            <input type="checkbox" checked={formulaire.reglementaire} onChange={(e) => setFormulaire({ ...formulaire, reglementaire: e.target.checked })} />
            Obligation réglementaire (suivie au tableau de conformité)
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi || (!formulaire.periodicite_jours && !formulaire.periodicite_km)}>
            Déclarer le plan
          </button>
        </div>
      </form>

      <h2 style={{ marginTop: '1rem' }}>Kilométrage de la flotte</h2>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Véhicule</th>
              <th>Compteur</th>
              <th>Relevé</th>
            </tr>
          </thead>
          <tbody>
            {vehicules.map((vehicule) => (
              <Kilometrage key={vehicule.id} vehicule={vehicule} envoi={envoi} onReleve={releverKm} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
