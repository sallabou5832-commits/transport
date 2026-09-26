import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { LABELS_VEHICULE } from '../lib/format.js'

const FORMULAIRE_VIDE = { vehicule: '', gare: '', motif: '' }

/**
 * Arbitrage des véhicules entre gares : pour chaque gare, les départs des prochaines 24 heures face aux véhicules disponibles
 * qui lui sont rattachés. Une gare en tension a besoin d'un renfort ; une gare qui a des véhicules en trop peut en prêter.
 */
export default function TensionGares({ gares, onChange, version = 0 }) {
  const [formulaire, setFormulaire] = useState(FORMULAIRE_VIDE)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data: vehicules, error, recharger } = useChargement(() => apiFetch('/vehicules/'), { cle: version })

  const garesParId = Object.fromEntries(gares.map((g) => [g.id, g]))
  const enTension = gares.filter((g) => g.en_tension)
  const preteuses = gares.filter((g) => g.tension < 0)

  async function rattacher(event) {
    event.preventDefault()
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      const vehicule = await apiFetch(`/vehicules/${formulaire.vehicule}/reaffecter-gare/`, {
        method: 'POST',
        body: { gare: Number(formulaire.gare), motif: formulaire.motif },
      })
      await recharger()
      if (onChange) await onChange()
      setFormulaire(FORMULAIRE_VIDE)
      setMessage({
        type: 'success',
        texte: `${vehicule.immatriculation} est rattaché à ${vehicule.gare_nom} : les chefs des deux gares sont prévenus.`,
      })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card">
      <h2>Gares en tension</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Gare</th>
              <th>Départs (24 h)</th>
              <th>Véhicules disponibles</th>
              <th>Rattachés</th>
              <th>Situation</th>
            </tr>
          </thead>
          <tbody>
            {gares.map((gare) => (
              <tr key={gare.id} className={gare.en_tension ? 'row-danger' : ''}>
                <td>{gare.nom}</td>
                <td>{gare.departs_24h}</td>
                <td>{gare.vehicules_disponibles}</td>
                <td>{gare.vehicules_attaches}</td>
                <td>
                  {gare.en_tension ? (
                    <Badge ton="rouge">Manque {gare.tension}</Badge>
                  ) : gare.tension < 0 ? (
                    <Badge ton="bleu">Peut prêter {-gare.tension}</Badge>
                  ) : (
                    <Badge ton="vert">Équilibrée</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {enTension.length > 0 && (
        <p className="muted">
          {enTension.map((g) => g.nom).join(', ')} : renfort nécessaire.{' '}
          {preteuses.length > 0
            ? `Peuvent prêter : ${preteuses.map((g) => `${g.nom} (${-g.tension})`).join(', ')}.`
            : "Aucune gare n'a de véhicule disponible en trop."}
        </p>
      )}

      <h2 style={{ marginTop: '1rem' }}>Rattacher un véhicule à une autre gare</h2>
      <form onSubmit={rattacher}>
        <div className="form-grid">
          <label>
            Véhicule
            <select value={formulaire.vehicule} onChange={(e) => setFormulaire({ ...formulaire, vehicule: e.target.value })} required>
              <option value="">— Choisir —</option>
              {(vehicules ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.immatriculation} — {v.gare ? garesParId[v.gare]?.nom ?? v.gare_nom : 'sans gare'} ({LABELS_VEHICULE[v.statut]})
                </option>
              ))}
            </select>
          </label>
          <label>
            Nouvelle gare d’attache
            <select value={formulaire.gare} onChange={(e) => setFormulaire({ ...formulaire, gare: e.target.value })} required>
              <option value="">— Choisir —</option>
              {gares.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.nom}
                </option>
              ))}
            </select>
          </label>
          <label>
            Motif du rattachement
            <input value={formulaire.motif} onChange={(e) => setFormulaire({ ...formulaire, motif: e.target.value })} required />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Rattacher le véhicule
          </button>
        </div>
      </form>
    </section>
  )
}
