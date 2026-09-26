"""Règle de ponctualité, partagée par les tableaux de bord et par les alertes automatiques (une seule définition)."""

import datetime

from django.utils import timezone

# Un départ est « à l'heure » s'il a lieu au plus tard 10 minutes après l'heure prévue.
TOLERANCE_RETARD = datetime.timedelta(minutes=10)
# Couleur d'une gare ou d'une ligne selon sa ponctualité (cahier des charges : vert/orange/rouge).
SEUIL_PONCTUALITE_VERT = 90
SEUIL_PONCTUALITE_ORANGE = 70


def bornes_du_jour(reference):
    debut = timezone.localtime(reference).replace(hour=0, minute=0, second=0, microsecond=0)
    return debut, debut + datetime.timedelta(days=1)


def pourcentage(partie, total):
    return round(100 * partie / total) if total else None


def statut_ponctualite(feuille, maintenant):
    """« a_l_heure », « en_retard » ou « en_attente » pour une feuille de route.

    Une feuille non démarrée est en retard une fois la tolérance dépassée : le départ
    n'a pas eu lieu, il ne faut pas attendre qu'il ait lieu pour le signaler.
    """
    limite = feuille.heure_depart_prevue + TOLERANCE_RETARD
    if feuille.heure_depart_reelle is not None:
        return "a_l_heure" if feuille.heure_depart_reelle <= limite else "en_retard"
    return "en_retard" if maintenant > limite else "en_attente"


def retard_minutes(feuille, maintenant):
    fin = feuille.heure_depart_reelle or maintenant
    return max(0, int((fin - feuille.heure_depart_prevue).total_seconds() // 60))


def couleur(ponctualite):
    if ponctualite is None:
        return "neutre"
    if ponctualite >= SEUIL_PONCTUALITE_VERT:
        return "vert"
    if ponctualite >= SEUIL_PONCTUALITE_ORANGE:
        return "orange"
    return "rouge"
