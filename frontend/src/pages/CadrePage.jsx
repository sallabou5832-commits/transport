import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'

/** Le cadre de la compagnie : les plafonds qu’aucun poste ne dépasse, fixés par le PDG. */
export default function CadrePage() {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  // Le choix en cours d'envoi, affiché tout de suite (sans attendre la réponse du serveur) ; un refus rend la valeur enregistrée.
  const [attente, setAttente] = useState({})

  const { data, error, loading, recharger } = useChargement(async () => {
    const [cadre, catalogue, reglement] = await Promise.all([
      apiFetch('/configuration/compagnie/'),
      apiFetch('/configuration/catalogue/'),
      apiFetch('/configuration/reglement/'),
    ])
    return { cadre, catalogue, reglement }
  })

  async function confierLesComptes(permis) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    setAttente({ drh_gere_les_comptes: permis })
    try {
      await apiFetch('/configuration/reglement/', { method: 'PATCH', body: { drh_gere_les_comptes: permis } })
      await recharger()
      setMessage({
        type: 'success',
        texte: permis ? 'Le DRH gère désormais aussi les comptes du personnel.' : 'La gestion des comptes est de nouveau réservée au PDG.',
      })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
      setAttente({})
    }
  }

  async function changer(champ, valeur) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    setAttente({ [champ]: valeur })
    try {
      await apiFetch('/configuration/compagnie/', { method: 'PATCH', body: { [champ]: valeur } })
      await recharger()
      setMessage({ type: 'success', texte: 'Cadre mis à jour : les postes déjà réglés au-dessus sont ramenés à ces plafonds.' })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnvoi(false)
      setAttente({})
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

  const { cadre: enregistre, catalogue, reglement } = data
  const cadre = { ...enregistre, ...attente }
  const drhGereLesComptes =
    attente.drh_gere_les_comptes ?? reglement.find((regle) => regle.code === 'drh_gere_les_comptes')?.permis ?? false

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
      <section className="card">
        <h2>Accès aux comptes</h2>
        <div className="form-grid">
          <label>
            Session la plus longue (« rester connecté »)
            <select value={cadre.duree_session_max} disabled={envoi} onChange={(e) => changer('duree_session_max', e.target.value)}>
              {catalogue.durees_session.map((d) => (
                <option key={d.valeur} value={d.valeur}>
                  {d.libelle}
                </option>
              ))}
            </select>
          </label>
          <label className="checkbox-ligne">
            <input
              type="checkbox"
              checked={cadre.code_court_exige}
              disabled={envoi}
              onChange={(e) => changer('code_court_exige', e.target.checked)}
            />
            Exiger un code court pour rouvrir l&apos;application mobile
          </label>
          <label className="checkbox-ligne">
            <input
              type="checkbox"
              checked={drhGereLesComptes}
              disabled={envoi}
              onChange={(e) => confierLesComptes(e.target.checked)}
            />
            Le DRH crée et modifie aussi les comptes du personnel (sinon, le PDG seul)
          </label>
        </div>
        <p className="muted">
          Chacun choisit à la connexion de rester connecté ou non, sans dépasser cette durée ; abaissée, elle ferme au prochain
          renouvellement les sessions ouvertes depuis plus longtemps. Un supérieur peut la réduire pour un poste (un guichet
          partagé, par exemple) dans la configuration. Sans code court exigé, chaque agent choisit d&apos;en avoir un ou non.
        </p>
      </section>
    </Layout>
  )
}
