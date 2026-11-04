/** Le poste dont la fiche s'affiche : celui demandé dans l'adresse s'il existe, sinon celui du lecteur, sinon le premier. */
export function posteAffiche(guide, demande) {
  const postes = guide.poles.flatMap((pole) => pole.postes.map((fiche) => fiche.poste))
  if (postes.includes(demande)) return demande
  if (postes.includes(guide.mon_poste)) return guide.mon_poste
  return postes[0]
}

/** Les tâches regroupées par moment de la journée, dans l'ordre des moments ; un moment sans tâche n'apparaît pas. */
export function tachesParMoment(taches, moments) {
  return moments
    .map((moment) => ({ ...moment, taches: taches.filter((tache) => tache.moment === moment.code) }))
    .filter((moment) => moment.taches.length > 0)
}
