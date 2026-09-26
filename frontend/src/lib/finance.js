export const CATEGORIES_DEPENSE = {
  carburant: 'Carburant',
  maintenance: 'Maintenance',
  salaires: 'Salaires',
  assurance: 'Assurance',
  fournisseur: 'Achats et fournisseurs',
  autre: 'Autre',
}

const iso = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`

/** « AAAA-MM-01 » du mois en cours, décalé de `decalageMois` (−1 : le mois dernier). */
export function premierJourDuMois(decalageMois = 0, aujourdhui = new Date()) {
  return iso(new Date(aujourdhui.getFullYear(), aujourdhui.getMonth() + decalageMois, 1))
}

/** Dernier jour du mois en cours, décalé de `decalageMois` (« AAAA-MM-JJ »). */
export function dernierJourDuMois(decalageMois = 0, aujourdhui = new Date()) {
  return iso(new Date(aujourdhui.getFullYear(), aujourdhui.getMonth() + decalageMois + 1, 0))
}

/** « AAAA-MM » : la valeur d'un champ `<input type="month">` pour le mois en cours. */
export const moisCourant = (aujourdhui = new Date()) => premierJourDuMois(0, aujourdhui).slice(0, 7)

/** Le champ mois « AAAA-MM » ramené au premier jour du mois, tel que l'API l'attend. */
export const jourDuMois = (mois) => `${mois}-01`

/** L'état d'une facture à payer d'après le temps qu'il reste : en retard, à payer sous 7 jours, ou plus tard. */
export function etatEcheance(facture) {
  if (facture.en_retard) return { libelle: `En retard de ${-facture.jours_restants} j`, ton: 'rouge' }
  const jours = facture.jours_restants
  if (jours <= 7) return { libelle: jours === 0 ? "Aujourd'hui" : `Dans ${jours} j`, ton: 'orange' }
  return { libelle: `Dans ${jours} j`, ton: 'vert' }
}
