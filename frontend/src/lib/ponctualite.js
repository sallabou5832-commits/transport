// Même règle que le serveur (transpt1/dashboard/views.py, TOLERANCE_RETARD) : un départ est
// « à l'heure » s'il a lieu au plus tard 10 minutes après l'heure prévue.
export const TOLERANCE_RETARD_MINUTES = 10

/** « a_l_heure », « en_retard » ou « en_attente » pour une feuille de route. */
export function statutFeuille(feuille, maintenant = new Date()) {
  const limite = new Date(feuille.heure_depart_prevue).getTime() + TOLERANCE_RETARD_MINUTES * 60000
  if (feuille.heure_depart_reelle) {
    return new Date(feuille.heure_depart_reelle).getTime() <= limite ? 'a_l_heure' : 'en_retard'
  }
  // Non démarrée : en retard dès que la tolérance est dépassée, sans attendre que le départ ait lieu.
  return maintenant.getTime() > limite ? 'en_retard' : 'en_attente'
}

export function retardMinutes(feuille, maintenant = new Date()) {
  const fin = feuille.heure_depart_reelle ? new Date(feuille.heure_depart_reelle) : maintenant
  return Math.max(0, Math.floor((fin - new Date(feuille.heure_depart_prevue)) / 60000))
}
