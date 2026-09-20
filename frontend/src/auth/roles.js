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
  'drh',
  'directeur_financier',
  'responsable_juridique',
]

export const DASHBOARD_ROLES = {
  '/dashboard/direction': ['pdg', 'secretaire_general', 'qhse'],
  '/dashboard/gare': ['chef_gare'],
  '/dashboard/guichetier': ['guichetier'],
  '/dashboard/chauffeur': ['chauffeur_principal', 'chauffeur_relais'],
  '/dashboard/magasinier': ['magasinier'],
  '/dashboard/atelier': ['chef_atelier'],
}

const ROLES_AVEC_TABLEAU_DEDIE = new Set(Object.values(DASHBOARD_ROLES).flat())

export const ROLES_GENERIQUES = ALL_ROLES.filter((role) => !ROLES_AVEC_TABLEAU_DEDIE.has(role))

export function dashboardPathForRole(role) {
  for (const [path, roles] of Object.entries(DASHBOARD_ROLES)) {
    if (roles.includes(role)) return path
  }
  return '/dashboard/generique'
}
