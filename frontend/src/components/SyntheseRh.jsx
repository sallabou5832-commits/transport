import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Kpi from './Kpi.jsx'

/** Les chiffres de la gestion RH d'un coup d'œil : effectif, formations, congés, recrutement, médiation, contrats à terme. Lecture seule. */
export default function SyntheseRh() {
  const { data, error } = useChargement(() => apiFetch('/rh/synthese/'), { intervalleMs: 60000 })

  if (!data) return <Alert>{error}</Alert>
  const { effectif, formations, conges, recrutement, mediation, contrats } = data
  const aRenouveler = formations.expiree + formations.a_renouveler

  return (
    <div className="cards-grid">
      <Kpi titre="Effectif actif" valeur={effectif.total} ton="vert" detail="comptes utilisateurs actifs" />
      <Kpi
        titre="Formations à renouveler"
        valeur={aRenouveler}
        ton={formations.expiree > 0 ? 'rouge' : aRenouveler > 0 ? 'orange' : 'vert'}
        detail={`${formations.expiree} expirée(s) · ${formations.manquante} manquante(s)`}
      />
      <Kpi
        titre="Congés à traiter"
        valeur={conges.en_attente}
        ton={conges.en_attente > 0 ? 'orange' : 'vert'}
        detail={`${conges.en_cours} en cours · ${conges.a_venir_30_jours} à venir sous 30 jours`}
      />
      <Kpi
        titre="Recrutement"
        valeur={recrutement.offres_ouvertes}
        detail={`offre(s) ouverte(s) · ${recrutement.candidatures_a_traiter} candidature(s) à traiter`}
      />
      <Kpi
        titre="Doléances ouvertes"
        valeur={mediation.ouvertes}
        ton={mediation.litiges > 0 ? 'rouge' : mediation.a_traiter > 0 ? 'orange' : 'vert'}
        detail={`${mediation.a_traiter} à traiter · ${mediation.litiges} risque(s) de litige`}
      />
      <Kpi
        titre="Contrats à terme sous 30 jours"
        valeur={contrats.a_terme}
        ton={contrats.a_terme > 0 ? 'orange' : 'vert'}
        detail="CDD, stages et contrats journaliers"
      />
    </div>
  )
}
