import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDate, formatFCFA } from '../lib/format.js'
import { etatEcheance } from '../lib/finance.js'

/** L'échéancier des paiements aux fournisseurs et aux assureurs : ce qui reste à payer, le plus urgent d'abord. Lecture seule. */
export default function EcheancierFactures({ version = 0 }) {
  const { data, error } = useChargement(() => apiFetch('/factures/?statut=a_payer'), { cle: version, intervalleMs: 60000 })

  return (
    <section className="card">
      <h2>Échéancier des paiements</h2>
      <Alert>{error}</Alert>
      {data &&
        (data.length === 0 ? (
          <p className="muted">Aucune facture à payer.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Fournisseur</th>
                  <th>Objet</th>
                  <th>Montant</th>
                  <th>Échéance</th>
                  <th>Délai</th>
                </tr>
              </thead>
              <tbody>
                {data.map((facture) => {
                  const etat = etatEcheance(facture)
                  return (
                    <tr key={facture.id} className={facture.en_retard ? 'row-danger' : ''}>
                      <td>
                        {facture.fournisseur_nom}
                        <div className="muted">{facture.type_libelle}</div>
                      </td>
                      <td>{facture.libelle}</td>
                      <td className="montant">{formatFCFA(facture.montant)}</td>
                      <td>{formatDate(facture.echeance)}</td>
                      <td>
                        <Badge ton={etat.ton}>{etat.libelle}</Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ))}
    </section>
  )
}
