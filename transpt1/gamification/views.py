from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from configuration.regles import NiveauGamification
from configuration.services import niveau_gamification
from core.models import Role
from gamification import moteur

ROLES_VUE_DES_AGENTS = {Role.DRH, Role.PDG}


class PeutVoirLesAgents(BasePermission):
    """Vue transversale des scores : aide à l'évaluation du DRH (et du PDG). Pas de transparence par défaut."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_VUE_DES_AGENTS)


class MonEtatView(APIView):
    """Ce que le jeu montre à l'utilisateur connecté : niveau, points, missions du jour, badges. `actif` est faux quand
    le poste n'affiche pas la gamification : la page n'a alors rien à montrer (ce n'est pas une erreur)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(moteur.etat_agent(request.user))


class ClassementView(APIView):
    """`?type=gares|lignes|chauffeurs|guichetiers|bagagistes|ateliers&periode=jour|semaine|mois|tout`. Réservé aux postes dont
    la gamification est « complète » ; pour les autres, `visible` est faux et la liste vide (le classement est un choix
    de la compagnie, pas un droit)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        type_classement = request.query_params.get("type") or "gares"
        periode = request.query_params.get("periode") or "mois"
        if type_classement not in moteur.TYPES_CLASSEMENT:
            raise ValidationError({"type": f"Types possibles : {', '.join(moteur.TYPES_CLASSEMENT)}."})
        if periode not in moteur.PERIODES:
            raise ValidationError({"periode": f"Périodes possibles : {', '.join(moteur.PERIODES)}."})
        if user.company_id is None or niveau_gamification(user) != NiveauGamification.COMPLET:
            return Response({"visible": False, "type": type_classement, "periode": periode, "classement": []})
        if type_classement not in [t["type"] for t in moteur.types_de_classement(user)]:
            raise PermissionDenied("Ce classement n'est pas proposé à votre poste.")
        return Response(
            {
                "visible": True,
                "type": type_classement,
                "libelle": moteur.TYPES_CLASSEMENT[type_classement],
                "periode": periode,
                "classement": moteur.classement(user, type_classement, periode),
            }
        )


class VueDesAgentsView(APIView):
    permission_classes = [IsAuthenticated, PeutVoirLesAgents]

    def get(self, request):
        return Response({"agents": moteur.vue_des_agents(request.user.company_id)})
