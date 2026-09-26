// Libellés et tons des états RH et juridiques, tels que le serveur les nomme.

export const STATUTS_CONGE = {
  en_attente: { libelle: 'En attente', ton: 'orange' },
  approuve: { libelle: 'Approuvé', ton: 'vert' },
  refuse: { libelle: 'Refusé', ton: 'rouge' },
  annule: { libelle: 'Annulé', ton: 'neutre' },
}

export const TYPES_CONGE = {
  annuel: 'Congé annuel',
  maladie: 'Maladie',
  famille: 'Événement familial, maternité ou paternité',
  sans_solde: 'Sans solde',
  autre: 'Autre',
}

export const ETATS_FORMATION = {
  a_jour: { libelle: 'À jour', ton: 'vert' },
  a_renouveler: { libelle: 'À renouveler', ton: 'orange' },
  expiree: { libelle: 'Expirée', ton: 'rouge' },
  manquante: { libelle: 'Manquante', ton: 'rouge' },
}

export const NIVEAUX_IMPACT = {
  ok: { libelle: 'Sans risque', ton: 'vert' },
  tendu: { libelle: 'Tendu', ton: 'orange' },
  critique: { libelle: 'Critique', ton: 'rouge' },
}

export const GRAVITES_DOLEANCE = {
  faible: { libelle: 'Faible', ton: 'neutre' },
  moyenne: { libelle: 'Moyenne', ton: 'bleu' },
  grave: { libelle: 'Grave', ton: 'orange' },
  critique: { libelle: 'Critique', ton: 'rouge' },
}

export const STATUTS_DOLEANCE = {
  deposee: { libelle: 'Déposée', ton: 'orange' },
  en_mediation: { libelle: 'En médiation', ton: 'bleu' },
  resolue: { libelle: 'Résolue', ton: 'vert' },
  sans_suite: { libelle: 'Classée sans suite', ton: 'neutre' },
}

export const TYPES_CONTRAT = { cdi: 'CDI', cdd: 'CDD', journalier: 'Journalier / occasionnel', stage: 'Stage' }
export const TYPES_MESURE = { avertissement: 'Avertissement', blame: 'Blâme', mise_a_pied: 'Mise à pied', autre: 'Autre' }

export const STATUTS_OFFRE = { ouverte: 'Ouverte', pourvue: 'Pourvue', cloturee: 'Clôturée' }
export const STATUTS_CANDIDATURE = {
  recue: 'Reçue',
  preselectionnee: 'Présélectionnée',
  entretien: 'En entretien',
  retenue: 'Retenue',
  refusee: 'Refusée',
}

export const CATEGORIES_MODELE = {
  travail: 'Contrats et documents de travail',
  sinistre: 'Assurance et sinistres',
  commercial: 'Conditions de transport et clients',
  courrier: 'Courriers types',
  reglement: 'Règlements et chartes',
  autre: 'Autre',
}

export const POLES = {
  direction: 'Direction Générale',
  exploitation: 'Exploitation & Réseau',
  roulant: 'Personnel roulant',
  technique: 'Technique & Maintenance',
  supports: 'Fonctions supports',
}

export const STATUTS_SINISTRE = {
  ouvert: { libelle: 'Ouvert', ton: 'rouge' },
  en_cours: { libelle: 'En cours', ton: 'orange' },
  clos: { libelle: 'Clos', ton: 'vert' },
}

/** Taille lisible d'un fichier (« 1,4 Mo »). */
export function formatTaille(octets) {
  if (octets === null || octets === undefined) return ''
  if (octets < 1024) return `${octets} o`
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`
  return `${(octets / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`
}
