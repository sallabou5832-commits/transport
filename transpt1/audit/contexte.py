"""Qui agit, et d'où : porté par la requête en cours, lu par l'enregistrement automatique du journal.

Sans imports de modèles, pour que `core` puisse l'utiliser sans dépendance circulaire.
"""

import ipaddress
from contextvars import ContextVar

_acteur = ContextVar("audit_acteur", default=None)
_adresse_ip = ContextVar("audit_adresse_ip", default=None)


def definir(acteur=None, adresse_ip=None):
    if acteur is not None:
        _acteur.set(acteur)
    if adresse_ip is not None:
        _adresse_ip.set(adresse_ip)


def acteur():
    utilisateur = _acteur.get()
    # Un utilisateur anonyme ou non enregistré n'est pas un acteur identifiable.
    return utilisateur if utilisateur is not None and getattr(utilisateur, "pk", None) else None


def adresse_ip():
    return _adresse_ip.get()


def reinitialiser():
    _acteur.set(None)
    _adresse_ip.set(None)


def adresse_ip_de(requete):
    """Adresse du client. Derrière le proxy, la dernière entrée de X-Forwarded-For est celle qu'il a
    ajoutée lui-même (les entrées précédentes viennent du client, donc falsifiables) : voir DEPLOIEMENT.md."""
    transmise = requete.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = transmise.split(",")[-1].strip() if transmise else requete.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None
