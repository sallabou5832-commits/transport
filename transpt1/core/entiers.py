"""Lecture sûre d'un entier venu d'un paramètre de requête ou d'un corps JSON.

`str.isdigit()` accepte des caractères que `int()` refuse (« ² », les chiffres d'autres écritures) : le motif
`if texte.isdigit(): int(texte)` levait alors ValueError, soit une erreur 500 pour une simple fantaisie d'URL.
`int()` refuse aussi les textes de plus de 4 300 chiffres, et `int(1e400)` (un nombre JSON démesuré) lève
OverflowError. `lire_entier` ne lève jamais d'exception.
"""

# Les clés primaires sont des `BigAutoField` (entier signé sur 64 bits) : au-delà, aucune ligne ne peut exister.
CHIFFRES_MAX = 18


def lire_entier(valeur):
    """Entier positif ou nul d'un paramètre de requête (« 12 ») ou d'un champ JSON (12), ou None s'il est absent,
    invalide ou démesuré. Un booléen, un décimal et un texte non numérique ne sont pas des entiers."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return valeur if 0 <= valeur < 10**CHIFFRES_MAX else None
    if isinstance(valeur, str):
        valeur = valeur.strip()
        if valeur.isascii() and valeur.isdigit() and len(valeur) <= CHIFFRES_MAX:
            return int(valeur)
    return None
