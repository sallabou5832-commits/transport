"""Fiches de poste types, une par rôle de l'organigramme : le point de départ d'une offre de recrutement. Le DRH peut personnaliser
chaque fiche pour sa compagnie (`FicheDePoste`) ; tant qu'il ne l'a pas fait, c'est celle-ci qui sert."""

from core.models import Role

_HORAIRES_JOUR = "Horaires de bureau, du lundi au vendredi."
_HORAIRES_TERRAIN = "Travail par roulement, week-ends et jours fériés compris."
_HORAIRES_ROULANT = "Départs à toute heure ; repos obligatoires entre les trajets."


def _fiche(intitule, missions, profil, conditions):
    return {"intitule": intitule, "missions": "\n".join(f"- {m}" for m in missions), "profil": "\n".join(f"- {p}" for p in profil), "conditions": conditions}


FICHES_TYPES = {
    Role.PDG: _fiche(
        "Président-directeur général",
        ["Fixer la stratégie et le cadre de la compagnie", "Valider les investissements et arbitrer l'exploitation", "Représenter la compagnie"],
        ["Expérience confirmée de direction dans le transport ou les services", "Sens de la décision et du dialogue social"],
        _HORAIRES_JOUR,
    ),
    Role.SECRETAIRE_GENERAL: _fiche(
        "Secrétaire général",
        ["Tenir l'agenda de la direction", "Diffuser les notes de service", "Classer et archiver les documents administratifs"],
        ["Bac +3 en administration ou équivalent", "Rigueur, discrétion, maîtrise des outils bureautiques"],
        _HORAIRES_JOUR,
    ),
    Role.QHSE: _fiche(
        "Responsable qualité, hygiène, sécurité et environnement",
        ["Contrôler la sécurité des départs et bloquer un véhicule non conforme", "Suivre les incidents et les formations de sécurité", "Tenir le tableau de conformité"],
        ["Formation en sécurité routière ou HSE", "Connaissance de la réglementation du transport de voyageurs"],
        _HORAIRES_JOUR,
    ),
    Role.DIRECTEUR_EXPLOITATION: _fiche(
        "Directeur de l'exploitation",
        ["Piloter le réseau, les lignes et les gares", "Arbitrer les véhicules entre gares", "Suivre la ponctualité et les recettes"],
        ["Expérience de l'exploitation d'un réseau de transport", "Capacité à décider vite sous pression"],
        _HORAIRES_TERRAIN,
    ),
    Role.CHEF_GARE: _fiche(
        "Chef de gare",
        ["Animer l'équipe de la gare (guichetiers, bagagistes)", "Suivre les départs et les recettes de la gare", "Prévenir les chauffeurs et les clients en cas de retard"],
        ["Expérience en gare routière ou en exploitation", "Leadership et sens du service client"],
        _HORAIRES_TERRAIN,
    ),
    Role.CHEF_LIGNE: _fiche(
        "Chef de ligne",
        ["Planifier les départs de la ligne et affecter chauffeurs et véhicules", "Gérer les retards et les remplacements", "Suivre les chauffeurs de la ligne"],
        ["Expérience de la régulation ou de la conduite", "Réactivité, sens de l'organisation"],
        _HORAIRES_TERRAIN,
    ),
    Role.GUICHETIER: _fiche(
        "Guichetier",
        ["Vendre les billets et encaisser (espèces, mobile money)", "Clôturer sa caisse en fin de service", "Renseigner les voyageurs"],
        ["Niveau bac, aisance avec le calcul et le contact client", "Honnêteté et rigueur dans la manipulation d'argent"],
        _HORAIRES_TERRAIN,
    ),
    Role.BAGAGISTE: _fiche(
        "Bagagiste",
        ["Enregistrer les bagages et les colis", "Charger et décharger les soutes en équilibrant le poids", "Remettre les colis contre le code de retrait"],
        ["Bonne condition physique", "Soin, honnêteté, sens des responsabilités"],
        _HORAIRES_TERRAIN,
    ),
    Role.CHAUFFEUR_PRINCIPAL: _fiche(
        "Chauffeur d'autocar",
        ["Conduire en sécurité selon la feuille de route", "Faire la checklist avant chaque départ", "Signaler tout incident et respecter les pauses"],
        ["Permis D en cours de validité et visite médicale à jour", "Formation de sécurité routière (OSER)", "Expérience de la conduite de longue distance"],
        _HORAIRES_ROULANT,
    ),
    Role.CHAUFFEUR_RELAIS: _fiche(
        "Chauffeur relais",
        ["Prendre le relais d'un conducteur fatigué en cours de trajet", "Conduire en sécurité selon la feuille de route", "Signaler tout incident"],
        ["Permis D en cours de validité et visite médicale à jour", "Formation de sécurité routière (OSER)", "Disponibilité et mobilité"],
        _HORAIRES_ROULANT,
    ),
    Role.CONTROLEUR_LIGNE: _fiche(
        "Contrôleur de ligne",
        ["Vérifier les billets à bord", "Constater les infractions et fraudes", "Établir le rapport de contrôle"],
        ["Niveau bac, sens du contact et fermeté", "Intégrité"],
        _HORAIRES_TERRAIN,
    ),
    Role.DIRECTEUR_TECHNIQUE: _fiche(
        "Directeur technique",
        ["Piloter la maintenance et la disponibilité de la flotte", "Décider des renouvellements de véhicules", "Suivre les stocks de pièces et l'atelier"],
        ["Ingénieur ou technicien supérieur en mécanique", "Expérience de la maintenance d'une flotte de poids lourds"],
        _HORAIRES_JOUR,
    ),
    Role.MAGASINIER: _fiche(
        "Magasinier",
        ["Tenir le stock de pièces et servir les demandes de l'atelier", "Suivre les seuils et proposer les commandes", "Faire les inventaires"],
        ["Niveau bac, rigueur dans la tenue d'un stock", "Connaissance des pièces automobiles appréciée"],
        _HORAIRES_JOUR,
    ),
    Role.CHEF_ATELIER: _fiche(
        "Chef d'atelier",
        ["Répartir les ordres de réparation entre les mécaniciens", "Planifier l'entretien préventif", "Garantir les délais et la qualité des interventions"],
        ["Expérience confirmée en mécanique poids lourds", "Sens de l'organisation et de l'encadrement"],
        _HORAIRES_JOUR,
    ),
    Role.MECANICIEN: _fiche(
        "Mécanicien / électricien auto",
        ["Réaliser les réparations et l'entretien des véhicules", "Demander les pièces nécessaires", "Renseigner l'ordre de réparation"],
        ["CAP ou BEP en mécanique ou électricité automobile", "Expérience sur poids lourds appréciée"],
        _HORAIRES_JOUR,
    ),
    Role.DRH: _fiche(
        "Directeur des ressources humaines",
        ["Tenir les dossiers du personnel et suivre les formations obligatoires", "Gérer les congés et le recrutement", "Animer la médiation sociale"],
        ["Bac +4 en gestion des ressources humaines ou droit social", "Expérience du dialogue social"],
        _HORAIRES_JOUR,
    ),
    Role.DIRECTEUR_FINANCIER: _fiche(
        "Directeur financier et comptable",
        ["Consolider les recettes et suivre la trésorerie", "Suivre les budgets et la rentabilité par ligne", "Régler les fournisseurs et les assurances"],
        ["Bac +5 en finance ou comptabilité", "Expérience de la gestion d'une compagnie de transport ou de services"],
        _HORAIRES_JOUR,
    ),
    Role.RESPONSABLE_JURIDIQUE: _fiche(
        "Responsable juridique",
        ["Suivre les assurances de la flotte et les sinistres", "Veiller à la conformité réglementaire", "Traiter les litiges et tenir la bibliothèque de modèles de documents"],
        ["Bac +5 en droit des affaires ou des transports", "Expérience des assurances et du contentieux"],
        _HORAIRES_JOUR,
    ),
}

assert set(FICHES_TYPES) == {role for role in Role if role != Role.SUPERADMIN}, "une fiche type par rôle de l'organigramme"
