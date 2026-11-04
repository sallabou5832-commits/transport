import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatFCFA } from '../lib/format.js'

const STATUTS = {
  enregistre: { libelle: 'Enregistré', ton: 'bleu' },
  charge: { libelle: 'Chargé', ton: 'orange' },
  arrive: { libelle: 'Arrivé', ton: 'vert' },
}
const MOTIF_MIN = 5

function Ligne({ colis, gare, envoi, agir }) {
  const [motif, setMotif] = useState('')
  const part = colis.gare_depart === gare.id
  const annulable = ['enregistre', 'charge'].includes(colis.statut)
  const aMarquerArrive = colis.statut === 'charge' && colis.depart_statut === 'termine'

  function annuler() {
    if (!window.confirm(`Annuler l'enregistrement du colis ${colis.reference} ? Les frais (${formatFCFA(colis.frais)}) sont à rendre.`)) return
    agir(() => apiFetch(`/colis/${colis.id}/annuler/`, { method: 'POST', body: { motif } }), `Colis ${colis.reference} annulé.`)
  }

  return (
    <tr>
      <td>
        <strong>{colis.reference}</strong>
        <div className="muted">{colis.description}</div>
      </td>
      <td>
        {colis.depart_libelle}
        <div className="muted">{part ? `Part vers ${colis.gare_arrivee_nom}` : `Arrive de ${colis.gare_depart_nom}`}</div>
      </td>
      <td>
        {colis.destinataire_nom}
        <div className="muted">{colis.destinataire_telephone}</div>
      </td>
      <td>
        <Badge ton={STATUTS[colis.statut]?.ton}>{STATUTS[colis.statut]?.libelle || colis.statut}</Badge>{' '}
        {colis.code_verrouille && <Badge ton="rouge">Code verrouillé</Badge>}
      </td>
      <td>
        <div className="button-row">
          <button
            type="button"
            className="button-small"
            disabled={envoi}
            onClick={() =>
              agir(
                () => apiFetch(`/colis/${colis.id}/renvoyer-code/`, { method: 'POST' }),
                `Nouveau code envoyé au destinataire du colis ${colis.reference}.`,
              )
            }
          >
            Renvoyer le code
          </button>
          {aMarquerArrive && (
            <button
              type="button"
              className="button-small button-secondary"
              disabled={envoi}
              onClick={() => agir(() => apiFetch(`/colis/${colis.id}/arriver/`, { method: 'POST' }), `Colis ${colis.reference} arrivé.`)}
            >
              Marquer arrivé
            </button>
          )}
        </div>
        {annulable && (
          <div className="toolbar" style={{ margin: '0.4rem 0 0' }}>
            <input
              aria-label={`Motif d'annulation du colis ${colis.reference}`}
              placeholder="Motif de l'annulation"
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
            />
            <button type="button" className="button-small button-secondary" disabled={envoi || motif.trim().length < MOTIF_MIN} onClick={annuler}>
              Annuler l&apos;enregistrement
            </button>
          </div>
        )}
      </td>
    </tr>
  )
}

/**
 * Les colis qui partent de la gare ou y arrivent, tant qu'ils ne sont ni retirés ni annulés : le chef de gare renvoie un code de
 * retrait (SMS perdu, colis verrouillé après trop de codes faux), annule un enregistrement (motif obligatoire, frais à rendre) et
 * marque arrivé un colis resté « chargé » alors que le car est arrivé.
 */
export default function ColisDeLaGare({ gare }) {
  const { data: colis, error, recharger } = useChargement(
    () => apiFetch(`/colis/?gare=${gare.id}&statut=enregistre,charge,arrive`),
    { intervalleMs: 60000, cle: gare.id },
  )
  const { agir, envoi, message } = useActions(recharger)

  return (
    <section className="card">
      <h2>Colis de la gare</h2>
      <p className="muted">
        Ceux qui partent d&apos;ici ou y arrivent, jusqu&apos;à leur retrait. Un colis verrouillé après trop de codes faux se
        débloque en renvoyant un code au destinataire.
      </p>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {!colis ? null : colis.length === 0 ? (
        <p>Aucun colis en cours.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Colis</th>
                <th>Départ</th>
                <th>Destinataire</th>
                <th>État</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {colis.map((c) => (
                <Ligne key={c.id} colis={c} gare={gare} envoi={envoi} agir={agir} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
