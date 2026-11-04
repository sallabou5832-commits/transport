import { useState } from 'react'
import { apiEnvoyer, apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import { formatDateHeure } from '../lib/format.js'

/** Ce que l'import a fait de chaque ligne : les refus, avec leur raison, sont à corriger dans le logiciel puis à réimporter. */
function Rapport({ importation }) {
  const refus = (importation.rapport || []).filter((ligne) => ligne.statut === 'refusee')
  return (
    <div className="card card-highlight">
      <p>
        <strong>{importation.fichier}</strong> : {importation.lignes} ligne(s) — {importation.creees} vente(s) créée(s),{' '}
        {importation.deja_recues} déjà reçue(s), {importation.refusees} refusée(s).
      </p>
      {refus.length > 0 && (
        <ul>
          {refus.map((ligne) => (
            <li key={ligne.ligne}>
              Ligne {ligne.ligne} ({ligne.reference || 'sans référence'}) : {Object.values(ligne.erreurs || {}).flat().join(' ')}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Déposer le fichier de ventes exporté par le logiciel de billetterie de la compagnie (CSV ou Excel) : chaque ligne devient un
 * billet, comme une vente reçue par le lien ; réimporter le même fichier ne crée rien de plus. Le chef de gare n'importe que les
 * départs de sa gare. Fermé tant que la billetterie de la compagnie est intégrée.
 */
export default function ImportVentes() {
  const [logiciel, setLogiciel] = useState('')
  const [fichier, setFichier] = useState(null)
  const [dernier, setDernier] = useState(null)
  const { data, error, recharger } = useChargement(async () => {
    const [reglage, imports] = await Promise.all([apiFetch('/lien-billetterie/reglage/'), apiFetch('/lien-billetterie/imports/')])
    return { reglage, imports }
  })
  const { agir, envoi, message } = useActions(recharger)

  async function importer(event) {
    event.preventDefault()
    const corps = new FormData()
    corps.append('logiciel', logiciel)
    corps.append('fichier', fichier)
    const ok = await agir(async () => {
      const importation = await apiEnvoyer('/lien-billetterie/imports/', corps)
      setDernier(importation)
      return importation
    }, (importation) => `Import terminé : ${importation.creees} vente(s) créée(s).`)
    if (ok) {
      setFichier(null)
      event.target.reset()
    }
  }

  if (!data) return <Alert>{error}</Alert>
  const { reglage, imports } = data

  return (
    <section className="card">
      <h2>Importer les ventes du logiciel de billetterie</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {!reglage.ventes_externes ? (
        <p className="muted">
          La billetterie de la compagnie est intégrée : les ventes se font au guichet, il n&apos;y a rien à importer. Le PDG ou
          le directeur d&apos;exploitation peut passer en billetterie externe ou mixte.
        </p>
      ) : (
        <form className="form-grid" onSubmit={importer}>
          <label>
            Logiciel qui a produit le fichier
            <input value={logiciel} onChange={(e) => setLogiciel(e.target.value)} required minLength={2} />
          </label>
          <label>
            Fichier des ventes (CSV ou Excel)
            <input type="file" accept=".csv,.txt,.xlsx" onChange={(e) => setFichier(e.target.files[0] || null)} required />
          </label>
          <p className="muted">
            Colonnes attendues : référence du billet, passager, mode de paiement ; et le départ (son numéro, ou la ligne avec la
            date et l&apos;heure). Réimporter le même fichier ne crée rien de plus.
          </p>
          <button type="submit" disabled={envoi || !fichier}>
            Importer les ventes
          </button>
        </form>
      )}
      {dernier && <Rapport importation={dernier} />}
      {imports.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Déposé le</th>
                <th>Fichier</th>
                <th>Par</th>
                <th>Créées</th>
                <th>Déjà reçues</th>
                <th>Refusées</th>
              </tr>
            </thead>
            <tbody>
              {imports.slice(0, 10).map((importation) => (
                <tr key={importation.id}>
                  <td>{formatDateHeure(importation.depose_le)}</td>
                  <td>
                    {importation.fichier}
                    <div className="muted">{importation.logiciel}</div>
                  </td>
                  <td>{importation.depose_par_nom}</td>
                  <td>{importation.creees}</td>
                  <td>{importation.deja_recues}</td>
                  <td>{importation.refusees}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
