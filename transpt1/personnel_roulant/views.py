from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billetterie.models import DepartStatut
from core.mixins import CompanyScopedQuerysetMixin
from core.permissions import IsSameCompany
from personnel_roulant.models import ChecklistDepart, FeuilleDeRoute, GraviteIncident, Incident
from personnel_roulant.permissions import (
    IsOwnChecklist,
    IsOwnFeuilleDeRoute,
    IsOwnIncident,
    IsQhseOuDirecteurExploitation,
    IsRoulantManagerOrReadOnly,
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
    permission_classes = [IsAuthenticated, IsSameCompany, IsRoulantManagerOrReadOnly, IsOwnFeuilleDeRoute]

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

        depart, vehicule = feuille.depart, feuille.depart.vehicule
        with transaction.atomic():
            feuille.heure_depart_reelle = timezone.now()
            feuille.save(update_fields=["heure_depart_reelle"])
            # Le départ est en cours et le car en ligne : c'est ce que voient les régulateurs et la
            # direction. Un véhicule bloqué ou en maintenance ne peut pas partir (refusé plus haut).
            if depart.statut == DepartStatut.PLANIFIE:
                depart.statut = DepartStatut.EN_COURS
                depart.save(update_fields=["statut"])
            if vehicule.statut == VehiculeStatut.DISPONIBLE:
                vehicule.statut = VehiculeStatut.EN_LIGNE
                vehicule.save(update_fields=["statut"])
        return Response(self.get_serializer(feuille).data)

    @action(detail=True, methods=["post"], url_path="arriver")
    def arriver(self, request, pk=None):
        feuille = self.get_object()

        if feuille.heure_depart_reelle is None:
            raise ValidationError("Cette feuille de route n'a pas encore démarré.")
        if feuille.heure_arrivee_reelle is not None:
            raise ValidationError("Cette feuille de route est déjà arrivée.")

        depart, vehicule = feuille.depart, feuille.depart.vehicule
        with transaction.atomic():
            feuille.heure_arrivee_reelle = timezone.now()
            feuille.save(update_fields=["heure_arrivee_reelle"])
            depart.statut = DepartStatut.TERMINE
            depart.save(update_fields=["statut"])
            # Le car redevient disponible, sauf s'il est tombé en panne ou a été bloqué en route.
            if vehicule.statut == VehiculeStatut.EN_LIGNE:
                vehicule.statut = VehiculeStatut.DISPONIBLE
                vehicule.save(update_fields=["statut"])
        return Response(self.get_serializer(feuille).data)


class ChecklistDepartViewSet(PersonnelRoulantViewSet):
    queryset = ChecklistDepart.objects.select_related("feuille_de_route", "company")
    serializer_class = ChecklistDepartSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsRoulantManagerOrReadOnly, IsOwnChecklist]

    def create(self, request, *args, **kwargs):
        """Un item est unique par feuille de route : le renvoyer met à jour l'existant.

        Sans cela, un défaut de sécurité serait permanent : `FeuilleDeRoute.peut_demarrer` refuse tant
        qu'il existe un défaut sur la feuille, et refaire la checklist après la réparation ne
        ferait qu'ajouter des items « OK » à côté du défaut. Les contrôles (compagnie, feuille du
        chauffeur) sont ceux du sérialiseur, exécutés avant.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data
        existant = ChecklistDepart.objects.filter(
            feuille_de_route=donnees["feuille_de_route"], item__iexact=donnees["item"].strip()
        ).first()
        if existant is None:
            return super().create(request, *args, **kwargs)

        existant.etat = donnees["etat"]
        existant.commentaire = donnees.get("commentaire", "")
        existant.save()  # un défaut de sécurité rebloque le véhicule (ChecklistDepart.save)
        return Response(self.get_serializer(existant).data, status=200)


class IncidentViewSet(PersonnelRoulantViewSet):
    queryset = Incident.objects.select_related("feuille_de_route", "vehicule", "chauffeur", "company")
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsRoulantManagerOrReadOnly, IsOwnIncident]

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
