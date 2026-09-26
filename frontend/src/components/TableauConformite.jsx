import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import Kpi from './Kpi.jsx'
import { formatDate } from '../lib/format.js'

const ETATS_ASSURANCE = {
  valide: { libelle: 'Valide', ton: 'vert' },
  bientot: { libelle: 'Bientôt échue', ton: 'orange' },
  expiree: { libelle: 'Expirée', ton: 'rouge' },
  absente: { libelle: 'Absente', ton: 'rouge' },
}
const ETATS_OBLIGATION = { a_jour: { libelle: 'À jour', ton: 'vert' }, bientot: { libelle: 'Bientôt dû', ton: 'orange' }, en_retard: { libelle: 'En retard', ton: 'rouge' } }

/**
 * Tableau de conformité réglementaire de la flotte, partagé par le QHSE et le juridique : assurance, obligations (contrôle technique,
 * visite…), défauts de sécurité ouverts et blocages, véhicule par véhicule. Les obligations se déclarent dans le plan d'entretien
 * (case « obligation réglementaire »).
 */
export default function TableauConformite() {
  const { data, error } = useChargement(() => apiFetch('/conformite/'), { intervalleMs: 300000 })

  if (!data) return <Alert>{error}</Alert>
  const { resume, vehicules } = data
  const taux = resume.taux_conformite_pourcent

  return (
    <section>
      <Alert>{error}</Alert>
      <div className="cards-grid">
        <Kpi
          titre="Conformité de la flotte"
          valeur={taux === null ? '—' : `${taux} %`}
          detail={`${resume.conformes} véhicule(s) conforme(s) sur ${resume.vehicules}`}
          ton={taux === null ? undefined : taux >= 90 ? 'vert' : taux >= 70 ? 'orange' : 'rouge'}
        />
        <Kpi
          titre="Assurances à traiter"
          valeur={resume.assurances_expirees + resume.assurances_absentes}
          ton={resume.assurances_expirees + resume.assurances_absentes > 0 ? 'rouge' : 'vert'}
          detail={`${resume.assurances_expirees} expirée(s) · ${resume.assurances_absentes} absente(s) · ${resume.assurances_bientot_echues} bientôt échue(s)`}
        />
        <Kpi
          titre="Obligations réglementaires en retard"
          valeur={resume.obligations_en_retard}
          ton={resume.obligations_en_retard > 0 ? 'rouge' : 'vert'}
          detail={`${resume.obligations_bientot_dues} bientôt due(s) · ${resume.vehicules_sans_obligation_declaree} véhicule(s) sans obligation déclarée`}
        />
        <Kpi titre="Véhicules bloqués" valeur={resume.vehicules_bloques} ton={resume.vehicules_bloques > 0 ? 'rouge' : 'vert'} />
      </div>
      {vehicules.length === 0 ? (
        <p>Aucun véhicule.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Véhicule</th>
                <th>Assurance</th>
                <th>Obligations réglementaires</th>
                <th>Sécurité</th>
                <th>Conformité</th>
              </tr>
            </thead>
            <tbody>
              {vehicules.map((v) => (
                <tr key={v.vehicule} className={v.conforme ? '' : 'row-danger'}>
                  <td>{v.immatriculation}</td>
                  <td>
                    <Badge ton={ETATS_ASSURANCE[v.assurance.etat].ton}>{ETATS_ASSURANCE[v.assurance.etat].libelle}</Badge>
                    {v.assurance.date_echeance && <div className="muted">jusqu&apos;au {formatDate(v.assurance.date_echeance)}</div>}
                  </td>
                  <td>
                    {v.obligations.length === 0 ? (
                      <span className="muted">Aucune déclarée</span>
                    ) : (
                      v.obligations.map((o) => (
                        <div key={o.plan}>
                          {o.libelle} <Badge ton={ETATS_OBLIGATION[o.etat].ton}>{ETATS_OBLIGATION[o.etat].libelle}</Badge>
                        </div>
                      ))
                    )}
                  </td>
                  <td>
                    {v.bloque ? <Badge ton="rouge">Bloqué</Badge> : <Badge ton="vert">Roulant</Badge>}
                    {v.defauts_ouverts > 0 && <div className="muted">{v.defauts_ouverts} défaut(s) de checklist</div>}
                  </td>
                  <td>
                    {v.conforme ? (
                      <Badge ton="vert">Conforme</Badge>
                    ) : (
                      <ul className="motifs">
                        {v.motifs.map((motif) => (
                          <li key={motif}>{motif}</li>
                        ))}
                      </ul>
                    )}
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
