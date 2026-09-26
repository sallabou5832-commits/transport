from django.db.models import BooleanField, Exists, OuterRef, Q, Value
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from alertes.models import Alerte, LectureAlerte
from alertes.serializers import AlerteSerializer

LIMITE_PAR_DEFAUT = 30
LIMITE_MAX = 100


class AlerteViewSet(viewsets.GenericViewSet):
    """Les alertes qui concernent l'utilisateur connecté : celles adressées à son poste ou à lui-même.

    Chacun les marque lues pour lui seul. Aucune écriture par l'API en dehors de la lecture : les alertes naissent
    des actions des autres pôles (voir `alertes.services`).
    """

    serializer_class = AlerteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.company_id is None:  # le superadmin n'appartient à aucune compagnie
            return Alerte.objects.none().annotate(lue=Value(False, output_field=BooleanField()))
        lues = LectureAlerte.objects.filter(alerte=OuterRef("pk"), utilisateur=user)
        return (
            Alerte.objects.filter(company_id=user.company_id)
            .filter(Q(roles_destinataires__contains=[user.role]) | Q(destinataires=user))
            .distinct()
            .annotate(lue=Exists(lues))
        )

    def list(self, request):
        base = self.get_queryset()
        try:
            limite = max(1, min(int(request.query_params.get("limit", LIMITE_PAR_DEFAUT)), LIMITE_MAX))
        except ValueError:
            limite = LIMITE_PAR_DEFAUT
        liste = base.filter(lue=False) if request.query_params.get("non_lues") == "1" else base
        return Response(
            {
                "non_lues": base.filter(lue=False).count(),
                "alertes": self.get_serializer(liste[:limite], many=True).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="lire")
    def lire(self, request, pk=None):
        alerte = self.get_object()
        LectureAlerte.objects.get_or_create(alerte=alerte, utilisateur=request.user)
        alerte.lue = True
        return Response(self.get_serializer(alerte).data)

    @action(detail=False, methods=["post"], url_path="lire-tout")
    def lire_tout(self, request):
        non_lues = list(self.get_queryset().filter(lue=False).values_list("pk", flat=True))
        LectureAlerte.objects.bulk_create(
            [LectureAlerte(alerte_id=pk, utilisateur=request.user, lu_le=timezone.now()) for pk in non_lues],
            ignore_conflicts=True,
        )
        return Response({"marquees": len(non_lues)})
