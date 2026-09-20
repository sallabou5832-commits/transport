import datetime
from decimal import Decimal

from django.db.models import Case, Count, F, IntegerField, Sum, Value, When
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billetterie.models import Depart, DepartStatut, Ticket
from core.models import Company, Role, User
from core.serializers import nom_complet
from dashboard.permissions import IsDirection, IsExploitation, IsQhse, IsSuperadmin
from dashboard.serializers import IncidentTableauBordSerializer
from maintenance.models import Piece
from personnel_roulant.models import FeuilleDeRoute, GraviteIncident, Incident, StatutIncident
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut
from supports.models import Assurance

# Un départ est « à l'heure » s'il a lieu au plus tard 10 minutes après l'heure prévue.
TOLERANCE_RETARD = datetime.timedelta(minutes=10)
# Couleur d'une gare ou d'une ligne selon sa ponctualité (cahier des charges : vert/orange/rouge).
SEUIL_PONCTUALITE_VERT = 90
SEUIL_PONCTUALITE_ORANGE = 70


def _bornes_du_jour(reference):
    debut = timezone.localtime(reference).replace(hour=0, minute=0, second=0, microsecond=0)
    return debut, debut + datetime.timedelta(days=1)


def _pourcentage(partie, total):
    return round(100 * partie / total) if total else None


def _statut_ponctualite(feuille, maintenant):
    """« a_l_heure », « en_retard » ou « en_attente » pour une feuille de route.

    Une feuille non démarrée est en retard une fois la tolérance dépassée : le départ
    n'a pas eu lieu, il ne faut pas attendre qu'il ait lieu pour le signaler.
    """
    limite = feuille.heure_depart_prevue + TOLERANCE_RETARD
    if feuille.heure_depart_reelle is not None:
        return "a_l_heure" if feuille.heure_depart_reelle <= limite else "en_retard"
    return "en_retard" if maintenant > limite else "en_attente"


def _retard_minutes(feuille, maintenant):
    fin = feuille.heure_depart_reelle or maintenant
    return max(0, int((fin - feuille.heure_depart_prevue).total_seconds() // 60))


def _couleur(ponctualite):
    if ponctualite is None:
        return "neutre"
    if ponctualite >= SEUIL_PONCTUALITE_VERT:
        return "vert"
    if ponctualite >= SEUIL_PONCTUALITE_ORANGE:
        return "orange"
    return "rouge"


def _bilan(departs, feuilles, maintenant):
    """Remplissage et ponctualité d'un groupe de départs (une gare, une ligne, ou tout)."""
    places_vendues = sum(depart.places_vendues for depart in departs)
    capacite = sum(depart.vehicule.capacite for depart in departs)
    statuts = [_statut_ponctualite(feuille, maintenant) for feuille in feuilles]
    a_l_heure, en_retard = statuts.count("a_l_heure"), statuts.count("en_retard")
    ponctualite = _pourcentage(a_l_heure, a_l_heure + en_retard)
    return {
        "departs": len(departs),
        "places_vendues": places_vendues,
        "capacite": capacite,
        "remplissage_pourcent": _pourcentage(places_vendues, capacite),
        "a_l_heure": a_l_heure,
        "en_retard": en_retard,
        "en_attente": statuts.count("en_attente"),
        "ponctualite_pourcent": ponctualite,
        "couleur": _couleur(ponctualite),
    }


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


class DashboardExploitationView(APIView):
    """Vue d'ensemble de l'exploitation du jour : gares, lignes, ponctualité, flotte, incidents."""

    permission_classes = [IsAuthenticated, IsExploitation]

    def get(self, request):
        company = request.user.company
        maintenant = timezone.now()
        debut_jour, fin_jour = _bornes_du_jour(maintenant)

        departs = list(
            Depart.objects.filter(
                company=company, date_heure__gte=debut_jour, date_heure__lt=fin_jour
            ).select_related("ligne", "vehicule")
        )
        feuilles = list(
            FeuilleDeRoute.objects.filter(
                company=company,
                heure_depart_prevue__gte=debut_jour,
                heure_depart_prevue__lt=fin_jour,
            ).select_related("depart__ligne", "chauffeur")
        )

        departs_par_gare, feuilles_par_gare = {}, {}
        departs_par_ligne, feuilles_par_ligne = {}, {}
        for depart in departs:
            departs_par_gare.setdefault(depart.ligne.gare_depart_id, []).append(depart)
            departs_par_ligne.setdefault(depart.ligne_id, []).append(depart)
        for feuille in feuilles:
            ligne = feuille.depart.ligne
            feuilles_par_gare.setdefault(ligne.gare_depart_id, []).append(feuille)
            feuilles_par_ligne.setdefault(ligne.id, []).append(feuille)

        gares = [
            {
                "id": gare.id,
                "nom": gare.nom,
                "ville": gare.ville,
                **_bilan(
                    departs_par_gare.get(gare.id, []), feuilles_par_gare.get(gare.id, []), maintenant
                ),
            }
            for gare in Gare.objects.filter(company=company)
        ]
        lignes = [
            {
                "id": ligne.id,
                "nom": ligne.nom,
                "gare_depart": ligne.gare_depart.nom,
                "gare_arrivee": ligne.gare_arrivee.nom,
                **_bilan(
                    departs_par_ligne.get(ligne.id, []), feuilles_par_ligne.get(ligne.id, []), maintenant
                ),
            }
            for ligne in Ligne.objects.filter(company=company).select_related(
                "gare_depart", "gare_arrivee"
            )
        ]

        departs_en_retard = [
            {
                "depart": feuille.depart_id,
                "ligne": feuille.depart.ligne.nom,
                "chauffeur_nom": nom_complet(feuille.chauffeur),
                "heure_depart_prevue": feuille.heure_depart_prevue,
                "retard_minutes": _retard_minutes(feuille, maintenant),
            }
            for feuille in feuilles
            if feuille.heure_depart_reelle is None
            and _statut_ponctualite(feuille, maintenant) == "en_retard"
        ]

        feuilles_7_jours = FeuilleDeRoute.objects.filter(
            company=company,
            heure_depart_prevue__gte=maintenant - datetime.timedelta(days=7),
            heure_depart_prevue__lte=maintenant,
        )
        statuts_7_jours = [_statut_ponctualite(feuille, maintenant) for feuille in feuilles_7_jours]
        ponctualite_7_jours = _pourcentage(
            statuts_7_jours.count("a_l_heure"),
            statuts_7_jours.count("a_l_heure") + statuts_7_jours.count("en_retard"),
        )

        vehicules_par_statut = {statut: 0 for statut in VehiculeStatut.values}
        for row in Vehicule.objects.filter(company=company).values("statut").annotate(
            nombre=Count("id")
        ):
            vehicules_par_statut[row["statut"]] = row["nombre"]
        vehicules_indisponibles = [
            {"id": vehicule.id, "immatriculation": vehicule.immatriculation, "statut": vehicule.statut}
            for vehicule in Vehicule.objects.filter(
                company=company,
                statut__in=[VehiculeStatut.BLOQUE_SECURITE, VehiculeStatut.EN_MAINTENANCE],
            )
        ]

        incidents_ouverts = Incident.objects.filter(company=company, statut=StatutIncident.OUVERT)
        incidents_par_gravite = {gravite: 0 for gravite in GraviteIncident.values}
        for row in incidents_ouverts.values("gravite").annotate(nombre=Count("id")).order_by():
            incidents_par_gravite[row["gravite"]] = row["nombre"]
        incidents_graves = [
            {
                "id": incident.id,
                "type_incident": incident.type_incident,
                "description": incident.description,
                "date": incident.date,
                "vehicule": {
                    "id": incident.vehicule_id,
                    "immatriculation": incident.vehicule.immatriculation,
                },
                "chauffeur_nom": nom_complet(incident.chauffeur),
            }
            for incident in incidents_ouverts.filter(gravite=GraviteIncident.GRAVE)
            .select_related("vehicule", "chauffeur")
            .order_by("-date")[:10]
        ]

        return Response(
            {
                "date": timezone.localdate(maintenant),
                "jour": {
                    **_bilan(departs, feuilles, maintenant),
                    "departs_par_statut": {
                        statut: sum(1 for depart in departs if depart.statut == statut)
                        for statut in DepartStatut.values
                    },
                },
                "ponctualite_7_jours_pourcent": ponctualite_7_jours,
                "gares": gares,
                "lignes": lignes,
                "departs_en_retard": departs_en_retard,
                "vehicules_par_statut": vehicules_par_statut,
                "vehicules_indisponibles": vehicules_indisponibles,
                "incidents_ouverts_par_gravite": incidents_par_gravite,
                "incidents_graves_ouverts": incidents_graves,
            }
        )


class DashboardPlateformeView(APIView):
    """Vue de l'opérateur de la plateforme : une ligne par compagnie cliente."""

    permission_classes = [IsAuthenticated, IsSuperadmin]

    def get(self, request):
        maintenant = timezone.now()
        debut_jour, fin_jour = _bornes_du_jour(maintenant)

        def compter(queryset, **filtre):
            lignes = queryset.filter(**filtre).values("company_id").annotate(n=Count("id")).order_by()
            return {ligne["company_id"]: ligne["n"] for ligne in lignes}

        agents = compter(User.objects.exclude(role=Role.SUPERADMIN))
        gares = compter(Gare.objects.all())
        lignes = compter(Ligne.objects.all())
        vehicules = compter(Vehicule.objects.all())
        vehicules_bloques = compter(Vehicule.objects.all(), statut=VehiculeStatut.BLOQUE_SECURITE)
        departs_du_jour = compter(
            Depart.objects.all(), date_heure__gte=debut_jour, date_heure__lt=fin_jour
        )
        incidents_ouverts = compter(Incident.objects.all(), statut=StatutIncident.OUVERT)

        tickets_du_jour = {
            ligne["company_id"]: ligne
            for ligne in Ticket.objects.filter(date_vente__gte=debut_jour, date_vente__lt=fin_jour)
            .values("company_id")
            .annotate(nombre=Count("id"), montant=Sum("prix"))
            .order_by()
        }

        compagnies = []
        for company in Company.objects.all():
            ventes = tickets_du_jour.get(company.id, {})
            compagnies.append(
                {
                    "id": company.id,
                    "nom": company.name,
                    "ville": company.headquarters_city,
                    "agents": agents.get(company.id, 0),
                    "gares": gares.get(company.id, 0),
                    "lignes": lignes.get(company.id, 0),
                    "vehicules": vehicules.get(company.id, 0),
                    "vehicules_bloques": vehicules_bloques.get(company.id, 0),
                    "departs_du_jour": departs_du_jour.get(company.id, 0),
                    "tickets_du_jour": ventes.get("nombre", 0),
                    "recettes_du_jour": ventes.get("montant") or Decimal("0"),
                    "incidents_ouverts": incidents_ouverts.get(company.id, 0),
                }
            )

        return Response(
            {
                "date": timezone.localdate(maintenant),
                "compagnies": compagnies,
                "totaux": {
                    "compagnies": len(compagnies),
                    "agents": sum(c["agents"] for c in compagnies),
                    "vehicules": sum(c["vehicules"] for c in compagnies),
                    "tickets_du_jour": sum(c["tickets_du_jour"] for c in compagnies),
                    "recettes_du_jour": sum((c["recettes_du_jour"] for c in compagnies), Decimal("0")),
                },
            }
        )
