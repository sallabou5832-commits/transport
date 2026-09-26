import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import { ROLE_LABELS } from '../auth/roles.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate } from '../lib/format.js'
import { STATUTS_CANDIDATURE, STATUTS_OFFRE } from '../lib/rh.js'

const POSTES = Object.entries(ROLE_LABELS).filter(([role]) => role !== 'superadmin')
const OFFRE_VIDE = { role: '', intitule: '', nombre_postes: '1', date_limite: '', gare: '' }
const CANDIDAT_VIDE = { nom: '', telephone: '', email: '', source: '' }

/** Les candidats d'une offre, de la réception à la décision. Quand assez de candidats sont retenus, l'offre est pourvue. */
function Candidatures({ offre, onChange }) {
  const [candidat, setCandidat] = useState(CANDIDAT_VIDE)
  const { data, error, recharger } = useChargement(() => apiFetch(`/candidatures/?offre=${offre.id}`), { cle: offre.id })
  const { agir, envoi, message } = useActions(async () => {
    await recharger()
    if (onChange) await onChange()
  })

  async function ajouter(event) {
    event.preventDefault()
    const corps = { ...candidat, offre: offre.id }
    if (await agir(() => apiFetch('/candidatures/', { method: 'POST', body: corps }), `Candidature de ${candidat.nom} enregistrée.`)) setCandidat(CANDIDAT_VIDE)
  }

  const changer = (candidature, statut) =>
    agir(() => apiFetch(`/candidatures/${candidature.id}/`, { method: 'PATCH', body: { statut } }), `${candidature.nom} : ${STATUTS_CANDIDATURE[statut].toLowerCase()}.`)

  const champ = (nom) => ({ value: candidat[nom], onChange: (e) => setCandidat({ ...candidat, [nom]: e.target.value }) })

  return (
    <section className="card detail-panneau">
      <h3>Candidatures — {offre.intitule}</h3>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {data &&
        (data.length === 0 ? (
          <p className="muted">Aucune candidature reçue.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Candidat</th>
                  <th>Contact</th>
                  <th>Reçue le</th>
                  <th>Décision</th>
                </tr>
              </thead>
              <tbody>
                {data.map((c) => (
                  <tr key={c.id}>
                    <td>
                      {c.nom}
                      {c.source && <div className="muted">{c.source}</div>}
                    </td>
                    <td>
                      {c.telephone}
                      {c.email && <div className="muted">{c.email}</div>}
                    </td>
                    <td>{formatDate(c.cree_le)}</td>
                    <td>
                      <select aria-label={`Décision pour ${c.nom}`} value={c.statut} disabled={envoi} onChange={(e) => changer(c, e.target.value)}>
                        {Object.entries(STATUTS_CANDIDATURE).map(([valeur, libelle]) => (
                          <option key={valeur} value={valeur}>
                            {libelle}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      {offre.statut === 'ouverte' && (
        <form onSubmit={ajouter}>
          <div className="form-grid">
            <label>
              Nom du candidat
              <input {...champ('nom')} required />
            </label>
            <label>
              Téléphone du candidat
              <input {...champ('telephone')} required />
            </label>
            <label>
              E-mail du candidat
              <input type="email" {...champ('email')} />
            </label>
            <label>
              Provenance
              <input {...champ('source')} placeholder="Annonce, recommandation…" />
            </label>
          </div>
          <div className="button-row">
            <button type="submit" disabled={envoi}>
              Ajouter la candidature
            </button>
          </div>
        </form>
      )}
    </section>
  )
}

/** Les offres de recrutement : une offre s'ouvre à partir de la fiche de poste du rôle recherché (fiche type ou personnalisée). */
export default function OffresRecrutement() {
  const [offre, setOffre] = useState(OFFRE_VIDE)
  const [choisie, setChoisie] = useState(null)
  const { data, error, recharger } = useChargement(async () => {
    const [offres, gares] = await Promise.all([apiFetch('/offres-recrutement/'), apiFetch('/gares/')])
    return { offres, gares }
  })
  const { agir, envoi, message } = useActions(recharger)

  async function ouvrir(event) {
    event.preventDefault()
    const corps = { role: offre.role, nombre_postes: Number(offre.nombre_postes) || 1 }
    if (offre.intitule.trim()) corps.intitule = offre.intitule.trim()
    if (offre.date_limite) corps.date_limite = offre.date_limite
    if (offre.gare) corps.gare = Number(offre.gare)
    if (await agir(() => apiFetch('/offres-recrutement/', { method: 'POST', body: corps }), 'Offre ouverte, à partir de la fiche de poste.')) {
      setOffre(OFFRE_VIDE)
    }
  }

  const changer = (o, statut) => agir(() => apiFetch(`/offres-recrutement/${o.id}/`, { method: 'PATCH', body: { statut } }), `Offre « ${o.intitule} » : ${STATUTS_OFFRE[statut].toLowerCase()}.`)
  const champ = (nom) => ({ value: offre[nom], onChange: (e) => setOffre({ ...offre, [nom]: e.target.value }) })

  const selection = data?.offres.find((o) => o.id === choisie)

  return (
    <section className="card">
      <h2>Offres de recrutement</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      {data && (
        <>
          {data.offres.length === 0 ? (
            <p className="muted">Aucune offre pour le moment.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Poste</th>
                    <th>Postes à pourvoir</th>
                    <th>Date limite</th>
                    <th>Candidatures</th>
                    <th>État</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.offres.map((o) => (
                    <tr key={o.id}>
                      <td>
                        {o.intitule}
                        <div className="muted">
                          {o.role_libelle}
                          {o.gare_nom && ` · ${o.gare_nom}`}
                        </div>
                      </td>
                      <td>{o.nombre_postes}</td>
                      <td>{o.date_limite ? formatDate(o.date_limite) : '—'}</td>
                      <td>
                        {o.candidatures_total} ({o.retenues} retenue(s))
                      </td>
                      <td>
                        <Badge ton={o.statut === 'ouverte' ? 'vert' : 'neutre'}>{STATUTS_OFFRE[o.statut]}</Badge>
                        <select aria-label={`État de l'offre ${o.intitule}`} value={o.statut} disabled={envoi} onChange={(e) => changer(o, e.target.value)}>
                          {Object.entries(STATUTS_OFFRE).map(([valeur, libelle]) => (
                            <option key={valeur} value={valeur}>
                              {libelle}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <button type="button" className="button-secondary button-small" onClick={() => setChoisie(choisie === o.id ? null : o.id)}>
                          {choisie === o.id ? 'Masquer les candidatures' : 'Candidatures'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {selection && <Candidatures offre={selection} onChange={recharger} />}

          <h3>Ouvrir une offre</h3>
          <form onSubmit={ouvrir}>
            <div className="form-grid">
              <label>
                Poste recherché
                <select {...champ('role')} required>
                  <option value="">— Choisir —</option>
                  {POSTES.map(([role, libelle]) => (
                    <option key={role} value={role}>
                      {libelle}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Intitulé (vide : celui de la fiche)
                <input {...champ('intitule')} />
              </label>
              <label>
                Nombre de postes
                <input type="number" min="1" {...champ('nombre_postes')} required />
              </label>
              <label>
                Date limite
                <input type="date" {...champ('date_limite')} />
              </label>
              <label>
                Lieu d&apos;affectation
                <select {...champ('gare')}>
                  <option value="">— Toute la compagnie —</option>
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
                Ouvrir l&apos;offre
              </button>
            </div>
          </form>
        </>
      )}
    </section>
  )
}
