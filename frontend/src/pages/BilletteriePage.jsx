import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import ImportVentes from '../components/ImportVentes.jsx'
import Layout from '../components/Layout.jsx'
import { formatDateHeure } from '../lib/format.js'

const EXPLICATIONS = {
  integre: 'Les guichets vendent avec cette application ; aucun autre logiciel ne lui envoie de ventes (comme avant).',
  externe: "Le logiciel de la compagnie vend seul : la vente au guichet est fermée, ses ventes arrivent par le lien ou l'import.",
  mixte: 'Les deux : les guichets vendent ici, et le logiciel de la compagnie envoie aussi ses ventes.',
}

/** « Mixte » pour « Mixte : les deux à la fois » : l'explication suit, plus précise. */
const nomCourt = (mode) => mode.libelle.split(' : ')[0]

function Mode({ reglage, apres }) {
  const { agir, envoi, message } = useActions(apres)
  // Le choix s'affiche aussitôt ; il revient à l'état du serveur si celui-ci le refuse.
  const [choisi, setChoisi] = useState(null)

  async function choisir(mode) {
    setChoisi(mode.valeur)
    await agir(
      () => apiFetch('/lien-billetterie/reglage/', { method: 'PATCH', body: { mode: mode.valeur } }),
      `Billetterie ${nomCourt(mode).toLowerCase()}.`,
    )
    setChoisi(null)
  }

  return (
    <section className="card">
      <h2>Mode de billetterie</h2>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {reglage.modes.map((mode) => (
        <label key={mode.valeur} className="checkbox-ligne">
          <input
            type="radio"
            name="mode-billetterie"
            checked={(choisi ?? reglage.mode) === mode.valeur}
            disabled={envoi || !reglage.modifiable}
            onChange={() => choisir(mode)}
          />
          <span>
            <strong>{nomCourt(mode)}</strong> — {EXPLICATIONS[mode.valeur]}
          </span>
        </label>
      ))}
    </section>
  )
}

function Cles({ cles, apres }) {
  const [logiciel, setLogiciel] = useState('')
  const [nouvelle, setNouvelle] = useState(null)
  const { agir, envoi, message } = useActions(apres)

  async function creer(event) {
    event.preventDefault()
    const ok = await agir(async () => {
      const cle = await apiFetch('/lien-billetterie/cles/', { method: 'POST', body: { logiciel } })
      setNouvelle(cle)
      return cle
    })
    if (ok) setLogiciel('')
  }

  function revoquer(cle) {
    if (!window.confirm(`Révoquer la clé de « ${cle.logiciel} » ? Ce logiciel ne pourra plus envoyer de ventes avec elle.`)) return
    agir(() => apiFetch(`/lien-billetterie/cles/${cle.id}/revoquer/`, { method: 'POST' }), `Clé de « ${cle.logiciel} » révoquée.`)
  }

  return (
    <section className="card">
      <h2>Clés du lien</h2>
      <p className="muted">
        Le logiciel de billetterie de la compagnie s&apos;identifie par une clé pour envoyer ses ventes et ses annulations. Une
        clé révoquée reste dans l&apos;historique.
      </p>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {nouvelle && (
        <div className="card card-highlight" role="status">
          <p>
            Clé de <strong>{nouvelle.logiciel}</strong> : <code>{nouvelle.cle}</code>
          </p>
          <p className="muted">Copiez-la maintenant dans le logiciel : elle ne sera plus affichée.</p>
          <button type="button" className="button-small" onClick={() => setNouvelle(null)}>
            C&apos;est noté
          </button>
        </div>
      )}
      <form className="toolbar" onSubmit={creer}>
        <label>
          Logiciel à relier
          <input value={logiciel} onChange={(e) => setLogiciel(e.target.value)} required minLength={2} />
        </label>
        <button type="submit" disabled={envoi}>
          Créer une clé
        </button>
      </form>
      {cles.length === 0 ? (
        <p>Aucune clé.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Logiciel</th>
                <th>Clé</th>
                <th>Créée</th>
                <th>Dernière utilisation</th>
                <th>État</th>
              </tr>
            </thead>
            <tbody>
              {cles.map((cle) => (
                <tr key={cle.id}>
                  <td>{cle.logiciel}</td>
                  <td>
                    <code>{cle.debut_cle}…</code>
                  </td>
                  <td>
                    {formatDateHeure(cle.creee_le)}
                    <div className="muted">{cle.creee_par_nom}</div>
                  </td>
                  <td>{cle.derniere_utilisation ? formatDateHeure(cle.derniere_utilisation) : 'Jamais'}</td>
                  <td>
                    {cle.active ? (
                      <button type="button" className="button-small button-secondary" disabled={envoi} onClick={() => revoquer(cle)}>
                        Révoquer
                      </button>
                    ) : (
                      <Badge>Révoquée le {formatDateHeure(cle.revoquee_le)}</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

/**
 * Le lien avec le logiciel de billetterie de la compagnie, sans l'administration Django : le mode de billetterie (intégrée,
 * externe ou mixte), les clés qui identifient le logiciel, et l'import d'un fichier de ventes. Le PDG et le directeur
 * d'exploitation ; le chef de gare importe les ventes de sa gare depuis son tableau de bord.
 */
export default function BilletteriePage() {
  const { data, error, loading, recharger } = useChargement(async () => {
    const [reglage, cles] = await Promise.all([apiFetch('/lien-billetterie/reglage/'), apiFetch('/lien-billetterie/cles/')])
    return { reglage, cles }
  })

  return (
    <Layout title="Billetterie">
      <Alert>{error}</Alert>
      {!data ? (
        loading && <p>Chargement…</p>
      ) : (
        <>
          <Mode reglage={data.reglage} apres={recharger} />
          {data.reglage.ventes_externes && <Cles cles={data.cles} apres={recharger} />}
          <ImportVentes key={data.reglage.mode} />
        </>
      )}
    </Layout>
  )
}
