import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import { formatDateHeure } from '../lib/format.js'

const VIDE = { vehicule: '', chauffeur: '' }

/**
 * Pouvoir d'intervention directe du PDG : réaffecter le véhicule ou le chauffeur d'un départ planifié (imprévu, panne, absence). Le
 * serveur ne propose que des véhicules et des chauffeurs réellement libres à cette heure et refuse un départ déjà parti.
 */
export default function ReaffectationDepart() {
  const [departId, setDepartId] = useState('')
  const [options, setOptions] = useState(null)
  const [choix, setChoix] = useState(VIDE)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(async () => {
    const [departs, lignes] = await Promise.all([apiFetch('/departs/'), apiFetch('/lignes/')])
    return { departs, lignes }
  })

  if (!data) return <Alert>{error}</Alert>

  const lignesParId = Object.fromEntries(data.lignes.map((l) => [l.id, l]))
  const departs = data.departs
    .filter((d) => d.statut === 'planifie')
    .sort((a, b) => new Date(a.date_heure) - new Date(b.date_heure))
  const depart = departs.find((d) => String(d.id) === departId)

  async function choisir(id) {
    setDepartId(id)
    setChoix(VIDE)
    setOptions(null)
    setMessage({ type: '', texte: '' })
    if (!id) return
    try {
      setOptions(await apiFetch(`/departs/${id}/remplacants-possibles/`))
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    }
  }

  async function reaffecter(event) {
    event.preventDefault()
    const corps = {}
    if (choix.vehicule) corps.vehicule = Number(choix.vehicule)
    if (choix.chauffeur) corps.chauffeur = Number(choix.chauffeur)
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch(`/departs/${departId}/`, { method: 'PATCH', body: corps })
      await recharger()
      await choisir('')
      setMessage({ type: 'success', texte: 'Départ réaffecté : la feuille de route suit le nouveau chauffeur.' })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card">
      <h2>Réaffecter un véhicule ou un chauffeur</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="toolbar">
        <label>
          Départ planifié
          <select value={departId} onChange={(e) => choisir(e.target.value)}>
            <option value="">— Choisir un départ —</option>
            {departs.map((d) => (
              <option key={d.id} value={d.id}>
                {lignesParId[d.ligne]?.nom} — {formatDateHeure(d.date_heure)} — {d.chauffeur_nom}
              </option>
            ))}
          </select>
        </label>
      </div>
      {depart && options && (
        <form onSubmit={reaffecter}>
          <div className="form-grid">
            <label>
              Nouveau véhicule
              <select value={choix.vehicule} onChange={(e) => setChoix({ ...choix, vehicule: e.target.value })}>
                <option value="">— inchangé —</option>
                {options.vehicules.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.immatriculation} ({v.capacite} places)
                  </option>
                ))}
              </select>
            </label>
            <label>
              Nouveau chauffeur
              <select value={choix.chauffeur} onChange={(e) => setChoix({ ...choix, chauffeur: e.target.value })}>
                <option value="">— inchangé —</option>
                {options.chauffeurs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nom}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {options.vehicules.length === 0 && <Alert type="warning">Aucun véhicule libre pour ce créneau.</Alert>}
          <div className="button-row">
            <button type="submit" disabled={envoi || (!choix.vehicule && !choix.chauffeur)}>
              Réaffecter
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
