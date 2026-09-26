"""Caisse d'un guichetier : calcul des totaux, et clôture (photo figée transmise au chef de gare)."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Sum

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from billetterie.models import ClotureCaisse, ModePaiement, StatutTicket, Ticket
from core.models import Role


def _totaux(queryset):
    agregat = queryset.aggregate(nombre=Count("id"), montant=Sum("prix"))
    return agregat["nombre"] or 0, agregat["montant"] or Decimal("0")


def calculer_caisse(company_id, guichetier_id, date_debut, date_fin):
    """Totaux de la caisse d'un guichetier sur une période (`company_id` None : sans restriction de compagnie). Un ticket annulé n'est pas une recette : la caisse ne
    compte que les ventes valides et déclare les annulations à part (l'argent correspondant a dû être rendu)."""
    periode = Ticket.objects.filter(
        vendu_par_id=guichetier_id, date_vente__date__gte=date_debut, date_vente__date__lte=date_fin
    )
    if company_id is not None:  # None : le superadmin, qui n'a pas de compagnie, voit toutes les caisses
        periode = periode.filter(company_id=company_id)
    valides = periode.filter(statut=StatutTicket.VALIDE)
    nombre_annules, montant_annules = _totaux(periode.filter(statut=StatutTicket.ANNULE))
    nombre, montant = _totaux(valides)
    nombre_especes, montant_especes = _totaux(valides.filter(mode_paiement=ModePaiement.ESPECES))
    nombre_mobile, montant_mobile = _totaux(valides.filter(mode_paiement=ModePaiement.MOBILE_MONEY))
    return {
        "nombre_tickets": nombre,
        "montant_total": montant,
        "especes": {"nombre": nombre_especes, "montant": montant_especes},
        "mobile_money": {"nombre": nombre_mobile, "montant": montant_mobile},
        "annulations": {"nombre": nombre_annules, "montant": montant_annules},
    }


def destinataires_de_la_caisse(guichetier):
    """Le chef de la gare du guichetier ; à défaut d'affectation, tous les chefs de gare de la compagnie."""
    from reseau.models import AffectationGare

    affectation = AffectationGare.objects.filter(agent=guichetier).select_related("gare__chef").first()
    if affectation is not None and affectation.gare.chef_id:
        return [], [affectation.gare.chef], affectation.gare
    return [Role.CHEF_GARE], [], (affectation.gare if affectation else None)


def cloturer(guichetier, date, *, par=None, automatique=False):
    """Clôture la caisse d'un guichetier pour un jour : fige les totaux et prévient le chef de gare. Renvoie
    `(clôture, créée)` ; une caisse déjà clôturée pour ce jour est renvoyée telle quelle (on ne clôture qu'une fois)."""
    existante = ClotureCaisse.objects.filter(guichetier=guichetier, date=date).first()
    if existante is not None:
        return existante, False
    totaux = calculer_caisse(guichetier.company_id, guichetier.pk, date, date)
    roles, chefs, gare = destinataires_de_la_caisse(guichetier)
    try:
        with transaction.atomic():
            cloture = ClotureCaisse.objects.create(
                company_id=guichetier.company_id,
                guichetier=guichetier,
                date=date,
                nombre_tickets=totaux["nombre_tickets"],
                montant_total=totaux["montant_total"],
                especes_nombre=totaux["especes"]["nombre"],
                especes_montant=totaux["especes"]["montant"],
                mobile_nombre=totaux["mobile_money"]["nombre"],
                mobile_montant=totaux["mobile_money"]["montant"],
                annulations_nombre=totaux["annulations"]["nombre"],
                annulations_montant=totaux["annulations"]["montant"],
                cloture_par=par,
                automatique=automatique,
                gare=gare,
            )
    except IntegrityError:  # deux clôtures simultanées : l'autre a gagné
        return ClotureCaisse.objects.get(guichetier=guichetier, date=date), False

    nom = guichetier.get_full_name() or guichetier.username
    alerter(
        guichetier.company,
        type=TypeAlerte.CLOTURE_CAISSE,
        gravite=GraviteAlerte.INFO,
        titre=f"Caisse clôturée : {nom} — {int(cloture.montant_total):,} FCFA".replace(",", " "),
        message=(
            f"{cloture.nombre_tickets} ticket(s) : espèces {int(cloture.especes_montant):,} FCFA, "
            f"mobile money {int(cloture.mobile_montant):,} FCFA. "
            f"{cloture.annulations_nombre} annulation(s) ({int(cloture.annulations_montant):,} FCFA à rendre). "
            f"{'Clôture automatique de fin de service.' if automatique else 'Clôture faite par le guichetier.'}"
        ).replace(",", " "),
        roles=roles,
        destinataires=chefs,
        objet=cloture,
        cree_par=par,
    )
    return cloture, True
