from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedQuerysetMixin
from core.permissions import IsPdg, IsSameCompany
from investissements import services
from investissements.models import Investissement, StatutInvestissement, TypeInvestissement
from investissements.permissions import ROLES_SUPERVISION, PeutGererLesInvestissements
from investissements.serializers import InvestissementSerializer


class InvestissementViewSet(
    CompanyScopedQuerysetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Demandes d'investissement. Le technique, l'exploitation et la finance les déposent (et voient les leurs) ; le PDG, le
    secrétaire général et la finance voient toutes les demandes ; le PDG seul les décide (`decider`)."""

    queryset = Investissement.objects.select_related("demandeur", "decide_par")
    serializer_class = InvestissementSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutGererLesInvestissements]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role not in ROLES_SUPERVISION:
            queryset = queryset.filter(demandeur=user)
        parametres = self.request.query_params
        if parametres.get("statut") in StatutInvestissement.values:
            queryset = queryset.filter(statut=parametres["statut"])
        if parametres.get("type") in TypeInvestissement.values:
            queryset = queryset.filter(type=parametres["type"])
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        investissement = serializer.save(company=user.company, demandeur=user)
        services.annoncer_demande(investissement, user)

    @action(detail=True, methods=["post"], url_path="decider", permission_classes=[IsAuthenticated, IsSameCompany, IsPdg])
    def decider(self, request, pk=None):
        """Valide ou refuse la demande (`decision` : « valider » ou « refuser » ; `commentaire`, obligatoire pour un refus)."""
        investissement = services.decider(
            self.get_object(), request.user, decision=request.data.get("decision"), commentaire=request.data.get("commentaire")
        )
        return Response(self.get_serializer(investissement).data)
