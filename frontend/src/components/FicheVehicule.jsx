import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from './Alert.jsx'
import Badge from './Badge.jsx'
import { LABELS_VEHICULE, TON_VEHICULE, formatDate, formatDateHeure } from '../lib/format.js'

const ETATS = { a_jour: { libelle: 'À jour', ton: 'vert' }, bientot: { libelle: 'Bientôt dû', ton: 'orange' }, en_retard: { libelle: 'En retard', ton: 'rouge' } }
const STATUTS = { ouvert: 'Ouvert', en_cours: 'En cours', termine: 'Terminé' }

function Fiche({ vehiculeId }) {
  const { data: fiche, error } = useChargement(() => apiFetch(`/fiche-vehicule/${vehiculeId}/`), { cle: vehiculeId })

  if (!fiche) return <Alert>{error}</Alert>
  const { vehicule, plans_entretien: plans, ordres, pieces_montees: pieces, pannes_recurrentes: pannes, indicateurs } = fiche

  return (
    <div>
      <Alert>{error}</Alert>
      <p>
        <strong>{vehicule.immatriculation}</strong> · {vehicule.capacite} places · {vehicule.kilometrage.toLocaleString('fr-FR')} km ·{' '}
        {vehicule.gare ?? 'sans gare d’attache'}{' '}
        <Badge ton={TON_VEHICULE[vehicule.statut]}>{LABELS_VEHICULE[vehicule.statut]}</Badge>
      </p>
      <ul className="stat-list">
        <li>
          <span>Réparations sur 12 mois</span>
          <strong>{indicateurs.ordres_12_mois}</strong>
        </li>
        <li>
          <span>Jours d&apos;immobilisation sur 12 mois</span>
          <strong>{indicateurs.jours_immobilise_12_mois} j</strong>
        </li>
        <li>
          <span>Pannes déclarées (90 jours)</span>
          <strong>{indicateurs.pannes_declarees_90_jours}</strong>
        </li>
      </ul>

      <h2 style={{ marginTop: '1rem' }}>Pannes récurrentes</h2>
      {pannes.length === 0 ? (
        <p className="muted">Aucune pièce remplacée plusieurs fois en {indicateurs.fenetre_panne_recurrente_jours} jours.</p>
      ) : (
        <ul className="stat-list">
          {pannes.map((p) => (
            <li key={p.piece}>
              <span>{p.nom}</span>
              <Badge ton="rouge">{p.interventions} remplacements</Badge>
            </li>
          ))}
        </ul>
      )}

      <h2 style={{ marginTop: '1rem' }}>Entretiens à venir</h2>
      {plans.length === 0 ? (
        <p className="muted">Aucun plan d&apos;entretien.</p>
      ) : (
        <ul className="stat-list">
          {plans.map((p) => (
            <li key={p.id}>
              <span>
                {p.libelle}
                <span className="muted">
                  {' '}
                  — {p.prochaine_date ? formatDate(p.prochaine_date) : ''}
                  {p.prochain_km ? ` ${p.prochain_km.toLocaleString('fr-FR')} km` : ''}
                </span>
              </span>
              <Badge ton={ETATS[p.etat].ton}>{ETATS[p.etat].libelle}</Badge>
            </li>
          ))}
        </ul>
      )}

      <h2 style={{ marginTop: '1rem' }}>Pièces montées</h2>
      {pieces.length === 0 ? (
        <p className="muted">Aucune pièce sortie pour ce véhicule.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Pièce</th>
                <th>Quantité</th>
                <th>Interventions</th>
                <th>Dernière sortie</th>
              </tr>
            </thead>
            <tbody>
              {pieces.map((p) => (
                <tr key={p.piece}>
                  <td>
                    {p.nom} <span className="muted">({p.reference})</span>
                  </td>
                  <td>{p.quantite}</td>
                  <td>{p.interventions}</td>
                  <td>{formatDateHeure(p.derniere_sortie)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 style={{ marginTop: '1rem' }}>Historique des interventions</h2>
      {ordres.length === 0 ? (
        <p className="muted">Aucune intervention.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Ouvert le</th>
                <th>Intervention</th>
                <th>Intervenant</th>
                <th>Statut</th>
                <th>Temps passé</th>
              </tr>
            </thead>
            <tbody>
              {ordres.map((o) => (
                <tr key={o.id}>
                  <td>{formatDateHeure(o.date_creation)}</td>
                  <td>
                    {o.description} {o.preventif && <Badge ton="bleu">Préventif</Badge>}
                  </td>
                  <td>{o.mecanicien_nom}</td>
                  <td>{STATUTS[o.statut]}</td>
                  <td>{o.temps_passe_minutes ? `${o.temps_passe_minutes} min` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** La fiche complète d'un véhicule : historique, pièces montées, pannes récurrentes, entretiens à venir. */
export default function FicheVehicule() {
  const [vehiculeId, setVehiculeId] = useState('')
  const { data: vehicules, error } = useChargement(() => apiFetch('/vehicules/'))

  return (
    <section className="card">
      <h2>Fiche véhicule</h2>
      <Alert>{error}</Alert>
      <div className="toolbar">
        <label>
          Véhicule à consulter
          <select value={vehiculeId} onChange={(e) => setVehiculeId(e.target.value)}>
            <option value="">— Choisir —</option>
            {(vehicules ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.immatriculation}
              </option>
            ))}
          </select>
        </label>
      </div>
      {vehiculeId && <Fiche vehiculeId={vehiculeId} />}
    </section>
  )
}
