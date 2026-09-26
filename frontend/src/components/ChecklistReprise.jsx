import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import Alert from './Alert.jsx'
import { formatHeure } from '../lib/format.js'

const LIBELLES = {
  pneus: 'Pneus',
  freins: 'Freins',
  carburant: 'Carburant',
  eclairage: 'Éclairage',
  direction: 'Direction',
  ceintures: 'Ceintures',
}

/**
 * La checklist de reprise : le conducteur qui vient de reprendre le trajet constate l'état du car qu'on lui remet, item par item. Un
 * défaut prévient aussitôt la régulation et l'atelier ; s'il touche la sécurité, le QHSE et la direction des opérations aussi.
 * `reprise` vient de `/suivi/moi/` (relais, lieu, items, état transmis par l'ancien conducteur). Une fois validée, la checklist disparaît :
 * `onFait(confirmation)` laisse à la page le soin de recharger et d'afficher la confirmation.
 */
export default function ChecklistReprise({ reprise, onFait }) {
  const [etats, setEtats] = useState(() => Object.fromEntries(reprise.items.map((item) => [item, { etat: 'ok', commentaire: '' }])))
  const { agir, envoi, message } = useActions()
  const defauts = reprise.items.filter((item) => etats[item].etat === 'defaut')
  const transmis = reprise.etat_transmis || {}

  function changer(item, champs) {
    setEtats({ ...etats, [item]: { ...etats[item], ...champs } })
  }

  async function valider(event) {
    event.preventDefault()
    const items = reprise.items.map((item) => ({ item, etat: etats[item].etat, commentaire: etats[item].commentaire }))
    const enregistree = await agir(() => apiFetch(`/relais/${reprise.relais}/reprise/`, { method: 'POST', body: { items } }))
    if (enregistree) {
      await onFait(
        defauts.length > 0
          ? 'Checklist enregistrée : les défauts constatés sont signalés à la régulation et à l’atelier.'
          : 'Checklist de reprise enregistrée : bonne route.',
      )
    }
  }

  return (
    <section className="detail-panneau card" aria-label="Checklist de reprise">
      <h3>Checklist de reprise</h3>
      <p className="muted">
        Vous avez repris le trajet à {reprise.lieu} à {formatHeure(reprise.effectue_le)}. Constatez l&apos;état du car avant de repartir.
      </p>
      {((transmis.defauts_checklist || []).length > 0 || (transmis.incidents_ouverts || []).length > 0) && (
        <Alert type="warning">
          Signalé par le conducteur précédent :{' '}
          {[
            (transmis.defauts_checklist || []).length > 0 && `défaut(s) de checklist (${transmis.defauts_checklist.join(', ')})`,
            (transmis.incidents_ouverts || []).length > 0 && `${transmis.incidents_ouverts.length} incident(s) ouvert(s)`,
          ]
            .filter(Boolean)
            .join(' ; ')}
          .
        </Alert>
      )}
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <form onSubmit={valider}>
        {reprise.items.map((item) => (
          <fieldset key={item} className="cases">
            <legend>{LIBELLES[item] || item}</legend>
            <label>
              <input type="radio" name={`reprise-${item}`} checked={etats[item].etat === 'ok'} onChange={() => changer(item, { etat: 'ok', commentaire: '' })} />
              OK
            </label>
            <label>
              <input type="radio" name={`reprise-${item}`} checked={etats[item].etat === 'defaut'} onChange={() => changer(item, { etat: 'defaut' })} />
              Défaut
            </label>
            {etats[item].etat === 'defaut' && (
              <input
                aria-label={`Défaut constaté : ${LIBELLES[item] || item}`}
                placeholder="Ce que vous constatez"
                value={etats[item].commentaire}
                onChange={(e) => changer(item, { commentaire: e.target.value })}
              />
            )}
          </fieldset>
        ))}
        <div className="button-row">
          <button type="submit" disabled={envoi}>
            Valider la reprise{defauts.length > 0 ? ` (${defauts.length} défaut${defauts.length > 1 ? 's' : ''})` : ''}
          </button>
        </div>
      </form>
    </section>
  )
}
