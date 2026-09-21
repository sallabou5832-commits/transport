from django.conf import settings
from django.core.management.base import CommandError


def refuser_hors_developpement(nom_commande):
    """Les commandes de démonstration créent des comptes au mot de passe public, dont un superadmin
    (voir les README) : sur une base de production, ce serait une porte ouverte. Elles ne tournent
    donc que si DJANGO_DEBUG=True, c'est-à-dire en développement."""
    if not settings.DEBUG:
        raise CommandError(
            f"{nom_commande} crée des comptes de démonstration au mot de passe public (dont un "
            "superadmin) : elle est réservée au développement (DJANGO_DEBUG=True) et refusée en "
            "production. Sur une base de production, créez les comptes réels par l'administration Django."
        )
