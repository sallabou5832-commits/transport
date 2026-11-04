"""Le guide d'utilisation de chaque poste, rangé par pôle (GET /api/guides/) : à quoi sert le poste, ses écrans, ses gestes pas à
pas dans l'ordre d'une journée de travail, à qui s'adresser. Une seule source pour le site et le mobile ; chacun peut lire le guide
de tous les postes.

Règles de rédaction, vérifiées par les tests :
- une tâche ne décrit qu'un geste qu'un écran permet ; une règle du règlement intérieur sans écran figure seulement dans la section
  « règlement » de la fiche, que `guide_pour` calcule pour la compagnie du lecteur (comme « qui règle ce poste ») ;
- les tâches d'une fiche suivent l'ordre des MOMENTS ;
- `avec` nomme les postes avec qui le geste se coordonne (qui est prévenu, qui prend la suite) ; tout passage de relais est
  décrit des deux côtés : si la fiche A cite B, la fiche B cite A ;
- role_coverage_tests/test_guides.py vérifie que chaque fiche cite toutes les pages que le site ouvre à son poste, et seulement
  celles-là.
"""

from communication.poles import POLES
from configuration import regles
from configuration.services import reglement_de
from core.models import Role

SITE, MOBILE = "site", "mobile"

# Le déroulé d'une journée de travail : les tâches d'une fiche sont rangées dans cet ordre.
MISE_EN_PLACE, DEBUT, JOURNEE, FIN, BESOIN = "mise_en_place", "debut", "journee", "fin", "besoin"
MOMENTS = {
    MISE_EN_PLACE: "Pour démarrer",
    DEBUT: "En début de journée",
    JOURNEE: "Au fil de la journée",
    FIN: "En fin de journée",
    BESOIN: "Au besoin",
}

R = Role


def ecran(chemin, titre, usage):
    """Une page du site, par sa route (frontend/src/auth/roles.js)."""
    return {"support": SITE, "chemin": chemin, "titre": titre, "usage": usage}


def ecran_mobile(titre, usage):
    return {"support": MOBILE, "chemin": None, "titre": titre, "usage": usage}


def tache(titre, *etapes, moment=JOURNEE, avec=(), regle=None):
    """Un geste pas à pas. `avec` : les postes avec qui il se coordonne ; `regle` : la règle du règlement intérieur dont il
    dépend (le guide dit si la compagnie du lecteur le permet)."""
    return {"titre": titre, "etapes": list(etapes), "moment": moment, "avec": list(avec), "regle": regle}


_CHAUFFEURS = (R.CHAUFFEUR_PRINCIPAL, R.CHAUFFEUR_RELAIS)

# Ce que tout poste d'une compagnie trouve, quel que soit son pôle.
COMMUNS = {
    "ecrans": [
        ecran("/espace", "Mon espace", "Demander un congé, suivre ses formations obligatoires, déposer une doléance auprès du DRH."),
        ecran("/notes", "Notes de service", "Les notes de la direction adressées à votre poste (elles arrivent aussi dans la cloche)."),
        ecran("/modeles", "Modèles juridiques", "Les documents types que le responsable juridique a ouverts à votre pôle : lire, copier, télécharger."),
        ecran("/parametres", "Mes paramètres", "Changer son mot de passe, voir sa session, déconnecter ses autres appareils, ses préférences."),
        ecran("/guide", "Guide", "Ce guide : la fiche de chaque poste, rangée par pôle."),
        ecran_mobile("Mes paramètres (roue dentée)", "Sur le téléphone : code court, mode vocal, mot de passe et session."),
    ],
    "taches": [
        tache(
            "Se connecter la première fois",
            "Saisissez l'identifiant et le mot de passe provisoire remis par votre direction.",
            "L'application ouvre « Mes paramètres » : choisissez votre propre mot de passe (8 caractères au moins).",
            "Vous accédez ensuite à votre tableau de bord ; celui qui vous a remis le mot de passe provisoire ne connaît pas le vôtre.",
            moment=MISE_EN_PLACE,
        ),
        tache(
            "Rester connecté sur son appareil",
            "À la connexion, cochez « Rester connecté » et choisissez la durée (seulement sur un appareil personnel).",
            "Votre compagnie peut limiter cette durée ; « Mes paramètres » montre jusqu'à quand cet appareil reste connecté.",
            "Appareil perdu ou prêté : « Déconnecter mes autres appareils », ou changez votre mot de passe.",
            moment=MISE_EN_PLACE,
        ),
        tache(
            "Lire ses alertes",
            "La cloche de la barre du haut compte les alertes adressées à votre poste ; elle se met à jour chaque minute.",
            "Ouvrez-la et lisez l'alerte : elle passe en lue ; « Tout marquer comme lu » les vide toutes.",
            "Dans « Mes paramètres », un son ou une notification du navigateur peut signaler une alerte critique.",
            moment=DEBUT,
        ),
        tache(
            "Demander un congé",
            "« Mon espace » > « Demander un congé » : nature, premier et dernier jour, motif si besoin.",
            "« Envoyer la demande » : le DRH décide ; la réponse s'affiche dans « Mes congés ».",
            moment=BESOIN,
        ),
        tache(
            "Signaler une difficulté au DRH",
            "« Mon espace » > « Déposer une doléance » : gravité et ce qui se passe.",
            "Le DRH seul la lit ; ses réponses s'affichent dans « Échanges avec le DRH ».",
            moment=BESOIN,
        ),
    ],
    "contacts": [
        "Mot de passe oublié : le PDG le réinitialise dans « Personnel et comptes » (le DRH aussi, si le règlement intérieur le permet).",
        "Un bouton refuse avec un message : votre supérieur ou le règlement intérieur ne vous le permet pas ; le message dit à qui vous adresser.",
    ],
    "astuces": [
        "Chaque compagnie ne voit que ses propres données : rien de ce que vous saisissez n'est visible d'une autre compagnie.",
        "Tout ce qui est créé, modifié ou supprimé est inscrit au journal d'audit, avec son auteur et l'heure.",
        "Sur le téléphone, ce qui est saisi sans réseau est gardé et envoyé seul au retour de la connexion (bandeau de synchronisation).",
    ],
}


FICHES = {
    # ── Direction Générale ──────────────────────────────────────────────────────────────────────────────────────────
    R.PDG: {
        "mission": (
            "Dirige la compagnie : fixe son cadre et son règlement intérieur, tient sa fiche et son réseau, décide des "
            "investissements et intervient directement sur les lignes, les véhicules et les comptes."
        ),
        "ecrans": [
            ecran("/dashboard/direction", "Tableau de bord — Direction", "Recettes et ponctualité du jour, flotte, pièces sous seuil, assurances à échéance, carte du réseau en temps réel, trésorerie, renouvellement de la flotte."),
            ecran("/pilotage", "Pilotage", "Geler ou rouvrir une ligne, réaffecter un véhicule ou un chauffeur, rattacher un véhicule à une autre gare, décider des investissements, suspendre un compte."),
            ecran("/cadre", "Cadre de la compagnie", "Les plafonds que nul ne dépasse : automatisation, gamification, durée de session, code court mobile, gestion des comptes par le DRH."),
            ecran("/configuration", "Configuration", "Régler un poste ou un agent de la compagnie : niveau d'automatisation, gamification, mode vocal, fonctions retirées."),
            ecran("/compagnie", "Ma compagnie", "Identité, coordonnées, mentions légales et logo."),
            ecran("/personnel", "Personnel et comptes", "Créer les comptes, modifier une fiche, changer de poste, réinitialiser un mot de passe."),
            ecran("/reglement", "Règlement intérieur", "Ce que la compagnie permet ou non à certains postes : toutes les règles."),
            ecran("/billetterie", "Billetterie", "Mode de billetterie (intégrée, externe, mixte), clés du logiciel de la compagnie, import des ventes."),
            ecran("/gares", "Gares et quais", "Créer les gares, leurs horaires, leur chef et leurs quais."),
            ecran("/lignes", "Lignes et tarifs", "Créer les lignes, fixer le tarif (ou le prix libre), la distance et la durée prévue."),
            ecran("/vehicules", "Véhicules", "Le parc : immatriculation, places, papiers, gare d'attache."),
            ecran("/finances", "Finances", "Trésorerie, budget carburant, rentabilité par ligne et par gare, paiements à venir."),
            ecran("/secretariat", "Secrétariat", "Diffuser une note de service, tenir l'agenda de la direction, classer les dossiers."),
            ecran("/synthese", "Synthèse RH et juridique", "Effectif, congés, formations, recrutement, doléances ; assurances, sinistres et litiges."),
            ecran("/audit", "Journal d'audit", "Qui a fait quoi, quand et d'où ; il ne se modifie ni ne se supprime."),
        ],
        "taches": [
            tache(
                "Mettre la compagnie en service",
                "« Ma compagnie » : identité, coordonnées, mentions légales, logo, puis « Enregistrer la fiche ».",
                "« Gares et quais » : créez les gares (« Nouvelle gare »), désignez leur chef, ajoutez les quais.",
                "« Lignes et tarifs » : une ligne relie deux gares ; tarif vide = prix saisi à la vente.",
                "« Véhicules » : ajoutez le parc ; puis créez les comptes du personnel.",
                moment=MISE_EN_PLACE,
            ),
            tache(
                "Créer le compte d'un agent",
                "« Personnel et comptes » > « Nouveau compte » : prénom, nom, poste ; la gare pour un guichetier ou un bagagiste.",
                "La date d'embauche ouvre son dossier chez le DRH ; matricule et téléphone sont facultatifs.",
                "« Créer le compte » : le mot de passe provisoire s'affiche une seule fois, remettez-le à l'agent.",
                moment=MISE_EN_PLACE,
                avec=[R.DRH],
            ),
            tache(
                "Confier la gestion des comptes au DRH",
                "« Cadre de la compagnie » > « Accès aux comptes » : cochez « Le DRH crée et modifie aussi les comptes du personnel ».",
                "Vous êtes prévenu de ce que fait le DRH, et lui de ce que vous faites ; la suspension d'un compte reste à vous.",
                moment=MISE_EN_PLACE,
                avec=[R.DRH],
            ),
            tache(
                "Régler le règlement intérieur",
                "« Règlement intérieur » : cochez ce que la compagnie permet (une règle jamais réglée garde le comportement d'origine).",
                "Les écrans des postes concernés n'affichent alors que les gestes permis ; les directeurs règlent aussi les règles de leur pôle.",
                "Exemple : exiger que le QHSE lève lui-même le blocage d'un car réparé.",
                moment=MISE_EN_PLACE,
                avec=[R.DIRECTEUR_TECHNIQUE, R.DIRECTEUR_EXPLOITATION],
            ),
            tache(
                "Relier le logiciel de billetterie de la compagnie",
                "« Billetterie » : choisissez le mode (intégrée : rien ne change ; externe : le logiciel vend seul ; mixte : les deux).",
                "En externe ou mixte, « Créer une clé » pour le logiciel : la clé ne s'affiche qu'une fois ; « Révoquer » la coupe.",
                moment=MISE_EN_PLACE,
                avec=[R.DIRECTEUR_EXPLOITATION],
            ),
            tache(
                "Faire le point de la journée",
                "« Tableau de bord — Direction » : recettes et ponctualité du jour, disponibilité de la flotte, carte du réseau.",
                "La cloche vous signale les retards récurrents, les pannes en hausse, une recette en baisse, un véhicule à renouveler "
                "et toute infraction grave relevée au contrôle à bord.",
                moment=DEBUT,
                avec=[R.CONTROLEUR_LIGNE],
            ),
            tache(
                "Décider d'un investissement",
                "« Pilotage » : les demandes « À décider » des directeurs (achat de véhicules, ouverture de ligne...).",
                "« Valider », ou « Refuser » avec un commentaire obligatoire : le demandeur voit la décision.",
                avec=[R.DIRECTEUR_EXPLOITATION, R.DIRECTEUR_TECHNIQUE, R.DIRECTEUR_FINANCIER],
            ),
            tache(
                "Suivre les fonctions supports",
                "« Finances » : trésorerie, budget carburant, rentabilité, paiements à venir, tenus par le directeur financier.",
                "« Synthèse RH et juridique » : ce que le DRH et le responsable juridique vous remontent.",
                avec=[R.DIRECTEUR_FINANCIER, R.DRH, R.RESPONSABLE_JURIDIQUE],
            ),
            tache(
                "Geler une ligne",
                "« Pilotage » > « Geler ou rouvrir une ligne » : motif obligatoire, puis « Fermer ».",
                "Plus aucune vente ni aucun nouveau départ sur la ligne ; « Rouvrir » la rend aux guichets.",
                moment=BESOIN,
            ),
            tache(
                "Suspendre ou réactiver un compte",
                "« Pilotage » > « Comptes des agents » : cherchez l'agent.",
                "« Suspendre » coupe aussitôt son accès ; rien de ce qu'il a fait n'est perdu. Le DRH et son chef de gare sont prévenus.",
                "« Réactiver » lui rend l'accès.",
                moment=BESOIN,
                avec=[R.DRH],
            ),
        ],
        "contacts": ["Le secrétaire général prépare notes, agenda et archives ; chaque directeur tient son pôle."],
        "astuces": [
            "Une compagnie qui ne règle rien fonctionne d'emblée : chaque réglage part d'un défaut raisonnable.",
            "Le cadre de la compagnie plafonne tous les réglages faits plus bas : un supérieur ne peut pas le dépasser.",
            "Une gare, une ligne ou un véhicule saisi par erreur se supprime depuis sa fiche ; s'il sert déjà, le serveur le garde.",
        ],
    },
    R.SECRETAIRE_GENERAL: {
        "mission": (
            "Seconde le PDG : tient le secrétariat de la direction (notes de service, agenda, archives) et suit le réseau, "
            "les finances et la situation RH et juridique."
        ),
        "ecrans": [
            ecran("/dashboard/direction", "Tableau de bord — Direction", "La même vue que le PDG : recettes, ponctualité, flotte, carte, trésorerie."),
            ecran("/secretariat", "Secrétariat", "Notes de service aux pôles, agenda de la direction, classement et archivage des dossiers."),
            ecran("/finances", "Finances", "Trésorerie, budget carburant, rentabilité, paiements à venir."),
            ecran("/synthese", "Synthèse RH et juridique", "Ce que la direction lit des fonctions supports."),
            ecran("/gares", "Gares et quais", "Créer et tenir les gares et leurs quais."),
            ecran("/lignes", "Lignes et tarifs", "Créer et tenir les lignes et leurs tarifs."),
            ecran("/vehicules", "Véhicules", "Tenir le parc et les papiers des véhicules."),
            ecran("/audit", "Journal d'audit", "Retrouver qui a fait quoi, quand et d'où."),
        ],
        "taches": [
            tache(
                "Faire le point de la journée",
                "« Tableau de bord — Direction » : recettes, ponctualité, flotte, carte du réseau.",
                "« Secrétariat » > « Agenda de la direction » : les rendez-vous à venir.",
                moment=DEBUT,
            ),
            tache(
                "Diffuser une note de service",
                "« Secrétariat » > « Notes de service » : titre, contenu.",
                "Cochez les pôles destinataires ou « Tous les postes » ; « Note urgente » si besoin.",
                "« Diffuser la note » : les postes visés la reçoivent dans leur cloche et dans « Notes de service ».",
            ),
            tache(
                "Planifier un rendez-vous de la direction",
                "« Secrétariat » > « Agenda de la direction » : titre, début, lieu, ordre du jour.",
                "Choisissez les invités (prévenus dans leur cloche), puis « Ajouter à l'agenda ».",
            ),
            tache(
                "Classer un dossier administratif",
                "« Secrétariat » > « Classement et archivage » : titre, catégorie, référence, emplacement (armoire, chemise, lien).",
                "« Classer le dossier » ; plus tard « Archiver » (un dossier ne se supprime pas), « Sortir des archives » au besoin.",
                moment=BESOIN,
            ),
        ],
        "contacts": ["Le PDG décide des investissements, des comptes et des pouvoirs d'intervention."],
        "astuces": ["Le registre des archives dit où trouver un dossier ; il ne contient pas le fichier lui-même."],
    },
    R.QHSE: {
        "mission": (
            "Veille à la sécurité, la qualité et la conformité : suit les incidents et les défauts de checklist, bloque un "
            "véhicule dangereux, contrôle la conformité de la flotte et les formations obligatoires."
        ),
        "ecrans": [
            ecran("/dashboard/qhse", "Tableau de bord — QHSE", "Incidents ouverts, défauts de checklist avant départ, véhicules bloqués, conformité de la flotte, formations obligatoires, échanges avec la tutelle."),
            ecran("/audit", "Journal d'audit", "Retrouver qui a fait quoi, quand et d'où."),
        ],
        "taches": [
            tache(
                "Surveiller les défauts avant départ",
                "« Défauts de checklist avant départ » : les défauts signalés par les chauffeurs sur les départs à venir.",
                "Un défaut de sécurité bloque le véhicule (« Bloqué (défaut de checklist) ») et vous est signalé aussitôt.",
                "Un défaut de sécurité constaté par le conducteur qui reprend le car au relais vous est signalé aussi (le car, lui, roule).",
                moment=DEBUT,
                avec=_CHAUFFEURS,
            ),
            tache(
                "Traiter un incident",
                "« Incidents ouverts » sont rangés du plus grave au moins grave ; un incident grave vous est signalé dès sa déclaration.",
                "Une fois l'incident réglé, « Marquer traité ».",
                avec=[*_CHAUFFEURS, R.CONTROLEUR_LIGNE],
            ),
            tache(
                "Suivre les échanges avec la tutelle",
                "« Échanges avec la tutelle » : incidents graves et assurances à échéance remontés au ministère, normes reçues de lui.",
                "« Marquer traité » ; « Rattraper les flux automatiques » génère ceux qui manquent, sans doublon.",
                avec=[R.RESPONSABLE_JURIDIQUE],
            ),
            tache(
                "Contrôler la conformité",
                "« Conformité réglementaire de la flotte » : assurances, obligations réglementaires, véhicules bloqués (partagée avec le responsable juridique).",
                "« Formations obligatoires » : sécurité routière, permis, visite médicale, que le DRH tient à jour.",
                avec=[R.RESPONSABLE_JURIDIQUE, R.DRH],
            ),
            tache(
                "Bloquer le départ d'un véhicule",
                "« Bloquer le départ d'un véhicule » : choisissez le véhicule, saisissez le motif.",
                "« Bloquer le départ » : le chef d'atelier, le directeur technique, le chef de ligne et le chef de gare sont prévenus aussitôt.",
                moment=BESOIN,
                avec=[R.CHEF_ATELIER, R.DIRECTEUR_TECHNIQUE, R.CHEF_LIGNE, R.CHEF_GARE],
            ),
            tache(
                "Lever un blocage",
                "« Véhicules bloqués pour raison de sécurité » : saisissez le motif de la levée, puis « Lever le blocage ».",
                "Le chef d'atelier, le chef de ligne et la gare sont prévenus.",
                "Une réparation clôturée à l'atelier remet aussi le car en service, sauf si le règlement intérieur exige votre levée : "
                "vous êtes alors prévenu que le car réparé l'attend.",
                moment=BESOIN,
                avec=[R.CHEF_ATELIER],
            ),
        ],
        "contacts": ["La conformité de la flotte est partagée avec le responsable juridique ; les formations, avec le DRH."],
        "astuces": ["Les défauts relevés avant départ s'affichent avec la ligne et l'heure du départ concerné."],
    },
    # ── Exploitation & Réseau ───────────────────────────────────────────────────────────────────────────────────────
    R.DIRECTEUR_EXPLOITATION: {
        "mission": (
            "Fait tourner le réseau : suit la ponctualité, le remplissage et les incidents graves, planifie les départs, "
            "arbitre les demandes des chefs de gare et de ligne et équilibre les véhicules entre les gares."
        ),
        "ecrans": [
            ecran("/dashboard/exploitation", "Tableau de bord — Exploitation", "Départs du jour, ponctualité, remplissage, départs en retard, carte en temps réel, arbitrage du réseau, flotte, incidents graves."),
            ecran("/configuration", "Configuration", "Régler les chefs de gare, les chefs de ligne et les contrôleurs."),
            ecran("/investissements", "Investissements", "Demander un achat de véhicules ou une ouverture de ligne au PDG."),
            ecran("/reglement", "Règlement intérieur", "Les règles des chauffeurs (supprimer sa feuille de route, un incident déclaré)."),
            ecran("/billetterie", "Billetterie", "Mode de billetterie, clés du logiciel de la compagnie, import des ventes."),
            ecran("/gares", "Gares et quais", "Créer et tenir les gares et leurs quais."),
            ecran("/lignes", "Lignes et tarifs", "Créer et tenir les lignes et leurs tarifs."),
            ecran("/vehicules", "Véhicules", "Tenir le parc et la gare d'attache des véhicules."),
        ],
        "taches": [
            tache(
                "Régler ce que les chauffeurs peuvent faire",
                "« Règlement intérieur » : supprimer sa feuille de route, supprimer un incident déclaré par erreur (permis par défaut).",
                "Leurs écrans n'affichent ces boutons que si la compagnie le permet.",
                moment=MISE_EN_PLACE,
                avec=[R.PDG, *_CHAUFFEURS],
            ),
            tache(
                "Relier et alimenter la billetterie",
                "« Billetterie » : mode, clés du logiciel de la compagnie ; « Importer les ventes » dépose le fichier exporté par le logiciel.",
                "Le compte rendu dit ce qui est créé, déjà reçu ou refusé (et pourquoi) ; réimporter le même fichier ne crée rien de plus.",
                moment=MISE_EN_PLACE,
                avec=[R.PDG, R.CHEF_GARE],
            ),
            tache(
                "Faire le point du réseau",
                "« Tableau de bord — Exploitation » : départs du jour, ponctualité, remplissage, départs en retard, carte en temps réel.",
                "« Actualiser maintenant » force la mise à jour.",
                moment=DEBUT,
            ),
            tache(
                "Planifier un départ",
                "« Planifier un départ » : ligne, date et heure.",
                "Seuls les véhicules et chauffeurs libres à cette heure sont proposés ; choisissez-les.",
                "« Planifier le départ » : la feuille de route du chauffeur est créée.",
                avec=[R.CHAUFFEUR_PRINCIPAL],
            ),
            tache(
                "Suivre les incidents graves",
                "Un incident grave déclaré par un chauffeur, ou une infraction grave relevée au contrôle, vous est signalé.",
                "« Incidents graves ouverts » sur le tableau de bord ; le QHSE les traite.",
                avec=[R.CHAUFFEUR_PRINCIPAL, R.CONTROLEUR_LIGNE],
            ),
            tache(
                "Décider d'une demande de fermeture de ligne",
                "« Arbitrage du réseau » : les demandes des chefs de gare et de ligne.",
                "« Valider » ou « Refuser », avec un commentaire facultatif.",
                avec=[R.CHEF_GARE, R.CHEF_LIGNE],
            ),
            tache(
                "Arbitrer une pénurie",
                "Quand un chef de ligne ne trouve aucun véhicule ou chauffeur libre pour remplacer, vous êtes prévenu de la pénurie ; "
                "de même quand un congé validé par le DRH touche des départs.",
                "« Gares en tension » montre où manquent les véhicules : « Rattacher un véhicule à une autre gare » (véhicule, nouvelle gare, motif).",
                moment=BESOIN,
                avec=[R.CHEF_LIGNE, R.DRH],
            ),
            tache(
                "Demander un investissement",
                "« Investissements » > « Nouvelle demande » : type, intitulé, montant, justification.",
                "« Envoyer la demande » : le PDG est prévenu et décide ; suivez la réponse dans « Mes demandes ».",
                moment=BESOIN,
                avec=[R.PDG],
            ),
        ],
        "contacts": ["Le PDG peut geler une ligne ou réaffecter un véhicule directement depuis « Pilotage »."],
        "astuces": ["Une ligne fermée n'accepte plus ni vente ni nouveau départ."],
    },
    R.CHEF_GARE: {
        "mission": (
            "Tient sa gare : ses départs et leur remplissage, la caisse de ses guichetiers, son équipe locale, sa fiche et "
            "ses quais ; demande la fermeture d'une ligne quand il le faut."
        ),
        "ecrans": [
            ecran("/dashboard/gare", "Tableau de bord — Chef de gare", "Santé de la gare, départs et leurs tickets, caisses du jour de l'équipe, équipe locale, messages, colis de la gare, import des ventes, fiche de la gare et quais."),
            ecran("/configuration", "Configuration", "Régler les guichetiers et les bagagistes : automatisation, mode vocal, fonctions retirées."),
        ],
        "taches": [
            tache(
                "Tenir la fiche de sa gare",
                "« Fiche de la gare » : adresse, téléphone, horaires, coordonnées sur la carte.",
                "Ajoutez ou fermez les quais d'embarquement.",
                moment=MISE_EN_PLACE,
            ),
            tache(
                "Constituer son équipe locale",
                "« Mon équipe locale » liste les guichetiers et bagagistes de la compagnie.",
                "« Affecter à ma gare » ou « Retirer de mon équipe ».",
                moment=MISE_EN_PLACE,
                avec=[R.GUICHETIER, R.BAGAGISTE],
            ),
            tache(
                "Suivre sa gare",
                "« Santé de la gare » : ponctualité, remplissage, recettes du jour, départs en retard ; elle s'actualise chaque minute.",
                "La cloche vous signale un risque de retard, un relais sur vos départs, un véhicule bloqué par le QHSE ou par un défaut "
                "de checklist, et sa remise en service.",
                moment=DEBUT,
                avec=[R.CHEF_LIGNE, R.QHSE],
            ),
            tache(
                "Prévenir son équipe et les chauffeurs en approche",
                "« Message à mon équipe et aux chauffeurs en approche » : destinataires, texte.",
                "« Envoyer le message ».",
                avec=[R.GUICHETIER, R.BAGAGISTE],
            ),
            tache(
                "Clôturer la caisse d'un guichetier",
                "« Caisses du jour de l'équipe » : un bloc par guichetier, avec ses totaux en espèces et en mobile money.",
                "« Clôturer sa caisse » fige le montant. Chaque caisse clôturée, par le guichetier ou en fin de service, vous est signalée.",
                moment=FIN,
                avec=[R.GUICHETIER],
            ),
            tache(
                "Annuler un ticket vendu par erreur",
                "« Départs de la gare » : « Tickets » sur la ligne du départ, puis repérez le ticket.",
                "Saisissez le motif, puis « Annuler le ticket » : la place est libérée, la vente sort des recettes, l'annulation est tracée.",
                moment=BESOIN,
                avec=[R.GUICHETIER],
            ),
            tache(
                "Débloquer un colis ou annuler un enregistrement",
                "« Colis de la gare » : ceux qui partent d'ici ou y arrivent, jusqu'à leur retrait.",
                "« Renvoyer le code » : le destinataire reçoit un nouveau code, le colis verrouillé est débloqué.",
                "« Annuler l'enregistrement » avec un motif (les frais sont à rendre) ; « Marquer arrivé » un colis resté chargé alors que le car est arrivé.",
                moment=BESOIN,
                avec=[R.BAGAGISTE],
            ),
            tache(
                "Importer les ventes du logiciel de billetterie",
                "« Importer les ventes du logiciel de billetterie » : nom du logiciel, fichier CSV ou Excel, puis « Importer les ventes ».",
                "Seuls les départs de votre gare sont pris ; possible quand la billetterie de la compagnie est externe ou mixte.",
                moment=BESOIN,
                avec=[R.DIRECTEUR_EXPLOITATION],
            ),
            tache(
                "Demander la fermeture d'une ligne",
                "« Fermer ou rouvrir une ligne » : ligne concernée, motif, dernier jour de fermeture si vous le connaissez.",
                "Le directeur d'exploitation décide ; suivez la décision dans « Mes demandes ».",
                moment=BESOIN,
                avec=[R.DIRECTEUR_EXPLOITATION],
            ),
        ],
        "contacts": [
            "Les guichetiers vous demandent l'annulation d'un ticket ; les bagagistes, un nouveau code pour un colis verrouillé.",
            "Aucune gare rattachée : demandez au PDG de vous désigner chef de gare.",
        ],
        "astuces": ["Les caisses de l'équipe s'actualisent chaque minute."],
    },
    R.CHEF_LIGNE: {
        "mission": (
            "Fait rouler ses lignes à l'heure : suit les départs et les conducteurs, réaffecte un véhicule ou un chauffeur, "
            "planifie les départs, suit les véhicules à l'atelier et demande la fermeture d'une ligne."
        ),
        "ecrans": [
            ecran("/dashboard/ligne", "Tableau de bord — Chef de ligne", "Rotations, retard cumulé, cars en circulation, départs du jour et à venir, véhicules à l'atelier."),
            ecran("/lignes", "Lignes et tarifs", "Tenir les lignes et leurs tarifs."),
            ecran("/configuration", "Configuration", "Régler les chauffeurs principaux et relais."),
        ],
        "taches": [
            tache(
                "Suivre ses lignes",
                "« Départs du jour et à venir » : heure, véhicule, chauffeur, remplissage ; filtrez par ligne, le tableau s'actualise chaque minute.",
                "La cloche vous signale un risque de retard (le chef de gare du départ aussi), chaque relais et chaque incident déclaré "
                "par un conducteur ou un contrôleur.",
                moment=DEBUT,
                avec=[R.CHEF_GARE, *_CHAUFFEURS, R.CONTROLEUR_LIGNE],
            ),
            tache(
                "Planifier un départ",
                "« Planifier un départ » : ligne, date et heure, véhicule et chauffeur libres.",
                "« Planifier le départ » : la feuille de route du chauffeur est créée.",
                avec=[R.CHAUFFEUR_PRINCIPAL],
            ),
            tache(
                "Veiller au temps de conduite",
                "L'alerte « Fatigue » signale un conducteur au-delà du seuil de conduite continue, avec les relais possibles ; il est prévenu aussi.",
                "Joignez-le : il fait sa pause ou passe le relais depuis son tableau de bord.",
                avec=_CHAUFFEURS,
            ),
            tache(
                "Savoir quand un car revient de l'atelier",
                "« Véhicules à l'atelier » : réparation, urgence et retour estimé par l'atelier.",
                "À la clôture de la réparation, vous êtes prévenu que le véhicule est disponible.",
                avec=[R.CHEF_ATELIER],
            ),
            tache(
                "Remplacer un véhicule ou un chauffeur",
                "Un car bloqué (QHSE, défaut de checklist) ou en panne, ou un conducteur dont le DRH a validé le congé, vous est signalé : "
                "« Réaffecter » sur le départ.",
                "Des remplaçants libres sont suggérés ; laissez « inchangé » ce que vous ne remplacez pas, décalez l'heure au besoin, puis « Appliquer ».",
                "Aucun remplaçant : le directeur d'exploitation est prévenu de la pénurie.",
                moment=BESOIN,
                avec=[R.QHSE, R.DIRECTEUR_EXPLOITATION, R.DRH],
            ),
            tache(
                "Demander la fermeture d'une ligne",
                "« Fermer ou rouvrir une ligne » : ligne, motif, dernier jour de fermeture.",
                "Le directeur d'exploitation décide.",
                moment=BESOIN,
                avec=[R.DIRECTEUR_EXPLOITATION],
            ),
        ],
        "contacts": ["Le directeur d'exploitation arbitre les pénuries et les fermetures de ligne."],
        "astuces": ["« Supprimer » retire un départ planifié par erreur."],
    },
    R.GUICHETIER: {
        "mission": "Vend les tickets au guichet, en espèces ou en mobile money, et rend sa caisse en fin de journée.",
        "ecrans": [
            ecran("/dashboard/guichetier", "Tableau de bord — Guichetier", "Vente de ticket, remplissage du départ, caisse du jour."),
            ecran_mobile("Vendre un ticket", "Sur le téléphone, même sans réseau : la vente est envoyée dès que la connexion revient."),
        ],
        "taches": [
            tache(
                "Vendre un ticket",
                "« Vente de ticket » : choisissez le départ (la jauge montre les places restantes).",
                "Nom et téléphone du passager, mode de paiement ; le prix si la ligne est à prix libre.",
                "« Vendre le ticket ».",
            ),
            tache(
                "Vendre depuis le téléphone",
                "Accueil > « Vendre un ticket » : départ, passager, « Espèces » ou « Mobile money ».",
                "« Valider la vente ». Sans réseau, elle attend sur le téléphone et part seule ensuite.",
                "En mode vocal, la dictée démarre au choix du départ ; « Annuler » la coupe.",
            ),
            tache(
                "Clôturer sa caisse",
                "« Ma caisse du jour » : totaux en espèces et en mobile money, annulations à rendre.",
                "Niveau assisté : « Clôturer ma caisse ». Niveau manuel : remettez-la au chef de gare, qui la clôture. Niveau automatique : "
                "elle se clôture seule en fin de journée, vérifiez-la.",
                "Le chef de gare est prévenu de chaque caisse clôturée.",
                moment=FIN,
                avec=[R.CHEF_GARE],
            ),
            tache(
                "Faire annuler une vente erronée",
                "Un ticket vendu ne se modifie pas : signalez l'erreur à votre chef de gare, avec le motif.",
                "Il l'annule : la place est libérée et la somme apparaît dans les annulations à rendre de votre caisse.",
                moment=BESOIN,
                avec=[R.CHEF_GARE],
            ),
        ],
        "contacts": ["Votre chef de gare vous affecte à sa gare, clôture votre caisse et annule un ticket."],
        "astuces": ["Avant de vous déconnecter du téléphone, laissez partir les ventes en attente."],
    },
    R.BAGAGISTE: {
        "mission": "Enregistre les bagages et les colis, les charge dans le bon car et remet les colis arrivés à leur destinataire.",
        "ecrans": [
            ecran("/dashboard/bagagiste", "Tableau de bord — Bagagiste", "Enregistrer un bagage ou un colis, aide au chargement, colis à remettre, colis en route."),
        ],
        "taches": [
            tache(
                "Enregistrer un bagage ou un colis",
                "« Enregistrer un bagage ou un colis » : départ, nature (colis seul ou bagage d'un voyageur), description, poids.",
                "Frais de fret et paiement, expéditeur, destinataire et son téléphone.",
                "« Enregistrer et envoyer le code » : le destinataire reçoit son code de retrait.",
            ),
            tache(
                "Charger les colis",
                "« Aide au chargement » > « Colis à charger » : chaque colis du départ ; « Marquer chargé » au fur et à mesure.",
                "Un colis oublié au départ du car vous est signalé, ainsi qu'à votre chef de gare : voyez avec lui le prochain départ.",
                "Quand le chauffeur signale l'arrivée, les colis chargés passent en « arrivés » ; la gare d'arrivée et les clients sont prévenus.",
                avec=[*_CHAUFFEURS, R.CHEF_GARE],
            ),
            tache(
                "Remettre un colis à son destinataire",
                "« Colis à remettre (arrivés dans votre gare) » : saisissez le code du client et le nom de la personne, puis « Remettre ».",
                "Après trop de codes faux, le colis se verrouille : votre chef de gare renvoie un nouveau code au destinataire.",
                avec=[R.CHEF_GARE],
            ),
        ],
        "contacts": ["Un colis verrouillé ou un enregistrement à annuler : votre chef de gare le fait depuis « Colis de la gare »."],
        "astuces": ["« Colis en route » et « Derniers colis clôturés » répondent aux clients qui demandent où en est leur envoi."],
    },
    # ── Personnel roulant ───────────────────────────────────────────────────────────────────────────────────────────
    R.CHAUFFEUR_PRINCIPAL: {
        "mission": (
            "Conduit le car du départ à l'arrivée : contrôle le véhicule avant de partir, signale le départ, l'arrivée et "
            "les incidents, respecte les temps de conduite et passe le relais."
        ),
        "ecrans": [
            ecran("/dashboard/chauffeur", "Tableau de bord — Chauffeur", "Feuille de route du jour, checklist avant-départ, suivi du trajet (GPS, temps de conduite, relais), papiers du véhicule et carnet de route."),
            ecran_mobile("Feuille de route du jour", "Sur le téléphone, même sans réseau : le trajet du jour et la checklist avant-départ."),
        ],
        "taches": [
            tache(
                "Trouver son trajet du jour",
                "« Feuille de route du jour » (site ou téléphone) : ligne, véhicule, heure de départ.",
                "Elle est créée quand le chef de ligne ou le directeur d'exploitation planifie le départ.",
                moment=DEBUT,
                avec=[R.CHEF_LIGNE, R.DIRECTEUR_EXPLOITATION],
            ),
            tache(
                "Faire la checklist avant-départ",
                "« Remplir la checklist avant-départ » : cochez « Défaut » pour chaque élément en cause, commentaire si besoin.",
                "« Valider la checklist ». Un défaut de sécurité bloque le car ; le QHSE, l'atelier, le chef de ligne et le chef de gare sont prévenus.",
                "Sur le téléphone, en mode vocal, la dictée démarre à l'ouverture de la checklist.",
                moment=DEBUT,
                avec=[R.QHSE, R.CHEF_ATELIER],
            ),
            tache(
                "Partir et arriver",
                "« Démarrer » au départ, puis « Activer le suivi GPS » ; les positions prises sans réseau partent plus tard.",
                "« Signaler l'arrivée » à destination : le car redevient disponible, les colis chargés passent en « arrivés ».",
                avec=[R.BAGAGISTE],
            ),
            tache(
                "Respecter le temps de conduite",
                "« Temps de conduite » compte la conduite continue : « Commencer une pause », puis « Terminer la pause ».",
                "Au-delà du seuil, vous et le chef de ligne êtes prévenus.",
                avec=[R.CHEF_LIGNE],
            ),
            tache(
                "Passer le relais",
                "« Passer le relais » : conducteur qui reprend, lieu du relais ; lui, le chef de ligne et les chefs de gare sont prévenus.",
                "Celui qui reprend remplit la « Checklist de reprise » du car qu'on lui remet.",
                moment=BESOIN,
                avec=[R.CHAUFFEUR_RELAIS],
            ),
            tache(
                "Signaler un incident",
                "« Signaler un incident » : type, gravité, description, puis « Envoyer le signalement ».",
                "Le chef de ligne est prévenu ; une panne ou un accident prévient aussi l'atelier ; un incident grave, le directeur "
                "d'exploitation, le QHSE et le chef de gare.",
                "Une anomalie de cargaison se signale de même dans « Surveillance de la cargaison ».",
                moment=BESOIN,
                avec=[R.CHEF_LIGNE, R.CHEF_ATELIER, R.QHSE, R.DIRECTEUR_EXPLOITATION],
            ),
            tache(
                "Supprimer sa feuille de route",
                "« Supprimer cette feuille de route », tant que le départ n'a pas démarré ; le départ reste planifié.",
                moment=BESOIN,
                avec=[R.DIRECTEUR_EXPLOITATION],
                regle="chauffeur_supprime_ses_feuilles",
            ),
            tache(
                "Supprimer un incident déclaré par erreur",
                "« Mes incidents déclarés » : « Supprimer » sur l'incident.",
                moment=BESOIN,
                avec=[R.DIRECTEUR_EXPLOITATION],
                regle="chauffeur_supprime_ses_incidents",
            ),
        ],
        "contacts": ["Le chef de ligne planifie et réaffecte vos départs."],
        "astuces": ["« Carnet de route » garde les papiers du véhicule et vos derniers trajets."],
    },
    R.CHAUFFEUR_RELAIS: {
        "mission": "Prend le volant au relais : reçoit le car, constate son état, poursuit le trajet jusqu'à l'arrivée.",
        "ecrans": [
            ecran("/dashboard/chauffeur", "Tableau de bord — Chauffeur", "Feuille de route du jour, checklist de reprise, suivi du trajet, papiers du véhicule et carnet de route."),
            ecran_mobile("Feuille de route du jour", "Sur le téléphone, même sans réseau : le trajet du jour et la checklist avant-départ."),
        ],
        "taches": [
            tache(
                "Être prévenu du relais",
                "L'alerte « Relais » vous dit la ligne et le lieu ; le chef de ligne la reçoit aussi.",
                moment=DEBUT,
                avec=[R.CHEF_LIGNE, R.CHAUFFEUR_PRINCIPAL],
            ),
            tache(
                "Reprendre le car au relais",
                "« Checklist de reprise » : constatez l'état du car qu'on vous remet, élément par élément.",
                "Un défaut prévient le chef de ligne et l'atelier ; un défaut de sécurité, aussi le QHSE et le directeur d'exploitation.",
                avec=[R.CHAUFFEUR_PRINCIPAL, R.CHEF_ATELIER, R.QHSE],
            ),
            tache(
                "Conduire et arriver",
                "« Activer le suivi GPS », respectez les pauses (« Commencer une pause »).",
                "« Signaler l'arrivée » à destination : les colis chargés passent en « arrivés ».",
                avec=[R.BAGAGISTE],
            ),
            tache(
                "Signaler un incident",
                "« Signaler un incident » : type, gravité, description, puis « Envoyer le signalement ».",
                "Le chef de ligne est prévenu ; un incident grave, aussi le QHSE.",
                moment=BESOIN,
                avec=[R.CHEF_LIGNE, R.QHSE],
            ),
            tache(
                "Supprimer sa feuille de route",
                "« Supprimer cette feuille de route », tant que le départ n'a pas démarré ; le départ reste planifié.",
                moment=BESOIN,
                avec=[R.DIRECTEUR_EXPLOITATION],
                regle="chauffeur_supprime_ses_feuilles",
            ),
            tache(
                "Supprimer un incident déclaré par erreur",
                "« Mes incidents déclarés » : « Supprimer » sur l'incident.",
                moment=BESOIN,
                avec=[R.DIRECTEUR_EXPLOITATION],
                regle="chauffeur_supprime_ses_incidents",
            ),
        ],
        "contacts": ["Le chef de ligne organise les relais et règle votre poste."],
        "astuces": ["Vos trajets passés sont dans « Carnet de route »."],
    },
    R.CONTROLEUR_LIGNE: {
        "mission": (
            "Contrôle à bord : vérifie chaque billet, compte les voyageurs, vérifie la charge et signale les infractions "
            "et les incidents."
        ),
        "ecrans": [
            ecran("/dashboard/controle", "Tableau de bord — Contrôleur de ligne", "Contrôle à bord des billets, vérification de la charge, liste des passagers, infractions et incidents."),
        ],
        "taches": [
            tache(
                "Contrôler les billets",
                "« Ouvrir un contrôle » : choisissez le trajet, puis « Ouvrir le contrôle ».",
                "« Code du billet » : saisissez ou scannez, « Vérifier ». Un billet ne sert qu'une fois (« Déjà utilisé », « Autre départ »...).",
            ),
            tache(
                "Vérifier la charge et les passagers",
                "« Vérification de la charge et incidents » : choisissez le départ du jour.",
                "Comparez la liste des passagers aux voyageurs à bord ; cherchez par nom ou téléphone.",
            ),
            tache(
                "Clôturer le contrôle",
                "« Clôturer le contrôle » : voyageurs comptés à bord, charge constatée, commentaire.",
                "Infraction grave : cochez-la et donnez son motif ; le PDG, le directeur d'exploitation et le QHSE sont prévenus.",
                "« Clôturer et générer le rapport ».",
                moment=FIN,
                avec=[R.PDG, R.DIRECTEUR_EXPLOITATION, R.QHSE],
            ),
            tache(
                "Signaler une infraction ou un incident",
                "« Signaler une infraction ou un incident » : type, gravité, description, puis « Signaler ».",
                "Le chef de ligne est prévenu ; un incident grave, aussi le QHSE, le directeur d'exploitation et le chef de gare.",
                moment=BESOIN,
                avec=[R.CHEF_LIGNE, R.QHSE],
            ),
        ],
        "contacts": ["Le directeur d'exploitation règle votre poste."],
        "astuces": ["« Historique des contrôles » se filtre par ligne et par conducteur."],
    },
    # ── Technique & Maintenance ─────────────────────────────────────────────────────────────────────────────────────
    R.DIRECTEUR_TECHNIQUE: {
        "mission": (
            "Garde la flotte disponible et sûre : priorise les réparations, planifie l'entretien préventif, surveille le "
            "stock, les assurances et le renouvellement des véhicules."
        ),
        "ecrans": [
            ecran("/dashboard/technique", "Tableau de bord — Technique", "Disponibilité de la flotte, file de l'atelier, pièces sous seuil, assurances à renouveler, entretien préventif, approvisionnement, fiche véhicule."),
            ecran("/vehicules", "Véhicules", "Le parc, ses papiers et son kilométrage."),
            ecran("/pieces", "Pièces et stock", "Catalogue, réceptions, inventaire et historique de chaque pièce."),
            ecran("/investissements", "Investissements", "Demander l'achat de véhicules au PDG."),
            ecran("/reglement", "Règlement intérieur", "Les règles de l'atelier et du magasin (sorties de pièces, ordres du mécanicien)."),
            ecran("/configuration", "Configuration", "Régler le magasinier et le chef d'atelier."),
        ],
        "taches": [
            tache(
                "Régler ce que l'atelier et le magasin peuvent faire",
                "« Règlement intérieur » : corriger une sortie de pièce, confier ou supprimer un ordre de réparation (permis par défaut).",
                "Leurs écrans n'affichent ces boutons que si la compagnie le permet.",
                moment=MISE_EN_PLACE,
                avec=[R.PDG, R.MAGASINIER, R.CHEF_ATELIER, R.MECANICIEN],
            ),
            tache(
                "Planifier l'entretien préventif",
                "« Entretien préventif » > « Déclarer un plan d'entretien » : véhicule, périodicité en jours ou en km.",
                "Cochez « Obligation réglementaire » pour le suivre au tableau de conformité ; « Retirer » un plan devenu sans objet.",
                moment=MISE_EN_PLACE,
            ),
            tache(
                "Faire le point de la flotte",
                "« Tableau de bord — Technique » : disponibilité, véhicules bloqués par le QHSE, en maintenance, sinistres en cours.",
                "La cloche vous signale un blocage de sécurité, un défaut de checklist, une panne déclarée, un stock bas et les pannes en hausse.",
                moment=DEBUT,
                avec=[R.QHSE],
            ),
            tache(
                "Prioriser l'atelier",
                "« Réparations » > « File d'attente de l'atelier » : urgence, délai estimé, intervenant.",
                "Changez l'urgence ou l'ordre de la file ; à urgence égale, la position prime sur l'ancienneté.",
                avec=[R.CHEF_ATELIER],
            ),
            tache(
                "Commander les pièces à temps",
                "« Approvisionnement » : le réapprovisionnement suggéré d'après la consommation des 90 derniers jours.",
                "Un stock bas, une rupture ou un manque relevé à l'inventaire par le magasinier vous est signalé.",
                avec=[R.MAGASINIER],
            ),
            tache(
                "Renouveler les assurances",
                "« Assurances à renouveler (30 jours) » : chaque échéance vous est signalée, comme au responsable juridique qui les renouvelle.",
                moment=BESOIN,
                avec=[R.RESPONSABLE_JURIDIQUE],
            ),
            tache(
                "Décider du renouvellement d'un véhicule",
                "« Renouvellement de la flotte » : compteur, réparations et immobilisation sur 12 mois, recommandation.",
                "« Investissements » > « Nouvelle demande » : le PDG décide.",
                moment=BESOIN,
                avec=[R.PDG],
            ),
            tache(
                "Corriger ou annuler une sortie de pièce",
                "« Pièces et stock » > « Mouvements » de la pièce : sur la sortie, « Corriger » la quantité ou « Annuler la sortie ».",
                "La différence revient au stock (ou en sort, si le stock la couvre).",
                moment=BESOIN,
                avec=[R.MAGASINIER],
                regle="sorties_pieces_corrigeables",
            ),
        ],
        "contacts": ["Le magasinier et le chef d'atelier relèvent de vous."],
        "astuces": ["« Fiche véhicule » : pannes récurrentes, pièces montées et historique des interventions d'un car."],
    },
    R.MAGASINIER: {
        "mission": "Tient le magasin de pièces : reçoit les livraisons, sert les demandes de l'atelier et compte le stock.",
        "ecrans": [
            ecran("/dashboard/magasinier", "Tableau de bord — Magasinier", "Stock et seuils d'alerte, demandes de pièces de l'atelier, réapprovisionnement suggéré."),
            ecran("/pieces", "Pièces et stock", "Catalogue, réceptions, inventaire, historique de chaque pièce."),
        ],
        "taches": [
            tache(
                "Ajouter une pièce au catalogue",
                "« Pièces et stock » > « Nouvelle pièce » : désignation, référence, stock de départ, seuil d'alerte, prix, fournisseur, emplacement.",
                moment=MISE_EN_PLACE,
            ),
            tache(
                "Servir une demande de l'atelier",
                "Chaque demande de pièce vous est signalée et s'affiche sur votre tableau de bord, avec le stock disponible.",
                "« Servir », ou « Refuser » avec un motif : le demandeur est prévenu.",
                avec=[R.MECANICIEN, R.CHEF_ATELIER],
            ),
            tache(
                "Enregistrer une livraison",
                "« Pièces et stock » > « Réception » : pièce, quantité reçue, prix payé, fournisseur, n° du bon.",
                "« Enregistrer la réception » : le stock monte, le prix suit le coût moyen.",
            ),
            tache(
                "Anticiper les ruptures",
                "« Réapprovisionnement suggéré » : jours de stock et quantité à commander.",
                "Un stock bas ou une rupture vous est signalé, ainsi qu'au directeur technique qui décide des commandes.",
                avec=[R.DIRECTEUR_TECHNIQUE],
            ),
            tache(
                "Faire l'inventaire",
                "« Pièces et stock » > « Inventaire » : pièce, quantité comptée ; un écart exige un motif.",
                "« Enregistrer le comptage » : le stock prend la quantité comptée ; un manque prévient le directeur technique.",
                moment=BESOIN,
                avec=[R.DIRECTEUR_TECHNIQUE],
            ),
            tache(
                "Corriger ou annuler une sortie de pièce",
                "« Pièces et stock » > « Mouvements » de la pièce : sur la sortie, « Corriger » la quantité ou « Annuler la sortie ».",
                "La différence revient au stock (ou en sort, si le stock la couvre).",
                moment=BESOIN,
                avec=[R.DIRECTEUR_TECHNIQUE],
                regle="sorties_pieces_corrigeables",
            ),
        ],
        "contacts": ["Le directeur technique règle votre poste et décide des commandes."],
        "astuces": ["Réceptions et inventaires ne se modifient pas : l'historique d'une pièce reste juste."],
    },
    R.CHEF_ATELIER: {
        "mission": (
            "Dirige l'atelier : prend en charge les pannes signalées, ouvre les ordres de réparation, les répartit entre "
            "mécaniciens, suit leur avancement et l'entretien préventif."
        ),
        "ecrans": [
            ecran("/dashboard/atelier", "Tableau de bord — Chef d'atelier", "Ordres de réparation en cours, ouvrir un ordre, pilotage de l'atelier, entretien préventif, fiche véhicule, demandes de pièces."),
            ecran("/vehicules", "Véhicules", "Le parc et son kilométrage."),
            ecran("/pieces", "Pièces et stock", "Catalogue, réceptions, inventaire."),
            ecran("/configuration", "Configuration", "Régler les mécaniciens."),
        ],
        "taches": [
            tache(
                "Prendre en charge les pannes signalées",
                "La cloche vous signale un défaut de checklist, une panne ou un accident déclaré, un défaut à la reprise d'un trajet "
                "et un blocage de sécurité posé par le QHSE.",
                "« Fiche véhicule » montre les pannes récurrentes du car avant d'ouvrir l'ordre.",
                moment=DEBUT,
                avec=[R.QHSE, *_CHAUFFEURS],
            ),
            tache(
                "Ouvrir un ordre de réparation",
                "« Ouvrir un ordre de réparation » : véhicule, description de la panne, mécanicien.",
                "« Ouvrir l'ordre » : le mécanicien est prévenu ; un véhicule bloqué passe en maintenance.",
                avec=[R.MECANICIEN],
            ),
            tache(
                "Répartir et prioriser",
                "« Pilotage de l'atelier » : file d'attente, urgence, délai estimé, intervenant ; la charge suggère à qui confier le prochain ordre.",
                "Le délai estimé donne au chef de ligne le retour prévu du car ; le directeur technique suit la même file.",
                avec=[R.DIRECTEUR_TECHNIQUE, R.CHEF_LIGNE],
            ),
            tache(
                "Suivre une intervention",
                "« Ordres de réparation en cours » : « Démarrer », puis « Clôturer » avec le temps passé.",
                "À la clôture, le véhicule redevient disponible ; le chef de ligne et les gares en sont prévenus. Un car bloqué par le QHSE "
                "attend sa levée si le règlement intérieur l'exige.",
            ),
            tache(
                "Demander une pièce au magasin",
                "« Demander une pièce au magasinier » : ordre de réparation, pièce, quantité, puis « Envoyer la demande ».",
                moment=BESOIN,
                avec=[R.MAGASINIER],
            ),
            tache(
                "Corriger ou annuler une sortie de pièce",
                "« Pièces et stock » > « Mouvements » de la pièce : sur la sortie, « Corriger » la quantité ou « Annuler la sortie ».",
                "La différence revient au stock (ou en sort, si le stock la couvre).",
                moment=BESOIN,
                avec=[R.DIRECTEUR_TECHNIQUE],
                regle="sorties_pieces_corrigeables",
            ),
        ],
        "contacts": ["Le directeur technique règle votre poste ; le magasinier sert les pièces."],
        "astuces": ["« Entretien préventif » : relevez le kilométrage et marquez « Fait » un entretien réalisé."],
    },
    R.MECANICIEN: {
        "mission": "Répare les véhicules : réalise les interventions qui lui sont confiées et trace les pièces utilisées.",
        "ecrans": [
            ecran("/dashboard/mecanicien", "Tableau de bord — Mécanicien", "Mes interventions, sortir une pièce du stock, demander une pièce."),
        ],
        "taches": [
            tache(
                "Voir ses interventions",
                "« Mes interventions » : les ordres que le chef d'atelier vous confie ; chaque nouvel ordre vous est signalé.",
                moment=DEBUT,
                avec=[R.CHEF_ATELIER],
            ),
            tache(
                "Réaliser une intervention",
                "« Démarrer » quand vous commencez ; « Clôturer » avec le temps passé (en minutes).",
            ),
            tache(
                "Sortir une pièce du stock",
                "« Sortir une pièce du stock » : ordre de réparation, pièce, quantité, puis « Enregistrer la sortie ».",
            ),
            tache(
                "Demander une pièce au magasinier",
                "« Demander une pièce au magasinier » : ordre, pièce, quantité, puis « Envoyer la demande ».",
                "Le magasinier la sert ou la refuse : vous êtes prévenu ; « Annuler » si elle n'est plus utile.",
                moment=BESOIN,
                avec=[R.MAGASINIER],
            ),
            tache(
                "Confier son intervention à un collègue",
                "« Mes interventions » : choisissez le collègue dans « Confier à », puis « Confier ».",
                "Lui et le chef d'atelier sont prévenus. Le directeur technique décide, au règlement intérieur, si ce geste est permis.",
                moment=BESOIN,
                avec=[R.CHEF_ATELIER, R.DIRECTEUR_TECHNIQUE],
                regle="mecanicien_confie_ses_ordres",
            ),
            tache(
                "Supprimer un ordre de réparation",
                "« Mes interventions » : « Supprimer » sur l'ordre ouvert par erreur.",
                moment=BESOIN,
                avec=[R.CHEF_ATELIER, R.DIRECTEUR_TECHNIQUE],
                regle="mecanicien_supprime_ses_ordres",
            ),
        ],
        "contacts": ["Le chef d'atelier vous confie les ordres, les réaffecte et règle votre poste."],
        "astuces": ["Le nombre d'interventions à faire et clôturées aujourd'hui s'affiche en haut du tableau."],
    },
    # ── Fonctions supports ──────────────────────────────────────────────────────────────────────────────────────────
    R.DRH: {
        "mission": (
            "Gère les ressources humaines : dossiers des agents, contrats, évaluations et discipline, formations "
            "obligatoires, congés, recrutement et médiation sociale."
        ),
        "ecrans": [
            ecran("/dashboard/rh", "Tableau de bord — Ressources humaines", "Vue d'ensemble, dossiers, formations obligatoires, congés, recrutement, médiation sociale."),
            ecran("/personnel", "Personnel et comptes", "Créer et modifier les comptes, si le règlement intérieur vous le permet."),
        ],
        "taches": [
            tache(
                "Ouvrir et tenir un dossier agent",
                "Un compte créé avec sa date d'embauche a déjà son dossier ; sinon, onglet « Dossiers » > « Ouvrir un dossier ».",
                "« Fiche complète » : contrats, évaluations, discipline, formations obligatoires.",
                moment=MISE_EN_PLACE,
                avec=[R.PDG],
            ),
            tache(
                "Suivre les formations obligatoires",
                "Onglet « Formations obligatoires » : « Ajouter une obligation » (validité, préavis, postes concernés).",
                "« Enregistrer une session suivie » ; le suivi par agent montre les formations expirées, à renouveler, manquantes.",
                "Une formation expirée ou à renouveler vous est signalée, ainsi qu'au QHSE qui lit le même suivi.",
                moment=MISE_EN_PLACE,
                avec=[R.QHSE],
            ),
            tache(
                "Décider d'un congé",
                "Onglet « Congés » : « Approuver le congé de... » ; s'il touche des départs de l'agent, ils s'affichent : "
                "« Valider malgré tout » ou renoncez.",
                "« Refuser » demande un motif ; l'agent voit la réponse dans « Mes congés ».",
                "Un congé validé qui touche des départs d'un conducteur prévient le directeur d'exploitation et le chef de ligne, qui les réaffectent.",
                avec=[R.DIRECTEUR_EXPLOITATION, R.CHEF_LIGNE],
            ),
            tache(
                "Instruire une doléance",
                "Onglet « Médiation sociale » : ouvrez la doléance, ajoutez une étape (visible ou non du déposant), changez son statut.",
                "Une doléance grave est signalée au responsable juridique comme risque de litige social (au PDG aussi si elle est critique).",
                moment=BESOIN,
                avec=[R.RESPONSABLE_JURIDIQUE],
            ),
            tache(
                "Recruter",
                "Onglet « Recrutement » > « Ouvrir une offre » : poste, nombre, lieu, date limite.",
                "Ajoutez les candidatures reçues et décidez.",
                moment=BESOIN,
            ),
            tache(
                "Créer le compte d'un agent",
                "« Personnel et comptes » > « Nouveau compte » ; le mot de passe provisoire s'affiche une seule fois.",
                "Le PDG est prévenu des comptes que vous créez ou modifiez.",
                moment=BESOIN,
                avec=[R.PDG],
                regle="drh_gere_les_comptes",
            ),
        ],
        "contacts": ["Le PDG suspend un compte ; vous en êtes prévenu."],
        "astuces": ["Les scores de gamification aident à l'évaluation : lisez-les avec le contexte de chaque poste."],
    },
    R.DIRECTEUR_FINANCIER: {
        "mission": (
            "Tient la comptabilité : recettes, dépenses, budgets carburant, factures fournisseurs et trésorerie ; mesure "
            "la rentabilité par ligne et par gare."
        ),
        "ecrans": [
            ecran("/dashboard/finance", "Tableau de bord — Finance", "Recettes de billetterie et de fret, modes d'encaissement, recettes par gare, évolution, trésorerie."),
            ecran("/comptabilite", "Comptabilité", "Trésorerie, budget carburant, rentabilité, dépenses, fournisseurs et paiements."),
            ecran("/investissements", "Investissements", "Demander un investissement au PDG."),
        ],
        "taches": [
            tache(
                "Fixer le point de départ et les budgets",
                "« Solde de caisse de départ » : le solde à partir duquel la trésorerie se calcule.",
                "« Budget carburant » > « Fixer le budget carburant » : mois, ligne, montant.",
                moment=MISE_EN_PLACE,
            ),
            tache(
                "Faire le point des recettes",
                "« Tableau de bord — Finance » : recettes de billetterie et de fret, part du mobile money, recettes par gare.",
                "Une recette en baisse sur 7 jours vous est signalée, ainsi qu'au PDG.",
                moment=DEBUT,
                avec=[R.PDG],
            ),
            tache(
                "Enregistrer une dépense",
                "« Comptabilité » > « Dépenses » : date, catégorie, libellé, montant ; la ligne, le véhicule ou la gare concernés.",
                "« Enregistrer la dépense ».",
            ),
            tache(
                "Payer une facture",
                "« Fournisseurs et paiements » : ajoutez le fournisseur, puis « Enregistrer une facture ou une prime à payer ».",
                "À l'échéance, « Payer » ; « Annuler » une facture erronée ; « Retirer » un fournisseur sans facture.",
            ),
            tache(
                "Exporter les recettes",
                "Tableau de bord : choisissez la période, puis « Exporter (Excel / CSV) » ; « Rentabilité » s'imprime en PDF.",
                moment=FIN,
            ),
            tache(
                "Demander un investissement",
                "« Investissements » > « Nouvelle demande » : type, intitulé, montant, justification ; le PDG décide.",
                moment=BESOIN,
                avec=[R.PDG],
            ),
        ],
        "contacts": ["Le PDG et le secrétaire général lisent la situation dans « Finances »."],
        "astuces": ["Le suivi du budget carburant compare le budget au dépensé, ligne par ligne."],
    },
    R.RESPONSABLE_JURIDIQUE: {
        "mission": (
            "Protège la compagnie : assurances de la flotte, sinistres et leurs pièces, conformité réglementaire, litiges "
            "sociaux et bibliothèque de modèles de documents."
        ),
        "ecrans": [
            ecran("/dashboard/juridique", "Tableau de bord — Juridique", "Assurances et sinistres, litiges sociaux, modèles de documents, synthèse pour la direction, échanges avec la tutelle, conformité de la flotte."),
        ],
        "taches": [
            tache(
                "Publier un modèle de document",
                "Onglet « Modèles de documents » : titre, catégorie, texte, fichier.",
                "Cochez les pôles autorisés (aucun coché : tous) ; ils le lisent dans « Modèles juridiques ».",
                moment=MISE_EN_PLACE,
            ),
            tache(
                "Enregistrer et renouveler une assurance",
                "« Enregistrer une assurance » : véhicule, assureur, n° de police, échéance.",
                "Chaque échéance proche vous est signalée, comme au directeur technique : « Renouveler » jusqu'à la nouvelle date.",
                "« Supprimer » une police saisie par erreur.",
                avec=[R.DIRECTEUR_TECHNIQUE],
            ),
            tache(
                "Suivre la conformité et les litiges",
                "« Conformité réglementaire de la flotte » : la même vue que le QHSE.",
                "Onglet « Litiges sociaux » : les doléances graves que le DRH instruit ; chacune vous est signalée (au PDG aussi si elle est critique).",
                avec=[R.QHSE, R.DRH],
            ),
            tache(
                "Déclarer et suivre un sinistre",
                "« Déclarer un sinistre » : véhicule, description, incident lié s'il existe.",
                "Le dossier : référence chez l'assureur, montants, « Joindre la pièce » (constat, photo, expertise).",
                "Un sinistre déclaré par erreur se supprime tant qu'il n'a aucune pièce jointe.",
                moment=BESOIN,
            ),
            tache(
                "Suivre les échanges avec la tutelle",
                "Onglet « Tutelle » : ce qui part vers le ministère (incidents graves, assurances à échéance) et ce qu'il envoie.",
                "« Marquer traité » ; « Rattraper les flux automatiques » génère ceux qui manquent, sans doublon.",
                moment=BESOIN,
                avec=[R.QHSE],
            ),
            tache(
                "Informer la direction",
                "Onglet « Synthèse pour la Direction » : points de vigilance, puis « Imprimer / PDF ».",
                "Le PDG la lit aussi dans « Synthèse RH et juridique ».",
                moment=BESOIN,
                avec=[R.PDG],
            ),
        ],
        "contacts": ["La conformité de la flotte est partagée avec le QHSE ; les litiges sociaux viennent du DRH."],
        "astuces": ["Les assurances expirées et à renouveler sous 30 jours sont comptées en haut du tableau."],
    },
}

# L'opérateur de la plateforme : hors des compagnies, sa fiche n'est montrée qu'à lui.
PLATEFORME = {
    "pole": "plateforme",
    "libelle": "Plateforme",
    "fiche": {
        "mission": "Opère la plateforme : suit l'activité de chaque compagnie, sans en faire partie.",
        "ecrans": [
            ecran("/dashboard/plateforme", "Tableau de bord — Plateforme", "Compagnies, agents, gares, lignes, véhicules, ventes et recettes du jour, alertes."),
            ecran("/audit", "Journal d'audit", "Le journal de toutes les compagnies."),
        ],
        "taches": [
            tache("Suivre les compagnies", "Le tableau liste chaque compagnie avec son activité du jour et ses alertes.", moment=DEBUT),
        ],
        "contacts": ["Chaque compagnie gère ses comptes, son cadre et son règlement intérieur."],
        "astuces": ["Vous lisez les guides de tous les postes pour accompagner les compagnies."],
    },
}

POLE_DU_POSTE = {role: cle for cle, (_, roles) in POLES.items() for role in roles}


def _regle_par(role):
    """Qui règle ce poste dans la configuration : son supérieur direct, puis le PDG (qui règle tout poste)."""
    superieurs = [sup for sup, subordonnes in regles.SUBORDONNES.items() if role in subordonnes and sup != Role.PDG]
    return [sup.label for sup in superieurs] + ([Role.PDG.label] if role != Role.PDG else [])


def _fiche(role, contenu, reglement):
    societe = role != Role.SUPERADMIN
    return {
        "poste": role.value,
        "libelle": role.label,
        **contenu,
        "taches": [
            {
                **t,
                "moment_libelle": MOMENTS[t["moment"]],
                "avec": [{"poste": r.value, "libelle": r.label} for r in t["avec"]],
                "permise": reglement[t["regle"]] if t["regle"] else None,
            }
            for t in contenu["taches"]
        ],
        "regle_par": _regle_par(role) if societe else [],
        "regle": [sub.label for sub in regles.POSTES if sub in regles.SUBORDONNES.get(role, ())],
        "reglement": [
            {"code": code, "libelle": regle.libelle, "permis": reglement[code], "decide": Role(regle.pole).label}
            for code, regle in regles.REGLEMENT.items()
            if role in regle.roles
        ],
    }


def guide_pour(user):
    """Le guide de tous les postes, rangé par pôle ; le règlement intérieur cité est celui de la compagnie du lecteur (le défaut du
    socle pour l'opérateur de la plateforme)."""
    reglement = reglement_de(user.company_id)
    poles = [
        {"pole": cle, "libelle": libelle, "postes": [_fiche(role, FICHES[role], reglement) for role in roles]}
        for cle, (libelle, roles) in POLES.items()
    ]
    if user.role == Role.SUPERADMIN:
        fiche = _fiche(Role.SUPERADMIN, PLATEFORME["fiche"], reglement)
        poles.append({"pole": PLATEFORME["pole"], "libelle": PLATEFORME["libelle"], "postes": [fiche]})
    communs = {**COMMUNS, "taches": [{**t, "moment_libelle": MOMENTS[t["moment"]]} for t in COMMUNS["taches"]]}
    return {
        "mon_poste": user.role,
        "mon_pole": POLE_DU_POSTE.get(user.role, PLATEFORME["pole"] if user.role == Role.SUPERADMIN else None),
        "moments": [{"code": code, "libelle": libelle} for code, libelle in MOMENTS.items()],
        "communs": communs,
        "poles": poles,
    }
