import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'

/** Le cadre de la compagnie : les plafonds qu’aucun poste ne dépasse, fixés par le PDG. */
export default function CadrePage() {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(async () => {
    const [cadre, catalogue] = await Promise.all([apiFetch('/configuration/compagnie/'), apiFetch('/configuration/catalogue/')])
    return { cadre, catalogue }
  })

  async function changer(champ, valeur) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch('/configuration/compagnie/', { method: 'PATCH', body: { [champ]: valeur } })
      await recharger()
      setMessage({ type: 'success', texte: 'Cadre mis à jour : les postes déjà réglés au-dessus sont ramenés à ces plafonds.' })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
    }
  }

  if (!data) {
    return (
      <Layout title="Cadre de la compagnie">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { cadre, catalogue } = data

  return (
    <Layout title="Cadre de la compagnie">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <p className="muted">
        Chaque échelon règle les postes placés directement sous lui, mais jamais au-delà de ces plafonds : c&apos;est le cadre
        fixé par la compagnie.
      </p>
      <section className="card">
        <div className="form-grid">
          <label>
            Automatisation maximale
            <select value={cadre.automatisation_max} disabled={envoi} onChange={(e) => changer('automatisation_max', e.target.value)}>
              {catalogue.niveaux_automatisation.map((n) => (
                <option key={n.valeur} value={n.valeur}>
                  {n.libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Gamification maximale
            <select value={cadre.gamification_max} disabled={envoi} onChange={(e) => changer('gamification_max', e.target.value)}>
              {catalogue.niveaux_gamification.map((n) => (
                <option key={n.valeur} value={n.valeur}>
                  {n.libelle}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>
    </Layout>
  )
}
