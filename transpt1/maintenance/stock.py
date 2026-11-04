"""Mouvements du stock des pièces.

- **Sortie** : le stock baisse à chaque sortie enregistrée, et une sortie qui fait passer une pièce sous son seuil d'alerte
  prévient le magasinier (qui commande) et le technique. Corrigée après coup, la différence revient au stock (ou en sort) ;
  annulée, les pièces y reviennent (si le règlement intérieur le permet, voir `sorties_pieces_corrigeables`).
- **Réception** : le stock monte ; avec un prix, le prix unitaire de la pièce devient le coût moyen pondéré
  ((stock × prix actuel + quantité reçue × prix reçu) / nouveau stock), la valorisation habituelle d'un magasin.
- **Inventaire** : le stock prend la quantité comptée ; l'écart avec le stock attendu est gardé avec son motif, et un manque
  prévient le directeur technique.

Chaque mouvement verrouille la pièce le temps de l'écriture : deux mouvements simultanés ne se marchent pas dessus. La
correction directe de `quantite_stock` par l'API reste possible (tracée au journal d'audit), comme avant.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from core.serializers import nom_complet
from maintenance.models import EntreePiece, InventairePiece, Piece, SortiePiece

MOTIF_ECART_MIN = 5


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


def corriger_sortie(sortie, quantite, auteur):
    """Corrige la quantité d'une sortie : la différence revient au stock, ou en sort si le stock la couvre. Renvoie la sortie."""
    with transaction.atomic():
        sortie = SortiePiece.objects.select_for_update().get(pk=sortie.pk)
        piece = Piece.objects.select_for_update().get(pk=sortie.piece_id)
        ecart = quantite - sortie.quantite
        if ecart > piece.quantite_stock:
            raise ValidationError({"quantite": "Stock insuffisant pour cette pièce."})
        etait_en_alerte = piece.en_alerte
        piece.quantite_stock -= ecart
        piece.save(update_fields=["quantite_stock"])
        sortie.quantite = quantite
        sortie.save(update_fields=["quantite"])
    if piece.en_alerte and not etait_en_alerte:
        alerter_stock_bas(piece, auteur)
    return sortie


def annuler_sortie(sortie):
    """Annule une sortie enregistrée par erreur : ses pièces reviennent au stock."""
    with transaction.atomic():
        sortie = SortiePiece.objects.select_for_update().get(pk=sortie.pk)
        piece = Piece.objects.select_for_update().get(pk=sortie.piece_id)
        piece.quantite_stock += sortie.quantite
        piece.save(update_fields=["quantite_stock"])
        sortie.delete()


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


def cout_moyen(stock, prix_actuel, quantite, prix_recu):
    """Le coût moyen pondéré après une réception ; le prix actuel reste si la réception n'a pas de prix, le prix reçu le
    remplace si la pièce n'en avait pas (ou plus de stock)."""
    if prix_recu is None:
        return prix_actuel
    if prix_actuel is None or stock == 0:
        return prix_recu
    moyen = (Decimal(stock) * prix_actuel + Decimal(quantite) * prix_recu) / Decimal(stock + quantite)
    return moyen.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recevoir_piece(*, piece, quantite, auteur, prix_unitaire=None, fournisseur="", reference_document=""):
    """Enregistre une réception de `quantite` exemplaires et monte le stock. Renvoie la réception."""
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        entree = EntreePiece.objects.create(
            piece=piece,
            company_id=piece.company_id,
            quantite=quantite,
            prix_unitaire=prix_unitaire,
            fournisseur=fournisseur,
            reference_document=reference_document,
            recue_par=auteur,
        )
        piece.prix_unitaire = cout_moyen(piece.quantite_stock, piece.prix_unitaire, quantite, prix_unitaire)
        piece.quantite_stock += quantite
        piece.save(update_fields=["quantite_stock", "prix_unitaire"])
    return entree


def inventorier(*, piece, quantite_comptee, auteur, motif=""):
    """Enregistre le comptage : le stock prend la quantité comptée. Un écart exige son motif. Renvoie l'inventaire."""
    motif = (motif or "").strip()
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        ecart = quantite_comptee - piece.quantite_stock
        if ecart and len(motif) < MOTIF_ECART_MIN:
            raise ValidationError(
                {"motif": f"Écart de {ecart:+d} avec le stock attendu ({piece.quantite_stock}) : indiquez-en le motif."}
            )
        inventaire = InventairePiece.objects.create(
            piece=piece,
            company_id=piece.company_id,
            quantite_attendue=piece.quantite_stock,
            quantite_comptee=quantite_comptee,
            motif=motif[:255],
            compte_par=auteur,
        )
        etait_en_alerte = piece.en_alerte
        piece.quantite_stock = quantite_comptee
        piece.save(update_fields=["quantite_stock"])
    if ecart < 0:
        alerter(
            piece.company,
            type=TypeAlerte.STOCK_BAS,
            gravite=GraviteAlerte.ATTENTION,
            titre=f"Écart d'inventaire : {piece.nom}",
            message=(
                f"{-ecart} manquant(s) au comptage de {nom_complet(auteur)} ({quantite_comptee} compté(s), "
                f"{inventaire.quantite_attendue} attendu(s)). Motif : {motif}."
            ),
            roles=[Role.DIRECTEUR_TECHNIQUE],
            objet=piece,
            cree_par=auteur,
        )
    if piece.en_alerte and not etait_en_alerte:
        alerter_stock_bas(piece, auteur)
    return inventaire
