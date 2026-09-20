"""Réservation de places pour la vente hors ligne (voir ReservationHorsLigne)."""

import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ReservationHorsLigne

MAX_DEPARTS_PAR_DEMANDE = 50


def _reservees_par_les_autres(depart, guichetier, maintenant):
    return (
        ReservationHorsLigne.objects.filter(depart=depart, expire_le__gt=maintenant)
        .exclude(guichetier=guichetier)
        .aggregate(total=Sum("places"))["total"]
        or 0
    )


def accorder_reservations(user, maintenant=None):
    """Met de côté, pour `user`, jusqu'au quota de places sur chaque départ à venir.

    Idempotent : rappeler la fonction complète la réservation existante jusqu'au quota
    (par exemple après des ventes) et prolonge son expiration. Premier arrivé, premier
    servi : jamais plus que les places réellement libres (invariant tenu sous verrou du départ).
    Retourne la liste des réservations actives de `user`.
    """
    maintenant = maintenant or timezone.now()
    quota = settings.BILLETTERIE_QUOTA_HORS_LIGNE
    duree = datetime.timedelta(hours=settings.BILLETTERIE_RESERVATION_TTL_HEURES)
    horizon = maintenant + datetime.timedelta(hours=settings.BILLETTERIE_HORIZON_HORS_LIGNE_HEURES)

    depart_ids = list(
        Depart.objects.filter(
            company_id=user.company_id,
            statut=DepartStatut.PLANIFIE,
            date_heure__gt=maintenant,
            date_heure__lte=horizon,
        )
        .order_by("date_heure")
        .values_list("id", flat=True)[:MAX_DEPARTS_PAR_DEMANDE]
    )

    accordees = []
    for depart_id in depart_ids:
        with transaction.atomic():
            depart = Depart.objects.select_for_update().select_related("vehicule").get(pk=depart_id)
            ReservationHorsLigne.objects.filter(depart=depart, expire_le__lte=maintenant).delete()

            libres_pour_moi = (
                depart.vehicule.capacite
                - depart.places_vendues
                - _reservees_par_les_autres(depart, user, maintenant)
            )
            cible = max(0, min(quota, libres_pour_moi))
            if cible == 0:
                ReservationHorsLigne.objects.filter(depart=depart, guichetier=user).delete()
                continue

            reservation, _ = ReservationHorsLigne.objects.update_or_create(
                depart=depart,
                guichetier=user,
                defaults={
                    "company": user.company,
                    "places": cible,
                    "expire_le": min(depart.date_heure, maintenant + duree),
                },
            )
            accordees.append(reservation)
    return accordees


def liberer_reservations(user):
    """Rend toutes les places réservées par `user` (fin de service, déconnexion)."""
    supprimees, _ = ReservationHorsLigne.objects.filter(guichetier=user).delete()
    return supprimees
