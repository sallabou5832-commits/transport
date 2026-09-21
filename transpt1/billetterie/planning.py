"""Règles de planification des départs : qui et quoi est libre à quelle heure.

Le modèle ne connaît pas la durée d'un trajet : un véhicule ou un chauffeur est considéré comme pris s'il a un
autre départ non terminé à moins de FENETRE_OCCUPATION du départ visé. Les mêmes règles servent à la création,
à la réaffectation et aux suggestions, pour que ce qu'on propose soit toujours ce qu'on accepte.
"""

import datetime

from billetterie.models import Depart, DepartStatut
from core.models import Role, User
from reseau.models import Vehicule, VehiculeStatut

FENETRE_OCCUPATION = datetime.timedelta(hours=8)
# Un véhicule bloqué par le QHSE ou à l'atelier ne se planifie pas, quel que soit l'horaire.
STATUTS_VEHICULE_IMMOBILISES = (VehiculeStatut.BLOQUE_SECURITE, VehiculeStatut.EN_MAINTENANCE)
ROLES_CHAUFFEUR = (Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS)
# Un départ ne se planifie pas plus d'une heure dans le passé (saisie tardive d'un départ tout juste parti).
TOLERANCE_DATE_PASSEE = datetime.timedelta(hours=1)


def departs_proches(company_id, date_heure, exclure_depart_id=None):
    proches = (
        Depart.objects.filter(
            company_id=company_id,
            date_heure__gte=date_heure - FENETRE_OCCUPATION,
            date_heure__lte=date_heure + FENETRE_OCCUPATION,
        )
        .exclude(statut=DepartStatut.TERMINE)
        .select_related("ligne")
    )
    return proches.exclude(pk=exclure_depart_id) if exclure_depart_id else proches


def depart_en_conflit(*, vehicule=None, chauffeur=None, date_heure, exclure_depart_id=None):
    """Le premier autre départ proche qui utilise déjà ce véhicule ou ce chauffeur, sinon None."""
    if vehicule is not None:
        company_id, filtre = vehicule.company_id, {"vehicule": vehicule}
    else:
        company_id, filtre = chauffeur.company_id, {"chauffeur": chauffeur}
    return departs_proches(company_id, date_heure, exclure_depart_id).filter(**filtre).order_by("date_heure").first()


def vehicules_disponibles(company_id, date_heure, places_min=0, exclure_depart_id=None):
    occupes = departs_proches(company_id, date_heure, exclure_depart_id).values("vehicule_id")
    return (
        Vehicule.objects.filter(company_id=company_id, capacite__gte=places_min)
        .exclude(statut__in=STATUTS_VEHICULE_IMMOBILISES)
        .exclude(pk__in=occupes)
        .order_by("immatriculation")
    )


def chauffeurs_disponibles(company_id, date_heure, exclure_depart_id=None):
    occupes = departs_proches(company_id, date_heure, exclure_depart_id).values("chauffeur_id")
    return (
        User.objects.filter(company_id=company_id, role__in=ROLES_CHAUFFEUR, is_active=True)
        .exclude(pk__in=occupes)
        .order_by("username")
    )
