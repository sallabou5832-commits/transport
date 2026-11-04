import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Layout from '../components/Layout.jsx'
import { ROLE_LABELS } from '../auth/roles.js'

/**
 * Le règlement intérieur de la compagnie : ce qu'elle permet ou non à certains postes. Le PDG règle toutes les règles, chaque
 * directeur celles de son pôle ; une règle jamais réglée suit le défaut du socle (le comportement d'avant). Les écrans des postes
 * concernés n'affichent que les gestes permis, et le serveur refuse les autres.
 */
export default function ReglementPage() {
  const { data: regles, error, loading, recharger } = useChargement(() => apiFetch('/configuration/reglement/'))
  const [attente, setAttente] = useState({})
  const [message, setMessage] = useState({ type: '', texte: '' })

  async function regler(regle, permis) {
    setMessage({ type: '', texte: '' })
    setAttente((avant) => ({ ...avant, [regle.code]: permis }))
    try {
      await apiFetch('/configuration/reglement/', { method: 'PATCH', body: { [regle.code]: permis } })
      await recharger()
      setMessage({ type: 'success', texte: `${permis ? 'Permis' : 'Non permis'} : ${regle.libelle}.` })
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setAttente((avant) => {
        const reste = { ...avant }
        delete reste[regle.code]
        return reste
      })
    }
  }

  const modifiables = (regles || []).filter((regle) => regle.modifiable)

  return (
    <Layout title="Règlement intérieur">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {!regles ? (
        loading && <p>Chargement…</p>
      ) : (
        <section className="card">
          <p className="muted">
            Cochez ce que votre compagnie permet. Une règle jamais réglée garde le comportement d&apos;origine ; le serveur
            applique la règle, l&apos;écran de chaque poste ne propose que les gestes permis.
          </p>
          {modifiables.length === 0 ? (
            <p>Aucune règle ne relève de votre poste.</p>
          ) : (
            modifiables.map((regle) => {
              const permis = attente[regle.code] ?? regle.permis
              return (
                <label key={regle.code} className="checkbox-ligne">
                  <input
                    type="checkbox"
                    checked={permis}
                    disabled={regle.code in attente}
                    onChange={(e) => regler(regle, e.target.checked)}
                  />
                  <span>
                    {regle.libelle}{' '}
                    {regle.permis !== regle.defaut && <Badge ton="orange">Différent du défaut</Badge>}
                    <div className="muted">
                      Postes concernés : {regle.postes.map((poste) => ROLE_LABELS[poste] || poste).join(', ')} — décidé par :{' '}
                      {regle.pole === 'pdg' ? 'PDG' : `${ROLE_LABELS[regle.pole]} ou PDG`}
                    </div>
                  </span>
                </label>
              )
            })
          )}
        </section>
      )}
    </Layout>
  )
}
