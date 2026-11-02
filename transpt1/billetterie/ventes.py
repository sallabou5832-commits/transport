"""Annuler un billet : une seule règle, qu'il ait été vendu au guichet ou reçu du logiciel de billetterie d'une compagnie
(voir `lien_billetterie`)."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from billetterie.models import Depart, DepartStatut, StatutTicket, Ticket


def annuler_ticket(ticket_id, *, par, motif):
    """Annule le billet : la place est libérée, la vente sort des recettes, le billet reste visible avec l'auteur (`par`,
    vide quand l'annulation vient d'un logiciel externe), la date et le motif. Renvoie le billet annulé."""
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
        if ticket.statut == StatutTicket.ANNULE:
            raise ValidationError("Ce ticket est déjà annulé.")
        depart = Depart.objects.select_for_update().get(pk=ticket.depart_id)

        ticket.statut = StatutTicket.ANNULE
        ticket.annule_par = par
        ticket.annule_le = timezone.now()
        ticket.motif_annulation = motif[:255]
        ticket.save(update_fields=["statut", "annule_par", "annule_le", "motif_annulation"])

        # Un départ terminé n'a plus de places à rendre : l'annulation (remboursement) reste possible.
        if depart.statut != DepartStatut.TERMINE and depart.places_vendues > 0:
            depart.places_vendues -= 1
            depart.save(update_fields=["places_vendues"])
    return ticket
