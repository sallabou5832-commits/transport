import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { formatDateHeure } from '../lib/format.js'

const TONS_STATUT = { envoye: 'bleu', recu: 'orange', traite: 'vert' }

/** Le contenu d'un flux en une ligne lisible : ses champs, sans la mécanique du format d'échange. */
function resume(contenu) {
  return Object.entries(contenu || {})
    .filter(([, valeur]) => valeur !== null && valeur !== '' && typeof valeur !== 'object')
    .slice(0, 5)
    .map(([cle, valeur]) => `${cle.replaceAll('_', ' ')} : ${valeur}`)
    .join(' · ')
}

/**
 * Les échanges avec la tutelle (Ministère des Transports, OSER, AMUGA, OFT) : ce qui part vers elle (incident grave, assurance à
 * échéance) et ce qu'elle envoie (une nouvelle norme de conformité). Le QHSE et le responsable juridique marquent un flux traité
 * et rattrapent les flux automatiques pas encore générés (jamais de doublon).
 */
export default function EchangesTutelle() {
  const [direction, setDirection] = useState('')
  const { data: flux, error, recharger } = useChargement(
    () => apiFetch(`/flux-tutelle/?direction=${direction}`), // vide : tous les sens
    { cle: direction },
  )
  const { agir, envoi, message } = useActions(recharger)

  return (
    <section className="card">
      <h2>Échanges avec la tutelle</h2>
      <Alert>{error}</Alert>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="toolbar">
        <label>
          Sens
          <select value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="">Tous</option>
            <option value="vers_tutelle">Vers la tutelle</option>
            <option value="vers_compagnie">Reçus de la tutelle</option>
          </select>
        </label>
        <button
          type="button"
          className="button-secondary"
          disabled={envoi}
          onClick={() =>
            agir(
              () => apiFetch('/tutelle/generer/', { method: 'POST' }),
              (crees) => `Flux rattrapés : ${crees.securite} de sécurité, ${crees.conformite} de conformité.`,
            )
          }
        >
          Rattraper les flux automatiques
        </button>
      </div>
      {!flux ? null : flux.length === 0 ? (
        <p>Aucun échange.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Flux</th>
                <th>Contenu</th>
                <th>État</th>
              </tr>
            </thead>
            <tbody>
              {flux.slice(0, 30).map((f) => (
                <tr key={f.id}>
                  <td>{formatDateHeure(f.date)}</td>
                  <td>
                    {f.type_libelle}
                    <div className="muted">{f.direction_libelle}</div>
                  </td>
                  <td className="muted">{resume(f.contenu)}</td>
                  <td>
                    <Badge ton={TONS_STATUT[f.statut]}>{f.statut_libelle}</Badge>{' '}
                    {f.statut !== 'traite' && (
                      <button
                        type="button"
                        className="button-small"
                        disabled={envoi}
                        onClick={() => agir(() => apiFetch(`/flux-tutelle/${f.id}/traiter/`, { method: 'POST' }), 'Flux marqué traité.')}
                      >
                        Marquer traité
                      </button>
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
