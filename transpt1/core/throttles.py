"""Limitation des tentatives de connexion : freine l'essai de mots de passe (sans elle, 40 mots de passe faux
d'affilée étaient tous traités).

Deux compteurs indépendants : par couple (adresse, identifiant), qui protège un compte visé, et par adresse seule,
qui freine celui qui essaie beaucoup d'identifiants depuis la même machine. Les débits se règlent dans les réglages
(`CONNEXION_LIMITE_COMPTE`, `CONNEXION_LIMITE_ADRESSE`, ex. « 10/min »).

Le compteur vit dans le cache de Django : celui par défaut est propre à chaque processus. Avec plusieurs processus ou
machines, configurer un cache partagé (voir DEPLOIEMENT.md), sans quoi la limite réelle est multipliée d'autant.
"""

import hashlib

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

from audit.contexte import adresse_ip_de
from core.textes import champ_du_corps


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
        # Tout caractère est permis dans un identifiant saisi, pas dans une clé de cache : on n'en garde que l'empreinte.
        nom = champ_du_corps(request.data, "username", 150).lower()
        return f"{adresse}:{hashlib.sha256(nom.encode()).hexdigest()[:32]}"


class ThrottleMotDePasse(SimpleRateThrottle):
    """Changer son mot de passe demande l'actuel : sans limite, une session laissée ouverte permettrait de l'essayer à
    volonté. Compté par compte, au débit de `CONNEXION_LIMITE_COMPTE`."""

    scope = "mot_de_passe"

    def get_rate(self):
        return settings.CONNEXION_LIMITE_COMPTE

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class ThrottleConnexionAdresse(_ThrottleConnexion):
    scope = "connexion_adresse"
    reglage = "CONNEXION_LIMITE_ADRESSE"

    def identifiant(self, request, adresse):
        return adresse
