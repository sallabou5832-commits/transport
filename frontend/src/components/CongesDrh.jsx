import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatDateHeure } from '../lib/format.js'
import { NIVEAUX_IMPACT } from '../lib/rh.js'

/** L'effet d'un congé sur le personnel disponible : le niveau, les collègues déjà absents, les départs à réaffecter, jour par jour. */
function Impact({ impact }) {
  const niveau = NIVEAUX_IMPACT[impact.niveau]
  return (
    <div>
      <p>
        <Badge ton={niveau.ton}>Impact {niveau.libelle.toLowerCase()}</Badge>{' '}
        <span className="muted">
          {impact.effectif} agent(s) sur ce poste
          {impact.jours_critiques > 0 && ` · ${impact.jours_critiques} jour(s) critique(s)`}
          {impact.jours_tendus > 0 && ` · ${impact.jours_tendus} jour(s) tendu(s)`}
        </span>
      </p>
      <div aria-label="Jour par jour">
        {impact.jours.map((jour) => (
          <span
            key={jour.date}
            className={`impact-jour impact-${jour.niveau}`}
            title={`${formatDate(jour.date)} : ${jour.disponibles_apres} disponible(s) après ce congé${jour.besoin === null ? '' : `, ${jour.besoin} départ(s) au programme`}`}
          >
            {jour.date.slice(8)}
          </span>
        ))}
      </div>
      {impact.collegues_en_conge.length > 0 && (
        <p className="muted">
          Déjà absents : {impact.collegues_en_conge.map((c) => `${c.agent_nom} (${formatDate(c.debut)} – ${formatDate(c.fin)})`).join(', ')}.
        </p>
      )}
      {impact.departs_a_reaffecter.length > 0 && (
        <p>
          <strong>Départs à réaffecter :</strong>{' '}
          {impact.departs_a_reaffecter.map((d) => `${d.ligne} le ${formatDateHeure(d.date_heure)}`).join(' ; ')}.
        </p>
      )}
    </div>
  )
}

/**
 * Les congés à valider et à venir, tels que le DRH les traite : pour chaque demande, l'effet sur le personnel disponible s'affiche avant la
 * décision. Un impact critique, ou des départs déjà confiés au demandeur, demandent une confirmation explicite.
 */
export default function CongesDrh() {
  const [motifs, setMotifs] = useState({})
  const [confirmation, setConfirmation] = useState(null)
  const { data, error, recharger } = useChargement(
    async () => {
      const [attente, approuves] = await Promise.all([apiFetch('/conges/?statut=en_attente'), apiFetch('/conges/?statut=approuve')])
      const impacts = await Promise.all(attente.map((demande) => apiFetch(`/conges/${demande.id}/impact/`)))
      return { attente, approuves, impacts: Object.fromEntries(attente.map((demande, i) => [demande.id, impacts[i]])) }
    },
    { intervalleMs: 60000 },
  )
  const { agir, envoi, message, setMessage } = useActions(recharger)

  async function approuver(demande, forcer = false) {
    setConfirmation(null)
    setMessage({ type: '', texte: '' })
    try {
      await apiFetch(`/conges/${demande.id}/approuver/`, { method: 'POST', body: { forcer } })
      await recharger()
      setMessage({ type: 'success', texte: `Congé de ${demande.agent_nom} approuvé : l'agent est prévenu.` })
    } catch (err) {
      if (err.status === 409) setConfirmation({ demande, texte: err.message })
      else setMessage({ type: 'error', texte: err.message })
    }
  }

  const refuser = (demande) =>
    agir(
      () => apiFetch(`/conges/${demande.id}/refuser/`, { method: 'POST', body: { motif: motifs[demande.id] || '' } }),
      `Congé de ${demande.agent_nom} refusé : l'agent est prévenu.`,
    )
  const annuler = (conge) => agir(() => apiFetch(`/conges/${conge.id}/annuler/`, { method: 'POST', body: {} }), 'Congé annulé.')

  if (!data) return <Alert>{error}</Alert>

  return (
    <div>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {confirmation && (
        <Alert type="warning">
          {confirmation.texte}{' '}
          <button type="button" className="button-small" disabled={envoi} onClick={() => approuver(confirmation.demande, true)}>
            Valider malgré tout
          </button>
        </Alert>
      )}

      <h2 className="section-title">Demandes à valider ({data.attente.length})</h2>
      {data.attente.length === 0 && <p className="muted">Aucune demande en attente.</p>}
      {data.attente.map((demande) => (
        <section className="card" key={demande.id}>
          <h3>
            {demande.agent_nom} <span className="muted">({ROLE_LABELS[demande.agent_role] || demande.agent_role})</span>
          </h3>
          <p>
            {demande.type_libelle} du {formatDate(demande.debut)} au {formatDate(demande.fin)} ({demande.jours} j)
            {demande.motif && <span className="muted"> — {demande.motif}</span>}
          </p>
          <Impact impact={data.impacts[demande.id]} />
          <div className="ligne-fermeture">
            <button type="button" disabled={envoi} onClick={() => approuver(demande)}>
              Approuver le congé de {demande.agent_nom}
            </button>
            <input
              aria-label={`Motif du refus pour ${demande.agent_nom}`}
              placeholder="Motif du refus"
              value={motifs[demande.id] || ''}
              onChange={(e) => setMotifs({ ...motifs, [demande.id]: e.target.value })}
            />
            <button type="button" className="button-secondary" disabled={envoi || !(motifs[demande.id] || '').trim()} onClick={() => refuser(demande)}>
              Refuser
            </button>
          </div>
        </section>
      ))}

      <h2 className="section-title">Congés approuvés</h2>
      {data.approuves.length === 0 ? (
        <p className="muted">Aucun congé approuvé.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Nature</th>
                <th>Du</th>
                <th>Au</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.approuves.map((conge) => (
                <tr key={conge.id}>
                  <td>{conge.agent_nom}</td>
                  <td>{conge.type_libelle}</td>
                  <td>{formatDate(conge.debut)}</td>
                  <td>{formatDate(conge.fin)}</td>
                  <td>
                    <button type="button" className="button-secondary button-small" disabled={envoi} onClick={() => annuler(conge)}>
                      Annuler
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
