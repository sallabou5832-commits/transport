import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate } from '../lib/format.js'

function EtatLigne({ ligne }) {
  if (!ligne.est_fermee) return <Badge ton="vert">Ouverte</Badge>
  return (
    <>
      <Badge ton="rouge">Fermée{ligne.fermee_jusqu_au ? ` jusqu'au ${formatDate(ligne.fermee_jusqu_au)}` : ''}</Badge>
      {ligne.motif_fermeture && <div className="muted">{ligne.motif_fermeture}</div>}
    </>
  )
}

function ActionLigne({ ligne, envoi, onEnvoyer }) {
  const [motif, setMotif] = useState('')
  const [jusquAu, setJusquAu] = useState('')
  const fermee = ligne.est_fermee

  async function soumettre(event) {
    event.preventDefault()
    const ok = await onEnvoyer(ligne, {
      action: fermee ? 'rouvrir' : 'fermer',
      motif,
      ...(!fermee && jusquAu ? { jusqu_au: jusquAu } : {}),
    })
    if (ok) {
      setMotif('')
      setJusquAu('')
    }
  }

  return (
    <form onSubmit={soumettre} className="ligne-fermeture">
      <input
        aria-label={`Motif ${fermee ? 'de la réouverture' : 'de la fermeture'} de ${ligne.nom}`}
        placeholder="Motif"
        value={motif}
        onChange={(e) => setMotif(e.target.value)}
        required
      />
      {!fermee && (
        <input
          type="date"
          aria-label={`Dernier jour de fermeture de ${ligne.nom}`}
          value={jusquAu}
          min={new Date().toISOString().slice(0, 10)}
          onChange={(e) => setJusquAu(e.target.value)}
        />
      )}
      <button type="submit" disabled={envoi} className={fermee ? '' : 'button-danger'}>
        {fermee ? 'Rouvrir' : 'Fermer'}
      </button>
    </form>
  )
}

/**
 * Fermer ou rouvrir une ligne : le directeur des opérations valide les fermetures temporaires, le PDG « gèle » une ligne.
 * Une ligne fermée n'accepte plus ni départ planifié ni vente de billet ; elle se rouvre d'elle-même après le dernier jour.
 */
export default function LignesFermeture({ titre = 'Ouverture des lignes', onChange, version = 0 }) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  // `version` change quand un autre bloc de la page modifie une ligne (validation d'une demande) : on recharge alors aussi.
  const { data: lignes, error, recharger } = useChargement(() => apiFetch('/lignes/'), { cle: version })

  async function envoyer(ligne, corps) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      await apiFetch(`/lignes/${ligne.id}/changement/`, { method: 'POST', body: corps })
      await recharger()
      if (onChange) await onChange()
      setMessage({
        type: 'success',
        texte:
          corps.action === 'fermer'
            ? `Ligne ${ligne.nom} fermée : les chefs de gare, la régulation et la direction sont prévenus.`
            : `Ligne ${ligne.nom} rouverte.`,
      })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <section className="card">
      <h2>{titre}</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {!lignes ? (
        <p>Chargement…</p>
      ) : lignes.length === 0 ? (
        <p>Aucune ligne.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Ligne</th>
                <th>État</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((ligne) => (
                <tr key={ligne.id} className={ligne.est_fermee ? 'row-danger' : ''}>
                  <td>{ligne.nom}</td>
                  <td>
                    <EtatLigne ligne={ligne} />
                  </td>
                  <td>
                    <ActionLigne ligne={ligne} envoi={envoi} onEnvoyer={envoyer} />
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
