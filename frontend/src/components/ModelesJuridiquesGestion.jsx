import { useState } from 'react'
import { apiEnvoyer, apiFetch, apiTelecharger } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate } from '../lib/format.js'
import { CATEGORIES_MODELE, POLES, formatTaille } from '../lib/rh.js'

const VIDE = { titre: '', categorie: 'travail', description: '', contenu: '', poles: [], version: '1.0' }

/**
 * La bibliothèque de documents juridiques types, telle que le responsable juridique la tient : texte du modèle, fichier joint, pôles qui
 * peuvent le consulter (aucun coché : tous). Les autres pôles la consultent dans « Modèles juridiques ».
 */
export default function ModelesJuridiquesGestion() {
  const [formulaire, setFormulaire] = useState(VIDE)
  const [edition, setEdition] = useState(null)
  const { data, error, recharger } = useChargement(() => apiFetch('/modeles-juridiques/'))
  const { agir, envoi, message } = useActions(recharger)

  const champ = (nom) => ({ value: formulaire[nom], onChange: (e) => setFormulaire({ ...formulaire, [nom]: e.target.value }) })
  const basculerPole = (pole) =>
    setFormulaire({
      ...formulaire,
      poles: formulaire.poles.includes(pole) ? formulaire.poles.filter((p) => p !== pole) : [...formulaire.poles, pole],
    })

  async function enregistrer(event) {
    event.preventDefault()
    const requete = edition
      ? () => apiFetch(`/modeles-juridiques/${edition}/`, { method: 'PATCH', body: formulaire })
      : () => apiFetch('/modeles-juridiques/', { method: 'POST', body: formulaire })
    if (await agir(requete, `Modèle « ${formulaire.titre} » ${edition ? 'modifié' : 'publié'}.`)) {
      setFormulaire(VIDE)
      setEdition(null)
    }
  }

  function modifier(modele) {
    setEdition(modele.id)
    setFormulaire({
      titre: modele.titre, categorie: modele.categorie, description: modele.description, contenu: modele.contenu,
      poles: modele.poles, version: modele.version,
    })
  }

  const supprimer = (modele) => agir(() => apiFetch(`/modeles-juridiques/${modele.id}/`, { method: 'DELETE' }), `Modèle « ${modele.titre} » supprimé.`)
  const retirerFichier = (modele) => agir(() => apiFetch(`/modeles-juridiques/${modele.id}/retirer-fichier/`, { method: 'POST', body: {} }), 'Fichier retiré.')

  function joindre(modele, fichier) {
    if (!fichier) return
    const envoye = new FormData()
    envoye.append('fichier', fichier)
    agir(() => apiEnvoyer(`/modeles-juridiques/${modele.id}/fichier/`, envoye), `Fichier « ${fichier.name} » joint au modèle.`)
  }

  const telecharger = (modele) =>
    agir(() => apiTelecharger(`/modeles-juridiques/${modele.id}/telecharger/`, modele.nom_fichier))

  return (
    <section className="card">
      <h2>Bibliothèque de modèles de documents</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      {data &&
        (data.length === 0 ? (
          <p className="muted">Aucun modèle publié.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Modèle</th>
                  <th>Consultable par</th>
                  <th>Fichier</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <strong>{m.titre}</strong> <Badge>{m.categorie_libelle}</Badge>
                      <div className="muted">
                        Version {m.version} · modifié le {formatDate(m.modifie_le)}
                      </div>
                    </td>
                    <td>{m.poles_libelles.join(', ')}</td>
                    <td>
                      {m.a_un_fichier ? (
                        <>
                          {m.nom_fichier} ({formatTaille(m.taille)}){' '}
                          <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => telecharger(m)}>
                            Télécharger
                          </button>{' '}
                          <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirerFichier(m)}>
                            Retirer le fichier
                          </button>
                        </>
                      ) : (
                        <input
                          type="file"
                          aria-label={`Fichier du modèle ${m.titre}`}
                          accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
                          onChange={(e) => joindre(m, e.target.files[0])}
                        />
                      )}
                    </td>
                    <td>
                      <button type="button" className="button-secondary button-small" onClick={() => modifier(m)}>
                        Modifier
                      </button>{' '}
                      <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => supprimer(m)}>
                        Supprimer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      <h3>{edition ? 'Modifier le modèle' : 'Publier un modèle'}</h3>
      <form onSubmit={enregistrer}>
        <div className="form-grid">
          <label>
            Titre du modèle
            <input {...champ('titre')} required />
          </label>
          <label>
            Catégorie du modèle
            <select {...champ('categorie')}>
              {Object.entries(CATEGORIES_MODELE).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Version
            <input {...champ('version')} required />
          </label>
          <label>
            À quoi sert ce modèle
            <input {...champ('description')} />
          </label>
        </div>
        <label className="grand-champ">
          Texte du modèle
          <textarea rows={6} {...champ('contenu')} placeholder="Je soussigné [nom], atteste que…" required />
        </label>
        <fieldset className="cases">
          <legend>Pôles autorisés à le consulter (aucun coché : tous)</legend>
          {Object.entries(POLES).map(([pole, libelle]) => (
            <label key={pole}>
              <input type="checkbox" checked={formulaire.poles.includes(pole)} onChange={() => basculerPole(pole)} />
              {libelle}
            </label>
          ))}
        </fieldset>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            {edition ? 'Enregistrer les modifications' : 'Publier le modèle'}
          </button>
          {edition && (
            <button
              type="button"
              className="button-secondary"
              onClick={() => {
                setEdition(null)
                setFormulaire(VIDE)
              }}
            >
              Annuler la modification
            </button>
          )}
        </div>
      </form>
    </section>
  )
}
