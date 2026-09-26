// Fusion des positions de la carte : le chargement HTTP périodique (`GET /dashboard/carte/`, voir
// `useChargement` dans `CarteReseau.jsx`) reste la seule source pour la liste des cars en route (un
// car qui vient de partir ou d'arriver n'apparaît/ne disparaît qu'à ce rafraîchissement) ; le flux
// poussé par WebSocket (`useFluxCarte.js`) n'améliore que la fraîcheur de la position de chaque car déjà
// listé, entre deux rafraîchissements — jamais l'ensemble affiché.

/** Ajoute ou remplace, par identifiant de véhicule, la position poussée la plus récente (immuable). */
export function appliquerPousse(positionsParVehicule, position) {
  return { ...positionsParVehicule, [position.vehicule]: position }
}

/**
 * Les véhicules de `vehiculesHttp`, avec la position la plus récente entre celle du chargement HTTP et
 * celle poussée par WebSocket pour ce véhicule (`positionsParVehicule`, voir `appliquerPousse`). Un
 * véhicule absent de `vehiculesHttp` (trajet terminé) ne réapparaît jamais, même si une position poussée
 * pour lui traîne encore dans `positionsParVehicule`.
 */
export function fusionnerPositions(vehiculesHttp, positionsParVehicule) {
  return vehiculesHttp.map((vehicule) => {
    const poussee = positionsParVehicule[vehicule.vehicule]
    if (!poussee) return vehicule
    return new Date(poussee.releve_le) > new Date(vehicule.releve_le) ? { ...vehicule, ...poussee } : vehicule
  })
}
