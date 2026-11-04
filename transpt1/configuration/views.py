from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from configuration import regles
from configuration.models import (
    ConfigurationAgent,
    ConfigurationCompagnie,
    ConfigurationPoste,
    PreferencePersonnelle,
    ReglementInterieur,
)
from configuration.regles import AisanceNumerique, DureeSession, NiveauAutomatisation, NiveauGamification
from configuration.serializers import (
    CadreCompagnieSerializer,
    ConfigurationAgentSerializer,
    ConfigurationPosteSerializer,
    PreferencePersonnelleSerializer,
)
from configuration.services import (
    cadre_de,
    configuration_effective,
    politique_session,
    reglement_de,
    vocal_impose_pour,
)
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
                # Accès au compte : la plus longue session permise et le code court exigé sur le mobile.
                "session": politique_session(request.user),
                # Le supérieur a imposé le mode vocal : l'agent ne le choisit pas dans « Mes paramètres ».
                "vocal_impose": vocal_impose_pour(request.user),
                # Ce que le règlement intérieur permet à son poste : les écrans n'affichent que les gestes permis.
                "reglement": {
                    code: permis
                    for code, permis in reglement_de(request.user.company_id).items()
                    if request.user.role in regles.REGLEMENT[code].roles
                },
                "peut_configurer": sorted(role.value for role in _roles_configurables(request.user)),
                "peut_fixer_le_cadre": request.user.role == Role.PDG,
            }
        )


class MesPreferencesView(RetrieveUpdateAPIView):
    """Ce que chacun règle pour lui-même : mode vocal (sauf s'il est imposé), son et notification du navigateur pour une
    alerte critique. Rien de réglé : comme avant."""

    serializer_class = PreferencePersonnelleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_object(self):
        return PreferencePersonnelle.objects.filter(agent=self.request.user).first() or PreferencePersonnelle(
            agent=self.request.user
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
                "durees_session": [{"valeur": v, "libelle": l} for v, l in DureeSession.CHOIX],
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


class PeutReglerLeReglement(BasePermission):
    """Tous lisent le règlement intérieur ; le règlent le PDG et, pour leur pôle, les directeurs (OPTIONS ne leur annonce
    l'écriture qu'à eux)."""

    message = "Le règlement intérieur se règle par le PDG et, pour leur pôle, par les directeurs."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or any(regles.peut_regler(user, code) for code in regles.REGLEMENT)


class ReglementInterieurView(ActeurAuditeMixin, APIView):
    """Le règlement intérieur de la compagnie : ce qu'elle permet ou non à certains postes. Tous le lisent ; le PDG règle
    toutes les règles, chaque directeur celles de son pôle. `PATCH` (ou `PUT`) `{code: vrai/faux, ...}` ne touche qu'aux
    règles données."""

    permission_classes = [IsAuthenticated, PeutReglerLeReglement]

    def get_serializer(self, *args, **kwargs):  # OPTIONS annonce ainsi l'écriture à qui peut régler
        return serializers.Serializer(*args, **kwargs)

    def get(self, request):
        return Response(self._donnees(request.user))

    def put(self, request):
        return self.patch(request)

    def patch(self, request):
        user = request.user
        if not isinstance(request.data, dict) or not request.data:
            raise ValidationError("Indiquez les règles à régler : {code: vrai ou faux}.")
        erreurs = {}
        for code, permis in request.data.items():
            if code not in regles.REGLEMENT:
                erreurs[code] = "Règle inconnue."
            elif not isinstance(permis, bool):
                erreurs[code] = "Vrai ou faux attendu."
        if erreurs:
            raise ValidationError(erreurs)
        hors_pole = sorted(code for code in request.data if not regles.peut_regler(user, code))
        if hors_pole:
            raise PermissionDenied(f"Ces règles ne relèvent pas de votre pôle : {', '.join(hors_pole)}.")
        with transaction.atomic():
            reglement, _ = ReglementInterieur.objects.select_for_update().get_or_create(company_id=user.company_id)
            reglement.regles = {**reglement.regles, **request.data}
            reglement.modifie_par = user
            reglement.modifie_le = timezone.now()
            reglement.save()
        return Response(self._donnees(user))

    @staticmethod
    def _donnees(user):
        permis = reglement_de(user.company_id)
        return [
            {
                "code": code,
                "libelle": regle.libelle,
                "permis": permis[code],
                "defaut": regle.defaut,
                "postes": sorted(role.value for role in regle.roles),
                "pole": regle.pole.value,
                "modifiable": regles.peut_regler(user, code),
            }
            for code, regle in regles.REGLEMENT.items()
        ]


def _effectif_du_poste(role, configuration, cadre, plafond_session):
    automatisation = (configuration and configuration.niveau_automatisation) or regles.AUTOMATISATION_PAR_DEFAUT
    gamification = (configuration and configuration.niveau_gamification) or regles.gamification_par_defaut(role)
    duree = (configuration and configuration.duree_session_max) or plafond_session
    return {
        "niveau_automatisation": regles.plafonner(automatisation, cadre[0], NiveauAutomatisation.ORDRE),
        "niveau_gamification": regles.plafonner(gamification, cadre[1], NiveauGamification.ORDRE),
        "duree_session_max": regles.plafonner(duree, plafond_session, DureeSession.ORDRE),
    }


def _plafond_session(company_id):
    cadre = ConfigurationCompagnie.objects.filter(company_id=company_id).first()
    return cadre.duree_session_max if cadre is not None else DureeSession.PLAFOND_PAR_DEFAUT


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
        donnees["effectif"] = _effectif_du_poste(
            instance.role,
            instance if instance.pk else None,
            cadre_de(instance.company_id),
            _plafond_session(instance.company_id),
        )
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
