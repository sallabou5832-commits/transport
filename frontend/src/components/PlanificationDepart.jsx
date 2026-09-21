import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import Alert from './Alert.jsx'

/**
 * Planifie un départ et sa feuille de route en une seule opération. Une fois la date et l'heure choisies, seuls les
 * véhicules et chauffeurs libres à cette heure sont proposés (le serveur applique les mêmes règles à l'envoi).
 */
export default function PlanificationDepart({ lignes, onPlanifie }) {
  const [ligne, setLigne] = useState('')
  const [quand, setQuand] = useState('')
  const [vehicule, setVehicule] = useState('')
  const [chauffeur, setChauffeur] = useState('')
  const [dispo, setDispo] = useState(null)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  // L'heure saisie est celle du navigateur : on l'envoie en instant absolu, sans ambiguïté de fuseau.
  const heureIso = quand ? new Date(quand).toISOString() : ''

  useEffect(() => {
    if (!heureIso) return undefined
    let annule = false
    apiFetch(`/departs/disponibilites/?date_heure=${encodeURIComponent(heureIso)}`)
      .then((donnees) => {
        if (annule) return
        setDispo(donnees)
        // Un choix devenu indisponible à la nouvelle heure est retiré.
        setVehicule((v) => (donnees.vehicules.some((x) => String(x.id) === v) ? v : ''))
        setChauffeur((c) => (donnees.chauffeurs.some((x) => String(x.id) === c) ? c : ''))
      })
      .catch((err) => {
        if (!annule) setMessage({ type: 'error', texte: err.message })
      })
    return () => {
      annule = true
    }
  }, [heureIso])

  const propositions = heureIso ? dispo : null

  async function planifier(event) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch('/departs/planifier/', {
        method: 'POST',
        body: { ligne: Number(ligne), vehicule: Number(vehicule), chauffeur: Number(chauffeur), date_heure: heureIso },
      })
      setMessage({ type: 'success', texte: 'Départ planifié : la feuille de route du chauffeur est créée.' })
      setVehicule('')
      setChauffeur('')
      setQuand('')
      setDispo(null)
      if (onPlanifie) await onPlanifie()
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card">
      <h2>Planifier un départ</h2>
      <form onSubmit={planifier}>
        <div className="form-grid">
          <label>
            Ligne
            <select value={ligne} onChange={(e) => setLigne(e.target.value)} required>
              <option value="">— Choisir —</option>
              {lignes.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nom}
                </option>
              ))}
            </select>
          </label>
          <label>
            Date et heure de départ
            <input type="datetime-local" value={quand} onChange={(e) => setQuand(e.target.value)} required />
          </label>
          <label>
            Véhicule
            <select value={vehicule} onChange={(e) => setVehicule(e.target.value)} disabled={!propositions} required>
              <option value="">{propositions ? '— Choisir —' : 'Choisissez d’abord l’heure'}</option>
              {propositions?.vehicules.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.immatriculation} ({v.capacite} places)
                </option>
              ))}
            </select>
          </label>
          <label>
            Chauffeur
            <select value={chauffeur} onChange={(e) => setChauffeur(e.target.value)} disabled={!propositions} required>
              <option value="">{propositions ? '— Choisir —' : 'Choisissez d’abord l’heure'}</option>
              {propositions?.chauffeurs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nom}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="muted">
          Seuls les véhicules et chauffeurs libres à cette heure sont proposés : sans autre départ dans les 8 heures
          autour, et véhicule ni bloqué ni en maintenance.
        </p>
        {propositions && propositions.vehicules.length === 0 && (
          <Alert type="warning">Aucun véhicule libre à cette heure : pénurie à signaler au directeur des opérations.</Alert>
        )}
        {propositions && propositions.chauffeurs.length === 0 && (
          <Alert type="warning">Aucun chauffeur libre à cette heure.</Alert>
        )}
        <Alert type={message.type || 'error'}>{message.texte}</Alert>
        <div className="button-row">
          <button type="submit" disabled={envoi || !ligne || !vehicule || !chauffeur || !heureIso}>
            {envoi ? 'Planification…' : 'Planifier le départ'}
          </button>
        </div>
      </form>
    </section>
  )
}
