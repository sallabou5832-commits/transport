import { useState } from 'react'
import { apiFetch, apiTelecharger } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate } from '../lib/format.js'
import { CATEGORIES_MODELE, formatTaille } from '../lib/rh.js'

/**
 * La bibliothèque de documents juridiques types, ouverte à tous les pôles : chaque poste voit les modèles que le responsable juridique a
 * ouverts à son pôle (ou à tous). On y lit le texte, on le copie pour le reprendre, on télécharge le fichier du modèle.
 */
export default function BibliothequeModeles() {
  const [recherche, setRecherche] = useState('')
  const [categorie, setCategorie] = useState('')
  const [ouvert, setOuvert] = useState(null)
  const [retour, setRetour] = useState({ type: '', texte: '' })
  const parametres = new URLSearchParams({ q: recherche, categorie }).toString()
  const { data, error } = useChargement(() => apiFetch(`/modeles-juridiques/?${parametres}`), { cle: parametres })

  async function copier(modele) {
    try {
      await navigator.clipboard.writeText(modele.contenu)
      setRetour({ type: 'success', texte: `Texte de « ${modele.titre} » copié.` })
    } catch {
      setRetour({ type: 'error', texte: 'Copie impossible : sélectionnez le texte et copiez-le.' })
    }
  }

  async function telecharger(modele) {
    setRetour({ type: '', texte: '' })
    try {
      await apiTelecharger(`/modeles-juridiques/${modele.id}/telecharger/`, modele.nom_fichier)
    } catch (err) {
      setRetour({ type: 'error', texte: err.message })
    }
  }

  return (
    <section className="card">
      <h2>Modèles de documents juridiques</h2>
      <div className="toolbar">
        <label>
          Rechercher un modèle
          <input type="search" placeholder="Attestation, constat, contrat…" value={recherche} onChange={(e) => setRecherche(e.target.value)} />
        </label>
        <label>
          Catégorie
          <select value={categorie} onChange={(e) => setCategorie(e.target.value)}>
            <option value="">Toutes</option>
            {Object.entries(CATEGORIES_MODELE).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Alert>{error}</Alert>
      <Alert type={retour.type || 'error'}>{retour.texte}</Alert>
      {data &&
        (data.length === 0 ? (
          <p className="muted">Aucun modèle ne correspond.</p>
        ) : (
          data.map((modele) => (
            <article key={modele.id} className="card">
              <h3>
                {modele.titre} <Badge>{modele.categorie_libelle}</Badge>
              </h3>
              <p className="muted">
                Version {modele.version} · mis à jour le {formatDate(modele.modifie_le)} par {modele.auteur_nom}
              </p>
              {modele.description && <p>{modele.description}</p>}
              <div className="button-row">
                <button type="button" className="button-secondary button-small" onClick={() => setOuvert(ouvert === modele.id ? null : modele.id)}>
                  {ouvert === modele.id ? 'Masquer le texte' : 'Lire le texte'}
                </button>
                <button type="button" className="button-secondary button-small" onClick={() => copier(modele)}>
                  Copier le texte
                </button>
                {modele.a_un_fichier && (
                  <button type="button" className="button-secondary button-small" onClick={() => telecharger(modele)}>
                    Télécharger le fichier ({formatTaille(modele.taille)})
                  </button>
                )}
              </div>
              {ouvert === modele.id && <pre className="texte-pre">{modele.contenu}</pre>}
            </article>
          ))
        ))}
    </section>
  )
}
