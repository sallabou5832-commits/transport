import os

from django.db.models import Q
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, Throttled, ValidationError
from rest_framework.generics import GenericAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView

from core import comptes, sessions
from core.fichiers import reponse_en_telechargement, verifier_fichier
from core.mixins import ActeurAuditeMixin, CompanyScopedQuerysetMixin
from core.models import Company, Role, User
from core.permissions import IsPdg, IsSameCompany, PeutGererLesComptes, PeutTenirLaFicheCompagnie
from core.serializers import (
    ChangementMotDePasseSerializer,
    CompanySerializer,
    CompteGereSerializer,
    CompteSerializer,
    FicheCompagnieSerializer,
    LogoCompagnieSerializer,
    UserSerializer,
)
from core.throttles import ThrottleMotDePasse

# Un logo s'imprime sur les billets et les reçus : une image légère suffit.
TYPES_LOGO = {".png", ".jpg", ".jpeg"}
LOGO_TAILLE_MAX_MO = 1


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class RenouvellementView(TokenRefreshView):
    """Nouveau jeton d'accès à partir du jeton de renouvellement, tant que la session vaut (voir `core.sessions`)."""

    serializer_class = sessions.RenouvellementSerializer


class ChangementMotDePasseView(ActeurAuditeMixin, GenericAPIView):
    """Changer son mot de passe (`ancien`, `nouveau`, et `refresh`, le jeton de cet appareil). Toutes les sessions ouvertes sont
    fermées ; cet appareil reçoit de nouveaux jetons, pour une session de même durée que la sienne."""

    serializer_class = ChangementMotDePasseSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ThrottleMotDePasse]

    def throttled(self, request, wait):
        raise Throttled(wait=wait, detail=f"Trop d'essais. Réessayez dans {int(wait) + 1} seconde(s).")

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        ancienne = sessions.session_envoyee(user, request.data.get("refresh"))
        user.set_password(serializer.validated_data["nouveau"])
        user.version_session += 1
        user.doit_changer_mot_de_passe = False
        user.save(update_fields=["password", "version_session", "doit_changer_mot_de_passe"])
        return Response(sessions.ouvrir_session(user, ancienne.get(sessions.DUREE) if ancienne is not None else None))


class FermetureAutresSessionsView(ActeurAuditeMixin, GenericAPIView):
    """« Déconnecter mes autres appareils » (`refresh`, le jeton de cet appareil) : toutes les autres sessions sont fermées,
    celle-ci reçoit de nouveaux jetons à la même échéance."""

    serializer_class = serializers.Serializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        ancienne = sessions.session_envoyee(user, request.data.get("refresh"))
        if ancienne is None:
            raise ValidationError({"refresh": "Le jeton de session de cet appareil est attendu (reconnectez-vous)."})
        sessions.fermer_les_sessions(user)
        return Response(sessions.garder_session(user, ancienne))


class CompanyDetailView(RetrieveAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, IsSameCompany]


class MaCompagnieView(ActeurAuditeMixin, RetrieveUpdateAPIView):
    """La fiche de la compagnie de l'utilisateur : identité, coordonnées, mentions légales. Tous la lisent ; le PDG la modifie."""

    serializer_class = FicheCompagnieSerializer
    permission_classes = [IsAuthenticated, PeutTenirLaFicheCompagnie]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_object(self):
        return self.request.user.company


class LogoCompagnieView(ActeurAuditeMixin, GenericAPIView):
    """Le logo de la compagnie (PNG ou JPEG, 1 Mo au plus). Tous le récupèrent (`GET`, servi en téléchargement, jamais par un
    lien public) ; le PDG l'envoie (`POST`, champ `fichier` en multipart, remplace l'ancien) ou le retire
    (`POST /compagnie/logo/retirer/`)."""

    serializer_class = LogoCompagnieSerializer
    permission_classes = [IsAuthenticated, PeutTenirLaFicheCompagnie]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        company = request.user.company
        if not company.logo:
            raise NotFound("Votre compagnie n'a pas encore de logo.")
        return reponse_en_telechargement(company.logo, f"logo{os.path.splitext(company.logo.name)[1].lower()}")

    def post(self, request):
        envoye = request.FILES.get("fichier")
        if envoye is None:
            raise ValidationError({"fichier": "Joignez l'image du logo."})
        if verifier_fichier(envoye) not in TYPES_LOGO:
            raise ValidationError({"fichier": "Le logo doit être une image PNG ou JPEG."})
        if envoye.size > LOGO_TAILLE_MAX_MO * 1024 * 1024:
            raise ValidationError({"fichier": f"Le logo dépasse {LOGO_TAILLE_MAX_MO} Mo."})
        company = request.user.company
        ancien = company.logo.name if company.logo else None
        company.logo = envoye
        company.save(update_fields=["logo"])
        if ancien:
            company.logo.storage.delete(ancien)
        return Response(FicheCompagnieSerializer(company).data)


class RetraitLogoCompagnieView(ActeurAuditeMixin, GenericAPIView):
    """Retire le logo de la compagnie (le PDG) : le fichier est effacé, la fiche reste."""

    serializer_class = serializers.Serializer
    permission_classes = [IsAuthenticated, PeutTenirLaFicheCompagnie]

    def post(self, request):
        company = request.user.company
        if company.logo:
            company.logo.delete(save=False)
            company.save(update_fields=["logo"])
        return Response(FicheCompagnieSerializer(company).data)


class ComptesViewSet(
    CompanyScopedQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """Les comptes du personnel de la compagnie (« Personnel et comptes »), pour le PDG et, si le règlement intérieur le lui
    permet, le DRH : les voir, en créer un (`POST`, mot de passe provisoire renvoyé une seule fois),
    modifier sa fiche (`PATCH`), réinitialiser son mot de passe (`reinitialiser-mot-de-passe`). Suspendre (`suspendre`) et
    réactiver (`reactiver`) restent au PDG. Filtres : `role`, `q` (identifiant, nom ou matricule), `suspendus=1`. Les PDG n'y
    figurent pas."""

    queryset = User.objects.select_related("suspendu_par", "affectation_gare__gare", "gare_dirigee", "dossier_agent")
    serializer_class = CompteSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutGererLesComptes]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_serializer_class(self):
        return CompteGereSerializer if self.action in ("create", "update", "partial_update") else CompteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agent, provisoire = comptes.creer(request.user, **serializer.validated_data)
        return Response({**CompteSerializer(agent).data, "mot_de_passe_provisoire": provisoire}, status=201)

    def update(self, request, *args, **kwargs):
        agent = self.get_object()
        ancien_role = agent.role
        serializer = self.get_serializer(agent, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if agent.role != ancien_role:
            comptes.changer_de_poste(agent, request.user, ancien_role)
        return Response(CompteSerializer(agent).data)

    @action(detail=True, methods=["post"], url_path="reinitialiser-mot-de-passe")
    def reinitialiser_mot_de_passe(self, request, pk=None):
        """Nouveau mot de passe provisoire (renvoyé une seule fois), à changer à la prochaine connexion ; sessions fermées."""
        agent = self.get_object()
        provisoire = comptes.reinitialiser(agent, request.user)
        return Response({**CompteSerializer(agent).data, "mot_de_passe_provisoire": provisoire})

    def get_queryset(self):
        queryset = super().get_queryset().exclude(role__in=comptes.ROLES_INTOUCHABLES).order_by("role", "username")
        parametres = self.request.query_params
        if parametres.get("role") in Role.values:
            queryset = queryset.filter(role=parametres["role"])
        recherche = parametres.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(username__icontains=recherche)
                | Q(first_name__icontains=recherche)
                | Q(last_name__icontains=recherche)
                | Q(matricule__icontains=recherche)
            )
        if parametres.get("suspendus") == "1":
            queryset = queryset.filter(is_active=False)
        return queryset

    @action(detail=True, methods=["post"], url_path="suspendre", permission_classes=[IsAuthenticated, IsSameCompany, IsPdg])
    def suspendre(self, request, pk=None):
        """Suspend le compte (`motif` obligatoire) : plus de connexion, sessions ouvertes coupées."""
        agent = comptes.suspendre(self.get_object(), request.user, request.data.get("motif"))
        return Response(self.get_serializer(agent).data)

    @action(detail=True, methods=["post"], url_path="reactiver", permission_classes=[IsAuthenticated, IsSameCompany, IsPdg])
    def reactiver(self, request, pk=None):
        """Rend le compte tel qu'il était (`motif` facultatif)."""
        agent = comptes.reactiver(self.get_object(), request.user, request.data.get("motif"))
        return Response(self.get_serializer(agent).data)
