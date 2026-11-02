"""Analyseur JSON de l'API : le corps d'une requête doit être un objet JSON.

Une vingtaine de vues lisent leurs champs par `request.data.get(...)`. Si le client envoie `[]`, `123`, `"x"`, `true` ou
`null`, `request.data` n'est pas un dictionnaire et `.get` levait AttributeError : une erreur 500 pour une simple
fantaisie de corps. Plutôt que de protéger chaque vue une à une, l'analyseur répond 400 dès la lecture.

Une vue qui accepte réellement une liste (l'envoi de positions GPS par lot) le déclare avec `corps_json_liste = True`.
"""

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class AnalyseurJSON(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        donnees = super().parse(stream, media_type, parser_context)
        vue = (parser_context or {}).get("view")
        if isinstance(donnees, dict) or (isinstance(donnees, list) and getattr(vue, "corps_json_liste", False)):
            return donnees
        raise ParseError("Le corps de la requête doit être un objet JSON.")
