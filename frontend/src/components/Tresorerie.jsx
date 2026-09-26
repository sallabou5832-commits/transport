import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Kpi from './Kpi.jsx'
import { formatDate, formatFCFA } from '../lib/format.js'

const LARGEUR_JOUR = 10

/** Les 30 derniers jours : ce qui est entré (vert) et ce qui est sorti (rouge), jour par jour. */
function Serie({ jours }) {
  const max = Math.max(1, ...jours.flatMap((jour) => [Number(jour.encaissements), Number(jour.decaissements)]))
  return (
    <svg
      className="serie-tresorerie"
      viewBox={`0 0 ${jours.length * LARGEUR_JOUR} 60`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Encaissements et dépenses des 30 derniers jours"
    >
      {jours.map((jour, i) => {
        const entre = (Number(jour.encaissements) / max) * 56
        const sorti = (Number(jour.decaissements) / max) * 56
        return (
          <g key={jour.date}>
            <title>{`${formatDate(jour.date)} : encaissé ${formatFCFA(jour.encaissements)}, dépensé ${formatFCFA(jour.decaissements)}`}</title>
            <rect x={i * LARGEUR_JOUR + 1} y={58 - entre} width={4} height={entre} className="serie-encaisse" />
            <rect x={i * LARGEUR_JOUR + 5} y={58 - sorti} width={4} height={sorti} className="serie-decaisse" />
          </g>
        )
      })}
    </svg>
  )
}

/**
 * La trésorerie en temps réel, telle que la finance et le PDG la lisent : le solde de caisse, ce qui est entré et sorti ce mois-ci,
 * ce qui reste à payer (échéances proches et retards) et le solde prévu à 30 jours. Lecture seule ; `version` la recharge après
 * une écriture faite ailleurs sur la page.
 */
export default function Tresorerie({ version = 0 }) {
  const { data, error } = useChargement(() => apiFetch('/finance/tresorerie/'), { cle: version, intervalleMs: 60000 })

  if (!data) return <Alert>{error}</Alert>
  const { a_payer: aPayer } = data

  return (
    <>
      <Alert>{error}</Alert>
      <div className="cards-grid">
        <Kpi
          titre="Solde de caisse"
          valeur={formatFCFA(data.solde)}
          ton={Number(data.solde) < 0 ? 'rouge' : 'vert'}
          detail={`Solde de départ : ${formatFCFA(data.solde_initial)}`}
        />
        <Kpi titre="Encaissé ce mois" valeur={formatFCFA(data.mois.encaissements)} ton="vert" detail="billets et fret" />
        <Kpi titre="Dépensé ce mois" valeur={formatFCFA(data.mois.decaissements)} />
        <Kpi
          titre="À payer sous 7 jours"
          valeur={formatFCFA(aPayer.sous_7_jours)}
          ton={Number(aPayer.sous_7_jours) > 0 ? 'orange' : 'vert'}
          detail={`${formatFCFA(aPayer.sous_30_jours)} sous 30 jours (${aPayer.factures_sous_30_jours} facture(s))`}
        />
        <Kpi
          titre="Factures en retard"
          valeur={formatFCFA(aPayer.en_retard)}
          ton={aPayer.factures_en_retard > 0 ? 'rouge' : 'vert'}
          detail={`${aPayer.factures_en_retard} facture(s)`}
        />
        <Kpi
          titre="Solde prévu à 30 jours"
          valeur={formatFCFA(data.solde_previsionnel_30_jours)}
          ton={Number(data.solde_previsionnel_30_jours) < 0 ? 'rouge' : undefined}
          detail="solde moins les retards et les échéances des 30 jours"
        />
      </div>
      <section className="card">
        <h2>Entrées et sorties des 30 derniers jours</h2>
        <Serie jours={data.serie_30_jours} />
        <p className="muted legende-serie">
          <span className="legende-encaisse" /> Encaissements <span className="legende-decaisse" /> Dépenses
        </p>
      </section>
    </>
  )
}
