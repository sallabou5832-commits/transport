from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def lire_date(valeur):
    """Date « AAAA-MM-JJ » d'un paramètre de requête ou d'un champ JSON, ou None si elle est absente ou invalide.

    `parse_date` renvoie None pour un texte mal formé mais **lève ValueError** pour une date bien formée et
    impossible (« 2030-13-45 ») et **TypeError** pour une valeur qui n'est pas un texte (un nombre, une liste ou
    un objet dans un corps JSON) : sans ce garde-fou, un paramètre fantaisiste provoquait une erreur 500.
    """
    if not isinstance(valeur, str):
        return None
    try:
        return parse_date(valeur)
    except ValueError:
        return None


def lire_date_heure(valeur):
    """Date et heure ISO d'un paramètre de requête (rendue « aware » dans le fuseau du projet si elle ne l'est
    pas), ou None si elle est absente ou invalide (`parse_datetime` lève aussi ValueError, voir `lire_date`)."""
    if not isinstance(valeur, str):
        return None
    try:
        resultat = parse_datetime(valeur)
    except ValueError:
        return None
    if resultat is not None and timezone.is_naive(resultat):
        resultat = timezone.make_aware(resultat)
    return resultat
