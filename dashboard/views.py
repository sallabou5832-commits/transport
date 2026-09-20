import datetime
from decimal import Decimal

from django.db.models import Case, Count, F, IntegerField, Sum, Value, When
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billetterie.models import Ticket
from dashboard.permissions import IsDirection, IsQhse
from dashboard.serializers import IncidentTableauBordSerializer
from maintenance.models import Piece
from personnel_roulant.models import GraviteIncident, Incident, StatutIncident
from reseau.models import Vehicule, VehiculeStatut
from supports.models import Assurance


class DashboardDirectionView(APIView):
    permission_classes = [IsAuthenticated, IsDirection]

    def get(self, request):
        company = request.user.company
        today = timezone.localdate()

        vehicules_par_statut = {statut: 0 for statut in VehiculeStatut.values}
        for row in Vehicule.objects.filter(company=company).values("statut").annotate(
            nombre=Count("id")
        ):
            vehicules_par_statut[row["statut"]] = row["nombre"]

        incidents_par_gravite = {gravite: 0 for gravite in GraviteIncident.values}
        depuis_7_jours = timezone.now() - datetime.timedelta(days=7)
        for row in (
            Incident.objects.filter(
                company=company, statut=StatutIncident.OUVERT, date__gte=depuis_7_jours
            )
            .values("gravite")
            .annotate(nombre=Count("id"))
        ):
            incidents_par_gravite[row["gravite"]] = row["nombre"]

        recettes_du_jour = (
            Ticket.objects.filter(company=company, date_vente__date=today).aggregate(
                total=Sum("prix")
            )["total"]
            or Decimal("0")
        )

        pieces_sous_seuil = Piece.objects.filter(
            company=company, quantite_stock__lte=F("seuil_alerte")
        ).count()

        limite_echeance = today + datetime.timedelta(days=30)
        assurances_echeance_proche = Assurance.objects.filter(
            company=company, date_echeance__lte=limite_echeance
        ).count()

        return Response(
            {
                "vehicules_par_statut": vehicules_par_statut,
                "incidents_ouverts_par_gravite_7_jours": incidents_par_gravite,
                "recettes_du_jour": recettes_du_jour,
                "pieces_sous_seuil": pieces_sous_seuil,
                "assurances_echeance_proche": assurances_echeance_proche,
            }
        )


class DashboardQhseView(APIView):
    permission_classes = [IsAuthenticated, IsQhse]

    def get(self, request):
        company = request.user.company

        severite = Case(
            When(gravite=GraviteIncident.GRAVE, then=Value(0)),
            When(gravite=GraviteIncident.MOYENNE, then=Value(1)),
            When(gravite=GraviteIncident.FAIBLE, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )

        incidents = (
            Incident.objects.filter(company=company, statut=StatutIncident.OUVERT)
            .select_related("vehicule")
            .annotate(severite=severite)
            .order_by("severite", "-date")
        )

        serializer = IncidentTableauBordSerializer(incidents, many=True)
        return Response(serializer.data)
