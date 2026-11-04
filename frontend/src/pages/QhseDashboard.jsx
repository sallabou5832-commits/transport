import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import EchangesTutelle from '../components/EchangesTutelle.jsx'
import FormationsObligatoires from '../components/FormationsObligatoires.jsx'
import Kpi from '../components/Kpi.jsx'
import TableauConformite from '../components/TableauConformite.jsx'
import {
  LABELS_GRAVITE,
  LABELS_TYPE_INCIDENT,
  TON_GRAVITE,
  estAujourdhui,
  formatDateHeure,
  indexParId,
} from '../lib/format.js'

export default function QhseDashboard() {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [enCours, setEnCours] = useState(null)
  const [blocage, setBlocage] = useState({ vehicule: '', motif: '' })
  const [motifsLevee, setMotifsLevee] = useState({})

  const { data, error, loading, recharger } = useChargement(async () => {
    const [incidents, vehicules, feuilles, checklists, departs, lignes, blocages] = await Promise.all([
      apiFetch('/dashboard/qhse/'),
      apiFetch('/vehicules/'),
      apiFetch('/feuilles-de-route/'),
      apiFetch('/checklists/'),
      apiFetch('/departs/'),
      apiFetch('/lignes/'),
      apiFetch('/blocages-securite/'),
    ])
    return { incidents, vehicules, feuilles, checklists, departs, lignes, blocages }
  })

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    try {
      await requete()
      await recharger()  // les listes d'abord, le message ensuite
      setMessage({ type: 'success', texte: confirmation })
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    }
  }

  async function bloquer(event) {
    event.preventDefault()
    const ok = await agir(
      () =>
        apiFetch('/blocages-securite/', {
          method: 'POST',
          body: { vehicule: Number(blocage.vehicule), motif: blocage.motif },
        }),
      'Départ bloqué : le chef de gare, le chef d’atelier et la régulation sont prévenus.',
    )
    if (ok) setBlocage({ vehicule: '', motif: '' })
  }

  function lever(bloc) {
    return agir(
      () =>
        apiFetch(`/blocages-securite/${bloc.id}/lever/`, { method: 'POST', body: { motif: motifsLevee[bloc.id] } }),
      `Blocage de ${bloc.vehicule_immatriculation} levé.`,
    )
  }

  async function marquerTraite(incident) {
    setMessage({ type: '', texte: '' })
    setEnCours(incident.id)
    try {
      await apiFetch(`/incidents/${incident.id}/`, { method: 'PATCH', body: { statut: 'traite' } })
      setMessage({ type: 'success', texte: `Incident #${incident.id} marqué comme traité.` })
      await recharger()
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
    } finally {
      setEnCours(null)
    }
  }

  if (!data) {
    return (
      <Layout title="Tableau de bord — QHSE">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { incidents, vehicules, feuilles, checklists, departs, lignes, blocages } = data
  const graves = incidents.filter((i) => i.gravite === 'grave')
  const bloques = vehicules.filter((v) => v.statut === 'bloque_securite')
  const blocagesActifs = blocages.filter((b) => b.est_actif)
  const blocageParVehicule = Object.fromEntries(blocagesActifs.map((b) => [b.vehicule, b]))
  const bloquables = vehicules.filter((v) => v.statut === 'disponible')

  const feuillesParId = indexParId(feuilles)
  const departsParId = indexParId(departs)
  const lignesParId = indexParId(lignes)
  const vehiculesParId = indexParId(vehicules)

  // Checklists complétées : parmi les feuilles de route du jour, celles qui ont au moins un item saisi.
  const feuillesDuJour = feuilles.filter((f) => estAujourdhui(f.heure_depart_prevue))
  const feuillesAvecChecklist = new Set(checklists.map((c) => c.feuille_de_route))
  const completees = feuillesDuJour.filter((f) => feuillesAvecChecklist.has(f.id)).length

  // Défauts à traiter : items en défaut sur une feuille dont le car n'est pas encore parti.
  const defauts = checklists
    .filter((c) => c.etat === 'defaut' && !feuillesParId[c.feuille_de_route]?.heure_depart_reelle)
    .map((c) => {
      const feuille = feuillesParId[c.feuille_de_route]
      const depart = departsParId[feuille?.depart]
      return {
        ...c,
        ligne: lignesParId[depart?.ligne]?.nom,
        vehicule: vehiculesParId[depart?.vehicule]?.immatriculation,
        depart_prevu: feuille?.heure_depart_prevue,
      }
    })

  return (
    <Layout title="Tableau de bord — QHSE">
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>

      <div className="cards-grid">
        <Kpi
          titre="Incidents ouverts"
          valeur={incidents.length}
          detail={`dont ${graves.length} grave${graves.length > 1 ? 's' : ''}`}
          ton={graves.length > 0 ? 'rouge' : incidents.length > 0 ? 'orange' : 'vert'}
        />
        <Kpi
          titre="Véhicules bloqués (sécurité)"
          valeur={bloques.length}
          ton={bloques.length > 0 ? 'rouge' : 'vert'}
        />
        <Kpi
          titre="Checklists complétées aujourd'hui"
          valeur={`${completees} / ${feuillesDuJour.length}`}
          detail="feuilles de route du jour avec une checklist saisie"
          ton={feuillesDuJour.length > 0 && completees < feuillesDuJour.length ? 'orange' : 'vert'}
        />
        <Kpi
          titre="Défauts avant départ"
          valeur={defauts.length}
          detail="sur des départs pas encore partis"
          ton={defauts.length > 0 ? 'rouge' : 'vert'}
        />
      </div>

      <h2 className="section-title">Incidents ouverts (du plus grave au moins grave)</h2>
      {incidents.length === 0 ? (
        <p>Aucun incident ouvert.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Gravité</th>
                <th>Type</th>
                <th>Véhicule</th>
                <th>Description</th>
                <th>Date</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => (
                <tr key={incident.id} className={incident.gravite === 'grave' ? 'row-danger' : ''}>
                  <td>
                    <Badge ton={TON_GRAVITE[incident.gravite]}>{LABELS_GRAVITE[incident.gravite]}</Badge>
                  </td>
                  <td>{LABELS_TYPE_INCIDENT[incident.type_incident] || incident.type_incident}</td>
                  <td>{incident.vehicule.immatriculation}</td>
                  <td>{incident.description}</td>
                  <td>{formatDateHeure(incident.date)}</td>
                  <td>
                    <button
                      type="button"
                      className="button-small"
                      disabled={enCours === incident.id}
                      onClick={() => marquerTraite(incident)}
                    >
                      Marquer traité
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section-title">Défauts de checklist avant départ</h2>
      {defauts.length === 0 ? (
        <p>Aucun défaut signalé sur les départs à venir.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Élément</th>
                <th />
                <th>Ligne</th>
                <th>Véhicule</th>
                <th>Départ prévu</th>
                <th>Commentaire</th>
              </tr>
            </thead>
            <tbody>
              {defauts.map((defaut) => (
                <tr key={defaut.id}>
                  <td style={{ textTransform: 'capitalize' }}>{defaut.item}</td>
                  <td>{defaut.est_item_securite && <Badge ton="rouge">Sécurité : départ bloqué</Badge>}</td>
                  <td>{defaut.ligne || '—'}</td>
                  <td>{defaut.vehicule || '—'}</td>
                  <td>{formatDateHeure(defaut.depart_prevu)}</td>
                  <td>{defaut.commentaire || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section-title">Véhicules bloqués pour raison de sécurité</h2>
      {bloques.length === 0 ? (
        <p>Aucun véhicule bloqué.</p>
      ) : (
        <ul className="stat-list">
          {bloques.map((v) => {
            const pose = blocageParVehicule[v.id]
            return (
              <li key={v.id}>
                <span>
                  {v.immatriculation}
                  {pose && (
                    <span className="muted">
                      {' '}
                      — {pose.motif} (par {pose.pose_par_nom}, {formatDateHeure(pose.pose_le)})
                    </span>
                  )}
                </span>
                {pose ? (
                  <span className="toolbar" style={{ margin: 0 }}>
                    <input
                      placeholder="Motif de la levée"
                      aria-label={`Motif de la levée du blocage de ${v.immatriculation}`}
                      value={motifsLevee[pose.id] || ''}
                      onChange={(e) => setMotifsLevee({ ...motifsLevee, [pose.id]: e.target.value })}
                    />
                    <button
                      type="button"
                      className="button-small"
                      disabled={(motifsLevee[pose.id] || '').trim().length < 5}
                      onClick={() => lever(pose)}
                    >
                      Lever le blocage
                    </button>
                  </span>
                ) : (
                  <Badge ton="rouge">Bloqué (défaut de checklist)</Badge>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <h2 className="section-title">Bloquer le départ d&apos;un véhicule</h2>
      <section className="card">
        <p className="muted">
          Le chef de gare concerné, le chef d&apos;atelier, le directeur technique et la régulation sont prévenus
          aussitôt.
        </p>
        <form onSubmit={bloquer}>
          <div className="form-grid">
            <label>
              Véhicule
              <select value={blocage.vehicule} onChange={(e) => setBlocage({ ...blocage, vehicule: e.target.value })} required>
                <option value="">— Choisir —</option>
                {bloquables.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.immatriculation}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Motif du blocage
              <input value={blocage.motif} onChange={(e) => setBlocage({ ...blocage, motif: e.target.value })} required minLength={5} />
            </label>
          </div>
          <div className="button-row">
            <button type="submit" disabled={bloquables.length === 0}>
              Bloquer le départ
            </button>
          </div>
        </form>
      </section>

      <h2 className="section-title">Conformité réglementaire de la flotte</h2>
      <TableauConformite />

      <h2 className="section-title">Formations obligatoires (sécurité routière OSER, permis, visite médicale)</h2>
      <FormationsObligatoires />

      <EchangesTutelle />
    </Layout>
  )
}
