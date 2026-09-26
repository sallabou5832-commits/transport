import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatFCFA } from '../lib/format.js'
import { jourDuMois, moisCourant } from '../lib/finance.js'

const ETATS = {
  ok: { libelle: 'Dans le budget', ton: 'vert' },
  alerte: { libelle: 'Plus de 80 %', ton: 'orange' },
  depasse: { libelle: 'Dépassé', ton: 'rouge' },
  sans_budget: { libelle: 'Sans budget', ton: 'neutre' },
}

/**
 * Budget carburant par ligne pour un mois : prévu, dépensé, reste, et l'état (la finance et le PDG sont alertés à 80 % puis
 * au dépassement). Lecture seule ; `version` recharge le suivi après une saisie faite ailleurs sur la page.
 */
export default function SuiviBudgetCarburant({ version = 0 }) {
  const [mois, setMois] = useState(moisCourant())
  const { data, error } = useChargement(() => apiFetch(`/finance/budget-carburant/?mois=${jourDuMois(mois || moisCourant())}`), {
    cle: `${mois}|${version}`,
    intervalleMs: 60000,
  })

  return (
    <section className="card">
      <h2>Budget carburant par ligne</h2>
      <div className="toolbar no-print">
        <label>
          Mois
          <input type="month" value={mois} onChange={(e) => setMois(e.target.value)} />
        </label>
      </div>
      <Alert>{error}</Alert>
      {data &&
        (data.lignes.length === 0 ? (
          <p className="muted">Aucun budget ni dépense de carburant sur ce mois.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Ligne</th>
                  <th>Budget</th>
                  <th>Dépensé</th>
                  <th>Reste</th>
                  <th>Consommation</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {data.lignes.map((ligne) => (
                  <tr key={ligne.ligne} className={ligne.etat === 'depasse' ? 'row-danger' : ligne.etat === 'alerte' ? 'row-alerte' : ''}>
                    <td>{ligne.nom}</td>
                    <td className="montant">{ligne.budget === null ? '—' : formatFCFA(ligne.budget)}</td>
                    <td className="montant">{formatFCFA(ligne.realise)}</td>
                    <td className="montant">{ligne.reste === null ? '—' : formatFCFA(ligne.reste)}</td>
                    <td>
                      {ligne.pourcentage === null ? (
                        '—'
                      ) : (
                        <span className="consommation">
                          <span className="consommation-piste">
                            <span
                              className={`consommation-barre consommation-${ligne.etat}`}
                              style={{ width: `${Math.min(100, ligne.pourcentage)}%` }}
                            />
                          </span>
                          {ligne.pourcentage} %
                        </span>
                      )}
                    </td>
                    <td>
                      <Badge ton={ETATS[ligne.etat].ton}>{ETATS[ligne.etat].libelle}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </section>
  )
}
