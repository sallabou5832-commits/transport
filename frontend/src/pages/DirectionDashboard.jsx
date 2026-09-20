import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Layout from '../components/Layout.jsx'
import Alert from '../components/Alert.jsx'
import Barres from '../components/Barres.jsx'
import Kpi from '../components/Kpi.jsx'
import TuilesGares from '../components/TuilesGares.jsx'
import {
  LABELS_GRAVITE,
  LABELS_VEHICULE,
  TON_COULEUR,
  formatDate,
  formatFCFA,
  isoAujourdhui,
} from '../lib/format.js'

export default function DirectionDashboard() {
  const { data, error, loading } = useChargement(
    async () => {
      const [direction, exploitation, finance] = await Promise.all([
        apiFetch('/dashboard/direction/'),
        apiFetch('/dashboard/exploitation/'),
        apiFetch(`/synthese-financiere/?date_debut=${isoAujourdhui(-6)}&date_fin=${isoAujourdhui(0)}`),
      ])
      return { direction, exploitation, finance }
    },
    { intervalleMs: 60000 },
  )

  if (!data) {
    return (
      <Layout title="Tableau de bord — Direction">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { direction, exploitation, finance } = data
  const jour = exploitation.jour

  return (
    <Layout title="Tableau de bord — Direction">
      <Alert>{error}</Alert>

      <div className="cards-grid">
        <Kpi
          titre="Recettes du jour"
          valeur={formatFCFA(direction.recettes_du_jour)}
          ton="vert"
          detail={`${formatFCFA(finance.total.montant_total)} sur 7 jours`}
        />
        <Kpi
          titre="Ponctualité du jour"
          valeur={jour.ponctualite_pourcent === null ? '—' : `${jour.ponctualite_pourcent} %`}
          detail={`${jour.en_retard} départ(s) en retard · ${jour.departs} au programme`}
          ton={jour.couleur === 'neutre' ? undefined : TON_COULEUR[jour.couleur]}
        />
        <Kpi
          titre="Pièces sous seuil d'alerte"
          valeur={direction.pieces_sous_seuil}
          ton={direction.pieces_sous_seuil > 0 ? 'orange' : 'vert'}
        />
        <Kpi
          titre="Assurances à échéance proche (< 30 jours)"
          valeur={direction.assurances_echeance_proche}
          ton={direction.assurances_echeance_proche > 0 ? 'orange' : 'vert'}
        />
      </div>

      <h2 className="section-title">Statut des gares aujourd&apos;hui ({formatDate(exploitation.date)})</h2>
      <TuilesGares gares={exploitation.gares} />

      <div className="cards-grid">
        <section className="card">
          <h2>Recettes des 7 derniers jours</h2>
          <Barres
            lignes={finance.par_jour.map((j) => ({
              cle: j.date,
              label: formatDate(j.date),
              valeur: Number(j.montant_total),
            }))}
            format={formatFCFA}
            vide="Aucune vente sur la période."
          />
        </section>

        <section className="card">
          <h2>Véhicules par statut</h2>
          <ul className="stat-list">
            {Object.entries(direction.vehicules_par_statut).map(([statut, nombre]) => (
              <li key={statut}>
                <span>{LABELS_VEHICULE[statut] || statut}</span>
                <strong>{nombre}</strong>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2>Incidents ouverts (7 derniers jours)</h2>
          <ul className="stat-list">
            {Object.entries(direction.incidents_ouverts_par_gravite_7_jours).map(([gravite, nombre]) => (
              <li key={gravite}>
                <span>{LABELS_GRAVITE[gravite] || gravite}</span>
                <strong>{nombre}</strong>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </Layout>
  )
}
