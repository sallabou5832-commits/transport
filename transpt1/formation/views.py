from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from formation import services
from formation.serializers import ParcoursFormationSerializer


def _reponse(parcours, progression, *, code=status.HTTP_200_OK):
    serializer = ParcoursFormationSerializer(parcours, context={"progression": progression})
    return Response(serializer.data, status=code)


class MonParcoursView(APIView):
    """Le parcours de formation du rôle de l'utilisateur, avec sa progression."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        parcours = services.parcours_du_role(request.user)
        return _reponse(parcours, services.progression_de(request.user, parcours))


class DemarrerParcoursView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        parcours, progression = services.demarrer_parcours(request.user)
        return _reponse(parcours, progression)


class TerminerEtapeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, etape_id):
        parcours, progression = services.terminer_etape(request.user, etape_id)
        return _reponse(parcours, progression)
