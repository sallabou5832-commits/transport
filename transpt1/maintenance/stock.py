"""Sorties de pièces : le stock baisse à chaque sortie enregistrée, et une sortie qui fait passer une pièce sous son seuil
d'alerte prévient le magasinier (qui commande) et le technique."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from maintenance.models import Piece, SortiePiece


def sortir_piece(*, ordre, piece, quantite, company, auteur):
    """Enregistre la sortie de `quantite` exemplaires de `piece` pour l'ordre de réparation, et baisse le stock. La pièce est
    verrouillée le temps de la sortie : deux sorties simultanées ne dépassent jamais le stock. Renvoie la sortie."""
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        if piece.quantite_stock < quantite:
            raise ValidationError({"quantite": "Stock insuffisant pour cette pièce."})
        sortie = SortiePiece.objects.create(ordre_reparation=ordre, piece=piece, company=company, quantite=quantite)
        etait_en_alerte = piece.en_alerte
        piece.quantite_stock -= quantite
        piece.save(update_fields=["quantite_stock"])
    if piece.en_alerte and not etait_en_alerte:
        alerter_stock_bas(piece, auteur)
    return sortie


def alerter_stock_bas(piece, auteur):
    """La sortie qui fait passer une pièce sous son seuil prévient le magasinier (qui commande) et le technique."""
    rupture = piece.quantite_stock == 0
    alerter(
        piece.company,
        type=TypeAlerte.STOCK_BAS,
        gravite=GraviteAlerte.CRITIQUE if rupture else GraviteAlerte.ATTENTION,
        titre=f"{'Rupture' if rupture else 'Stock bas'} : {piece.nom}",
        message=f"{piece.quantite_stock} en stock (seuil d'alerte : {piece.seuil_alerte}). Pensez au réapprovisionnement.",
        roles=[Role.MAGASINIER, Role.DIRECTEUR_TECHNIQUE],
        objet=piece,
        cree_par=auteur,
    )
