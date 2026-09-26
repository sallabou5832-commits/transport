import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatFCFA, isoAujourdhui } from '../lib/format.js'
import { CATEGORIES_DEPENSE, dernierJourDuMois, jourDuMois, moisCourant } from '../lib/finance.js'

const vide = () => ({ date: isoAujourdhui(0), categorie: 'carburant', libelle: '', montant: '', ligne: '', vehicule: '', gare: '' })

/**
 * Les dépenses de la compagnie : saisie (carburant, maintenance, salaires…) et liste du mois. Une dépense rattachée à une ligne, à
 * un véhicule ou à une gare se compare aux recettes (rentabilité) ; une dépense de carburant compte dans le budget de sa ligne.
 * Les factures payées y apparaissent d'elles-mêmes : `version` recharge la liste quand un paiement se fait ailleurs sur la page.
 */
export default function DepensesFinance({ onChange, version = 0 }) {
  const [formulaire, setFormulaire] = useState(vide)
  const [mois, setMois] = useState(moisCourant())
  const [categorie, setCategorie] = useState('')
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  // Sans mois choisi, tout l'historique.
  const debut = mois ? jourDuMois(mois) : ''
  const fin = mois ? dernierJourDuMois(0, new Date(`${mois}-15T12:00:00`)) : ''
  const { data, error, recharger } = useChargement(
    async () => {
      const [depenses, lignes, vehicules, gares] = await Promise.all([
        apiFetch(`/depenses/?date_debut=${debut}&date_fin=${fin}`),
        apiFetch('/lignes/'),
        apiFetch('/vehicules/'),
        apiFetch('/gares/'),
      ])
      return { depenses, lignes, vehicules, gares }
    },
    { cle: `${debut}|${fin}|${version}` },
  )

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await requete()
      await recharger()
      if (onChange) await onChange()
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  async function saisir(event) {
    event.preventDefault()
    const corps = { date: formulaire.date, categorie: formulaire.categorie, libelle: formulaire.libelle, montant: formulaire.montant }
    for (const champ of ['ligne', 'vehicule', 'gare']) {
      if (formulaire[champ]) corps[champ] = Number(formulaire[champ])
    }
    if (await agir(() => apiFetch('/depenses/', { method: 'POST', body: corps }), `Dépense « ${formulaire.libelle} » enregistrée.`)) {
      setFormulaire({ ...vide(), date: formulaire.date, categorie: formulaire.categorie })
    }
  }

  const supprimer = (depense) => agir(() => apiFetch(`/depenses/${depense.id}/`, { method: 'DELETE' }), `Dépense « ${depense.libelle} » supprimée.`)

  const champ = (nom) => ({ value: formulaire[nom], onChange: (e) => setFormulaire({ ...formulaire, [nom]: e.target.value }) })

  if (!data) return <Alert>{error}</Alert>
  const visibles = data.depenses.filter((depense) => !categorie || depense.categorie === categorie)
  const total = visibles.reduce((somme, depense) => somme + Number(depense.montant), 0)

  return (
    <section className="card">
      <h2>Dépenses</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <form onSubmit={saisir} className="no-print">
        <div className="form-grid">
          <label>
            Date
            <input type="date" max={isoAujourdhui(0)} {...champ('date')} required />
          </label>
          <label>
            Catégorie
            <select {...champ('categorie')}>
              {Object.entries(CATEGORIES_DEPENSE).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Libellé
            <input placeholder="Plein de la semaine, salaires de septembre…" {...champ('libelle')} required />
          </label>
          <label>
            Montant (FCFA)
            <input type="number" min="1" step="1" {...champ('montant')} required />
          </label>
          <label>
            Ligne concernée
            <select {...champ('ligne')}>
              <option value="">— Aucune —</option>
              {data.lignes.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nom}
                </option>
              ))}
            </select>
          </label>
          <label>
            Véhicule concerné
            <select {...champ('vehicule')}>
              <option value="">— Aucun —</option>
              {data.vehicules.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.immatriculation}
                </option>
              ))}
            </select>
          </label>
          <label>
            Gare concernée
            <select {...champ('gare')}>
              <option value="">— Aucune —</option>
              {data.gares.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.nom}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Enregistrer la dépense
          </button>
        </div>
      </form>

      <div className="toolbar no-print">
        <label>
          Mois
          <input type="month" value={mois} onChange={(e) => setMois(e.target.value)} />
        </label>
        <label>
          Catégorie affichée
          <select value={categorie} onChange={(e) => setCategorie(e.target.value)}>
            <option value="">Toutes</option>
            {Object.entries(CATEGORIES_DEPENSE).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
      </div>

      {visibles.length === 0 ? (
        <p className="muted">Aucune dépense sur ce mois.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Catégorie</th>
                <th>Libellé</th>
                <th>Rattachée à</th>
                <th>Montant</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visibles.map((depense) => (
                <tr key={depense.id}>
                  <td>{formatDate(depense.date)}</td>
                  <td>
                    <Badge>{depense.categorie_libelle}</Badge>
                  </td>
                  <td>{depense.libelle}</td>
                  <td>{[depense.ligne_nom, depense.vehicule_immatriculation, depense.gare_nom].filter(Boolean).join(' · ') || '—'}</td>
                  <td className="montant">{formatFCFA(depense.montant)}</td>
                  <td>
                    <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => supprimer(depense)}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th colSpan={4}>Total affiché</th>
                <th colSpan={2} className="montant">{formatFCFA(total)}</th>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  )
}
