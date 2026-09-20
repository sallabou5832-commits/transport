from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billetterie.models import Depart, ModePaiement, Ticket
from billetterie.permissions import (
    IsDispatchManagerOrReadOnly,
    IsGuichetierOrAboveAlways,
    IsGuichetierOrAboveWrite,
)
from billetterie.serializers import DepartSerializer, TicketSerializer
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role
from core.permissions import IsSameCompany
from notifications.services import envoyer_sms


class BilletterieViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class DepartViewSet(BilletterieViewSet):
    queryset = Depart.objects.select_related("ligne", "vehicule", "chauffeur", "company")
    serializer_class = DepartSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsDispatchManagerOrReadOnly]

    @action(detail=True, methods=["get"], url_path="places-restantes")
    def places_restantes(self, request, pk=None):
        depart = self.get_object()
        return Response(
            {
                "depart": depart.id,
                "capacite": depart.vehicule.capacite,
                "places_vendues": depart.places_vendues,
                "places_restantes": depart.places_restantes,
            }
        )


class TicketViewSet(BilletterieViewSet):
    queryset = Ticket.objects.select_related("depart", "depart__vehicule", "company", "vendu_par")
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsGuichetierOrAboveWrite]

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")

        depart_pk = serializer.validated_data["depart"].pk
        with transaction.atomic():
            depart = (
                Depart.objects.select_for_update()
                .select_related("vehicule", "ligne")
                .get(pk=depart_pk)
            )
            if depart.places_vendues >= depart.vehicule.capacite:
                raise ValidationError(
                    {"depart": "Plus aucune place disponible sur ce départ."}
                )
            serializer.save(vendu_par=user, company=user.company)
            depart.places_vendues += 1
            depart.save(update_fields=["places_vendues"])

        ticket = serializer.instance
        message = (
            f"Bonjour {ticket.passager_nom}, votre billet pour {depart.ligne.nom} le "
            f"{depart.date_heure:%d/%m/%Y à %H:%M} est confirmé. Prix : {ticket.prix} FCFA. "
            "Bon voyage !"
        )
        envoyer_sms(ticket.passager_telephone, message, company=user.company, ticket=ticket)

    @action(
        detail=False,
        methods=["get"],
        url_path="cloture-caisse",
        permission_classes=[IsAuthenticated, IsSameCompany, IsGuichetierOrAboveAlways],
    )
    def cloture_caisse(self, request):
        user = request.user
        raw_guichetier_id = request.query_params.get("guichetier", user.id)
        date_debut = parse_date(request.query_params.get("date_debut") or "")
        date_fin = parse_date(request.query_params.get("date_fin") or "")

        if date_debut is None or date_fin is None:
            raise ValidationError(
                "Les paramètres date_debut et date_fin (format AAAA-MM-JJ) sont requis."
            )

        try:
            guichetier_id = int(raw_guichetier_id)
        except (TypeError, ValueError):
            raise ValidationError({"guichetier": "Identifiant invalide."})

        if user.role == Role.GUICHETIER and guichetier_id != user.id:
            raise PermissionDenied(
                "Vous ne pouvez consulter que votre propre clôture de caisse."
            )

        base_qs = self.get_queryset().filter(
            vendu_par_id=guichetier_id,
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
        )

        def totals(queryset):
            agg = queryset.aggregate(nombre=Count("id"), montant=Sum("prix"))
            return agg["nombre"] or 0, agg["montant"] or Decimal("0")

        nombre_tickets, montant_total = totals(base_qs)
        nombre_especes, montant_especes = totals(
            base_qs.filter(mode_paiement=ModePaiement.ESPECES)
        )
        nombre_mobile, montant_mobile = totals(
            base_qs.filter(mode_paiement=ModePaiement.MOBILE_MONEY)
        )

        return Response(
            {
                "guichetier": guichetier_id,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "nombre_tickets": nombre_tickets,
                "montant_total": montant_total,
                "especes": {"nombre": nombre_especes, "montant": montant_especes},
                "mobile_money": {"nombre": nombre_mobile, "montant": montant_mobile},
            }
        )
