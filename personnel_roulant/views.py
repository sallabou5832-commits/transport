from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedQuerysetMixin
from core.permissions import IsSameCompany
from personnel_roulant.models import ChecklistDepart, FeuilleDeRoute, GraviteIncident, Incident
from personnel_roulant.permissions import (
    IsOwnChecklist,
    IsOwnFeuilleDeRoute,
    IsOwnIncident,
    IsQhseOuDirecteurExploitation,
)
from personnel_roulant.serializers import (
    ChecklistDepartSerializer,
    FeuilleDeRouteSerializer,
    IncidentSerializer,
)
from reseau.models import VehiculeStatut


class PersonnelRoulantViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class FeuilleDeRouteViewSet(PersonnelRoulantViewSet):
    queryset = FeuilleDeRoute.objects.select_related(
        "depart", "depart__vehicule", "chauffeur", "company"
    )
    serializer_class = FeuilleDeRouteSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsOwnFeuilleDeRoute]

    @action(detail=True, methods=["post"], url_path="demarrer")
    def demarrer(self, request, pk=None):
        feuille = self.get_object()

        if feuille.heure_depart_reelle is not None:
            raise ValidationError("Cette feuille de route a déjà démarré.")
        if feuille.depart.vehicule.statut == VehiculeStatut.BLOQUE_SECURITE:
            raise ValidationError(
                "Le véhicule est bloqué pour raison de sécurité : la feuille de route ne peut pas démarrer."
            )
        if not feuille.peut_demarrer:
            raise ValidationError(
                "Un défaut de sécurité est signalé sur la checklist : la feuille de route ne peut pas démarrer."
            )

        feuille.heure_depart_reelle = timezone.now()
        feuille.save(update_fields=["heure_depart_reelle"])
        return Response(self.get_serializer(feuille).data)

    @action(detail=True, methods=["post"], url_path="arriver")
    def arriver(self, request, pk=None):
        feuille = self.get_object()

        if feuille.heure_depart_reelle is None:
            raise ValidationError("Cette feuille de route n'a pas encore démarré.")
        if feuille.heure_arrivee_reelle is not None:
            raise ValidationError("Cette feuille de route est déjà arrivée.")

        feuille.heure_arrivee_reelle = timezone.now()
        feuille.save(update_fields=["heure_arrivee_reelle"])
        return Response(self.get_serializer(feuille).data)


class ChecklistDepartViewSet(PersonnelRoulantViewSet):
    queryset = ChecklistDepart.objects.select_related("feuille_de_route", "company")
    serializer_class = ChecklistDepartSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsOwnChecklist]


class IncidentViewSet(PersonnelRoulantViewSet):
    queryset = Incident.objects.select_related("feuille_de_route", "vehicule", "chauffeur", "company")
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsOwnIncident]

    @action(
        detail=False,
        methods=["get"],
        url_path="graves",
        permission_classes=[IsAuthenticated, IsSameCompany, IsQhseOuDirecteurExploitation],
    )
    def graves(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(gravite=GraviteIncident.GRAVE)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
