"""Parcours de formation livrés par défaut, d'après le cahier des charges.

Toutes les données ci-dessous sont FICTIVES et propres à la formation : elles
n'existent que dans ``EtapeFormation.donnees_simulees`` et ne correspondent à
aucun enregistrement des vrais modules (billetterie, personnel roulant, maintenance).
Les phrases sont volontairement courtes : ces postes de terrain sont peu familiers
du numérique (voir « Contraintes et risques » du cahier des charges).
"""

from django.db import transaction

from core.models import Role
from formation.models import EtapeFormation, ParcoursFormation, TypeAction

PARCOURS_DE_BASE = [
    {
        "role": Role.GUICHETIER,
        "titre": "Formation guichetier : vendre, encaisser, clôturer",
        "description": (
            "Apprenez à vendre un ticket en un geste, à encaisser en espèces ou en mobile money, "
            "à gérer un car complet et à clôturer votre caisse. Tout se passe en simulation : "
            "aucune vraie vente n'est enregistrée et aucun SMS n'est envoyé."
        ),
        "etapes": [
            {
                "ordre": 1,
                "titre": "Consulter les départs et la jauge de remplissage",
                "instructions": (
                    "Ouvrez la liste des départs du jour. Pour chaque départ, repérez le nombre de "
                    "places restantes. C'est ce que vous regardez avant chaque vente."
                ),
                "scenario": "consulter_departs",
                "donnees_simulees": {
                    "departs": [
                        {"ligne": "Abidjan → Bouaké (formation)", "heure": "08:00", "capacite": 30, "places_vendues": 12},
                        {"ligne": "Abidjan → Yamoussoukro (formation)", "heure": "09:30", "capacite": 30, "places_vendues": 29},
                        {"ligne": "Abidjan → Korhogo (formation)", "heure": "11:00", "capacite": 30, "places_vendues": 30},
                    ],
                    "question": "Sur quel départ reste-t-il une seule place ?",
                    "reponse_attendue": "Abidjan → Yamoussoukro (formation)",
                },
            },
            {
                "ordre": 2,
                "titre": "Vendre un ticket en espèces",
                "instructions": (
                    "Choisissez le départ, saisissez le nom et le téléphone du voyageur, vérifiez le "
                    "tarif proposé, puis validez l'encaissement en espèces. La jauge du car augmente "
                    "de 1. Exercice simulé : aucun SMS n'est envoyé."
                ),
                "scenario": "vente_ticket",
                "donnees_simulees": {
                    "depart": {"ligne": "Abidjan → Bouaké (formation)", "heure": "08:00", "capacite": 30, "places_vendues": 12},
                    "passager": {"nom": "Kouadio Formation", "telephone": "+2250000000000"},
                    "tarif": 5000,
                    "mode_paiement": "especes",
                    "resultat_attendu": {"places_vendues": 13, "places_restantes": 17},
                },
            },
            {
                "ordre": 3,
                "titre": "Encaisser un ticket par mobile money",
                "instructions": (
                    "Même vente, mais le voyageur paie par mobile money. Choisissez ce mode de "
                    "paiement avant de valider. Exercice simulé : aucun vrai paiement n'est déclenché."
                ),
                "scenario": "vente_ticket",
                "donnees_simulees": {
                    "depart": {"ligne": "Abidjan → Bouaké (formation)", "heure": "08:00", "capacite": 30, "places_vendues": 13},
                    "passager": {"nom": "Aminata Formation", "telephone": "+2250000000001"},
                    "tarif": 5000,
                    "mode_paiement": "mobile_money",
                    "resultat_attendu": {"places_vendues": 14, "places_restantes": 16},
                },
            },
            {
                "ordre": 4,
                "titre": "Refuser une vente quand le car est complet",
                "instructions": (
                    "Essayez de vendre une place sur un départ complet. Le logiciel refuse : vous ne "
                    "pouvez pas vendre plus de places que le car n'en a. Proposez un autre départ."
                ),
                "scenario": "vente_ticket_depart_complet",
                "donnees_simulees": {
                    "depart": {"ligne": "Abidjan → Korhogo (formation)", "heure": "11:00", "capacite": 30, "places_vendues": 30},
                    "resultat_attendu": {"vente_acceptee": False, "message": "Plus aucune place disponible sur ce départ."},
                },
            },
            {
                "ordre": 5,
                "titre": "Clôturer votre caisse en fin de service",
                "instructions": (
                    "Vérifiez le total de vos ventes de la journée, en espèces et en mobile money, "
                    "puis validez la clôture. Le chef de gare reçoit ce total."
                ),
                "scenario": "cloture_caisse",
                "donnees_simulees": {
                    "ventes": [
                        {"tarif": 5000, "mode_paiement": "especes"},
                        {"tarif": 5000, "mode_paiement": "especes"},
                        {"tarif": 5000, "mode_paiement": "especes"},
                        {"tarif": 5000, "mode_paiement": "mobile_money"},
                        {"tarif": 5000, "mode_paiement": "mobile_money"},
                    ],
                    "resultat_attendu": {"total_especes": 15000, "total_mobile_money": 10000, "total": 25000},
                },
            },
        ],
    },
    {
        "role": Role.CHAUFFEUR_PRINCIPAL,
        "titre": "Formation chauffeur : avant le départ, sécurité d'abord",
        "description": (
            "Apprenez à lire votre feuille de route, à faire la checklist avant-départ, à comprendre "
            "pourquoi un défaut de sécurité bloque le véhicule, et à signaler une panne. Tout se "
            "passe en simulation : aucun vrai véhicule n'est bloqué."
        ),
        "etapes": [
            {
                "ordre": 1,
                "titre": "Consulter votre feuille de route du jour",
                "instructions": (
                    "Ouvrez votre feuille de route : ligne, heure de départ prévue et véhicule affecté. "
                    "C'est le chef de ligne qui vous l'envoie."
                ),
                "scenario": "consulter_feuille_de_route",
                "donnees_simulees": {
                    "feuille_de_route": {
                        "ligne": "Abidjan → Bouaké (formation)",
                        "heure_depart_prevue": "06:30",
                        "vehicule": "SIM-0001-AA",
                    },
                    "question": "À quelle heure devez-vous partir ?",
                    "reponse_attendue": "06:30",
                },
            },
            {
                "ordre": 2,
                "titre": "Faire la checklist avant-départ",
                "instructions": (
                    "Passez chaque point en revue, un par un : pneus, freins, direction, éclairage, "
                    "ceintures, extincteur, carburant. Marquez chacun « OK » ou « Défaut »."
                ),
                "scenario": "checklist_avant_depart",
                "donnees_simulees": {
                    "vehicule": "SIM-0001-AA",
                    "items": [
                        {"item": "pneus", "etat": "ok"},
                        {"item": "freins", "etat": "ok"},
                        {"item": "direction", "etat": "ok"},
                        {"item": "eclairage", "etat": "ok"},
                        {"item": "ceintures", "etat": "ok"},
                        {"item": "extincteur", "etat": "ok"},
                        {"item": "carburant", "etat": "ok"},
                    ],
                    "resultat_attendu": {"depart_autorise": True},
                },
            },
            {
                "ordre": 3,
                "titre": "Signaler un défaut de sécurité : le véhicule est bloqué",
                "instructions": (
                    "Les freins sont défaillants : marquez « Défaut ». Un défaut sur un point de "
                    "sécurité (pneus, freins, direction, éclairage, ceintures, extincteur) bloque "
                    "le véhicule : vous ne pouvez pas partir. Un carburant bas, lui, ne bloque pas."
                ),
                "scenario": "checklist_defaut_securite",
                "donnees_simulees": {
                    "vehicule": "SIM-0002-AA",
                    "items": [
                        {"item": "pneus", "etat": "ok"},
                        {"item": "freins", "etat": "defaut"},
                        {"item": "direction", "etat": "ok"},
                        {"item": "eclairage", "etat": "ok"},
                        {"item": "ceintures", "etat": "ok"},
                        {"item": "extincteur", "etat": "ok"},
                        {"item": "carburant", "etat": "defaut"},
                    ],
                    "resultat_attendu": {"vehicule_bloque": True, "depart_autorise": False},
                },
            },
            {
                "ordre": 4,
                "titre": "Signaler une panne ou un incident",
                "instructions": (
                    "En route, votre car tombe en panne. Choisissez le type d'incident et sa gravité, "
                    "puis décrivez en quelques mots. Le chef de ligne et le technique sont prévenus."
                ),
                "scenario": "signaler_incident",
                "donnees_simulees": {
                    "vehicule": "SIM-0001-AA",
                    "incident": {
                        "type_incident": "panne",
                        "gravite": "moyenne",
                        "description": "Le moteur chauffe et le car s'arrête (exercice de formation).",
                    },
                    "personnes_prevenues": ["chef de ligne", "technique"],
                },
            },
        ],
    },
    {
        "role": Role.MAGASINIER,
        "titre": "Formation magasinier : stock, sorties de pièces, réapprovisionnement",
        "description": (
            "Apprenez à surveiller le stock, à traiter une demande de pièce de l'atelier, à refuser "
            "une sortie quand le stock ne suffit pas et à enregistrer une livraison. Tout se passe "
            "en simulation : le vrai stock n'est jamais modifié."
        ),
        "etapes": [
            {
                "ordre": 1,
                "titre": "Consulter le stock et repérer les pièces en alerte",
                "instructions": (
                    "Ouvrez le stock. Une pièce est en alerte quand sa quantité est égale ou "
                    "inférieure à son seuil d'alerte. Repérez-les avant qu'elles ne soient en rupture."
                ),
                "scenario": "consulter_stock",
                "donnees_simulees": {
                    "pieces": [
                        {"nom": "Filtre à huile (formation)", "reference": "SIM-FH-01", "quantite_stock": 10, "seuil_alerte": 4},
                        {"nom": "Plaquettes de frein (formation)", "reference": "SIM-PF-02", "quantite_stock": 3, "seuil_alerte": 5},
                        {"nom": "Courroie (formation)", "reference": "SIM-CO-03", "quantite_stock": 0, "seuil_alerte": 2},
                    ],
                    "question": "Quelles pièces sont en alerte ?",
                    "reponse_attendue": ["SIM-PF-02", "SIM-CO-03"],
                },
            },
            {
                "ordre": 2,
                "titre": "Traiter une demande de pièce de l'atelier",
                "instructions": (
                    "Le chef d'atelier demande 2 filtres à huile pour un ordre de réparation. Le stock "
                    "est suffisant : confirmez la disponibilité et enregistrez la sortie, liée à "
                    "l'ordre de réparation. Le stock baisse de 2."
                ),
                "scenario": "demande_piece",
                "donnees_simulees": {
                    "demande": {"ordre_reparation": "SIM-OR-001", "reference": "SIM-FH-01", "quantite": 2},
                    "stock_avant": 10,
                    "resultat_attendu": {"sortie_acceptee": True, "stock_apres": 8},
                },
            },
            {
                "ordre": 3,
                "titre": "Refuser une sortie quand le stock est insuffisant",
                "instructions": (
                    "L'atelier demande 5 plaquettes de frein, mais il n'en reste que 3. Le logiciel "
                    "refuse la sortie. Prévenez l'atelier de l'indisponibilité et préparez un "
                    "réapprovisionnement."
                ),
                "scenario": "demande_piece_stock_insuffisant",
                "donnees_simulees": {
                    "demande": {"ordre_reparation": "SIM-OR-002", "reference": "SIM-PF-02", "quantite": 5},
                    "stock_avant": 3,
                    "resultat_attendu": {"sortie_acceptee": False, "stock_apres": 3},
                },
            },
            {
                "ordre": 4,
                "titre": "Enregistrer une livraison de pièces",
                "instructions": (
                    "Le fournisseur livre 20 plaquettes de frein. Mettez à jour le stock de la pièce : "
                    "elle sort de l'alerte."
                ),
                "scenario": "reception_livraison",
                "donnees_simulees": {
                    "livraison": {"reference": "SIM-PF-02", "quantite": 20},
                    "stock_avant": 3,
                    "resultat_attendu": {"stock_apres": 23, "en_alerte": False},
                },
            },
        ],
    },
]


@transaction.atomic
def charger_parcours_de_base(*, force=False):
    """Crée les parcours de base ; retourne (rôles créés, rôles ignorés).

    Un parcours déjà présent (peut-être modifié par un administrateur) est laissé
    intact, sauf avec ``force=True`` qui réécrit son contenu et celui de ses étapes.
    """
    crees, ignores = [], []
    for definition in PARCOURS_DE_BASE:
        existant = ParcoursFormation.objects.filter(role=definition["role"]).exists()
        if existant and not force:
            ignores.append(definition["role"])
            continue

        parcours, _ = ParcoursFormation.objects.update_or_create(
            role=definition["role"],
            defaults={"titre": definition["titre"], "description": definition["description"]},
        )
        for etape in definition["etapes"]:
            EtapeFormation.objects.update_or_create(
                parcours=parcours,
                ordre=etape["ordre"],
                defaults={
                    "titre": etape["titre"],
                    "instructions": etape["instructions"],
                    "type_action": TypeAction.SIMULEE,
                    "scenario": etape["scenario"],
                    "donnees_simulees": etape["donnees_simulees"],
                },
            )
        crees.append(definition["role"])
    return crees, ignores
