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

// Le pôle de chaque poste (le même rangement que le serveur, communication/poles.py) : il donne sa couleur à l'interface.
// L'opérateur de la plateforme, hors des compagnies, a la sienne.
export const POLE_DU_ROLE = {
  pdg: 'direction',
  secretaire_general: 'direction',
  qhse: 'direction',
  directeur_exploitation: 'exploitation',
  chef_gare: 'exploitation',
  chef_ligne: 'exploitation',
  guichetier: 'exploitation',
  bagagiste: 'exploitation',
  chauffeur_principal: 'roulant',
  chauffeur_relais: 'roulant',
  controleur_ligne: 'roulant',
  directeur_technique: 'technique',
  magasinier: 'technique',
  chef_atelier: 'technique',
  mecanicien: 'technique',
  drh: 'supports',
  directeur_financier: 'supports',
  responsable_juridique: 'supports',
  superadmin: 'plateforme',
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
  // Mes paramètres : son mot de passe et sa session, pour chacun (l'opérateur de la plateforme compris).
  '/parametres': [
    'pdg', 'secretaire_general', 'qhse', 'directeur_exploitation', 'chef_gare', 'chef_ligne', 'guichetier', 'bagagiste',
    'chauffeur_principal', 'chauffeur_relais', 'controleur_ligne', 'directeur_technique', 'magasinier', 'chef_atelier',
    'mecanicien', 'drh', 'directeur_financier', 'responsable_juridique', 'superadmin',
  ],
  // Le guide d'utilisation : la fiche de chaque poste, rangée par pôle. Chacun lit celle de tous les postes.
  '/guide': [
    'pdg', 'secretaire_general', 'qhse', 'directeur_exploitation', 'chef_gare', 'chef_ligne', 'guichetier', 'bagagiste',
    'chauffeur_principal', 'chauffeur_relais', 'controleur_ligne', 'directeur_technique', 'magasinier', 'chef_atelier',
    'mecanicien', 'drh', 'directeur_financier', 'responsable_juridique', 'superadmin',
  ],
  // Paramètres de la compagnie, tenus sans l'administration Django. Chaque page ne s'ouvre qu'aux postes qui peuvent y écrire
  // (le chef de gare tient la fiche de sa gare depuis son tableau de bord).
  '/compagnie': ['pdg'],
  // Le DRH ne gère les comptes que si le règlement intérieur le lui permet (sinon la page affiche le refus du serveur).
  '/personnel': ['pdg', 'drh'],
  '/gares': ['pdg', 'secretaire_general', 'directeur_exploitation'],
  '/lignes': ['pdg', 'secretaire_general', 'directeur_exploitation', 'chef_ligne'],
  '/vehicules': ['pdg', 'secretaire_general', 'directeur_exploitation', 'directeur_technique', 'chef_atelier'],
  // Catalogue, réceptions et inventaire : ceux qui enregistrent les mouvements du stock.
  '/pieces': ['magasinier', 'chef_atelier', 'directeur_technique'],
  // Le règlement intérieur : le PDG règle toutes les règles, chaque directeur celles de son pôle.
  '/reglement': ['pdg', 'directeur_technique', 'directeur_exploitation'],
  // Le lien avec le logiciel de billetterie de la compagnie : mode, clés, import (le chef de gare importe depuis son tableau de bord).
  '/billetterie': ['pdg', 'directeur_exploitation'],
}

// Les pages annexes regroupées sous le menu « Paramètres » de la barre du haut (les autres restent des liens directs).
export const PAGES_PARAMETRES = [
  '/parametres', '/compagnie', '/personnel', '/reglement', '/billetterie', '/gares', '/lignes', '/vehicules', '/pieces',
]

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
  '/parametres': 'Mes paramètres',
  '/guide': 'Guide',
  '/compagnie': 'Ma compagnie',
  '/personnel': 'Personnel et comptes',
  '/gares': 'Gares et quais',
  '/lignes': 'Lignes et tarifs',
  '/vehicules': 'Véhicules',
  '/pieces': 'Pièces et stock',
  '/reglement': 'Règlement intérieur',
  '/billetterie': 'Billetterie',
}

// Repli pour un rôle inconnu du frontend (ex. rôle ajouté côté serveur) : la page générique
// est ouverte à tout utilisateur connecté, sans quoi ProtectedRoute le renverrait vers elle-même.
export function dashboardPathForRole(role) {
  for (const [path, roles] of Object.entries(DASHBOARD_ROLES)) {
    if (roles.includes(role)) return path
  }
  return '/dashboard/generique'
}
