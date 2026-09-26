import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'

const DEGRES = { rupture: { libelle: 'Rupture', ton: 'rouge' }, critique: { libelle: 'Critique', ton: 'orange' }, a_prevoir: { libelle: 'À prévoir', ton: 'bleu' } }

/** Les pièces à commander d'après la consommation habituelle (90 jours) : sous le seuil, ou à moins d'un mois de la rupture. */
export default function SuggestionsCommande() {
  const { data: suggestions, error } = useChargement(() => apiFetch('/pieces/suggestions-commande/'), { intervalleMs: 300000 })

  return (
    <section className="card">
      <h2>Réapprovisionnement suggéré</h2>
      <Alert>{error}</Alert>
      {!suggestions ? (
        <p>Chargement…</p>
      ) : suggestions.length === 0 ? (
        <p className="muted">Aucune commande à passer : le stock couvre la consommation habituelle.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Pièce</th>
                <th>Stock</th>
                <th>Consommation (90 j)</th>
                <th>Jours de stock</th>
                <th>À commander</th>
                <th>Degré</th>
              </tr>
            </thead>
            <tbody>
              {suggestions.map((s) => (
                <tr key={s.piece} className={s.degre === 'rupture' ? 'row-danger' : ''}>
                  <td>
                    {s.nom} <span className="muted">({s.reference})</span>
                  </td>
                  <td>
                    {s.quantite_stock} / seuil {s.seuil_alerte}
                  </td>
                  <td>
                    {s.consommation_90_jours} ({s.consommation_par_jour} / j)
                  </td>
                  <td>{s.jours_restants === null ? '—' : `${s.jours_restants} j`}</td>
                  <td>
                    <strong>{s.quantite_suggeree}</strong>
                  </td>
                  <td>
                    <Badge ton={DEGRES[s.degre].ton}>{DEGRES[s.degre].libelle}</Badge>
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
