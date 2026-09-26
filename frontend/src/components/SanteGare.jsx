import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import Kpi from './Kpi.jsx'
import { TON_COULEUR, formatFCFA, formatHeure } from '../lib/format.js'

const MODES = { especes: 'Espèces', mobile_money: 'Mobile money' }

function pourcent(valeur) {
  return valeur === null || valeur === undefined ? '—' : `${valeur} %`
}

/**
 * « Santé de la gare » du chef de gare : ponctualité et remplissage du jour, recettes calculées depuis la billetterie et le fret,
 * incidents ouverts, véhicules disponibles et départs en retard. Rien à ressaisir : tout vient des ventes et des feuilles de route.
 */
export default function SanteGare() {
  const { data, error } = useChargement(() => apiFetch('/dashboard/gare/'), { intervalleMs: 60000 })

  if (!data) return <Alert>{error}</Alert>

  const { jour, recettes, incidents_ouverts: incidents, vehicules, equipe } = data
  const modes = Object.entries(recettes.billets_par_mode)
    .map(([mode, montant]) => `${MODES[mode] ?? mode} ${formatFCFA(montant)}`)
    .join(' · ')

  return (
    <section>
      <Alert>{error}</Alert>
      <div className="cards-grid">
        <Kpi
          titre="Ponctualité du jour"
          valeur={pourcent(jour.ponctualite_pourcent)}
          detail={`${jour.a_l_heure} à l'heure · ${jour.en_retard} en retard · ${jour.en_attente} en attente (7 jours : ${pourcent(data.ponctualite_7_jours_pourcent)})`}
          ton={jour.couleur === 'neutre' ? undefined : TON_COULEUR[jour.couleur]}
        />
        <Kpi
          titre="Remplissage moyen"
          valeur={pourcent(jour.remplissage_pourcent)}
          detail={`${jour.places_vendues} places vendues sur ${jour.capacite} (${jour.departs} départ(s))`}
        />
        <Kpi
          titre="Recettes du jour de la gare"
          valeur={formatFCFA(recettes.total)}
          detail={`${recettes.nombre_de_billets} billet(s) ${formatFCFA(recettes.billets)}${modes ? ` (${modes})` : ''} · fret ${formatFCFA(recettes.fret)}`}
        />
        <Kpi
          titre="Incidents ouverts"
          valeur={incidents.total}
          ton={incidents.graves > 0 ? 'rouge' : incidents.total > 0 ? 'orange' : 'vert'}
          detail={`${incidents.graves} grave(s)`}
        />
        <Kpi
          titre="Véhicules de la gare"
          valeur={`${vehicules.vehicules_disponibles} / ${vehicules.vehicules_attaches}`}
          ton={vehicules.en_tension ? 'rouge' : undefined}
          detail={
            vehicules.en_tension
              ? `Gare en tension : ${vehicules.departs_24h} départ(s) en 24 h pour ${vehicules.vehicules_disponibles} véhicule(s) disponible(s)`
              : `disponibles sur rattachés · ${vehicules.departs_24h} départ(s) en 24 h · équipe de ${equipe.total} agent(s)`
          }
        />
      </div>

      {data.departs_en_retard.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Départ en retard, pas encore parti</th>
                <th>Chauffeur</th>
                <th>Prévu à</th>
                <th>Retard</th>
              </tr>
            </thead>
            <tbody>
              {data.departs_en_retard.map((retard) => (
                <tr key={retard.depart} className="row-alerte">
                  <td>{retard.ligne}</td>
                  <td>{retard.chauffeur_nom}</td>
                  <td>{formatHeure(retard.heure_depart_prevue)}</td>
                  <td>
                    <Badge ton="rouge">{retard.retard_minutes} min</Badge>
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
