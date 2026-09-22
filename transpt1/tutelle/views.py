from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import CompanyScopedQuerysetMixin
from tutelle import generation
from tutelle.authentication import CompteTutelleAuthentication
from tutelle.models import DirectionFlux, FluxTutelle, StatutFlux
from tutelle.permissions import EstCompteTutelle, PeutSuivreLesFluxTutelle
from tutelle.serializers import FluxEntrantSerializer, FluxTutelleSerializer


class FluxTutelleViewSet(CompanyScopedQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Les flux échangés avec la tutelle, pour le QHSE et le responsable juridique de la compagnie (`?type=`,
    `?direction=`, `?statut=`) : consultation et suivi (`traiter`). Jamais de création manuelle ici — les flux se
    génèrent automatiquement (incident grave, échéance d'assurance) ou arrivent de la tutelle par `FluxEntrantView`.
    """

    queryset = FluxTutelle.objects.select_related("company")
    serializer_class = FluxTutelleSerializer
    permission_classes = [IsAuthenticated, PeutSuivreLesFluxTutelle]

    def get_queryset(self):
        queryset = super().get_queryset()
        parametres = self.request.query_params
        for champ in ("type", "direction", "statut"):
            if parametres.get(champ):
                queryset = queryset.filter(**{champ: parametres[champ]})
        return queryset

    @action(detail=True, methods=["post"], url_path="traiter")
    def traiter(self, request, pk=None):
        flux = self.get_object()
        if flux.statut == StatutFlux.TRAITE:
            raise ValidationError("Ce flux est déjà traité.")
        flux.statut = StatutFlux.TRAITE
        flux.save(update_fields=["statut"])
        return Response(self.get_serializer(flux).data)


class FluxEntrantView(APIView):
    """Ce que la tutelle envoie à une compagnie — une nouvelle norme de conformité, par exemple
    (`POST /api/tutelle/entrant/`, `{"company": <id>, "type": "conformite", "contenu": {...}}`). Réservé aux
    comptes tutelle (clé d'API) : jamais aux comptes internes, même le PDG n'y accède pas par son propre jeton."""

    authentication_classes = [CompteTutelleAuthentication]
    permission_classes = [EstCompteTutelle]

    def post(self, request):
        serializer = FluxEntrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flux = serializer.save(direction=DirectionFlux.VERS_COMPAGNIE, statut=StatutFlux.RECU)
        return Response(FluxTutelleSerializer(flux).data, status=201)


class GenererFluxView(APIView):
    """Rattrape, pour la compagnie de l'appelant, les flux automatiques pas encore générés (incidents graves,
    assurances proches de l'échéance). Sans effet sur ce qui l'est déjà : jamais de doublon (voir
    `tutelle.generation`). En usage normal les flux se génèrent tout seuls (incident : à sa déclaration ; assurance :
    par la tâche planifiée — voir `tutelle/management/commands/generer_flux_tutelle.py`) ; cet endpoint sert à
    rattraper à la demande, par exemple juste après l'activation de ce module."""

    permission_classes = [IsAuthenticated, PeutSuivreLesFluxTutelle]

    def post(self, request):
        crees = generation.generer_tout(request.user.company)
        return Response({"securite": len(crees["securite"]), "conformite": len(crees["conformite"])}, status=201)
