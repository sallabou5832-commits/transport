from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed, Throttled, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.views import TokenObtainPairView

from audit import contexte
from audit.models import ActionAudit, JournalAudit
from audit.serializers import JournalAuditSerializer
from core.dates import lire_date
from core.models import Role
from core.throttles import ThrottleConnexionAdresse, ThrottleConnexionCompte

# Traçabilité pour l'audit et la conformité (cahier des charges) : la direction et le QHSE. Le journal d'une
# compagnie ne sort jamais de cette compagnie ; seul le superadmin, opérateur de la plateforme, les voit toutes.
ROLES_AUDIT = {Role.PDG, Role.SECRETAIRE_GENERAL, Role.QHSE, Role.SUPERADMIN}


class PeutConsulterAudit(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_AUDIT)


class PaginationJournal(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


class JournalAuditView(ListAPIView):
    """Journal d'audit, du plus récent au plus ancien. Filtres : objet_type, objet_id, action, acteur,
    date_debut, date_fin (AAAA-MM-JJ). Paginé : ?limit=50&offset=0."""

    serializer_class = JournalAuditSerializer
    permission_classes = [IsAuthenticated, PeutConsulterAudit]
    pagination_class = PaginationJournal

    def get_queryset(self):
        user = self.request.user
        entrees = JournalAudit.objects.all()
        if user.role != Role.SUPERADMIN:
            entrees = entrees.filter(company_id=user.company_id)

        parametres = self.request.query_params
        for parametre in ("objet_type", "objet_id", "action"):
            if parametres.get(parametre):
                entrees = entrees.filter(**{parametre: parametres[parametre]})
        if parametres.get("acteur"):
            try:
                entrees = entrees.filter(acteur_id=int(parametres["acteur"]))
            except ValueError:
                raise ValidationError({"acteur": "Identifiant invalide."})
        for parametre, filtre in (("date_debut", "date__date__gte"), ("date_fin", "date__date__lte")):
            if parametres.get(parametre):
                date = lire_date(parametres[parametre])
                if date is None:
                    raise ValidationError({parametre: "Format attendu : AAAA-MM-JJ."})
                entrees = entrees.filter(**{filtre: date})
        return entrees


def _enregistrer_connexion(action, username, utilisateur=None):
    JournalAudit.objects.create(
        company=utilisateur.company if utilisateur else None,
        acteur=utilisateur,
        acteur_nom=(utilisateur.get_full_name() or utilisateur.username) if utilisateur else username,
        acteur_role=utilisateur.role if utilisateur else "",
        action=action,
        objet_type="core.user",
        objet_id=str(utilisateur.pk) if utilisateur else "",
        objet_repr=username,
        adresse_ip=contexte.adresse_ip(),
    )


class ConnexionAuditee(TokenObtainPairView):
    """Connexion JWT dont chaque tentative, réussie ou non, est tracée (repérer un essai de mots de passe).
    Le mot de passe saisi n'est jamais conservé : seul l'identifiant l'est. Les essais trop rapprochés sont refusés
    (429) : voir `core.throttles`."""

    throttle_classes = [ThrottleConnexionCompte, ThrottleConnexionAdresse]

    def throttled(self, request, wait):
        raise Throttled(
            wait=wait,
            detail=f"Trop de tentatives de connexion. Réessayez dans {int(wait) + 1} seconde(s).",
        )

    def post(self, request, *args, **kwargs):
        username = str(request.data.get("username", ""))[:150]
        try:
            reponse = super().post(request, *args, **kwargs)
        except (AuthenticationFailed, InvalidToken):
            _enregistrer_connexion(ActionAudit.CONNEXION_ECHEC, username)
            raise
        utilisateur = get_user_model().objects.filter(username=username).select_related("company").first()
        _enregistrer_connexion(ActionAudit.CONNEXION, username, utilisateur)
        return reponse
