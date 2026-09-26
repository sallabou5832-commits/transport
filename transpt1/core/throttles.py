"""Limitation des tentatives de connexion : freine l'essai de mots de passe (sans elle, 40 mots de passe faux
d'affilée étaient tous traités).

Deux compteurs indépendants : par couple (adresse, identifiant), qui protège un compte visé, et par adresse seule,
qui freine celui qui essaie beaucoup d'identifiants depuis la même machine. Les débits se règlent dans les réglages
(`CONNEXION_LIMITE_COMPTE`, `CONNEXION_LIMITE_ADRESSE`, ex. « 10/min »).

Le compteur vit dans le cache de Django : celui par défaut est propre à chaque processus. Avec plusieurs processus ou
machines, configurer un cache partagé (voir DEPLOIEMENT.md), sans quoi la limite réelle est multipliée d'autant.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

from audit.contexte import adresse_ip_de


class _ThrottleConnexion(SimpleRateThrottle):
    reglage = ""

    def get_rate(self):
        return getattr(settings, self.reglage)

    def identifiant(self, request, adresse):
        raise NotImplementedError

    def get_cache_key(self, request, view):
        adresse = adresse_ip_de(request) or "inconnue"
        return self.cache_format % {"scope": self.scope, "ident": self.identifiant(request, adresse)}


class ThrottleConnexionCompte(_ThrottleConnexion):
    scope = "connexion_compte"
    reglage = "CONNEXION_LIMITE_COMPTE"

    def identifiant(self, request, adresse):
        return f"{adresse}:{str(request.data.get('username', ''))[:150].lower()}"


class ThrottleConnexionAdresse(_ThrottleConnexion):
    scope = "connexion_adresse"
    reglage = "CONNEXION_LIMITE_ADRESSE"

    def identifiant(self, request, adresse):
        return adresse
