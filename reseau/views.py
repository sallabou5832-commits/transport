from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.mixins import CompanyScopedQuerysetMixin
from core.permissions import IsSameCompany
from reseau.models import Gare, Ligne, Vehicule
from reseau.permissions import (
    CanManageOwnGare,
    IsGareManagerOrReadOnly,
    IsLigneManagerOrReadOnly,
    IsVehiculeManagerOrReadOnly,
)
from reseau.serializers import GareSerializer, LigneSerializer, VehiculeSerializer


class CompanyOwnedViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSameCompany]

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError(
                "Un compte sans compagnie ne peut pas créer cet objet."
            )
        serializer.save(company=user.company)


class GareViewSet(CompanyOwnedViewSet):
    queryset = Gare.objects.select_related("company", "chef")
    serializer_class = GareSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsGareManagerOrReadOnly, CanManageOwnGare]


class LigneViewSet(CompanyOwnedViewSet):
    queryset = Ligne.objects.select_related("company", "gare_depart", "gare_arrivee")
    serializer_class = LigneSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsLigneManagerOrReadOnly]


class VehiculeViewSet(CompanyOwnedViewSet):
    queryset = Vehicule.objects.select_related("company")
    serializer_class = VehiculeSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsVehiculeManagerOrReadOnly]
