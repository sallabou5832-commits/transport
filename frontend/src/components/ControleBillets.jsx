import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

const CLOTURE_VIDE = { passagers_constates: '', charge_constatee_kg: '', commentaire: '', infraction_grave: false, motif_infraction: '' }
const LIBELLES_RESULTAT = {
  valide: 'Valide',
  deja_utilise: 'Déjà utilisé',
  annule: 'Annulé',
  inconnu: 'Inconnu',
  autre_depart: 'Autre départ',
  depart_termine: 'Départ terminé',
}

function Rapport({ rapport }) {
  return (
    <div className="rapport">
      <p>
        <strong>{rapport.ligne}</strong> · {rapport.vehicule} · conducteur {rapport.chauffeur}
      </p>
      <ul className="stat-list">
        <li>
          <span>Billets vérifiés</span>
          <strong>
            {rapport.billets.verifies} ({rapport.billets.valides} valides, {rapport.billets.refuses} refusés)
          </strong>
        </li>
        <li>
          <span>Voyageurs : billets vendus / constatés / places</span>
          <strong>
            {rapport.voyageurs.vendus} / {rapport.voyageurs.constates ?? '—'} / {rapport.voyageurs.capacite}
          </strong>
        </li>
        <li>
          <span>Charge : enregistrée / constatée (kg)</span>
          <strong>
            {Math.round(rapport.charge.declaree_kg)} / {rapport.charge.constatee_kg === null ? '—' : Math.round(rapport.charge.constatee_kg)}
          </strong>
        </li>
      </ul>
      {rapport.anomalies.length === 0 ? (
        <p className="muted">Aucune anomalie relevée.</p>
      ) : (
        <ul>
          {rapport.anomalies.map((anomalie) => (
            <li key={anomalie}>{anomalie}</li>
          ))}
        </ul>
      )}
      {rapport.infraction_grave && <Alert type="error">Infraction grave : {rapport.motif_infraction}</Alert>}
    </div>
  )
}

/**
 * Contrôle à bord : ouvrir un contrôle sur un trajet, vérifier les billets un à un (code saisi ou lu par un lecteur : la
 * touche Entrée valide), clôturer avec les constats et lire le rapport ; historique par ligne et par conducteur.
 */
export default function ControleBillets() {
  const [feuilleChoisie, setFeuilleChoisie] = useState('')
  const [code, setCode] = useState('')
  const [dernier, setDernier] = useState(null)
  const [journal, setJournal] = useState([])
  const [cloture, setCloture] = useState(CLOTURE_VIDE)
  const [rapportFinal, setRapportFinal] = useState(null)
  const [filtre, setFiltre] = useState({ ligne: '', chauffeur: '' })
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  const { data, error, loading, recharger } = useChargement(
    async () => {
      const [controles, ouverts, feuilles, departs, lignes] = await Promise.all([
        apiFetch('/controles/?ligne=' + filtre.ligne + '&chauffeur=' + filtre.chauffeur),
        // Le contrôle en cours ne dépend pas des filtres de l'historique.
        apiFetch('/controles/?ouvert=1'),
        apiFetch('/feuilles-de-route/'),
        apiFetch('/departs/'),
        apiFetch('/lignes/'),
      ])
      return { controles, ouverts, feuilles, departs, lignes }
    },
    { cle: `${filtre.ligne}|${filtre.chauffeur}`, intervalleMs: 60000 },
  )

  if (!data) {
    return (
      <>
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </>
    )
  }

  const { controles, ouverts, feuilles, departs, lignes } = data
  const departsParId = Object.fromEntries(departs.map((d) => [d.id, d]))
  const lignesParId = Object.fromEntries(lignes.map((l) => [l.id, l]))
  const ouvert = ouverts[0]
  const clotures = controles.filter((c) => !c.est_ouvert)
  // Les cars qui roulent, et ceux d'hier à demain : un car qui part dans trois jours ne se contrôle pas.
  const debutFenetre = new Date()
  debutFenetre.setHours(0, 0, 0, 0)
  debutFenetre.setDate(debutFenetre.getDate() - 1)
  const finFenetre = new Date()
  finFenetre.setHours(23, 59, 59, 999)
  finFenetre.setDate(finFenetre.getDate() + 1)
  const trajets = feuilles
    .filter((f) => !f.heure_arrivee_reelle && departsParId[f.depart]?.statut !== 'termine')
    .filter((f) => f.heure_depart_reelle || (new Date(f.heure_depart_prevue) >= debutFenetre && new Date(f.heure_depart_prevue) <= finFenetre))
    .sort((a, b) => new Date(a.heure_depart_prevue) - new Date(b.heure_depart_prevue))
  const libelleTrajet = (f) => {
    const depart = departsParId[f.depart]
    return `${lignesParId[depart?.ligne]?.nom ?? 'Ligne'} — ${formatDateHeure(f.heure_depart_prevue)} — ${f.chauffeur_nom}`
  }
  const chauffeurs = [...new Map(controles.map((c) => [c.chauffeur, c.chauffeur_nom])).entries()]

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      const resultat = await requete()
      await recharger()
      if (confirmation) setMessage({ type: 'success', texte: confirmation })
      return resultat
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return null
    } finally {
      setEnvoi(false)
    }
  }

  async function ouvrir(event) {
    event.preventDefault()
    setJournal([])
    setDernier(null)
    setRapportFinal(null)
    const resultat = await agir(
      () => apiFetch('/controles/', { method: 'POST', body: { feuille_de_route: Number(feuilleChoisie) } }),
      'Contrôle ouvert : vérifiez les billets un à un.',
    )
    if (resultat) setFeuilleChoisie('')
  }

  async function verifier(event) {
    event.preventDefault()
    if (!code.trim()) return
    const verdict = await agir(() => apiFetch(`/controles/${ouvert.id}/verifier/`, { method: 'POST', body: { code } }))
    if (verdict) {
      setDernier(verdict)
      setJournal((liste) => [verdict, ...liste].slice(0, 8))
      setCode('')
    }
  }

  async function cloturerControle(event) {
    event.preventDefault()
    const resultat = await agir(
      () =>
        apiFetch(`/controles/${ouvert.id}/cloturer/`, {
          method: 'POST',
          body: {
            passagers_constates: cloture.passagers_constates,
            charge_constatee_kg: cloture.charge_constatee_kg,
            commentaire: cloture.commentaire,
            infraction_grave: cloture.infraction_grave,
            motif_infraction: cloture.motif_infraction,
          },
        }),
      'Contrôle clôturé : le rapport est généré.',
    )
    if (resultat) {
      setRapportFinal(resultat.rapport)
      setCloture(CLOTURE_VIDE)
      setDernier(null)
    }
  }

  return (
    <section>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      {rapportFinal && !ouvert && (
        <section className="card">
          <h2>Rapport du contrôle</h2>
          <Rapport rapport={rapportFinal} />
        </section>
      )}

      {!ouvert && (
        <section className="card">
          <h2>Ouvrir un contrôle</h2>
          <form onSubmit={ouvrir}>
            <div className="form-grid">
              <label>
                Trajet à contrôler
                <select value={feuilleChoisie} onChange={(e) => setFeuilleChoisie(e.target.value)} required>
                  <option value="">— Choisir un trajet —</option>
                  {trajets.map((f) => (
                    <option key={f.id} value={f.id}>
                      {libelleTrajet(f)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="button-row">
              <button type="submit" disabled={envoi || !feuilleChoisie}>
                Ouvrir le contrôle
              </button>
            </div>
          </form>
        </section>
      )}

      {ouvert && (
        <>
          <section className="card">
            <h2>
              Contrôle en cours : {ouvert.ligne_nom} ({ouvert.vehicule})
            </h2>
            <p className="muted">
              Conducteur {ouvert.chauffeur_nom} · {ouvert.nombre_verifications} billet(s) vérifié(s)
            </p>
            <form onSubmit={verifier} className="toolbar">
              <label>
                Code du billet
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  autoFocus
                  autoComplete="off"
                  spellCheck="false"
                  placeholder="Saisissez ou scannez"
                />
              </label>
              <button type="submit" disabled={envoi || !code.trim()}>
                Vérifier
              </button>
            </form>
            {dernier && (
              <div className={`verdict ${dernier.valide ? 'verdict-ok' : 'verdict-refus'}`} role="status">
                <strong>{dernier.valide ? '✓ ' : '✗ '}{dernier.message}</strong>
                {dernier.ticket && (
                  <span>
                    {' '}
                    {dernier.ticket.passager_nom}
                    {dernier.ticket.utilise_le && !dernier.valide && ` — utilisé le ${formatDateHeure(dernier.ticket.utilise_le)}`}
                  </span>
                )}
              </div>
            )}
            {journal.length > 1 && (
              <ul className="stat-list">
                {journal.slice(1).map((v, index) => (
                  <li key={`${v.code}-${index}`}>
                    <span>{v.code}</span>
                    <Badge ton={v.valide ? 'vert' : 'rouge'}>{LIBELLES_RESULTAT[v.resultat] ?? v.resultat}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <h2>Clôturer le contrôle</h2>
            <form onSubmit={cloturerControle}>
              <div className="form-grid">
                <label>
                  Voyageurs comptés à bord
                  <input type="number" min="0" value={cloture.passagers_constates} onChange={(e) => setCloture({ ...cloture, passagers_constates: e.target.value })} />
                </label>
                <label>
                  Charge constatée (kg)
                  <input type="number" min="0" step="1" value={cloture.charge_constatee_kg} onChange={(e) => setCloture({ ...cloture, charge_constatee_kg: e.target.value })} />
                </label>
                <label>
                  Commentaire
                  <input value={cloture.commentaire} onChange={(e) => setCloture({ ...cloture, commentaire: e.target.value })} />
                </label>
                <label className="checkbox-ligne">
                  <input type="checkbox" checked={cloture.infraction_grave} onChange={(e) => setCloture({ ...cloture, infraction_grave: e.target.checked })} />
                  Infraction grave à signaler à la direction et au QHSE
                </label>
                {cloture.infraction_grave && (
                  <label>
                    Motif de l’infraction
                    <input value={cloture.motif_infraction} onChange={(e) => setCloture({ ...cloture, motif_infraction: e.target.value })} required />
                  </label>
                )}
              </div>
              <div className="button-row">
                <button type="submit" disabled={envoi}>
                  Clôturer et générer le rapport
                </button>
              </div>
            </form>
          </section>
        </>
      )}

      <h2 className="section-title">Historique des contrôles</h2>
      <div className="toolbar">
        <label>
          Ligne
          <select value={filtre.ligne} onChange={(e) => setFiltre({ ...filtre, ligne: e.target.value })}>
            <option value="">Toutes</option>
            {lignes.map((l) => (
              <option key={l.id} value={l.id}>
                {l.nom}
              </option>
            ))}
          </select>
        </label>
        <label>
          Conducteur
          <select value={filtre.chauffeur} onChange={(e) => setFiltre({ ...filtre, chauffeur: e.target.value })}>
            <option value="">Tous</option>
            {chauffeurs.map(([id, nom]) => (
              <option key={id} value={id}>
                {nom}
              </option>
            ))}
          </select>
        </label>
      </div>
      {clotures.length === 0 ? (
        <p>Aucun contrôle clôturé.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Ligne</th>
                <th>Conducteur</th>
                <th>Billets</th>
                <th>Anomalies</th>
                <th>Rapport</th>
              </tr>
            </thead>
            <tbody>
              {clotures.map((c) => (
                <tr key={c.id} className={c.infraction_grave ? 'row-danger' : ''}>
                  <td>{formatDateHeure(c.cloture_le)}</td>
                  <td>{c.ligne_nom}</td>
                  <td>{c.chauffeur_nom}</td>
                  <td>
                    {c.rapport.billets.verifies} ({c.rapport.billets.refuses} refusé(s))
                  </td>
                  <td>{c.infraction_grave ? <Badge ton="rouge">Infraction grave</Badge> : c.rapport.anomalies.length || '—'}</td>
                  <td>
                    <details>
                      <summary>Voir</summary>
                      <Rapport rapport={c.rapport} />
                    </details>
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
