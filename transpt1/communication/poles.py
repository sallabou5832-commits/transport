"""Les cinq pôles de l'organigramme et les postes qu'ils regroupent : une note de service s'adresse « aux pôles concernés »."""

from core.models import Role

POLES = {
    "direction": ("Direction Générale", [Role.PDG, Role.SECRETAIRE_GENERAL, Role.QHSE]),
    "exploitation": (
        "Exploitation & Réseau",
        [Role.DIRECTEUR_EXPLOITATION, Role.CHEF_GARE, Role.CHEF_LIGNE, Role.GUICHETIER, Role.BAGAGISTE],
    ),
    "roulant": ("Personnel roulant", [Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS, Role.CONTROLEUR_LIGNE]),
    "technique": (
        "Technique & Maintenance",
        [Role.DIRECTEUR_TECHNIQUE, Role.MAGASINIER, Role.CHEF_ATELIER, Role.MECANICIEN],
    ),
    "supports": ("Fonctions supports", [Role.DRH, Role.DIRECTEUR_FINANCIER, Role.RESPONSABLE_JURIDIQUE]),
}

# Tous les postes d'une compagnie (le superadmin n'en fait pas partie).
TOUS_LES_POSTES = [role for _, roles in POLES.values() for role in roles]
