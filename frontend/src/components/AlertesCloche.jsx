import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { formatDateHeure } from '../lib/format.js'

const TON = { info: 'neutre', attention: 'orange', critique: 'rouge' }

/**
 * Cloche des alertes inter-pôles : celles adressées au poste de l'utilisateur (défaut de sécurité, départ bloqué
 * par le QHSE, panne, stock bas, pénurie…). Rafraîchie toute seule chaque minute ; chacun les marque lues pour lui.
 */
export default function AlertesCloche() {
  const [ouvert, setOuvert] = useState(false)
  const { data, recharger } = useChargement(() => apiFetch('/alertes/?limit=20'), { intervalleMs: 60000 })

  const nonLues = data?.non_lues ?? 0

  async function lire(alerte) {
    if (alerte.lue) return
    await apiFetch(`/alertes/${alerte.id}/lire/`, { method: 'POST' }).catch(() => {})
    await recharger()
  }

  async function toutLire() {
    await apiFetch('/alertes/lire-tout/', { method: 'POST' }).catch(() => {})
    await recharger()
  }

  return (
    <div className="cloche">
      <button
        type="button"
        className="cloche-bouton"
        aria-expanded={ouvert}
        aria-label={`Alertes, ${nonLues} non lue(s)`}
        onClick={() => setOuvert(!ouvert)}
      >
        Alertes
        {nonLues > 0 && <span className="cloche-compteur">{nonLues}</span>}
      </button>
      {ouvert && (
        <div className="cloche-panneau" role="region" aria-label="Alertes">
          <div className="cloche-entete">
            <strong>Alertes</strong>
            {nonLues > 0 && (
              <button type="button" className="button-secondary button-small" onClick={toutLire}>
                Tout marquer comme lu
              </button>
            )}
          </div>
          {(data?.alertes ?? []).length === 0 && <p className="muted">Aucune alerte.</p>}
          <ul className="cloche-liste">
            {(data?.alertes ?? []).map((alerte) => (
              <li key={alerte.id} className={alerte.lue ? 'alerte-lue' : 'alerte-non-lue'}>
                <button type="button" className="alerte-ligne" onClick={() => lire(alerte)}>
                  <span className={`badge badge-${TON[alerte.gravite] || 'neutre'}`}>{alerte.gravite}</span>
                  <span className="alerte-titre">{alerte.titre}</span>
                  {alerte.message && <span className="alerte-message">{alerte.message}</span>}
                  <span className="muted">{formatDateHeure(alerte.cree_le)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
