export const ALL_ROLES = [
  'superadmin',
  'pdg',
  'secretaire_general',
  'qhse',
  'directeur_exploitation',
  'chef_gare',
  'chef_ligne',
  'guichetier',
  'bagagiste',
  'chauffeur_principal',
  'chauffeur_relais',
  'controleur_ligne',
  'directeur_technique',
  'magasinier',
  'chef_atelier',
  'mecanicien',
  'drh',
  'directeur_financier',
  'responsable_juridique',
]

export const ROLE_LABELS = {
  pdg: 'PDG',
  secretaire_general: 'Secrétaire général',
  qhse: 'QHSE',
  directeur_exploitation: 'Directeur exploitation',
  chef_gare: 'Chef de gare',
  chef_ligne: 'Chef de ligne',
  guichetier: 'Guichetier',
  bagagiste: 'Bagagiste',
  chauffeur_principal: 'Chauffeur principal',
  chauffeur_relais: 'Chauffeur relais',
  controleur_ligne: 'Contrôleur de ligne',
  directeur_technique: 'Directeur technique',
  magasinier: 'Magasinier',
  chef_atelier: "Chef d'atelier",
  mecanicien: 'Mécanicien / électricien auto',
  drh: 'DRH',
  directeur_financier: 'Directeur financier',
  responsable_juridique: 'Responsable juridique',
  superadmin: 'Super administrateur',
}

// Un tableau de bord par poste. Les rôles de chaque page sont aussi ceux que
// role_coverage_tests/test_contrat_frontend.py confronte aux permissions de l'API.
export const DASHBOARD_ROLES = {
  '/dashboard/direction': ['pdg', 'secretaire_general'],
  '/dashboard/qhse': ['qhse'],
  '/dashboard/exploitation': ['directeur_exploitation'],
  '/dashboard/gare': ['chef_gare'],
  '/dashboard/ligne': ['chef_ligne'],
  '/dashboard/guichetier': ['guichetier'],
  '/dashboard/bagagiste': ['bagagiste'],
  '/dashboard/chauffeur': ['chauffeur_principal', 'chauffeur_relais'],
  '/dashboard/controle': ['controleur_ligne'],
  '/dashboard/technique': ['directeur_technique'],
  '/dashboard/magasinier': ['magasinier'],
  '/dashboard/atelier': ['chef_atelier'],
  '/dashboard/mecanicien': ['mecanicien'],
  '/dashboard/rh': ['drh'],
  '/dashboard/finance': ['directeur_financier'],
  '/dashboard/juridique': ['responsable_juridique'],
  '/dashboard/plateforme': ['superadmin'],
}

// Pages accessibles en plus du tableau de bord propre à chaque poste (elles ne comptent pas dans « un tableau de
// bord par rôle »). Le journal d'audit : traçabilité pour l'audit et la conformité, réservée à la direction et au QHSE.
export const PAGES_ANNEXES = {
  '/audit': ['pdg', 'secretaire_general', 'qhse', 'superadmin'],
  // Configuration hiérarchique : chaque échelon règle les postes placés directement sous son autorité.
  '/configuration': ['pdg', 'directeur_exploitation', 'chef_gare', 'chef_ligne', 'directeur_technique', 'chef_atelier'],
  '/cadre': ['pdg'],
  // Pouvoirs d'intervention directe du PDG : geler une ligne, valider les investissements, suspendre un compte.
  '/pilotage': ['pdg'],
  // Demander un investissement (achat de cars, ouverture de ligne) : le PDG décide.
  '/investissements': ['directeur_technique', 'directeur_exploitation', 'directeur_financier'],
  // Secrétariat de la direction : notes de service aux pôles, agenda partagé, classement et archivage.
  '/secretariat': ['secretaire_general', 'pdg'],
  // Comptabilité : la finance saisit les dépenses, budgets et factures ; le PDG et son secrétaire général lisent la situation.
  '/comptabilite': ['directeur_financier'],
  '/finances': ['pdg', 'secretaire_general'],
  // Mon espace : congés, formations obligatoires et médiation sociale, pour tout poste de la compagnie.
  '/espace': [
    'pdg', 'secretaire_general', 'qhse', 'directeur_exploitation', 'chef_gare', 'chef_ligne', 'guichetier', 'bagagiste',
    'chauffeur_principal', 'chauffeur_relais', 'controleur_ligne', 'directeur_technique', 'magasinier', 'chef_atelier',
    'mecanicien', 'drh', 'directeur_financier', 'responsable_juridique',
  ],
  // La bibliothèque de modèles de documents juridiques, ouverte aux autres pôles.
  '/modeles': [
    'pdg', 'secretaire_general', 'qhse', 'directeur_exploitation', 'chef_gare', 'chef_ligne', 'guichetier', 'bagagiste',
    'chauffeur_principal', 'chauffeur_relais', 'controleur_ligne', 'directeur_technique', 'magasinier', 'chef_atelier',
    'mecanicien', 'drh', 'directeur_financier', 'responsable_juridique',
  ],
  // Ce que la Direction Générale lit des fonctions supports : situation juridique et gestion RH.
  '/synthese': ['pdg', 'secretaire_general'],
  // Les notes de service adressées au poste : tous les postes d'une compagnie (elles arrivent aussi dans la cloche).
  '/notes': [
    'pdg', 'secretaire_general', 'qhse', 'directeur_exploitation', 'chef_gare', 'chef_ligne', 'guichetier', 'bagagiste',
    'chauffeur_principal', 'chauffeur_relais', 'controleur_ligne', 'directeur_technique', 'magasinier', 'chef_atelier',
    'mecanicien', 'drh', 'directeur_financier', 'responsable_juridique',
  ],
}

export const LIBELLES_PAGES_ANNEXES = {
  '/audit': "Journal d'audit",
  '/configuration': 'Configuration',
  '/cadre': 'Cadre de la compagnie',
  '/pilotage': 'Pilotage',
  '/investissements': 'Investissements',
  '/secretariat': 'Secrétariat',
  '/comptabilite': 'Comptabilité',
  '/finances': 'Finances',
  '/espace': 'Mon espace',
  '/modeles': 'Modèles juridiques',
  '/synthese': 'Synthèse RH et juridique',
  '/notes': 'Notes de service',
}

// Repli pour un rôle inconnu du frontend (ex. rôle ajouté côté serveur) : la page générique
// est ouverte à tout utilisateur connecté, sans quoi ProtectedRoute le renverrait vers elle-même.
export function dashboardPathForRole(role) {
  for (const [path, roles] of Object.entries(DASHBOARD_ROLES)) {
    if (roles.includes(role)) return path
  }
  return '/dashboard/generique'
}
