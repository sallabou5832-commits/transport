"""Ce que la maintenance sait dire de la flotte : la file des réparations, la charge de l'atelier, la fiche d'un véhicule, les
commandes à passer au magasin et les véhicules à renouveler. Lecture seule : rien ici ne modifie la base."""

import datetime
import math

from django.conf import settings
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from core.models import Role, User
from core.serializers import nom_complet
from maintenance import preventif
from maintenance.models import (
    RANG_URGENCE,
    OrdreReparation,
    Piece,
    SortiePiece,
    StatutOrdreReparation,
)
from personnel_roulant.models import Incident, TypeIncident
from reseau.models import Vehicule

EN_ATTENTE_OU_EN_COURS = [StatutOrdreReparation.OUVERT, StatutOrdreReparation.EN_COURS]
FENETRE_CONSOMMATION_JOURS = 90
COUVERTURE_COMMANDE_JOURS = 60
HORIZON_RUPTURE_JOURS = 30
PANNE_RECURRENTE_JOURS = 180
PANNE_RECURRENTE_MIN = 2


def file_attente(company):
    """Les réparations à faire (ouvertes ou en cours), classées par urgence, puis par la position que le directeur technique leur a
    donnée (une position posée passe avant l'ancienneté), puis par ancienneté."""
    ordres = OrdreReparation.objects.filter(company=company, statut__in=EN_ATTENTE_OU_EN_COURS).select_related(
        "vehicule", "mecanicien", "plan_entretien"
    )
    return sorted(
        ordres,
        key=lambda o: (RANG_URGENCE[o.urgence], 0 if o.position else 1, o.position, o.date_creation),
    )


def charge_mecaniciens(company):
    """La charge de chaque intervenant (mécaniciens et chef d'atelier) : ordres ouverts, en cours, heures estimées. Le moins chargé
    est marqué `suggere` : c'est à lui que l'on confie le prochain ordre."""
    depuis = timezone.now() - datetime.timedelta(days=7)
    intervenants = (
        User.objects.filter(company=company, role__in=[Role.MECANICIEN, Role.CHEF_ATELIER], is_active=True)
        .annotate(
            ouverts=Count("ordres_reparation", filter=Q(ordres_reparation__statut=StatutOrdreReparation.OUVERT)),
            en_cours=Count("ordres_reparation", filter=Q(ordres_reparation__statut=StatutOrdreReparation.EN_COURS)),
            heures=Sum("ordres_reparation__delai_estime_heures", filter=Q(ordres_reparation__statut__in=EN_ATTENTE_OU_EN_COURS)),
            cloturees_7_jours=Count(
                "ordres_reparation",
                filter=Q(ordres_reparation__statut=StatutOrdreReparation.TERMINE, ordres_reparation__date_cloture__gte=depuis),
            ),
        )
    )
    lignes = [
        {
            "id": u.id,
            "nom": nom_complet(u),
            "role": u.role,
            "ordres_ouverts": u.ouverts,
            "ordres_en_cours": u.en_cours,
            "heures_estimees": u.heures or 0,
            "cloturees_7_jours": u.cloturees_7_jours,
        }
        for u in intervenants
    ]
    # Un mécanicien passe avant le chef d'atelier, qui garde ses ordres pour les cas où l'atelier n'a personne d'autre.
    lignes.sort(key=lambda ligne: (ligne["role"] != Role.MECANICIEN, ligne["ordres_ouverts"] + ligne["ordres_en_cours"], ligne["heures_estimees"], ligne["nom"]))
    for i, ligne in enumerate(lignes):
        ligne["suggere"] = i == 0
    return lignes


def moins_charge(company):
    """L'intervenant à qui confier le prochain ordre (None si l'atelier n'a personne)."""
    lignes = charge_mecaniciens(company)
    return User.objects.get(pk=lignes[0]["id"]) if lignes else None


def _jours_immobilise(vehicule, depuis, maintenant):
    """Jours pendant lesquels le véhicule a eu au moins un ordre de réparation ouvert depuis `depuis` (les périodes qui se
    chevauchent ne comptent qu'une fois)."""
    periodes = []
    for ordre in OrdreReparation.objects.filter(vehicule=vehicule).filter(Q(date_cloture__isnull=True) | Q(date_cloture__gte=depuis)):
        debut, fin = max(ordre.date_creation, depuis), ordre.date_cloture or maintenant
        if fin > debut:
            periodes.append((debut, fin))
    total, courant = datetime.timedelta(), None
    for debut, fin in sorted(periodes):
        if courant is None or debut > courant[1]:
            if courant is not None:
                total += courant[1] - courant[0]
            courant = [debut, fin]
        else:
            courant[1] = max(courant[1], fin)
    if courant is not None:
        total += courant[1] - courant[0]
    return math.floor(total.total_seconds() / 86400 + 0.5)  # au jour le plus proche


def fiche_vehicule(vehicule, maintenant=None):
    """La fiche complète d'un véhicule : historique des interventions, pièces montées, pannes récurrentes, entretiens à venir."""
    maintenant = maintenant or timezone.now()
    aujourdhui = timezone.localdate(maintenant)
    il_y_a_un_an = maintenant - datetime.timedelta(days=365)

    ordres = list(vehicule.ordres_reparation.select_related("mecanicien").order_by("-date_creation")[:20])
    pieces = (
        SortiePiece.objects.filter(ordre_reparation__vehicule=vehicule)
        .values("piece_id", "piece__nom", "piece__reference")
        .annotate(quantite=Sum("quantite"), interventions=Count("ordre_reparation", distinct=True))
        .order_by("-interventions", "piece__nom")
    )
    derniere_sortie = {
        r["piece_id"]: r["date"]
        for r in SortiePiece.objects.filter(ordre_reparation__vehicule=vehicule).values("piece_id").annotate(date=Max("date"))
    }
    recentes = (
        SortiePiece.objects.filter(
            ordre_reparation__vehicule=vehicule, date__gte=maintenant - datetime.timedelta(days=PANNE_RECURRENTE_JOURS)
        )
        .values("piece_id", "piece__nom")
        .annotate(interventions=Count("ordre_reparation", distinct=True))
        .filter(interventions__gte=PANNE_RECURRENTE_MIN)
        .order_by("-interventions")
    )
    pannes_declarees = Incident.objects.filter(
        vehicule=vehicule, type_incident=TypeIncident.PANNE, date__gte=maintenant - datetime.timedelta(days=90)
    ).count()
    plans = [
        {
            "id": plan.id, "libelle": plan.libelle, "periodicite_jours": plan.periodicite_jours, "periodicite_km": plan.periodicite_km,
            "derniere_date": plan.derniere_date, "dernier_km": plan.dernier_km, **preventif.echeance(plan, aujourdhui),
        }
        for plan in vehicule.plans_entretien.filter(actif=True)
    ]
    return {
        "vehicule": {
            "id": vehicule.id,
            "immatriculation": vehicule.immatriculation,
            "capacite": vehicule.capacite,
            "statut": vehicule.statut,
            "kilometrage": vehicule.kilometrage,
            "gare": vehicule.gare.nom if vehicule.gare_id else None,
        },
        "plans_entretien": plans,
        "ordres": [
            {
                "id": o.id, "description": o.description, "statut": o.statut, "urgence": o.urgence,
                "date_creation": o.date_creation, "date_cloture": o.date_cloture, "temps_passe_minutes": o.temps_passe_minutes,
                "delai_estime_heures": o.delai_estime_heures, "mecanicien_nom": nom_complet(o.mecanicien),
                "preventif": o.plan_entretien_id is not None,
            }
            for o in ordres
        ],
        "pieces_montees": [
            {
                "piece": p["piece_id"], "nom": p["piece__nom"], "reference": p["piece__reference"], "quantite": p["quantite"],
                "interventions": p["interventions"], "derniere_sortie": derniere_sortie.get(p["piece_id"]),
            }
            for p in pieces
        ],
        "pannes_recurrentes": [
            {"piece": r["piece_id"], "nom": r["piece__nom"], "interventions": r["interventions"]} for r in recentes
        ],
        "indicateurs": {
            "ordres_12_mois": vehicule.ordres_reparation.filter(date_creation__gte=il_y_a_un_an).count(),
            "jours_immobilise_12_mois": _jours_immobilise(vehicule, il_y_a_un_an, maintenant),
            "pannes_declarees_90_jours": pannes_declarees,
            "fenetre_panne_recurrente_jours": PANNE_RECURRENTE_JOURS,
        },
    }


def suggestions_commande(company, maintenant=None):
    """Les pièces à commander, d'après la consommation habituelle : sous le seuil d'alerte, ou à moins d'un mois de la rupture au
    rythme des 90 derniers jours. La quantité suggérée couvre deux mois de consommation et reconstitue le stock de sécurité."""
    maintenant = maintenant or timezone.now()
    depuis = maintenant - datetime.timedelta(days=FENETRE_CONSOMMATION_JOURS)
    consommation = dict(
        SortiePiece.objects.filter(company=company, date__gte=depuis).values_list("piece_id").annotate(total=Sum("quantite"))
    )
    suggestions = []
    for piece in Piece.objects.filter(company=company):
        par_jour = consommation.get(piece.id, 0) / FENETRE_CONSOMMATION_JOURS
        jours_restants = None if par_jour == 0 else round(piece.quantite_stock / par_jour, 1)
        sous_seuil = piece.quantite_stock <= piece.seuil_alerte
        proche_rupture = jours_restants is not None and jours_restants < HORIZON_RUPTURE_JOURS
        if not (sous_seuil or proche_rupture):
            continue
        a_commander = max(1, math.ceil(par_jour * COUVERTURE_COMMANDE_JOURS) + piece.seuil_alerte - piece.quantite_stock)
        if piece.quantite_stock == 0:
            degre = "rupture"
        elif sous_seuil or (jours_restants is not None and jours_restants < 7):
            degre = "critique"
        else:
            degre = "a_prevoir"
        suggestions.append(
            {
                "piece": piece.id, "nom": piece.nom, "reference": piece.reference, "quantite_stock": piece.quantite_stock,
                "seuil_alerte": piece.seuil_alerte, "consommation_90_jours": consommation.get(piece.id, 0),
                "consommation_par_jour": round(par_jour, 2), "jours_restants": jours_restants, "quantite_suggeree": a_commander,
                "degre": degre,
            }
        )
    rang = {"rupture": 0, "critique": 1, "a_prevoir": 2}
    return sorted(suggestions, key=lambda s: (rang[s["degre"]], s["jours_restants"] if s["jours_restants"] is not None else 9999))


def besoin_renouvellement(company, maintenant=None):
    """Le rapport de besoin de renouvellement de la flotte pour la Direction Générale : un véhicule y figure dès qu'il atteint un
    des seuils (kilométrage, nombre d'ordres de réparation et jours d'immobilisation sur 12 mois). Deux seuils atteints ou plus :
    « à renouveler » ; un seul : « à surveiller »."""
    maintenant = maintenant or timezone.now()
    il_y_a_un_an = maintenant - datetime.timedelta(days=365)
    criteres = {
        "kilometrage": settings.RENOUVELLEMENT_KM,
        "ordres_12_mois": settings.RENOUVELLEMENT_ORDRES_12_MOIS,
        "jours_immobilise_12_mois": settings.RENOUVELLEMENT_JOURS_IMMOBILISE_12_MOIS,
    }
    vehicules = []
    flotte = list(Vehicule.objects.filter(company=company).annotate(
        ordres_an=Count("ordres_reparation", filter=Q(ordres_reparation__date_creation__gte=il_y_a_un_an))
    ))
    for vehicule in flotte:
        immobilise = _jours_immobilise(vehicule, il_y_a_un_an, maintenant) if vehicule.ordres_an else 0
        raisons = []
        if vehicule.kilometrage >= criteres["kilometrage"]:
            raisons.append(f"{vehicule.kilometrage:,} km au compteur (seuil {criteres['kilometrage']:,})".replace(",", " "))
        if vehicule.ordres_an >= criteres["ordres_12_mois"]:
            raisons.append(f"{vehicule.ordres_an} ordres de réparation en 12 mois (seuil {criteres['ordres_12_mois']})")
        if immobilise >= criteres["jours_immobilise_12_mois"]:
            raisons.append(f"{immobilise} jours d'immobilisation en 12 mois (seuil {criteres['jours_immobilise_12_mois']})")
        if raisons:
            vehicules.append(
                {
                    "id": vehicule.id, "immatriculation": vehicule.immatriculation, "capacite": vehicule.capacite,
                    "kilometrage": vehicule.kilometrage, "ordres_12_mois": vehicule.ordres_an,
                    "jours_immobilise_12_mois": immobilise, "raisons": raisons,
                    "recommandation": "a_renouveler" if len(raisons) >= 2 else "a_surveiller",
                }
            )
    vehicules.sort(key=lambda v: (v["recommandation"] != "a_renouveler", -len(v["raisons"]), -v["kilometrage"]))
    return {
        "genere_le": maintenant,
        "criteres": criteres,
        "flotte": len(flotte),
        "a_renouveler": sum(1 for v in vehicules if v["recommandation"] == "a_renouveler"),
        "a_surveiller": sum(1 for v in vehicules if v["recommandation"] == "a_surveiller"),
        "vehicules": vehicules,
    }
