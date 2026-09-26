from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from configuration import regles
from configuration.models import ConfigurationAgent, ConfigurationCompagnie, ConfigurationPoste
from configuration.regles import AisanceNumerique, NiveauAutomatisation, NiveauGamification
from configuration.serializers import (
    CadreCompagnieSerializer,
    ConfigurationAgentSerializer,
    ConfigurationPosteSerializer,
)
from configuration.services import cadre_de, configuration_effective
from core.mixins import ActeurAuditeMixin
from core.models import Role


def _roles_configurables(user):
    return regles.roles_configurables_par(user.role) if user.company_id is not None else set()


class MaConfigurationView(APIView):
    """Ce qui s'applique à l'utilisateur connecté (les interfaces s'y adaptent) et ce qu'il peut lui-même régler."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        automatisation_max, gamification_max = cadre_de(request.user.company_id)
        return Response(
            {
                "role": request.user.role,
                **configuration_effective(request.user),
                "cadre": {"automatisation_max": automatisation_max, "gamification_max": gamification_max},
                "peut_configurer": sorted(role.value for role in _roles_configurables(request.user)),
                "peut_fixer_le_cadre": request.user.role == Role.PDG,
            }
        )


class CatalogueView(APIView):
    """Les niveaux et fonctions configurables, de quoi construire l'écran de configuration."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "niveaux_automatisation": [{"valeur": v, "libelle": l} for v, l in NiveauAutomatisation.CHOIX],
                "niveaux_gamification": [{"valeur": v, "libelle": l} for v, l in NiveauGamification.CHOIX],
                "aisances": [{"valeur": v, "libelle": l} for v, l in AisanceNumerique.CHOIX],
                "fonctions": [{"code": code, "libelle": libelle} for code, libelle in regles.FONCTIONS.items()],
            }
        )


class PeutFixerLeCadre(BasePermission):
    """Tous voient le cadre de leur compagnie ; seul le PDG le fixe."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or (user.role == Role.PDG and user.company_id is not None)


class CadreCompagnieView(ActeurAuditeMixin, RetrieveUpdateAPIView):
    """Le cadre fixé par la compagnie : plafonds d'automatisation et de gamification pour tous les postes."""

    serializer_class = CadreCompagnieSerializer
    permission_classes = [IsAuthenticated, PeutFixerLeCadre]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_object(self):
        user = self.request.user
        return ConfigurationCompagnie.objects.filter(company_id=user.company_id).first() or ConfigurationCompagnie(
            company_id=user.company_id
        )

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user, modifie_le=timezone.now())


def _effectif_du_poste(role, configuration, cadre):
    automatisation = (configuration and configuration.niveau_automatisation) or regles.AUTOMATISATION_PAR_DEFAUT
    gamification = (configuration and configuration.niveau_gamification) or regles.gamification_par_defaut(role)
    return {
        "niveau_automatisation": regles.plafonner(automatisation, cadre[0], NiveauAutomatisation.ORDRE),
        "niveau_gamification": regles.plafonner(gamification, cadre[1], NiveauGamification.ORDRE),
    }


class ConfigurationPosteViewSet(ActeurAuditeMixin, viewsets.GenericViewSet):
    """Régler les postes placés sous son autorité : chaque échelon règle ses subordonnés directs, le PDG tous les
    postes (dans le cadre de la compagnie). Un poste sans réglage suit le défaut du socle."""

    serializer_class = ConfigurationPosteSerializer
    permission_classes = [IsAuthenticated]
    queryset = ConfigurationPoste.objects.none()
    lookup_field = "role"
    lookup_value_regex = "[a-z_]+"

    def _existantes(self):
        return {c.role: c for c in ConfigurationPoste.objects.filter(company_id=self.request.user.company_id)}

    def _instance(self, role, existantes=None):
        existantes = self._existantes() if existantes is None else existantes
        return existantes.get(role) or ConfigurationPoste(company_id=self.request.user.company_id, role=role)

    def _donnees(self, instance):
        donnees = dict(self.get_serializer(instance).data)
        donnees["effectif"] = _effectif_du_poste(instance.role, instance if instance.pk else None, cadre_de(instance.company_id))
        return donnees

    def get_object(self):
        role = self.kwargs["role"]
        if role not in {poste.value for poste in regles.POSTES}:
            raise Http404
        if Role(role) not in _roles_configurables(self.request.user):
            raise PermissionDenied("Ce poste n'est pas placé sous votre autorité.")
        return self._instance(role)

    def list(self, request):
        existantes = self._existantes()
        postes = [p for p in regles.POSTES if p in _roles_configurables(request.user)]
        return Response([self._donnees(self._instance(poste.value, existantes)) for poste in postes])

    def retrieve(self, request, role=None):
        return Response(self._donnees(self.get_object()))

    def update(self, request, role=None, partial=False):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(company_id=request.user.company_id, modifie_par=request.user, modifie_le=timezone.now())
        return Response(self._donnees(serializer.instance))

    def partial_update(self, request, role=None):
        return self.update(request, role=role, partial=True)


class ConfigurationAgentViewSet(ActeurAuditeMixin, viewsets.GenericViewSet):
    """Ajuster un agent précis (aisance avec le numérique, préférence vocale, niveau propre) : réservé à l'échelon qui
    règle son poste."""

    serializer_class = ConfigurationAgentSerializer
    permission_classes = [IsAuthenticated]
    queryset = ConfigurationAgent.objects.none()
    lookup_value_regex = "[0-9]+"

    def _agents(self):
        return get_user_model().objects.filter(
            company_id=self.request.user.company_id, role__in=_roles_configurables(self.request.user)
        )

    def _instance(self, agent):
        try:
            return agent.configuration_agent
        except ConfigurationAgent.DoesNotExist:
            return ConfigurationAgent(agent=agent, company_id=agent.company_id)

    def get_object(self):
        agent = self._agents().filter(pk=self.kwargs["pk"]).select_related("configuration_agent").first()
        if agent is None:
            raise Http404
        return self._instance(agent)

    def list(self, request):
        agents = self._agents().select_related("configuration_agent").order_by("username")
        return Response([self.get_serializer(self._instance(agent)).data for agent in agents])

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def update(self, request, pk=None, partial=False):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(company_id=request.user.company_id, modifie_par=request.user, modifie_le=timezone.now())
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk=pk, partial=True)
