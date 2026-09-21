import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Jauge from '../components/Jauge.jsx'

const MODES_PAIEMENT = [
  { value: 'especes', label: 'Espèces' },
  { value: 'mobile_money', label: 'Mobile money' },
]

export default function GuichetierDashboard() {
  const [departs, setDeparts] = useState([])
  const [lignes, setLignes] = useState([])
  const [vehicules, setVehicules] = useState([])
  const [loadError, setLoadError] = useState('')

  const [departId, setDepartId] = useState('')
  const [passagerNom, setPassagerNom] = useState('')
  const [passagerTelephone, setPassagerTelephone] = useState('')
  const [prix, setPrix] = useState('')
  const [modePaiement, setModePaiement] = useState('especes')
  const [formError, setFormError] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function chargerDonnees() {
    return Promise.all([apiFetch('/departs/'), apiFetch('/lignes/'), apiFetch('/vehicules/')]).then(
      ([departsData, lignesData, vehiculesData]) => {
        setDeparts(departsData.filter((d) => d.statut !== 'termine'))
        setLignes(lignesData)
        setVehicules(vehiculesData)
      },
    )
  }

  useEffect(() => {
    chargerDonnees().catch((err) => setLoadError(err.message))
  }, [])

  const lignesParId = Object.fromEntries(lignes.map((l) => [l.id, l]))
  const vehiculesParId = Object.fromEntries(vehicules.map((v) => [v.id, v]))
  const departSelectionne = departs.find((d) => String(d.id) === departId)
  const vehiculeSelectionne = departSelectionne ? vehiculesParId[departSelectionne.vehicule] : null

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    setConfirmation('')
    setSubmitting(true)
    try {
      await apiFetch('/tickets/', {
        method: 'POST',
        body: {
          depart: Number(departId),
          passager_nom: passagerNom,
          passager_telephone: passagerTelephone,
          prix,
          mode_paiement: modePaiement,
        },
      })
      setConfirmation(`Ticket vendu à ${passagerNom}.`)
      setPassagerNom('')
      setPassagerTelephone('')
      setPrix('')
      await chargerDonnees()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout title="Tableau de bord — Guichetier">
      <Alert>{loadError}</Alert>
      <section className="card">
        <h2>Vente de ticket</h2>
        <form className="form" onSubmit={handleSubmit}>
          <label>
            Départ
            <select value={departId} onChange={(e) => setDepartId(e.target.value)} required>
              <option value="">— Choisir un départ —</option>
              {departs.map((depart) => (
                <option key={depart.id} value={depart.id}>
                  {lignesParId[depart.ligne]?.nom} — {new Date(depart.date_heure).toLocaleString('fr-FR')}
                </option>
              ))}
            </select>
          </label>

          {departSelectionne && (
            <Jauge
              vendues={departSelectionne.places_vendues}
              capacite={vehiculeSelectionne?.capacite}
              reservees={departSelectionne.places_reservees}
            />
          )}

          <label>
            Nom du passager
            <input
              type="text"
              value={passagerNom}
              onChange={(e) => setPassagerNom(e.target.value)}
              required
            />
          </label>
          <label>
            Téléphone du passager
            <input
              type="tel"
              value={passagerTelephone}
              onChange={(e) => setPassagerTelephone(e.target.value)}
              required
            />
          </label>
          <label>
            Prix (FCFA)
            <input
              type="number"
              min="0"
              step="1"
              value={prix}
              onChange={(e) => setPrix(e.target.value)}
              required
            />
          </label>
          <label>
            Mode de paiement
            <select value={modePaiement} onChange={(e) => setModePaiement(e.target.value)}>
              {MODES_PAIEMENT.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </select>
          </label>

          <Alert>{formError}</Alert>
          <Alert type="success">{confirmation}</Alert>

          <button type="submit" disabled={submitting || !departId}>
            {submitting ? 'Vente en cours…' : 'Vendre le ticket'}
          </button>
          <p className="muted">
            Une erreur de vente ? Un ticket vendu ne se modifie pas : demandez son annulation à votre chef de gare.
          </p>
        </form>
      </section>
    </Layout>
  )
}
