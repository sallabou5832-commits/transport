"""Lecture sûre d'un texte venu d'un corps de requête.

Un corps JSON peut mettre un nombre, une liste ou un objet là où le code attend un texte : `(valeur or "").strip()`
levait alors AttributeError (erreur 500). `lire_texte` convertit au lieu de lever. Il retire aussi les caractères nuls
(PostgreSQL refuse de les stocker).
"""

from collections.abc import Mapping


def lire_texte(valeur, maximum=None):
    """Texte sans espaces de bord ni caractère nul, vide si la valeur est absente ; coupé à `maximum` caractères
    s'il est donné."""
    if valeur is None:
        return ""
    texte = (valeur if isinstance(valeur, str) else str(valeur)).replace("\x00", "").strip()
    return texte[:maximum] if maximum else texte


def champ_du_corps(donnees, nom, maximum=None):
    """Le champ `nom` d'un corps de requête lu comme un texte. Un corps qui n'est pas un objet JSON (une liste, un
    nombre…) n'a aucun champ : le résultat est vide au lieu d'une exception."""
    return lire_texte(donnees.get(nom) if isinstance(donnees, Mapping) else None, maximum)
