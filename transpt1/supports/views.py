import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billetterie.models import ModePaiement, Ticket
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role
from core.permissions import IsSameCompany
from core.serializers import nom_complet
from supports.models import Assurance, DossierAgent, Sinistre
from supports.permissions import (
    IsDrh,
    IsDrhOrOwnerReadOnly,
    IsFinance,
    IsResponsableJuridiqueOuDirecteurTechnique,
)
from supports.serializers import AssuranceSerializer, DossierAgentSerializer, SinistreSerializer


class SupportsViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class DossierAgentViewSet(SupportsViewSet):
    queryset = DossierAgent.objects.select_related("agent", "company")
    serializer_class = DossierAgentSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsDrhOrOwnerReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role in (Role.DRH, Role.SUPERADMIN):
            return queryset
        return queryset.filter(agent_id=user.id)

    @action(
        detail=False,
        methods=["get"],
        url_path="agents-sans-dossier",
        permission_classes=[IsAuthenticated, IsDrh],
    )
    def agents_sans_dossier(self, request):
        """Agents de la compagnie qui n'ont pas encore de dossier (pour en ouvrir un)."""
        agents = (
            get_user_model()
            .objects.filter(company_id=request.user.company_id, dossier_agent__isnull=True)
            .order_by("username")
        )
        return Response(
            [
                {"id": agent.id, "username": agent.username, "nom": nom_complet(agent), "role": agent.role}
                for agent in agents
            ]
        )


class AssuranceViewSet(SupportsViewSet):
    queryset = Assurance.objects.select_related("vehicule", "company")
    serializer_class = AssuranceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsResponsableJuridiqueOuDirecteurTechnique]

    @action(detail=False, methods=["get"], url_path="echeance-proche")
    def echeance_proche(self, request):
        limite = timezone.localdate() + datetime.timedelta(days=30)
        queryset = self.filter_queryset(self.get_queryset()).filter(date_echeance__lte=limite)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SinistreViewSet(SupportsViewSet):
    queryset = Sinistre.objects.select_related("vehicule", "incident", "company")
    serializer_class = SinistreSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsResponsableJuridiqueOuDirecteurTechnique]


class SyntheseFinanciereView(APIView):
    permission_classes = [IsAuthenticated, IsFinance]

    def get(self, request):
        user = request.user
        date_debut = parse_date(request.query_params.get("date_debut") or "")
        date_fin = parse_date(request.query_params.get("date_fin") or "")

        if date_debut is None or date_fin is None:
            raise ValidationError(
                "Les paramètres date_debut et date_fin (format AAAA-MM-JJ) sont requis."
            )

        tickets = Ticket.objects.filter(
            date_vente__date__gte=date_debut, date_vente__date__lte=date_fin
        )
        if user.role != Role.SUPERADMIN:
            tickets = tickets.filter(company_id=user.company_id)

        rows = (
            tickets.annotate(gare_id=F("depart__ligne__gare_depart_id"))
            .values("gare_id", "depart__ligne__gare_depart__nom")
            .annotate(nombre_tickets=Count("id"), montant_total=Sum("prix"))
            .order_by("depart__ligne__gare_depart__nom")
        )

        gares = [
            {
                "gare_id": row["gare_id"],
                "gare_nom": row["depart__ligne__gare_depart__nom"],
                "nombre_tickets": row["nombre_tickets"],
                "montant_total": row["montant_total"] or Decimal("0"),
            }
            for row in rows
        ]

        # Même périmètre (compagnie, période) que `gares`, vu sous deux autres angles : le mode
        # d'encaissement et l'évolution jour par jour. Calculés ici plutôt que côté client parce
        # que la liste des tickets est lisible par tous les rôles alors que ces montants ne le
        # sont pas (finance uniquement).
        total = tickets.aggregate(nombre=Count("id"), montant=Sum("prix"))

        par_mode = {
            row["mode_paiement"]: row
            for row in tickets.values("mode_paiement").annotate(
                nombre=Count("id"), montant=Sum("prix")
            ).order_by()
        }
        par_mode_paiement = [
            {
                "mode": mode,
                "nombre_tickets": par_mode.get(mode, {}).get("nombre", 0),
                "montant_total": par_mode.get(mode, {}).get("montant") or Decimal("0"),
            }
            for mode in ModePaiement.values
        ]

        par_jour = [
            {
                "date": row["jour"],
                "nombre_tickets": row["nombre"],
                "montant_total": row["montant"] or Decimal("0"),
            }
            for row in tickets.annotate(jour=TruncDate("date_vente"))
            .values("jour")
            .annotate(nombre=Count("id"), montant=Sum("prix"))
            .order_by("jour")
        ]

        return Response(
            {
                "date_debut": date_debut,
                "date_fin": date_fin,
                "total": {
                    "nombre_tickets": total["nombre"] or 0,
                    "montant_total": total["montant"] or Decimal("0"),
                },
                "gares": gares,
                "par_mode_paiement": par_mode_paiement,
                "par_jour": par_jour,
            }
        )
