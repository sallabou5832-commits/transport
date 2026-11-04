import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { formatDateHeure, nouvellesAlertesCritiques } from '../lib/format.js'

const TON = { info: 'neutre', attention: 'orange', critique: 'rouge' }

/** Deux bips courts, joués par le navigateur lui-même (aucun fichier son à charger). */
function sonner() {
  try {
    const contexte = new AudioContext()
    ;[0, 0.25].forEach((debut) => {
      const oscillateur = contexte.createOscillator()
      const volume = contexte.createGain()
      oscillateur.frequency.value = 880
      volume.gain.value = 0.15
      oscillateur.connect(volume).connect(contexte.destination)
      oscillateur.start(contexte.currentTime + debut)
      oscillateur.stop(contexte.currentTime + debut + 0.15)
    })
  } catch {
    // Navigateur sans son, ou son bloqué tant que la page n'a pas été touchée : la cloche suffit.
  }
}

/**
 * Cloche des alertes inter-pôles : celles adressées au poste de l'utilisateur (défaut de sécurité, départ bloqué
 * par le QHSE, panne, stock bas, pénurie…). Rafraîchie toute seule chaque minute ; chacun les marque lues pour lui.
 */
export default function AlertesCloche() {
  // Le panneau se ferme comme un menu : la cloche de nouveau, Échap, un clic ailleurs, ou une autre page (il ne reste ouvert
  // que sur la page où il a été ouvert).
  const { pathname } = useLocation()
  const [ouvertSur, setOuvertSur] = useState(null)
  const ouvert = ouvertSur === pathname
  const racine = useRef(null)
  const { data, recharger } = useChargement(() => apiFetch('/alertes/?limit=20'), { intervalleMs: 60000 })
  // Les préférences de l'agent (« Mes paramètres ») : être prévenu d'une alerte critique par un son, ou par une notification
  // du navigateur quand l'onglet est en arrière-plan. Rien de réglé : la cloche seule, comme avant.
  const { data: preferences } = useChargement(() => apiFetch('/configuration/mes-preferences/'))
  const dejaVues = useRef(null)

  useEffect(() => {
    if (!data) return
    const nouvelles = nouvellesAlertesCritiques(dejaVues.current, data.alertes)
    dejaVues.current = new Set(data.alertes.map((alerte) => alerte.id))
    if (nouvelles.length === 0 || !preferences) return
    if (preferences.son_alertes) sonner()
    if (preferences.notifications_navigateur && document.hidden && window.Notification?.permission === 'granted') {
      nouvelles.forEach((alerte) => new window.Notification(alerte.titre, { body: alerte.message, tag: `alerte-${alerte.id}` }))
    }
  }, [data, preferences])

  useEffect(() => {
    if (!ouvert) return undefined
    const fermer = () => setOuvertSur(null)
    const surTouche = (evenement) => evenement.key === 'Escape' && fermer()
    const surClic = (evenement) => !racine.current?.contains(evenement.target) && fermer()
    document.addEventListener('keydown', surTouche)
    document.addEventListener('pointerdown', surClic)
    return () => {
      document.removeEventListener('keydown', surTouche)
      document.removeEventListener('pointerdown', surClic)
    }
  }, [ouvert])

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
    <div className="cloche" ref={racine}>
      <button
        type="button"
        className="cloche-bouton"
        aria-expanded={ouvert}
        aria-label={`Alertes, ${nonLues} non lue(s)`}
        onClick={() => setOuvertSur(ouvert ? null : pathname)}
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
