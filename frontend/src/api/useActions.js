import { useState } from 'react'

/**
 * Le geste d'un bouton ou d'un formulaire : lance la requête, affiche la confirmation (ou l'erreur du serveur), puis rafraîchit.
 * `apres` est appelé après un succès (recharger la liste, prévenir la page). `agir` renvoie true si la requête a abouti.
 */
export default function useActions(apres) {
  const [message, setMessage] = useState({ type: '', texte: '' })
  const [envoi, setEnvoi] = useState(false)

  async function agir(requete, confirmation) {
    setMessage({ type: '', texte: '' })
    setEnvoi(true)
    try {
      const resultat = await requete()
      if (apres) await apres(resultat)
      if (confirmation) {
        setMessage({ type: 'success', texte: typeof confirmation === 'function' ? confirmation(resultat) : confirmation })
      }
      return true
    } catch (err) {
      setMessage({ type: 'error', texte: err.message })
      return false
    } finally {
      setEnvoi(false)
    }
  }

  return { agir, envoi, message, setMessage }
}
