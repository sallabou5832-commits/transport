import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

const TON_URGENCE = { critique: 'rouge', haute: 'orange', normale: 'neutre', basse: 'bleu' }
const LIBELLES_URGENCE = { critique: 'Critique', haute: 'Haute', normale: 'Normale', basse: 'Basse' }

/** Pour la régulation : les véhicules immobilisés à l'atelier et la date de retour estimée, à prendre en compte au planning. */
export default function VehiculesAtelier() {
  const { data: ordres, error } = useChargement(() => apiFetch('/ordres-reparation/file-attente/'), { intervalleMs: 60000 })

  if (!ordres) return <Alert>{error}</Alert>

  return (
    <section className="card">
      <h2>Véhicules à l&apos;atelier</h2>
      <Alert>{error}</Alert>
      {ordres.length === 0 ? (
        <p className="muted">Aucun véhicule à l&apos;atelier.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Véhicule</th>
                <th>Réparation</th>
                <th>Urgence</th>
                <th>Retour estimé</th>
              </tr>
            </thead>
            <tbody>
              {ordres.map((ordre) => (
                <tr key={ordre.id}>
                  <td>{ordre.vehicule_immatriculation}</td>
                  <td>{ordre.description}</td>
                  <td>
                    <Badge ton={TON_URGENCE[ordre.urgence]}>{LIBELLES_URGENCE[ordre.urgence]}</Badge>
                  </td>
                  <td>{ordre.retour_estime ? formatDateHeure(ordre.retour_estime) : 'Non estimé'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
