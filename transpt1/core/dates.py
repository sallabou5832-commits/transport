from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def lire_date(valeur):
    """Date « AAAA-MM-JJ » d'un paramètre de requête, ou None si elle est absente ou invalide.

    `parse_date` renvoie None pour un texte mal formé mais **lève ValueError** pour une date bien formée et
    impossible (« 2030-13-45 ») : sans ce garde-fou, un paramètre fantaisiste provoquait une erreur 500.
    """
    try:
        return parse_date(valeur or "")
    except ValueError:
        return None


def lire_date_heure(valeur):
    """Date et heure ISO d'un paramètre de requête (rendue « aware » dans le fuseau du projet si elle ne l'est
    pas), ou None si elle est absente ou invalide (`parse_datetime` lève aussi ValueError, voir `lire_date`)."""
    try:
        resultat = parse_datetime(valeur or "")
    except ValueError:
        return None
    if resultat is not None and timezone.is_naive(resultat):
        resultat = timezone.make_aware(resultat)
    return resultat
