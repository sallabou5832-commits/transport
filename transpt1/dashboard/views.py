import datetime
from decimal import Decimal

from django.db.models import Case, Count, F, IntegerField, Sum, Value, When
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billetterie.models import Depart, DepartStatut, StatutTicket, Ticket
from colis.models import Colis, StatutColis
from core.models import Company, Role, User
from core.serializers import nom_complet
from dashboard.permissions import IsDirection, IsExploitation, IsQhse, IsSuperadmin, PeutVoirLaCarte, PeutVoirLaSanteDeLaGare
from dashboard.ponctualite import bornes_du_jour, couleur, pourcentage, retard_minutes, statut_ponctualite
from dashboard.serializers import IncidentTableauBordSerializer
from maintenance.models import Piece
from personnel_roulant.models import FeuilleDeRoute, GraviteIncident, Incident, StatutIncident
from reseau.models import AffectationGare, Gare, Ligne, Vehicule, VehiculeStatut
from supports.models import Assurance


def _bilan(departs, feuilles, maintenant):
    """Remplissage et ponctualité d'un groupe de départs (une gare, une ligne, ou tout)."""
    places_vendues = sum(depart.places_vendues for depart in departs)
    capacite = sum(depart.vehicule.capacite for depart in departs)
    statuts = [statut_ponctualite(feuille, maintenant) for feuille in feuilles]
    a_l_heure, en_retard = statuts.count("a_l_heure"), statuts.count("en_retard")
    ponctualite = pourcentage(a_l_heure, a_l_heure + en_retard)
    return {
        "departs": len(departs),
        "places_vendues": places_vendues,
        "capacite": capacite,
        "remplissage_pourcent": pourcentage(places_vendues, capacite),
        "a_l_heure": a_l_heure,
        "en_retard": en_retard,
        "en_attente": statuts.count("en_attente"),
        "ponctualite_pourcent": ponctualite,
        "couleur": couleur(ponctualite),
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

        # Score de disponibilité de la flotte (Directeur technique -> tableau de bord du PDG) : part des véhicules en état de
        # rouler, c'est-à-dire ni bloqués pour la sécurité, ni à l'atelier.
        total_vehicules = sum(vehicules_par_statut.values())
        disponibilite_flotte = pourcentage(
            vehicules_par_statut[VehiculeStatut.DISPONIBLE] + vehicules_par_statut[VehiculeStatut.EN_LIGNE], total_vehicules
        )

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
            Ticket.objects.filter(
                company=company, date_vente__date=today, statut=StatutTicket.VALIDE
            ).aggregate(
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
                "disponibilite_flotte_pourcent": disponibilite_flotte,
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


_TENSION_VIDE = {"vehicules_attaches": 0, "vehicules_disponibles": 0, "departs_24h": 0, "tension": 0, "en_tension": False}


def _tension_des_gares(company, maintenant):
    """Par gare : départs à assurer dans les 24 heures contre véhicules disponibles rattachés à la gare. Un écart positif
    signale une gare en tension ; un écart négatif, une gare qui a de quoi en prêter. Les départs d'une ligne fermée ne
    comptent pas : ils ne rouleront pas."""
    horizon = maintenant + datetime.timedelta(hours=24)
    a_assurer = {}
    for depart in Depart.objects.filter(
        company=company,
        statut=DepartStatut.PLANIFIE,
        date_heure__gte=maintenant - datetime.timedelta(hours=2),
        date_heure__lte=horizon,
    ).select_related("ligne"):
        if not depart.ligne.est_fermee:
            a_assurer[depart.ligne.gare_depart_id] = a_assurer.get(depart.ligne.gare_depart_id, 0) + 1
    attaches, disponibles = {}, {}
    for ligne in Vehicule.objects.filter(company=company, gare__isnull=False).values("gare_id", "statut").annotate(n=Count("id")):
        attaches[ligne["gare_id"]] = attaches.get(ligne["gare_id"], 0) + ligne["n"]
        if ligne["statut"] == VehiculeStatut.DISPONIBLE:
            disponibles[ligne["gare_id"]] = disponibles.get(ligne["gare_id"], 0) + ligne["n"]
    resultat = {}
    for gare_id in set(a_assurer) | set(attaches):
        ecart = a_assurer.get(gare_id, 0) - disponibles.get(gare_id, 0)
        resultat[gare_id] = {
            "vehicules_attaches": attaches.get(gare_id, 0),
            "vehicules_disponibles": disponibles.get(gare_id, 0),
            "departs_24h": a_assurer.get(gare_id, 0),
            "tension": ecart,
            "en_tension": ecart > 0,
        }
    return resultat


class DashboardExploitationView(APIView):
    """Vue d'ensemble de l'exploitation du jour : gares, lignes, ponctualité, flotte, incidents."""

    permission_classes = [IsAuthenticated, IsExploitation]

    def get(self, request):
        company = request.user.company
        maintenant = timezone.now()
        debut_jour, fin_jour = bornes_du_jour(maintenant)

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

        tension = _tension_des_gares(company, maintenant)
        gares = [
            {
                "id": gare.id,
                "nom": gare.nom,
                "ville": gare.ville,
                **_bilan(
                    departs_par_gare.get(gare.id, []), feuilles_par_gare.get(gare.id, []), maintenant
                ),
                **tension.get(gare.id, _TENSION_VIDE),
            }
            for gare in Gare.objects.filter(company=company)
        ]
        lignes = [
            {
                "id": ligne.id,
                "nom": ligne.nom,
                "gare_depart": ligne.gare_depart.nom,
                "gare_arrivee": ligne.gare_arrivee.nom,
                "est_fermee": ligne.est_fermee,
                "fermee_jusqu_au": ligne.fermee_jusqu_au,
                "motif_fermeture": ligne.motif_fermeture if ligne.est_fermee else "",
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
                "retard_minutes": retard_minutes(feuille, maintenant),
            }
            for feuille in feuilles
            if feuille.heure_depart_reelle is None
            and statut_ponctualite(feuille, maintenant) == "en_retard"
        ]

        feuilles_7_jours = FeuilleDeRoute.objects.filter(
            company=company,
            heure_depart_prevue__gte=maintenant - datetime.timedelta(days=7),
            heure_depart_prevue__lte=maintenant,
        )
        statuts_7_jours = [statut_ponctualite(feuille, maintenant) for feuille in feuilles_7_jours]
        ponctualite_7_jours = pourcentage(
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


class DashboardGareView(APIView):
    """« Santé de la gare » : ponctualité, remplissage, recettes (billets et fret) et incidents du jour, départs en retard,
    véhicules et équipe. Le chef de gare voit la sienne ; le directeur des opérations, le PDG et le secrétaire général,
    la gare indiquée par `?gare=`."""

    permission_classes = [IsAuthenticated, PeutVoirLaSanteDeLaGare]

    def get(self, request):
        user = request.user
        if user.role == Role.CHEF_GARE:
            gare = Gare.objects.filter(company=user.company, chef=user).first()
            if gare is None:
                raise NotFound("Aucune gare ne vous est rattachée.")
        else:
            brut = request.query_params.get("gare", "")
            gare = Gare.objects.filter(company=user.company, pk=int(brut)).first() if brut.isdigit() else None
            if gare is None:
                raise ValidationError({"gare": "Indiquez une gare de votre compagnie (?gare=)."})

        company = user.company
        maintenant = timezone.now()
        aujourdhui = timezone.localdate(maintenant)
        debut_jour, fin_jour = bornes_du_jour(maintenant)
        de_la_gare = {"company": company}

        departs = list(
            Depart.objects.filter(
                ligne__gare_depart=gare, date_heure__gte=debut_jour, date_heure__lt=fin_jour, **de_la_gare
            ).select_related("ligne", "vehicule")
        )
        feuilles = list(
            FeuilleDeRoute.objects.filter(
                depart__ligne__gare_depart=gare, heure_depart_prevue__gte=debut_jour, heure_depart_prevue__lt=fin_jour, **de_la_gare
            ).select_related("depart__ligne", "chauffeur")
        )
        statuts_7_jours = [
            statut_ponctualite(feuille, maintenant)
            for feuille in FeuilleDeRoute.objects.filter(
                depart__ligne__gare_depart=gare,
                heure_depart_prevue__gte=maintenant - datetime.timedelta(days=7),
                heure_depart_prevue__lte=maintenant,
                **de_la_gare,
            )
        ]

        billets = {"total": Decimal("0"), "nombre": 0, "par_mode": {}}
        for ligne in (
            Ticket.objects.filter(depart__ligne__gare_depart=gare, date_vente__date=aujourdhui, statut=StatutTicket.VALIDE, **de_la_gare)
            .values("mode_paiement")
            .annotate(total=Sum("prix"), nombre=Count("id"))
            .order_by()
        ):
            billets["par_mode"][ligne["mode_paiement"]] = ligne["total"]
            billets["total"] += ligne["total"]
            billets["nombre"] += ligne["nombre"]
        fret = Colis.objects.filter(
            depart__ligne__gare_depart=gare, enregistre_le__date=aujourdhui, **de_la_gare
        ).exclude(statut=StatutColis.ANNULE).aggregate(total=Sum("frais"), nombre=Count("id"))

        incidents = Incident.objects.filter(
            statut=StatutIncident.OUVERT, feuille_de_route__depart__ligne__gare_depart=gare, **de_la_gare
        )
        equipe = {}
        for role in AffectationGare.objects.filter(gare=gare).values_list("agent__role", flat=True):
            equipe[role] = equipe.get(role, 0) + 1

        return Response(
            {
                "gare": {"id": gare.id, "nom": gare.nom, "ville": gare.ville},
                "date": aujourdhui,
                "jour": _bilan(departs, feuilles, maintenant),
                "ponctualite_7_jours_pourcent": pourcentage(
                    statuts_7_jours.count("a_l_heure"), statuts_7_jours.count("a_l_heure") + statuts_7_jours.count("en_retard")
                ),
                "recettes": {
                    "billets": billets["total"],
                    "billets_par_mode": billets["par_mode"],
                    "nombre_de_billets": billets["nombre"],
                    "fret": fret["total"] or Decimal("0"),
                    "nombre_de_colis": fret["nombre"],
                    "total": billets["total"] + (fret["total"] or Decimal("0")),
                },
                "incidents_ouverts": {
                    "total": incidents.count(),
                    "graves": incidents.filter(gravite=GraviteIncident.GRAVE).count(),
                },
                "departs_en_retard": [
                    {
                        "depart": feuille.depart_id,
                        "ligne": feuille.depart.ligne.nom,
                        "chauffeur_nom": nom_complet(feuille.chauffeur),
                        "heure_depart_prevue": feuille.heure_depart_prevue,
                        "retard_minutes": retard_minutes(feuille, maintenant),
                    }
                    for feuille in feuilles
                    if feuille.heure_depart_reelle is None and statut_ponctualite(feuille, maintenant) == "en_retard"
                ],
                "vehicules": _tension_des_gares(company, maintenant).get(gare.id, _TENSION_VIDE),
                "equipe": {"total": sum(equipe.values()), "par_role": equipe},
            }
        )


class DashboardPlateformeView(APIView):
    """Vue de l'opérateur de la plateforme : une ligne par compagnie cliente."""

    permission_classes = [IsAuthenticated, IsSuperadmin]

    def get(self, request):
        maintenant = timezone.now()
        debut_jour, fin_jour = bornes_du_jour(maintenant)

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
            for ligne in Ticket.objects.filter(
                date_vente__gte=debut_jour, date_vente__lt=fin_jour, statut=StatutTicket.VALIDE
            )
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


class CarteReseauView(APIView):
    """Carte du réseau en temps réel : les gares avec leur statut du jour (vert, orange, rouge selon la ponctualité), les lignes
    qui les relient et les cars en route avec leur dernière position connue."""

    permission_classes = [IsAuthenticated, PeutVoirLaCarte]

    def get(self, request):
        from personnel_roulant import suivi

        company = request.user.company
        maintenant = timezone.now()
        debut_jour, fin_jour = bornes_du_jour(maintenant)
        feuilles = FeuilleDeRoute.objects.filter(
            company=company, heure_depart_prevue__gte=debut_jour, heure_depart_prevue__lt=fin_jour
        ).select_related("depart__ligne")
        statuts_par_gare = {}
        for feuille in feuilles:
            statuts_par_gare.setdefault(feuille.depart.ligne.gare_depart_id, []).append(statut_ponctualite(feuille, maintenant))

        gares = []
        for gare in Gare.objects.filter(company=company).order_by("nom"):
            statuts = statuts_par_gare.get(gare.id, [])
            a_l_heure, en_retard = statuts.count("a_l_heure"), statuts.count("en_retard")
            ponctualite = pourcentage(a_l_heure, a_l_heure + en_retard)
            gares.append(
                {
                    "id": gare.id,
                    "nom": gare.nom,
                    "ville": gare.ville,
                    "latitude": gare.latitude,
                    "longitude": gare.longitude,
                    "departs_du_jour": len(statuts),
                    "ponctualite_pourcent": ponctualite,
                    "couleur": couleur(ponctualite),
                }
            )
        lignes = [
            {"id": ligne.id, "nom": ligne.nom, "gare_depart": ligne.gare_depart_id, "gare_arrivee": ligne.gare_arrivee_id}
            for ligne in Ligne.objects.filter(company=company)
        ]
        return Response(
            {
                "mis_a_jour": maintenant,
                "gares": gares,
                "lignes": lignes,
                "vehicules": suivi.dernieres_positions(company.id, maintenant),
            }
        )
