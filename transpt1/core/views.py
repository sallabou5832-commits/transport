from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core import comptes
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Company, Role, User
from core.permissions import IsPdg, IsSameCompany
from core.serializers import CompanySerializer, CompteSerializer, UserSerializer


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CompanyDetailView(RetrieveAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, IsSameCompany]


class ComptesViewSet(CompanyScopedQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Les comptes des agents de la compagnie, pour le PDG : les voir, suspendre un compte (`suspendre`), le réactiver
    (`reactiver`). Filtres : `role`, `q` (identifiant ou nom), `suspendus=1`. Le PDG et les autres PDG n'y figurent pas."""

    queryset = User.objects.select_related("suspendu_par", "affectation_gare__gare")
    serializer_class = CompteSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsPdg]

    def get_queryset(self):
        queryset = super().get_queryset().exclude(role__in=comptes.ROLES_INTOUCHABLES).order_by("role", "username")
        parametres = self.request.query_params
        if parametres.get("role") in Role.values:
            queryset = queryset.filter(role=parametres["role"])
        recherche = parametres.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(username__icontains=recherche) | Q(first_name__icontains=recherche) | Q(last_name__icontains=recherche)
            )
        if parametres.get("suspendus") == "1":
            queryset = queryset.filter(is_active=False)
        return queryset

    @action(detail=True, methods=["post"], url_path="suspendre")
    def suspendre(self, request, pk=None):
        """Suspend le compte (`motif` obligatoire) : plus de connexion, sessions ouvertes coupées."""
        agent = comptes.suspendre(self.get_object(), request.user, request.data.get("motif"))
        return Response(self.get_serializer(agent).data)

    @action(detail=True, methods=["post"], url_path="reactiver")
    def reactiver(self, request, pk=None):
        """Rend le compte tel qu'il était (`motif` facultatif)."""
        agent = comptes.reactiver(self.get_object(), request.user, request.data.get("motif"))
        return Response(self.get_serializer(agent).data)
