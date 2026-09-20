/// Rôles de l'API (`core.models.Role`) et leur libellé.
abstract final class Roles {
  static const guichetier = 'guichetier';
  static const bagagiste = 'bagagiste';
  static const chauffeurPrincipal = 'chauffeur_principal';
  static const chauffeurRelais = 'chauffeur_relais';
  static const controleurLigne = 'controleur_ligne';
  static const chefAtelier = 'chef_atelier';
  static const magasinier = 'magasinier';

  /// Rôles de terrain, ciblés par l'application mobile (cahier des charges :
  /// « application mobile pour les rôles de terrain »).
  static const terrain = {
    guichetier,
    bagagiste,
    chauffeurPrincipal,
    chauffeurRelais,
    controleurLigne,
    chefAtelier,
  };

  static const chauffeurs = {chauffeurPrincipal, chauffeurRelais};

  static const labels = {
    'superadmin': 'Super administrateur',
    'pdg': 'PDG',
    'secretaire_general': 'Secrétaire général',
    'qhse': 'QHSE',
    'directeur_exploitation': 'Directeur exploitation',
    'chef_gare': 'Chef de gare',
    'chef_ligne': 'Chef de ligne',
    guichetier: 'Guichetier',
    bagagiste: 'Bagagiste',
    chauffeurPrincipal: 'Chauffeur principal',
    chauffeurRelais: 'Chauffeur relais',
    controleurLigne: 'Contrôleur de ligne',
    'directeur_technique': 'Directeur technique',
    magasinier: 'Magasinier',
    chefAtelier: 'Chef d\'atelier',
    'drh': 'DRH',
    'directeur_financier': 'Directeur financier',
    'responsable_juridique': 'Responsable juridique',
  };

  static String label(String role) => labels[role] ?? role;
}
