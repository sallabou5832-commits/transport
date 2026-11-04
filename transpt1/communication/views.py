from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from communication import guides, services
from communication.models import DocumentArchive, EvenementAgenda, MessageDirect, NoteService
from communication.permissions import (
    ROLES_SECRETARIAT,
    ROLES_SUPERVISION_MESSAGES,
    PeutClasserLesArchives,
    PeutEcrireAuxEquipes,
    PeutLireLesNotes,
    PeutTenirLAgenda,
)
from communication.poles import POLES
from communication.serializers import (
    DocumentArchiveSerializer,
    EvenementAgendaSerializer,
    MessageDirectSerializer,
    NoteServiceSerializer,
)
from core.dates import lire_date
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role
from core.permissions import IsSameCompany
from reseau.models import Gare


class NoteServiceViewSet(
    CompanyScopedQuerysetMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Notes de service. Le secrétaire général et le PDG les rédigent et les adressent aux pôles, aux postes ou à tous ; chaque
    poste visé la reçoit dans sa cloche d'alertes et la relit ici. Un poste ne voit que les notes qui le visent."""

    queryset = NoteService.objects.select_related("auteur")
    serializer_class = NoteServiceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutLireLesNotes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role not in ROLES_SECRETARIAT:
            queryset = queryset.filter(roles_destinataires__contains=[user.role])
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        note = serializer.save(company=user.company, auteur=user)
        services.diffuser_note(note)


class MessageDirectViewSet(
    CompanyScopedQuerysetMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Messages directs du chef de gare à son équipe et aux chauffeurs en approche (`portee` : equipe, approche, les_deux)."""

    queryset = MessageDirect.objects.select_related("auteur", "gare")
    serializer_class = MessageDirectSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutEcrireAuxEquipes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role not in ROLES_SUPERVISION_MESSAGES:
            queryset = queryset.filter(auteur=user)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        gare = Gare.objects.filter(company=user.company, chef=user).first()
        if gare is None:
            raise ValidationError("Aucune gare ne vous est rattachée : vous n'avez pas d'équipe à prévenir.")
        message = serializer.save(company=user.company, auteur=user, gare=gare)
        try:
            services.envoyer_message(message)
        except ValidationError:
            message.delete()  # un message sans destinataire n'est pas conservé
            raise


class EvenementAgendaViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    """L'agenda partagé de la direction. Les postes de direction le lisent (`?du=` et `?au=`, ou `?a_venir=1`) ; le secrétaire
    général et le PDG le tiennent. Les postes invités (`participants`) sont alertés à la création."""

    queryset = EvenementAgenda.objects.select_related("auteur")
    serializer_class = EvenementAgendaSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutTenirLAgenda]

    def get_queryset(self):
        queryset = super().get_queryset()
        parametres = self.request.query_params
        if parametres.get("a_venir") == "1":
            queryset = queryset.filter(Q(debut__gte=timezone.now()) | Q(fin__gte=timezone.now()))
        du, au = lire_date(parametres.get("du")), lire_date(parametres.get("au"))
        if du:
            queryset = queryset.filter(debut__date__gte=du)
        if au:
            queryset = queryset.filter(debut__date__lte=au)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        evenement = serializer.save(company=user.company, auteur=user)
        services.annoncer_evenement(evenement)


class DocumentArchiveViewSet(
    CompanyScopedQuerysetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Registre des dossiers administratifs du secrétariat général : classer, retrouver (`?q=`, `?categorie=`, `?archive=0|1`),
    archiver. Un dossier ne se supprime pas : il s'archive."""

    queryset = DocumentArchive.objects.select_related("auteur")
    serializer_class = DocumentArchiveSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutClasserLesArchives]

    def get_queryset(self):
        queryset = super().get_queryset()
        parametres = self.request.query_params
        recherche = parametres.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(titre__icontains=recherche)
                | Q(reference__icontains=recherche)
                | Q(mots_cles__icontains=recherche)
                | Q(description__icontains=recherche)
                | Q(emplacement__icontains=recherche)
            )
        if parametres.get("categorie"):
            queryset = queryset.filter(categorie=parametres["categorie"])
        if parametres.get("archive") in ("0", "1"):
            queryset = queryset.filter(archive=parametres["archive"] == "1")
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(company=user.company, auteur=user)

    def _basculer(self, archive):
        document = self.get_object()
        if document.archive == archive:
            raise ValidationError("Ce dossier est déjà archivé." if archive else "Ce dossier n'est pas archivé.")
        document.archive, document.archive_le = archive, timezone.now() if archive else None
        document.save(update_fields=["archive", "archive_le"])
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=["post"], url_path="archiver")
    def archiver(self, request, pk=None):
        return self._basculer(True)

    @action(detail=True, methods=["post"], url_path="desarchiver")
    def desarchiver(self, request, pk=None):
        return self._basculer(False)


class GuidesView(APIView):
    """Le guide d'utilisation de chaque poste, rangé par pôle : chacun lit celui de tous les postes, le sien signalé."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(guides.guide_pour(request.user))


class CatalogueCommunicationView(APIView):
    """Les pôles et leurs postes, pour adresser une note ou une invitation."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            [
                {"pole": cle, "libelle": libelle, "postes": [{"role": r.value, "libelle": r.label} for r in roles]}
                for cle, (libelle, roles) in POLES.items()
            ]
        )
