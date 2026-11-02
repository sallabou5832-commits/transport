import { useEffect, useState } from 'react'
import { appliquerPousse } from '../lib/carte.js'
import { API_BASE_URL, getAccessToken, obtenirJetonValide } from './client.js'

// `API_BASE_URL` porte le préfixe HTTP de l'API REST (`.../api`) ; les WebSocket de `channels` sont
// routées à la racine du serveur ASGI (voir `transpt1/dashboard/routing.py`), pas sous `/api`.
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws').replace(/\/api\/?$/, '')
const DELAI_RECONNEXION_MS = 5000

/**
 * Flux poussé des positions de la carte (`ws/dashboard/carte/`) : un relevé GPS reçu par le serveur
 * (`POST /api/positions/`) arrive ici sans attendre le prochain rafraîchissement périodique de
 * `CarteReseau` (qui reste un filet de sécurité, à un intervalle bien plus large — voir son
 * `useChargement`). Se reconnecte tout seul si la connexion tombe ; sans jeton, ou si le rôle n'a pas
 * le droit de voir la carte, le serveur refuse simplement la connexion — aucune erreur affichée,
 * `CarteReseau` continue de fonctionner par rafraîchissement périodique seul. Le serveur coupe la connexion d'un compte
 * suspendu ou dont le jeton a expiré (code 4401) ; la reconnexion, avec un jeton renouvelé, suit sans rien afficher.
 *
 * Renvoie la dernière position poussée par véhicule (`{ [idVehicule]: position }`), à combiner avec le
 * chargement HTTP par `fusionnerPositions` (`lib/carte.js`).
 */
export default function useFluxCarte() {
  const [positionsParVehicule, setPositionsParVehicule] = useState({})

  useEffect(() => {
    let arrete = false
    let socket
    let minuteur

    async function connecter() {
      if (arrete) return
      // Le serveur coupe la connexion quand son jeton expire (ou quand le compte est suspendu) : se reconnecter avec le
      // jeton d'origine échouerait en boucle, d'où un jeton renouvelé si besoin.
      const jeton = await obtenirJetonValide()
      if (arrete) return
      if (!jeton) {
        // Plus de session (jetons effacés) : on s'arrête ; sinon (réseau coupé pendant le renouvellement) on réessaie.
        if (getAccessToken()) minuteur = setTimeout(connecter, DELAI_RECONNEXION_MS)
        return
      }
      socket = new WebSocket(`${WS_BASE_URL}/ws/dashboard/carte/?token=${encodeURIComponent(jeton)}`)
      socket.onmessage = (evenement) => {
        setPositionsParVehicule((precedent) => appliquerPousse(precedent, JSON.parse(evenement.data)))
      }
      socket.onclose = () => {
        if (!arrete) minuteur = setTimeout(connecter, DELAI_RECONNEXION_MS)
      }
      socket.onerror = () => socket.close()
    }
    connecter()

    return () => {
      arrete = true
      clearTimeout(minuteur)
      socket?.close()
    }
  }, [])

  return positionsParVehicule
}
