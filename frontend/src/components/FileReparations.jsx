import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

const URGENCES = { critique: 'Critique', haute: 'Haute', normale: 'Normale', basse: 'Basse' }
const TON_URGENCE = { critique: 'rouge', haute: 'orange', normale: 'neutre', basse: 'bleu' }
const STATUTS = { ouvert: 'Ouvert', en_cours: 'En cours' }

function DelaiEstime({ ordre, envoi, onEnregistrer }) {
  const [heures, setHeures] = useState('')
  return (
    <form
      className="ligne-fermeture"
      onSubmit={(event) => {
        event.preventDefault()
        onEnregistrer(ordre, { delai_estime_heures: Number(heures) }).then((ok) => ok && setHeures(''))
      }}
    >
      <input
        type="number"
        min="1"
        aria-label={`Délai estimé en heures de l'ordre ${ordre.id}`}
        placeholder={ordre.delai_estime_heures ? `${ordre.delai_estime_heures} h` : 'heures'}
        value={heures}
        onChange={(e) => setHeures(e.target.value)}
      />
      <button type="submit" className="button-secondary button-small" disabled={envoi || !heures}>
        OK
      </button>
    </form>
  )
}

/**
 * La file d'attente de l'atelier : les réparations à faire, la plus urgente d'abord. Le directeur technique et le chef d'atelier
 * fixent l'urgence et le délai estimé (qui remonte au régulateur), réordonnent les ordres de même urgence et répartissent les
 * interventions entre les mécaniciens en voyant la charge de chacun.
 */
export default function FileReparations({ onChange }) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)
  const { data, error, recharger } = useChargement(
    async () => {
      const [file, charge] = await Promise.all([apiFetch('/ordres-reparation/file-attente/'), apiFetch('/maintenance/charge-mecaniciens/')])
      return { file, charge }
    },
    { intervalleMs: 60000 },
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

  const prioriser = (ordre, corps) =>
    agir(() => apiFetch(`/ordres-reparation/${ordre.id}/prioriser/`, { method: 'POST', body: corps }), `Ordre ${ordre.id} mis à jour.`)

  const reaffecter = (ordre, mecanicien) =>
    agir(
      () => apiFetch(`/ordres-reparation/${ordre.id}/reaffecter/`, { method: 'POST', body: { mecanicien: Number(mecanicien) } }),
      `Ordre ${ordre.id} confié : l'intervenant est prévenu.`,
    )

  function deplacer(index, sens) {
    const ordre = data.file.map((o) => o.id)
    const cible = index + sens
    ;[ordre[index], ordre[cible]] = [ordre[cible], ordre[index]]
    return agir(
      () => apiFetch('/ordres-reparation/reordonner/', { method: 'POST', body: { ordres: ordre } }),
      "Ordre de la file enregistré (à urgence égale, la position prime sur l'ancienneté).",
    )
  }

  if (!data) return <Alert>{error}</Alert>
  const { file, charge } = data

  return (
    <section className="card">
      <h2>File d&apos;attente de l&apos;atelier</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {file.length === 0 ? (
        <p className="muted">Aucune réparation en attente.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Urgence</th>
                <th>Véhicule</th>
                <th>Description</th>
                <th>Intervenant</th>
                <th>Délai estimé</th>
                <th>Ordre</th>
              </tr>
            </thead>
            <tbody>
              {file.map((ordre, index) => (
                <tr key={ordre.id} className={ordre.urgence === 'critique' ? 'row-danger' : ''}>
                  <td>{index + 1}</td>
                  <td>
                    <select
                      aria-label={`Urgence de l'ordre ${ordre.id}`}
                      value={ordre.urgence}
                      disabled={envoi}
                      onChange={(e) => prioriser(ordre, { urgence: e.target.value })}
                    >
                      {Object.entries(URGENCES).map(([valeur, libelle]) => (
                        <option key={valeur} value={valeur}>
                          {libelle}
                        </option>
                      ))}
                    </select>
                    <div>
                      <Badge ton={TON_URGENCE[ordre.urgence]}>{URGENCES[ordre.urgence]}</Badge>
                    </div>
                  </td>
                  <td>
                    {ordre.vehicule_immatriculation}
                    <div className="muted">
                      {ordre.retour_estime ? `Retour prévu ${formatDateHeure(ordre.retour_estime)}` : 'Retour non estimé'}
                    </div>
                  </td>
                  <td>
                    {ordre.description}
                    <div className="muted">
                      {STATUTS[ordre.statut]}
                      {ordre.plan_entretien ? ' · entretien préventif' : ''}
                    </div>
                  </td>
                  <td>
                    <select
                      aria-label={`Intervenant de l'ordre ${ordre.id}`}
                      value={ordre.mecanicien}
                      disabled={envoi}
                      onChange={(e) => reaffecter(ordre, e.target.value)}
                    >
                      {charge.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nom} ({c.ordres_ouverts + c.ordres_en_cours})
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <DelaiEstime ordre={ordre} envoi={envoi} onEnregistrer={prioriser} />
                  </td>
                  <td className="button-row">
                    <button
                      type="button"
                      className="button-secondary button-small"
                      aria-label={`Monter l'ordre ${ordre.id}`}
                      disabled={envoi || index === 0}
                      onClick={() => deplacer(index, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="button-secondary button-small"
                      aria-label={`Descendre l'ordre ${ordre.id}`}
                      disabled={envoi || index === file.length - 1}
                      onClick={() => deplacer(index, 1)}
                    >
                      ↓
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 style={{ marginTop: '1rem' }}>Charge de l&apos;atelier</h2>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Intervenant</th>
              <th>Ordres ouverts</th>
              <th>En cours</th>
              <th>Heures estimées</th>
              <th>Clôturés (7 j)</th>
            </tr>
          </thead>
          <tbody>
            {charge.map((c) => (
              <tr key={c.id}>
                <td>
                  {c.nom} {c.suggere && <Badge ton="vert">Suggéré pour le prochain ordre</Badge>}
                </td>
                <td>{c.ordres_ouverts}</td>
                <td>{c.ordres_en_cours}</td>
                <td>{c.heures_estimees} h</td>
                <td>{c.cloturees_7_jours}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
