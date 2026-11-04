import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatFCFA, isoAujourdhui } from '../lib/format.js'
import { etatEcheance } from '../lib/finance.js'

const MODES = { virement: 'Virement', cheque: 'Chèque', especes: 'Espèces', mobile_money: 'Mobile money' }
const TYPES = { fournisseur: 'Fournisseur', assurance: 'Assurance (prime)', autre: 'Autre' }
const STATUTS = { a_payer: 'À payer', payee: 'Payées', annulee: 'Annulées', '': 'Toutes' }
const FOURNISSEUR_VIDE = { nom: '', categorie: '', telephone: '' }
const factureVide = () => ({ fournisseur: '', type: 'fournisseur', reference: '', libelle: '', montant: '', date_emission: isoAujourdhui(0), echeance: isoAujourdhui(30) })

/**
 * Fournisseurs, assureurs et leurs factures : l'échéancier des paiements. Les rappels partent à 7 jours, à 1 jour et au retard
 * (`manage.py generer_alertes`). Régler une facture enregistre la dépense correspondante, sans ressaisie.
 */
export default function FacturesFournisseurs({ onChange }) {
  const [statut, setStatut] = useState('a_payer')
  const [mode, setMode] = useState('virement')
  const [fournisseur, setFournisseur] = useState(FOURNISSEUR_VIDE)
  const [facture, setFacture] = useState(factureVide)
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(
    async () => {
      const [fournisseurs, factures] = await Promise.all([apiFetch('/fournisseurs/'), apiFetch(`/factures/?statut=${statut}`)])
      return { fournisseurs, factures }
    },
    { cle: statut, intervalleMs: 60000 },
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

  async function ajouterFournisseur(event) {
    event.preventDefault()
    if (await agir(() => apiFetch('/fournisseurs/', { method: 'POST', body: fournisseur }), `Fournisseur « ${fournisseur.nom} » ajouté.`)) {
      setFournisseur(FOURNISSEUR_VIDE)
    }
  }

  async function enregistrer(event) {
    event.preventDefault()
    const corps = { ...facture, fournisseur: Number(facture.fournisseur) }
    if (await agir(() => apiFetch('/factures/', { method: 'POST', body: corps }), `Facture « ${facture.libelle} » enregistrée : elle figure à l'échéancier.`)) {
      setFacture({ ...factureVide(), fournisseur: facture.fournisseur, type: facture.type })
    }
  }

  const payer = (f) =>
    agir(() => apiFetch(`/factures/${f.id}/payer/`, { method: 'POST', body: { mode_paiement: mode } }), `Facture « ${f.libelle} » payée : la dépense est enregistrée.`)
  const annuler = (f) => agir(() => apiFetch(`/factures/${f.id}/annuler/`, { method: 'POST', body: {} }), `Facture « ${f.libelle} » annulée.`)
  const supprimer = (f) => agir(() => apiFetch(`/factures/${f.id}/`, { method: 'DELETE' }), `Facture « ${f.libelle} » supprimée.`)
  function retirerFournisseur(f) {
    // Un fournisseur qui a des factures se garde (le serveur refuse et dit pourquoi).
    if (!window.confirm(`Retirer « ${f.nom} » de la liste des fournisseurs ?`)) return
    agir(() => apiFetch(`/fournisseurs/${f.id}/`, { method: 'DELETE' }), `Fournisseur « ${f.nom} » retiré.`)
  }

  const champFacture = (nom) => ({ value: facture[nom], onChange: (e) => setFacture({ ...facture, [nom]: e.target.value }) })
  const champFournisseur = (nom) => ({ value: fournisseur[nom], onChange: (e) => setFournisseur({ ...fournisseur, [nom]: e.target.value }) })

  if (!data) return <Alert>{error}</Alert>

  return (
    <section className="card">
      <h2>Fournisseurs, assurances et factures</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <div className="toolbar no-print">
        <label>
          Afficher
          <select value={statut} onChange={(e) => setStatut(e.target.value)}>
            {Object.entries(STATUTS).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
        <label>
          Mode de règlement
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            {Object.entries(MODES).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </label>
      </div>

      {data.factures.length === 0 ? (
        <p className="muted">Aucune facture dans cette liste.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Fournisseur</th>
                <th>Objet</th>
                <th>Montant</th>
                <th>Échéance</th>
                <th>État</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.factures.map((f) => {
                const echeance = f.statut === 'a_payer' ? etatEcheance(f) : null
                return (
                  <tr key={f.id} className={f.en_retard ? 'row-danger' : ''}>
                    <td>
                      {f.fournisseur_nom}
                      <div className="muted">{f.type_libelle}</div>
                    </td>
                    <td>
                      {f.libelle}
                      {f.reference && <div className="muted">Réf. {f.reference}</div>}
                    </td>
                    <td className="montant">{formatFCFA(f.montant)}</td>
                    <td>{formatDate(f.echeance)}</td>
                    <td>
                      {echeance ? (
                        <Badge ton={echeance.ton}>{echeance.libelle}</Badge>
                      ) : f.statut === 'payee' ? (
                        <Badge ton="vert">Payée le {formatDate(f.payee_le)}</Badge>
                      ) : (
                        <Badge>Annulée</Badge>
                      )}
                    </td>
                    <td>
                      {f.statut === 'a_payer' && (
                        <div className="ligne-fermeture">
                          <button type="button" className="button-small" disabled={envoi} onClick={() => payer(f)}>
                            Payer
                          </button>
                          <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => annuler(f)}>
                            Annuler
                          </button>
                          <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => supprimer(f)}>
                            Supprimer
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="no-print">Enregistrer une facture ou une prime à payer</h3>
      <form onSubmit={enregistrer} className="no-print">
        <div className="form-grid">
          <label>
            Fournisseur ou assureur
            <select {...champFacture('fournisseur')} required>
              <option value="">— Choisir —</option>
              {data.fournisseurs.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.nom}
                </option>
              ))}
            </select>
          </label>
          <label>
            Nature
            <select {...champFacture('type')}>
              {Object.entries(TYPES).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Objet
            <input placeholder="Pièces de rechange, prime flotte…" {...champFacture('libelle')} required />
          </label>
          <label>
            Référence
            <input {...champFacture('reference')} />
          </label>
          <label>
            Montant (FCFA)
            <input type="number" min="1" step="1" {...champFacture('montant')} required />
          </label>
          <label>
            Émise le
            <input type="date" {...champFacture('date_emission')} required />
          </label>
          <label>
            À payer avant le
            <input type="date" {...champFacture('echeance')} required />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Enregistrer la facture
          </button>
        </div>
      </form>

      <h3 className="no-print">Ajouter un fournisseur ou un assureur</h3>
      <form onSubmit={ajouterFournisseur} className="no-print">
        <div className="form-grid">
          <label>
            Nom
            <input {...champFournisseur('nom')} required />
          </label>
          <label>
            Activité
            <input placeholder="Pièces, carburant, assurance…" {...champFournisseur('categorie')} />
          </label>
          <label>
            Téléphone
            <input {...champFournisseur('telephone')} />
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Ajouter le fournisseur
          </button>
        </div>
      </form>
      {data.fournisseurs.length > 0 && (
        <div className="table-wrap no-print">
          <table className="table">
            <thead>
              <tr>
                <th>Fournisseur</th>
                <th>Activité</th>
                <th>Téléphone</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {data.fournisseurs.map((f) => (
                <tr key={f.id}>
                  <td>{f.nom}</td>
                  <td>{f.categorie || '—'}</td>
                  <td>{f.telephone || '—'}</td>
                  <td>
                    <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => retirerFournisseur(f)}>
                      Retirer
                    </button>
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
