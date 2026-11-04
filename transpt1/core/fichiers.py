"""Pièces jointes : ce que l'on accepte de stocker (sinistres, modèles de documents juridiques) et comment on le rend.

Un fichier n'est accepté que si son extension est connue, sa taille raisonnable et son contenu correspond à son extension (un
exécutable renommé « .pdf » est refusé). Il est rangé sous un nom aléatoire et n'est jamais servi par un lien public : seule l'API le
rend, après contrôle des droits, en téléchargement (`Content-Disposition: attachment`) et sans que le navigateur ne devine son type."""

import os
import uuid

from django.conf import settings
from django.http import FileResponse
from django.utils.deconstruct import deconstructible
from rest_framework.exceptions import ValidationError

TYPES = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    # Les documents Office sont des archives ZIP.
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (b"PK\x03\x04",)),
}


def taille_max_octets():
    return settings.PIECES_JOINTES_TAILLE_MAX_MO * 1024 * 1024


def nom_affichable(nom):
    """Le nom d'origine, réduit au nom de fichier (jamais un chemin) et borné."""
    return os.path.basename(str(nom).replace("\\", "/"))[:200] or "fichier"


def verifier_fichier(fichier):
    """Lève une erreur de validation claire si le fichier n'est pas acceptable ; renvoie son extension sinon."""
    extension = os.path.splitext(nom_affichable(fichier.name))[1].lower()
    if extension not in TYPES:
        raise ValidationError({"fichier": f"Types acceptés : {', '.join(sorted(t.lstrip('.') for t in TYPES))}."})
    if fichier.size == 0:
        raise ValidationError({"fichier": "Ce fichier est vide."})
    if fichier.size > taille_max_octets():
        raise ValidationError({"fichier": f"Ce fichier dépasse {settings.PIECES_JOINTES_TAILLE_MAX_MO} Mo."})
    debut = fichier.read(8)
    fichier.seek(0)
    if not any(debut.startswith(signature) for signature in TYPES[extension][1]):
        raise ValidationError({"fichier": "Le contenu de ce fichier ne correspond pas à son type."})
    return extension


@deconstructible
class CheminDeStockage:
    """`upload_to` d'un champ fichier : un nom aléatoire, rangé par compagnie, qui ne reprend rien du nom envoyé sauf l'extension.
    (Une classe et non une fonction : les migrations doivent pouvoir la retrouver.)"""

    def __init__(self, dossier):
        self.dossier = dossier

    def __call__(self, instance, nom):
        compagnie = getattr(instance, "company_id", instance.pk)  # la compagnie elle-même, pour son logo
        return f"{self.dossier}/{compagnie}/{uuid.uuid4().hex}{os.path.splitext(nom)[1].lower()}"

    def __eq__(self, autre):
        return isinstance(autre, CheminDeStockage) and autre.dossier == self.dossier

    def __hash__(self):
        return hash(self.dossier)


def reponse_en_telechargement(champ, nom):
    """Rend le fichier en téléchargement, sans que le navigateur n'en interprète le contenu."""
    extension = os.path.splitext(nom)[1].lower()
    reponse = FileResponse(champ.open("rb"), as_attachment=True, filename=nom, content_type=TYPES.get(extension, ("application/octet-stream",))[0])
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse
