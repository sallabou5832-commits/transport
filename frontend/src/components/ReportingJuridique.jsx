import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import Kpi from './Kpi.jsx'
import { formatDate, formatFCFA } from '../lib/format.js'
import { STATUTS_SINISTRE } from '../lib/rh.js'

/**
 * La synthèse juridique remontée à la Direction Générale : flotte assurée, sinistres, litiges sociaux (comptés seulement, sans nom ni
 * détail), conformité, et les points de vigilance du moment. Lecture seule ; s'imprime.
 */
export default function ReportingJuridique() {
  const { data, error } = useChargement(() => apiFetch('/juridique/reporting/'), { intervalleMs: 120000 })

  if (!data) return <Alert>{error}</Alert>
  const { assurances, sinistres, litiges_sociaux: litiges, conformite } = data
  const ouverts = sinistres.ouvert + sinistres.en_cours
  const pourcent = (valeur) => (valeur === null ? '—' : `${valeur} %`)

  return (
    <section className="card imprimable">
      <div className="button-row">
        <h2>Synthèse juridique au {formatDate(data.date)}</h2>
        <button type="button" className="button-secondary button-small no-print" onClick={() => window.print()}>
          Imprimer / PDF
        </button>
      </div>

      {data.points_de_vigilance.length === 0 ? (
        <Alert type="success">Aucun point de vigilance : assurances, sinistres et litiges sont à jour.</Alert>
      ) : (
        <Alert type="warning">
          Points de vigilance :
          <ul className="motifs">
            {data.points_de_vigilance.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </Alert>
      )}

      <div className="cards-grid">
        <Kpi
          titre="Flotte assurée"
          valeur={pourcent(assurances.couverts_pourcent)}
          ton={assurances.couverts_pourcent === null ? undefined : assurances.couverts_pourcent === 100 ? 'vert' : 'rouge'}
          detail={`${assurances.expirees} expirée(s) · ${assurances.absentes} sans assurance · ${assurances.a_renouveler_30_jours} à renouveler`}
        />
        <Kpi
          titre="Sinistres ouverts"
          valeur={ouverts}
          ton={sinistres.anciens_ouverts > 0 ? 'orange' : 'vert'}
          detail={`${sinistres.anciens_ouverts} depuis plus de 30 jours · ${sinistres.clos} clos`}
        />
        <Kpi
          titre="Litiges sociaux ouverts"
          valeur={litiges.ouverts}
          ton={litiges.critiques > 0 ? 'rouge' : litiges.ouverts > 0 ? 'orange' : 'vert'}
          detail={`${litiges.critiques} critique(s) · ${litiges.resolus_30_jours} résolu(s) sur 30 jours`}
        />
        <Kpi
          titre="Conformité de la flotte"
          valeur={pourcent(conformite.taux_pourcent)}
          detail={`${conformite.vehicules_non_conformes} véhicule(s) non conforme(s) · ${conformite.obligations_en_retard} obligation(s) en retard`}
          ton={conformite.taux_pourcent === null ? undefined : conformite.taux_pourcent >= 80 ? 'vert' : 'orange'}
        />
      </div>

      <p className="muted">
        Sinistres : {formatFCFA(sinistres.montant_estime_en_cours)} estimés sur les dossiers en cours, {formatFCFA(sinistres.montant_indemnise)}{' '}
        indemnisés
        {sinistres.delai_moyen_cloture_jours !== null && `, clôturés en moyenne en ${sinistres.delai_moyen_cloture_jours} jour(s)`}. Modèles de documents
        disponibles pour les autres pôles : {data.modeles_disponibles}.
      </p>

      {sinistres.recents.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Derniers sinistres</th>
                <th>Véhicule</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {sinistres.recents.map((s) => (
                <tr key={s.id}>
                  <td>
                    {formatDate(s.date)} — {s.description}
                  </td>
                  <td>{s.vehicule || '—'}</td>
                  <td>
                    <Badge ton={STATUTS_SINISTRE[s.statut].ton}>{STATUTS_SINISTRE[s.statut].libelle}</Badge>
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
