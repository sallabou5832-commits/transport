import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'

/**
 * Les fiches de poste : une par rôle de l'organigramme. Tant que le DRH ne l'a pas personnalisée, c'est la fiche type qui sert de base à
 * une offre de recrutement ; il peut l'adapter à sa compagnie, ou revenir à la fiche type.
 */
export default function FichesDePoste() {
  const [role, setRole] = useState('')
  const [brouillon, setBrouillon] = useState(null)
  const { data, error, recharger } = useChargement(() => apiFetch('/fiches-poste/'))
  const { agir, envoi, message } = useActions(recharger)

  const fiche = data?.find((f) => f.role === role)
  const courante = brouillon && brouillon.role === role ? brouillon : fiche

  function choisir(valeur) {
    setRole(valeur)
    setBrouillon(null)
  }

  const modifier = (nom, valeur) => setBrouillon({ ...courante, [nom]: valeur })

  async function enregistrer(event) {
    event.preventDefault()
    if (await agir(() => apiFetch('/fiches-poste/', { method: 'PUT', body: courante }), `Fiche « ${courante.intitule} » enregistrée.`)) {
      setBrouillon(null)
    }
  }

  async function reinitialiser() {
    if (await agir(() => apiFetch('/fiches-poste/reinitialiser/', { method: 'POST', body: { role } }), 'Fiche type rétablie.')) setBrouillon(null)
  }

  return (
    <section className="card">
      <h2>Fiches de poste</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {data && (
        <>
          <div className="toolbar">
            <label>
              Poste
              <select value={role} onChange={(e) => choisir(e.target.value)}>
                <option value="">— Choisir un poste —</option>
                {data.map((f) => (
                  <option key={f.role} value={f.role}>
                    {f.role_libelle}
                    {f.personnalisee ? ' (personnalisée)' : ''}
                  </option>
                ))}
              </select>
            </label>
            {courante && (
              <Badge ton={fiche.personnalisee ? 'bleu' : 'neutre'}>{fiche.personnalisee ? 'Fiche personnalisée' : 'Fiche type'}</Badge>
            )}
          </div>
          {courante && (
            <form onSubmit={enregistrer}>
              <label className="grand-champ">
                Intitulé du poste
                <input value={courante.intitule} onChange={(e) => modifier('intitule', e.target.value)} required />
              </label>
              <label className="grand-champ">
                Missions
                <textarea rows={5} value={courante.missions} onChange={(e) => modifier('missions', e.target.value)} required />
              </label>
              <label className="grand-champ">
                Profil recherché
                <textarea rows={4} value={courante.profil} onChange={(e) => modifier('profil', e.target.value)} required />
              </label>
              <label className="grand-champ">
                Conditions de travail
                <textarea rows={2} value={courante.conditions} onChange={(e) => modifier('conditions', e.target.value)} />
              </label>
              <div className="button-row">
                <button type="submit" disabled={envoi}>
                  Enregistrer la fiche
                </button>
                {fiche.personnalisee && (
                  <button type="button" className="button-secondary" disabled={envoi} onClick={reinitialiser}>
                    Revenir à la fiche type
                  </button>
                )}
              </div>
            </form>
          )}
        </>
      )}
    </section>
  )
}
