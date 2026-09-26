import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatDateHeure } from '../lib/format.js'
import { GRAVITES_DOLEANCE, STATUTS_DOLEANCE } from '../lib/rh.js'

const SYNDICAT_VIDE = { syndicat: '', objet: '', description: '', gravite: 'moyenne' }
const ETAPE_VIDE = { texte: '', visible_du_deposant: true, statut: '' }

/** Une doléance instruite par le DRH : le texte, les étapes de médiation déjà faites, une nouvelle étape, la gravité et le statut. */
function Instruction({ doleance, onChange }) {
  const [etape, setEtape] = useState(ETAPE_VIDE)
  const { agir, envoi, message } = useActions(onChange)

  async function ajouter(event) {
    event.preventDefault()
    const corps = { texte: etape.texte, visible_du_deposant: etape.visible_du_deposant }
    if (etape.statut) corps.statut = etape.statut
    if (await agir(() => apiFetch(`/doleances/${doleance.id}/suivre/`, { method: 'POST', body: corps }), 'Étape enregistrée.')) setEtape(ETAPE_VIDE)
  }

  const modifier = (champs, confirmation) => agir(() => apiFetch(`/doleances/${doleance.id}/`, { method: 'PATCH', body: champs }), confirmation)

  return (
    <section className="card detail-panneau">
      <h3>{doleance.objet}</h3>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <p className="texte-pre">{doleance.description}</p>
      <p className="muted">
        {doleance.origine === 'syndicat'
          ? `Déposée par ${doleance.syndicat}`
          : `Déposée par ${doleance.auteur_nom} (${ROLE_LABELS[doleance.auteur_role] || doleance.auteur_role})`}{' '}
        le {formatDateHeure(doleance.cree_le)}.
        {doleance.litige && ' Le responsable juridique a été prévenu d’un risque de litige.'}
      </p>

      <div className="toolbar">
        <label>
          Gravité de la doléance
          <select value={doleance.gravite} disabled={envoi} onChange={(e) => modifier({ gravite: e.target.value }, 'Gravité mise à jour.')}>
            {Object.entries(GRAVITES_DOLEANCE).map(([valeur, g]) => (
              <option key={valeur} value={valeur}>
                {g.libelle}
              </option>
            ))}
          </select>
        </label>
        <label>
          Statut de la doléance
          <select value={doleance.statut} disabled={envoi} onChange={(e) => modifier({ statut: e.target.value }, 'Statut mis à jour.')}>
            {Object.entries(STATUTS_DOLEANCE).map(([valeur, s]) => (
              <option key={valeur} value={valeur}>
                {s.libelle}
              </option>
            ))}
          </select>
        </label>
      </div>

      <h4>Étapes de la médiation</h4>
      {doleance.suivis.length === 0 ? (
        <p className="muted">Aucune étape pour le moment.</p>
      ) : (
        <ul className="motifs">
          {doleance.suivis.map((s) => (
            <li key={s.id}>
              <span className="muted">
                {formatDateHeure(s.cree_le)} — {s.auteur_nom} {s.visible_du_deposant ? '' : '(note interne)'} :
              </span>{' '}
              {s.texte}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={ajouter}>
        <label className="grand-champ">
          Nouvelle étape
          <textarea rows={2} value={etape.texte} onChange={(e) => setEtape({ ...etape, texte: e.target.value })} required />
        </label>
        <div className="toolbar">
          <label className="checkbox-ligne">
            <input
              type="checkbox"
              checked={etape.visible_du_deposant}
              onChange={(e) => setEtape({ ...etape, visible_du_deposant: e.target.checked })}
            />
            Visible du déposant
          </label>
          <label>
            Faire passer la doléance à
            <select value={etape.statut} onChange={(e) => setEtape({ ...etape, statut: e.target.value })}>
              <option value="">Statut inchangé</option>
              {Object.entries(STATUTS_DOLEANCE).map(([valeur, s]) => (
                <option key={valeur} value={valeur}>
                  {s.libelle}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={envoi}>
            Ajouter l&apos;étape
          </button>
        </div>
      </form>
    </section>
  )
}

/**
 * La médiation sociale vue du DRH : toutes les doléances des agents et des syndicats, leur instruction (étapes visibles ou non du déposant,
 * gravité, statut) et l'enregistrement d'une doléance de syndicat. Une doléance qui atteint le seuil de gravité prévient le juridique.
 */
export default function MediationDrh() {
  const [choisie, setChoisie] = useState(null)
  const [statut, setStatut] = useState('')
  const [syndicat, setSyndicat] = useState(SYNDICAT_VIDE)
  const { data, error, recharger } = useChargement(() => apiFetch('/doleances/'), { intervalleMs: 60000 })
  const { agir, envoi, message } = useActions(recharger)

  async function enregistrer(event) {
    event.preventDefault()
    if (
      await agir(
        () => apiFetch('/doleances/', { method: 'POST', body: { ...syndicat, origine: 'syndicat' } }),
        `Doléance de « ${syndicat.syndicat} » enregistrée.`,
      )
    ) {
      setSyndicat(SYNDICAT_VIDE)
    }
  }

  const champ = (nom) => ({ value: syndicat[nom], onChange: (e) => setSyndicat({ ...syndicat, [nom]: e.target.value }) })
  const visibles = (data || []).filter((d) => !statut || d.statut === statut)
  const selection = (data || []).find((d) => d.id === choisie)

  return (
    <div>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <section className="card">
        <h2>Doléances</h2>
        <div className="toolbar">
          <label>
            Statut affiché
            <select value={statut} onChange={(e) => setStatut(e.target.value)}>
              <option value="">Tous</option>
              {Object.entries(STATUTS_DOLEANCE).map(([valeur, s]) => (
                <option key={valeur} value={valeur}>
                  {s.libelle}
                </option>
              ))}
            </select>
          </label>
        </div>
        {visibles.length === 0 ? (
          <p className="muted">Aucune doléance.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Déposée le</th>
                  <th>Objet</th>
                  <th>Déposant</th>
                  <th>Gravité</th>
                  <th>Statut</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visibles.map((d) => (
                  <tr key={d.id} className={d.litige ? 'row-danger' : ''}>
                    <td>{formatDate(d.cree_le)}</td>
                    <td>{d.objet}</td>
                    <td>{d.origine === 'syndicat' ? d.syndicat : d.auteur_nom}</td>
                    <td>
                      <Badge ton={GRAVITES_DOLEANCE[d.gravite].ton}>{GRAVITES_DOLEANCE[d.gravite].libelle}</Badge>
                    </td>
                    <td>
                      <Badge ton={STATUTS_DOLEANCE[d.statut].ton}>{STATUTS_DOLEANCE[d.statut].libelle}</Badge>
                    </td>
                    <td>
                      <button type="button" className="button-secondary button-small" onClick={() => setChoisie(choisie === d.id ? null : d.id)}>
                        {choisie === d.id ? 'Fermer' : 'Instruire'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selection && <Instruction doleance={selection} onChange={recharger} />}

      <section className="card">
        <h2>Enregistrer la doléance d&apos;un syndicat</h2>
        <form onSubmit={enregistrer}>
          <div className="form-grid">
            <label>
              Syndicat ou délégués
              <input {...champ('syndicat')} required />
            </label>
            <label>
              Objet de la doléance
              <input {...champ('objet')} minLength={3} required />
            </label>
            <label>
              Gravité retenue
              <select {...champ('gravite')}>
                {Object.entries(GRAVITES_DOLEANCE).map(([valeur, g]) => (
                  <option key={valeur} value={valeur}>
                    {g.libelle}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="grand-champ">
            Contenu de la doléance
            <textarea rows={3} {...champ('description')} minLength={10} required />
          </label>
          <div className="button-row">
            <button type="submit" disabled={envoi}>
              Enregistrer la doléance
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
