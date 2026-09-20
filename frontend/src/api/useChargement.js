import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Charge des données au montage de la page, avec état de chargement et d'erreur.
 *
 * `chargeur` est une fonction qui renvoie une promesse (typiquement un `Promise.all` d'appels
 * `apiFetch`). `recharger()` la rejoue sans afficher l'écran de chargement, ce qui sert aussi
 * après une action (« marquer traité », « réaffecter »…).
 *
 * Options : `intervalleMs` rafraîchit la page toute seule (l'effet « temps réel » des tableaux
 * de bord) ; `cle` relance le chargement quand sa valeur change (ex. la période choisie).
 */
export default function useChargement(chargeur, { intervalleMs = 0, cle = '' } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  // Le chargeur est recréé à chaque rendu : on garde toujours le dernier sans relancer les effets.
  const chargeurRef = useRef(chargeur)
  useEffect(() => {
    chargeurRef.current = chargeur
  })

  const recharger = useCallback(() => {
    return chargeurRef
      .current()
      .then((resultat) => {
        setData(resultat)
        setError('')
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    recharger()
    if (!intervalleMs) return undefined
    const minuteur = setInterval(recharger, intervalleMs)
    return () => clearInterval(minuteur)
  }, [recharger, intervalleMs, cle])

  return { data, error, loading, recharger }
}
