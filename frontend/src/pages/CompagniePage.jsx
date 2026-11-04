import { useEffect, useState } from 'react'
import { apiEnvoyer, apiFetch, apiImage } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Layout from '../components/Layout.jsx'
import { etatEcheance } from '../lib/format.js'

const IDENTITE = [
  { champ: 'name', libelle: 'Raison sociale', requis: true, max: 255 },
  { champ: 'sigle', libelle: 'Sigle', max: 20 },
  { champ: 'headquarters_city', libelle: 'Ville du siège', requis: true, max: 255 },
  { champ: 'created_at', libelle: 'Date de création', type: 'date', requis: true },
  { champ: 'adresse', libelle: 'Adresse', max: 255 },
  { champ: 'telephone', libelle: 'Téléphone du service client', type: 'tel', max: 30 },
  { champ: 'email', libelle: 'Courriel', type: 'email', max: 254 },
]
const MENTIONS = [
  { champ: 'rccm', libelle: 'RCCM', max: 60 },
  { champ: 'compte_contribuable', libelle: 'Compte contribuable', max: 30 },
  { champ: 'autorisation_numero', libelle: "N° d'autorisation d'exercer", max: 60 },
  { champ: 'autorisation_echeance', libelle: "Échéance de l'autorisation", type: 'date' },
]

function Champ({ definition, valeurs, setValeurs }) {
  const { champ, libelle, type = 'text', requis = false, max } = definition
  return (
    <label>
      {libelle}
      <input
        type={type}
        value={valeurs[champ] ?? ''}
        onChange={(event) => setValeurs({ ...valeurs, [champ]: event.target.value })}
        required={requis}
        maxLength={max}
      />
    </label>
  )
}

/** Le formulaire de la fiche, initialisé une fois avec ce que renvoie le serveur. */
function Fiche({ fiche, onEnregistre }) {
  const [valeurs, setValeurs] = useState(fiche)
  const { agir, envoi, message } = useActions(onEnregistre)
  const autorisation = etatEcheance(fiche.autorisation_echeance)

  function enregistrer(event) {
    event.preventDefault()
    const corps = Object.fromEntries([...IDENTITE, ...MENTIONS].map(({ champ }) => [champ, valeurs[champ] ?? '']))
    corps.autorisation_echeance = valeurs.autorisation_echeance || null
    agir(() => apiFetch('/compagnie/', { method: 'PATCH', body: corps }), 'Fiche de la compagnie enregistrée.')
  }

  return (
    <form onSubmit={enregistrer}>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <section className="card">
        <h2>Identité et coordonnées</h2>
        <div className="form-grid">
          {IDENTITE.map((definition) => (
            <Champ key={definition.champ} definition={definition} valeurs={valeurs} setValeurs={setValeurs} />
          ))}
        </div>
      </section>
      <section className="card">
        <h2>Mentions légales</h2>
        <p className="muted">
          Reprises sur les billets, reçus et exports. L&apos;échéance de l&apos;autorisation d&apos;exercer (décret n° 2015-269) est
          seulement rappelée ici.
          {autorisation && (
            <>
              {' '}
              Autorisation : <Badge ton={autorisation.ton}>{autorisation.libelle}</Badge>
            </>
          )}
        </p>
        <div className="form-grid">
          {MENTIONS.map((definition) => (
            <Champ key={definition.champ} definition={definition} valeurs={valeurs} setValeurs={setValeurs} />
          ))}
        </div>
      </section>
      <div className="fiche-actions">
        <button type="submit" disabled={envoi}>
          Enregistrer la fiche
        </button>
      </div>
    </form>
  )
}

/** Le logo : aperçu (récupéré avec le jeton, jamais par un lien public), envoi d'une image PNG ou JPEG, retrait. */
function Logo({ aUnLogo, version, onChange }) {
  const [apercu, setApercu] = useState(null)
  const [fichier, setFichier] = useState(null)
  const { agir, envoi, message } = useActions(onChange)

  useEffect(() => {
    if (!aUnLogo) return undefined
    let adresse = null
    let abandonne = false
    apiImage('/compagnie/logo/')
      .then((url) => {
        if (abandonne) URL.revokeObjectURL(url)
        else {
          adresse = url
          setApercu(url)
        }
      })
      .catch(() => setApercu(null))
    return () => {
      abandonne = true
      if (adresse) URL.revokeObjectURL(adresse)
    }
  }, [aUnLogo, version])

  async function envoyer(event) {
    event.preventDefault()
    const donnees = new FormData()
    donnees.append('fichier', fichier)
    if (await agir(() => apiEnvoyer('/compagnie/logo/', donnees), 'Logo enregistré.')) {
      setFichier(null)
      event.target.reset()
    }
  }

  const retirer = () => {
    if (!window.confirm('Retirer le logo de la compagnie ?')) return
    agir(() => apiFetch('/compagnie/logo/retirer/', { method: 'POST' }), 'Logo retiré.')
  }

  return (
    <section className="card">
      <h2>Logo</h2>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {aUnLogo && apercu ? <img className="logo-apercu" src={apercu} alt="Logo de la compagnie" /> : <p className="muted">Aucun logo.</p>}
      <form className="toolbar" onSubmit={envoyer}>
        <label>
          Image PNG ou JPEG (1 Mo au plus)
          <input type="file" accept="image/png,image/jpeg" onChange={(e) => setFichier(e.target.files[0] || null)} required />
        </label>
        <button type="submit" disabled={envoi || !fichier}>
          {aUnLogo ? 'Remplacer le logo' : 'Envoyer le logo'}
        </button>
        {aUnLogo && (
          <button type="button" className="button-secondary" disabled={envoi} onClick={retirer}>
            Retirer le logo
          </button>
        )}
      </form>
    </section>
  )
}

/**
 * « Ma compagnie » : l'identité, les coordonnées, les mentions légales et le logo de la compagnie, tenus par le PDG sans passer
 * par l'administration. Tout est facultatif sauf la raison sociale, la ville du siège et la date de création.
 */
export default function CompagniePage() {
  const [version, setVersion] = useState(0)
  const { data: fiche, error, loading, recharger } = useChargement(() => apiFetch('/compagnie/'))
  const apresLogo = async () => {
    await recharger()
    setVersion((v) => v + 1)
  }

  return (
    <Layout title="Ma compagnie">
      <Alert>{error}</Alert>
      {loading && <p>Chargement…</p>}
      {fiche && (
        <>
          <Fiche key={fiche.id} fiche={fiche} onEnregistre={recharger} />
          <Logo aUnLogo={fiche.a_un_logo} version={version} onChange={apresLogo} />
        </>
      )}
    </Layout>
  )
}
