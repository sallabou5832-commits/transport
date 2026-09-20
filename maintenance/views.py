from django.db import transaction
from django.db.models import F
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedQuerysetMixin
from core.permissions import IsSameCompany
from maintenance.models import OrdreReparation, Piece, SortiePiece
from maintenance.permissions import CanManageOrdreReparation, CanManageStockMovement
from maintenance.serializers import OrdreReparationSerializer, PieceSerializer, SortiePieceSerializer


class MaintenanceViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class PieceViewSet(MaintenanceViewSet):
    queryset = Piece.objects.select_related("company")
    serializer_class = PieceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany]

    @action(detail=False, methods=["get"], url_path="sous-seuil")
    def sous_seuil(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            quantite_stock__lte=F("seuil_alerte")
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class OrdreReparationViewSet(MaintenanceViewSet):
    queryset = OrdreReparation.objects.select_related("vehicule", "mecanicien", "company")
    serializer_class = OrdreReparationSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, CanManageOrdreReparation]


class SortiePieceViewSet(MaintenanceViewSet):
    queryset = SortiePiece.objects.select_related("ordre_reparation", "piece", "company")
    serializer_class = SortiePieceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, CanManageStockMovement]

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")

        piece_pk = serializer.validated_data["piece"].pk
        quantite = serializer.validated_data["quantite"]
        with transaction.atomic():
            piece = Piece.objects.select_for_update().get(pk=piece_pk)
            if piece.quantite_stock < quantite:
                raise ValidationError(
                    {"quantite": "Stock insuffisant pour cette pièce."}
                )
            serializer.save(company=user.company)
            piece.quantite_stock -= quantite
            piece.save(update_fields=["quantite_stock"])
