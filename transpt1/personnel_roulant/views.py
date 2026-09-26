import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter, chef_de_gare_du_depart, chefs_de_gare_du_vehicule
from billetterie.models import DepartStatut
from colis import services as colis_services
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role
from core.permissions import IsSameCompany
from personnel_roulant.models import (
    BlocageSecurite,
    ChecklistDepart,
    ControleLigne,
    FeuilleDeRoute,
    ITEMS_REPRISE,
    GraviteIncident,
    Incident,
    PositionVehicule,
    Relais,
    ResultatVerification,
    TypeIncident,
)
from personnel_roulant.permissions import (
    CanControler,
    IsOwnChecklist,
    IsOwnFeuilleDeRoute,
    IsOwnIncident,
    IsQhseOrReadOnly,
    IsQhseOuDirecteurExploitation,
    IsRoulantManagerOrReadOnly,
    ROLES_SUIVI_TRAJETS,
)
from personnel_roulant.serializers import (
    BlocageSecuriteSerializer,
    ChecklistDepartSerializer,
    ControleLigneSerializer,
    FeuilleDeRouteSerializer,
    IncidentSerializer,
    PositionSerializer,
    RelaisSerializer,
)
from core.serializers import nom_complet
from personnel_roulant import carnet as carnet_service
from personnel_roulant import controle as controle_service
from personnel_roulant import suivi
from reseau.models import VehiculeStatut
from supports.services import ouvrir_sinistre_pour_incident

logger = logging.getLogger(__name__)


def _sans_echec(operation, depart):
    """Ce que le car déclenche chez les autres pôles (colis, alertes) ne doit jamais empêcher le chauffeur de partir ou
    d'arriver : un échec est journalisé, pas propagé."""
    try:
        operation(depart)
    except Exception:  # noqa: BLE001
        logger.exception("%s a échoué pour le départ %s", operation.__name__, depart.pk)


class PersonnelRoulantViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class FeuilleDeRouteViewSet(PersonnelRoulantViewSet):
    queryset = FeuilleDeRoute.objects.select_related(
        "depart", "depart__vehicule", "chauffeur", "company"
    )
    serializer_class = FeuilleDeRouteSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsRoulantManagerOrReadOnly, IsOwnFeuilleDeRoute]

    @action(detail=True, methods=["post"], url_path="demarrer")
    def demarrer(self, request, pk=None):
        feuille = self.get_object()

        if feuille.heure_depart_reelle is not None:
            raise ValidationError("Cette feuille de route a déjà démarré.")
        if feuille.depart.vehicule.statut == VehiculeStatut.BLOQUE_SECURITE:
            raise ValidationError(
                "Le véhicule est bloqué pour raison de sécurité : la feuille de route ne peut pas démarrer."
            )
        if not feuille.peut_demarrer:
            raise ValidationError(
                "Un défaut de sécurité est signalé sur la checklist : la feuille de route ne peut pas démarrer."
            )

        depart, vehicule = feuille.depart, feuille.depart.vehicule
        with transaction.atomic():
            feuille.heure_depart_reelle = timezone.now()
            feuille.save(update_fields=["heure_depart_reelle"])
            # Le départ est en cours et le car en ligne : c'est ce que voient les régulateurs et la
            # direction. Un véhicule bloqué ou en maintenance ne peut pas partir (refusé plus haut).
            if depart.statut == DepartStatut.PLANIFIE:
                depart.statut = DepartStatut.EN_COURS
                depart.save(update_fields=["statut"])
            if vehicule.statut == VehiculeStatut.DISPONIBLE:
                vehicule.statut = VehiculeStatut.EN_LIGNE
                vehicule.save(update_fields=["statut"])
        _sans_echec(colis_services.annoncer_restitution, depart)  # la gare d'arrivée sait ce qu'elle doit restituer
        return Response(self.get_serializer(feuille).data)

    @action(detail=True, methods=["post"], url_path="arriver")
    def arriver(self, request, pk=None):
        feuille = self.get_object()

        if feuille.heure_depart_reelle is None:
            raise ValidationError("Cette feuille de route n'a pas encore démarré.")
        if feuille.heure_arrivee_reelle is not None:
            raise ValidationError("Cette feuille de route est déjà arrivée.")

        depart, vehicule = feuille.depart, feuille.depart.vehicule
        with transaction.atomic():
            feuille.heure_arrivee_reelle = timezone.now()
            feuille.save(update_fields=["heure_arrivee_reelle"])
            depart.statut = DepartStatut.TERMINE
            depart.save(update_fields=["statut"])
            # Le car redevient disponible, sauf s'il est tombé en panne ou a été bloqué en route.
            if vehicule.statut == VehiculeStatut.EN_LIGNE:
                vehicule.statut = VehiculeStatut.DISPONIBLE
                vehicule.save(update_fields=["statut"])
        _sans_echec(colis_services.marquer_arrives, depart)  # colis arrivés : clients et gare d'arrivée prévenus
        return Response(self.get_serializer(feuille).data)

    # --- suivi du trajet en cours -----------------------------------------------------------------------------------

    @staticmethod
    def _verifier_conducteur(user, feuille):
        """Seul le conducteur du trajet agit dessus (pause, anomalie) : la supervision observe, elle ne conduit pas."""
        if user.role not in suivi.CHAUFFEURS or feuille.chauffeur_id != user.id:
            raise PermissionDenied("Seul le conducteur de ce trajet peut le faire.")

    @action(detail=True, methods=["get"], url_path="fatigue")
    def fatigue(self, request, pk=None):
        """Temps de conduite continue et alerte fatigue. Visible du conducteur, de la régulation et du QHSE ; l'alerte propose
        des conducteurs libres pour un relais."""
        feuille = self.get_object()
        user = request.user
        if not (
            (user.role in suivi.CHAUFFEURS and feuille.chauffeur_id == user.id)
            or user.role in ROLES_SUIVI_TRAJETS
        ):
            raise PermissionDenied("Le suivi de fatigue d'un conducteur n'est visible que de lui et de la régulation.")
        etat = suivi.etat_fatigue(feuille)
        if etat["alerte"]:
            etat["relais_suggeres"] = suivi.relais_suggeres(feuille)
        return Response(etat)

    @action(detail=True, methods=["post"], url_path="pause")
    def pause(self, request, pk=None):
        """`{"action": "debut"}` commence une pause, `{"action": "fin"}` la termine : elle remet à zéro le temps de conduite."""
        feuille = self.get_object()
        self._verifier_conducteur(request.user, feuille)
        if feuille.heure_depart_reelle is None or feuille.heure_arrivee_reelle is not None:
            raise ValidationError("Ce trajet n'est pas en cours.")
        choix = request.data.get("action")
        if choix == "debut":
            suivi.commencer_pause(feuille, request.user)
        elif choix == "fin":
            suivi.terminer_pause(feuille)
        else:
            raise ValidationError({"action": "« debut » ou « fin »."})
        return Response(suivi.etat_fatigue(feuille))

    @action(detail=True, methods=["post"], url_path="relais")
    def relais(self, request, pk=None):
        """Transfère le trajet en cours à un autre conducteur : `{"relais": <id du conducteur>, "lieu": "…"}`. Fait par le
        conducteur actuel ou par la régulation. La feuille de route et l'état du véhicule passent au nouveau conducteur, qui
        est prévenu avec la régulation et les gares ; le suivi GPS et l'alerte fatigue continuent sur lui."""
        feuille = self.get_object()
        user = request.user
        if not (
            (user.role in suivi.CHAUFFEURS and feuille.chauffeur_id == user.id) or user.role in ROLES_SUIVI_TRAJETS - {Role.QHSE, Role.DIRECTEUR_TECHNIQUE}
        ):
            raise PermissionDenied("Seul le conducteur du trajet ou la régulation organise un relais.")
        try:
            nouveau = get_user_model().objects.get(pk=int(request.data.get("relais")), company_id=feuille.company_id)
        except (TypeError, ValueError, get_user_model().DoesNotExist):
            raise ValidationError({"relais": "Indiquez le conducteur qui reprend le trajet."})
        relais = suivi.effectuer_relais(feuille, nouveau, request.data.get("lieu"), user)
        return Response(
            {
                "id": relais.id,
                "lieu": relais.lieu,
                "effectue_le": relais.effectue_le,
                "ancien_chauffeur": relais.ancien_chauffeur_id,
                "nouveau_chauffeur": relais.nouveau_chauffeur_id,
                "etat_vehicule": relais.etat_vehicule,
                "feuille_de_route": self.get_serializer(feuille).data,
            },
            status=201,
        )

    @action(detail=True, methods=["post"], url_path="anomalie-cargaison")
    def anomalie_cargaison(self, request, pk=None):
        """Mode surveillance de la cargaison (convoyeur) : signale une anomalie (colis déplacé, soute ouverte, odeur...). Elle
        devient un incident grave, la régulation, la direction et le QHSE en sont alertés aussitôt."""
        feuille = self.get_object()
        user = request.user
        if not (user.role in suivi.CHAUFFEURS and feuille.chauffeur_id == user.id) and user.role != Role.CONTROLEUR_LIGNE:
            raise PermissionDenied("Seul le convoyeur ou le contrôleur signale une anomalie de cargaison.")
        description = str(request.data.get("description", "")).strip()
        if len(description) < 5:
            raise ValidationError({"description": "Décrivez l'anomalie constatée (5 caractères au moins)."})
        position = suivi.derniere_position_recente(feuille.depart.vehicule_id)
        incident = Incident.objects.create(
            feuille_de_route=feuille, vehicule=feuille.depart.vehicule, chauffeur=feuille.chauffeur, company=feuille.company,
            type_incident=TypeIncident.CARGAISON, description=description, gravite=GraviteIncident.GRAVE,
            latitude=position.latitude if position else None, longitude=position.longitude if position else None,
        )
        IncidentViewSet._alerter(incident)
        return Response({"incident": incident.id, "gravite": incident.gravite}, status=201)


class ChecklistDepartViewSet(PersonnelRoulantViewSet):
    queryset = ChecklistDepart.objects.select_related("feuille_de_route", "company")
    serializer_class = ChecklistDepartSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsRoulantManagerOrReadOnly, IsOwnChecklist]

    def create(self, request, *args, **kwargs):
        """Un item est unique par feuille de route : le renvoyer met à jour l'existant.

        Sans cela, un défaut de sécurité serait permanent : `FeuilleDeRoute.peut_demarrer` refuse tant
        qu'il existe un défaut sur la feuille, et refaire la checklist après la réparation ne
        ferait qu'ajouter des items « OK » à côté du défaut. Les contrôles (compagnie, feuille du
        chauffeur) sont ceux du sérialiseur, exécutés avant.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data
        existant = ChecklistDepart.objects.filter(
            feuille_de_route=donnees["feuille_de_route"], item__iexact=donnees["item"].strip()
        ).first()
        if existant is None:
            return super().create(request, *args, **kwargs)

        existant.etat = donnees["etat"]
        existant.commentaire = donnees.get("commentaire", "")
        existant.save()  # un défaut de sécurité rebloque le véhicule (ChecklistDepart.save)
        return Response(self.get_serializer(existant).data, status=200)


class IncidentViewSet(PersonnelRoulantViewSet):
    queryset = Incident.objects.select_related("feuille_de_route", "vehicule", "chauffeur", "company")
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsRoulantManagerOrReadOnly, IsOwnIncident]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._geolocaliser(serializer.instance)
        self._alerter(serializer.instance)
        self._ouvrir_le_sinistre(serializer.instance)

    @staticmethod
    def _ouvrir_le_sinistre(incident):
        """Un accident ouvre le dossier de sinistre du juridique ; un échec ne doit jamais empêcher de déclarer l'incident."""
        try:
            ouvrir_sinistre_pour_incident(incident)
        except Exception:  # noqa: BLE001
            logger.exception("Impossible d'ouvrir le sinistre de l'incident %s", incident.pk)

    @staticmethod
    def _geolocaliser(incident):
        """Géolocalisation automatique : sans position donnée par l'appareil du chauffeur, on prend la dernière connue du car
        (relevée dans les 15 dernières minutes) : où qu'il soit, le signalement dit où il est."""
        if incident.latitude is not None and incident.longitude is not None:
            return
        position = suivi.derniere_position_recente(incident.vehicule_id)
        if position is not None:
            incident.latitude, incident.longitude = position.latitude, position.longitude
            incident.save(update_fields=["latitude", "longitude"])

    def perform_update(self, serializer):
        etait_grave = serializer.instance.gravite == GraviteIncident.GRAVE
        etait_accident = serializer.instance.type_incident == TypeIncident.ACCIDENT
        super().perform_update(serializer)
        if not etait_accident:
            self._ouvrir_le_sinistre(serializer.instance)  # un incident requalifié en accident ouvre lui aussi son dossier
        # Un incident requalifié en « grave » prévient les mêmes pôles qu'un incident déclaré grave d'emblée.
        if not etait_grave and serializer.instance.gravite == GraviteIncident.GRAVE:
            self._alerter(serializer.instance)

    @staticmethod
    def _alerter(incident):
        """Un incident concerne la régulation et le technique ; un incident grave, aussi la direction, le QHSE et la
        gare (« alerte au chef de ligne et au technique », puis remontée à la direction si c'est grave)."""
        grave = incident.gravite == GraviteIncident.GRAVE
        roles = {Role.CHEF_LIGNE}
        if incident.type_incident in (TypeIncident.PANNE, TypeIncident.ACCIDENT):
            roles |= {Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER}
        destinataires = []
        if grave:
            roles |= {Role.DIRECTEUR_EXPLOITATION, Role.QHSE}
            feuille = incident.feuille_de_route
            if feuille is not None:
                destinataires.append(chef_de_gare_du_depart(feuille.depart))
        alerter(
            incident.company,
            type=TypeAlerte.INCIDENT,
            gravite={"grave": GraviteAlerte.CRITIQUE, "moyenne": GraviteAlerte.ATTENTION}.get(
                incident.gravite, GraviteAlerte.INFO
            ),
            titre=f"{'Incident grave' if grave else 'Incident'} : {incident.get_type_incident_display().lower()} "
            f"— {incident.vehicule.immatriculation}",
            message=incident.description,
            roles=roles,
            destinataires=destinataires,
            objet=incident,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="graves",
        permission_classes=[IsAuthenticated, IsSameCompany, IsQhseOuDirecteurExploitation],
    )
    def graves(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(gravite=GraviteIncident.GRAVE)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BlocageSecuriteViewSet(PersonnelRoulantViewSet):
    """Le QHSE bloque le départ d'un véhicule en défaut de sécurité (et le libère) ; le chef de gare concerné, le
    chef d'atelier et la régulation en sont prévenus aussitôt. Ni modification ni suppression : l'historique est
    conservé (le journal d'audit aussi)."""

    queryset = BlocageSecurite.objects.select_related("vehicule", "pose_par", "company")
    serializer_class = BlocageSecuriteSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsQhseOrReadOnly]
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas bloquer un véhicule.")
        with transaction.atomic():
            blocage = serializer.save(company=user.company, pose_par=user)
            vehicule = blocage.vehicule
            vehicule.statut = VehiculeStatut.BLOQUE_SECURITE
            vehicule.save(update_fields=["statut"])
        alerter(
            user.company,
            type=TypeAlerte.BLOCAGE_SECURITE,
            gravite=GraviteAlerte.CRITIQUE,
            titre=f"Départ bloqué par le QHSE : {vehicule.immatriculation}",
            message=f"Motif : {blocage.motif}. Le véhicule ne peut plus partir tant que le QHSE ne lève pas le blocage.",
            roles=[Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE, Role.CHEF_LIGNE],
            destinataires=chefs_de_gare_du_vehicule(vehicule),
            objet=blocage,
            cree_par=user,
        )

    @action(detail=True, methods=["post"], url_path="lever")
    def lever(self, request, pk=None):
        motif = str(request.data.get("motif", "")).strip()
        if len(motif) < 5:
            raise ValidationError({"motif": "Indiquez pourquoi le blocage est levé (5 caractères au moins)."})
        blocage = self.get_object()
        with transaction.atomic():
            blocage = BlocageSecurite.objects.select_for_update().select_related("vehicule").get(pk=blocage.pk)
            if not blocage.est_actif:
                raise ValidationError("Ce blocage est déjà levé.")
            blocage.leve_par = request.user
            blocage.leve_le = timezone.now()
            blocage.motif_levee = motif[:255]
            blocage.save(update_fields=["leve_par", "leve_le", "motif_levee"])
            vehicule = blocage.vehicule
            # Un car passé à l'atelier entre-temps (ordre de réparation) reste immobilisé : seul l'atelier le libère.
            if vehicule.statut == VehiculeStatut.BLOQUE_SECURITE:
                vehicule.statut = VehiculeStatut.DISPONIBLE
                vehicule.save(update_fields=["statut"])
        alerter(
            request.user.company,
            type=TypeAlerte.VEHICULE_LIBERE,
            gravite=GraviteAlerte.INFO,
            titre=f"Blocage levé : {vehicule.immatriculation}",
            message=f"Levé par le QHSE : {blocage.motif_levee}",
            roles=[Role.CHEF_ATELIER, Role.CHEF_LIGNE],
            destinataires=chefs_de_gare_du_vehicule(vehicule),
            objet=blocage,
            cree_par=request.user,
        )
        return Response(self.get_serializer(blocage).data)


MAX_POSITIONS_PAR_ENVOI = 500


class PositionViewSet(viewsets.GenericViewSet):
    """Positions GPS des cars en route. Le conducteur envoie la sienne (une ou plusieurs à la fois : un lot après une zone
    sans réseau) ; la régulation, la direction, le QHSE et le technique voient la dernière position de chaque car."""

    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]
    queryset = PositionVehicule.objects.none()

    def create(self, request):
        user = request.user
        if user.role not in suivi.CHAUFFEURS:
            raise PermissionDenied("Seul un conducteur envoie sa position.")
        donnees = request.data if isinstance(request.data, list) else [request.data]
        if not donnees or len(donnees) > MAX_POSITIONS_PAR_ENVOI:
            raise ValidationError(f"Envoyez entre 1 et {MAX_POSITIONS_PAR_ENVOI} positions à la fois.")
        serializer = self.get_serializer(data=donnees, many=True)
        serializer.is_valid(raise_exception=True)
        trajet = suivi.trajet_en_cours_de(user)
        if trajet is None:
            raise ValidationError("Aucun trajet en cours : démarrez votre feuille de route avant d'envoyer des positions.")
        objets = [
            PositionVehicule(
                company=trajet.company, vehicule=trajet.depart.vehicule, feuille_de_route=trajet, releve_par=user, **valeurs
            )
            for valeurs in serializer.validated_data
        ]
        PositionVehicule.objects.bulk_create(objets)
        # La carte n'a besoin que de la plus récente (un envoi différé après une zone sans réseau peut
        # contenir des relevés plus anciens que la dernière position déjà affichée) : voir `_ligne_carte`.
        suivi.diffuser_position(trajet, max(objets, key=lambda position: position.releve_le))
        return Response({"enregistrees": len(donnees)}, status=201)

    @action(detail=False, methods=["get"], url_path="dernieres")
    def dernieres(self, request):
        if request.user.role not in ROLES_SUIVI_TRAJETS or request.user.company_id is None:
            raise PermissionDenied("La position des cars est réservée à la régulation, à la direction, au QHSE et au technique.")
        return Response(suivi.dernieres_positions(request.user.company_id))


class MonTrajetView(APIView):
    """Le trajet que mène l'utilisateur connecté, avec son temps de conduite et, si l'alerte est déclenchée, des relais
    possibles. Pour qui ne conduit pas, ou ne roule pas en ce moment : `en_cours` est faux (ce n'est pas une erreur)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        trajet = suivi.trajet_en_cours_de(user) if user.role in suivi.CHAUFFEURS and user.company_id else None
        if trajet is None:
            return Response({"en_cours": False})
        etat = suivi.etat_fatigue(trajet)
        if etat["alerte"]:
            etat["relais_suggeres"] = suivi.relais_suggeres(trajet)
        reprise = suivi.reprise_a_faire(user)
        return Response(
            {
                "en_cours": True, "feuille_de_route": trajet.pk, "ligne": trajet.depart.ligne.nom, "fatigue": etat,
                # Le conducteur qui vient de reprendre le trajet doit encore constater l'état du car (checklist de reprise).
                "reprise_a_faire": None if reprise is None else {
                    "relais": reprise.pk, "lieu": reprise.lieu, "effectue_le": reprise.effectue_le, "items": list(ITEMS_REPRISE),
                    "etat_transmis": reprise.etat_vehicule,
                },
            }
        )


class RelaisViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, CompanyScopedQuerysetMixin, viewsets.GenericViewSet):
    """Les relais de conducteur, avec la checklist de reprise du nouveau conducteur (`?feuille=`). Un conducteur voit ceux qu'il a cédés
    ou pris ; la régulation, la direction et le QHSE voient tous ceux de la compagnie. Le nouveau conducteur constate l'état du car par
    `POST /{id}/reprise/`."""

    queryset = Relais.objects.select_related(
        "ancien_chauffeur", "nouveau_chauffeur", "feuille_de_route__depart__ligne", "feuille_de_route__depart__vehicule"
    ).prefetch_related("checklist_reprise")
    serializer_class = RelaisSerializer
    permission_classes = [IsAuthenticated, IsSameCompany]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.company_id is None:
            return queryset.none()
        if user.role in suivi.CHAUFFEURS:
            queryset = queryset.filter(Q(ancien_chauffeur=user) | Q(nouveau_chauffeur=user))
        elif user.role not in ROLES_SUIVI_TRAJETS:
            return queryset.none()
        if self.request.query_params.get("feuille", "").isdigit():
            queryset = queryset.filter(feuille_de_route_id=int(self.request.query_params["feuille"]))
        return queryset

    @action(detail=True, methods=["post"], url_path="reprise")
    def reprise(self, request, pk=None):
        """Le nouveau conducteur constate l'état du car : `{"items": [{"item": "pneus", "etat": "ok"|"defaut", "commentaire": "…"}, …]}`."""
        relais = self.get_object()
        if relais.nouveau_chauffeur_id != request.user.id:
            raise PermissionDenied("Seul le conducteur qui reprend le trajet constate l'état du car.")
        suivi.enregistrer_reprise(relais, request.data.get("items"))
        # Relu après l'écriture : l'objet d'origine porte encore la checklist (vide) préchargée avant l'enregistrement.
        return Response(self.get_serializer(self.get_queryset().get(pk=relais.pk)).data, status=201)


class ControleLigneViewSet(
    CompanyScopedQuerysetMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Contrôle à bord (contrôleur de ligne) : ouvrir un contrôle sur un trajet, vérifier les billets un à un (un billet ne
    sert qu'une fois), clôturer avec les constats (voyageurs, charge) et obtenir le rapport. L'historique se filtre par ligne
    (`?ligne=`) et par chauffeur (`?chauffeur=`)."""

    queryset = ControleLigne.objects.select_related(
        "controleur", "feuille_de_route__depart__ligne", "feuille_de_route__depart__vehicule", "feuille_de_route__chauffeur"
    )
    serializer_class = ControleLigneSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, CanControler]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == Role.CONTROLEUR_LIGNE:  # chacun ses contrôles ; la supervision voit ceux de la compagnie
            queryset = queryset.filter(controleur=user)
        parametres = self.request.query_params
        if parametres.get("ligne", "").isdigit():
            queryset = queryset.filter(feuille_de_route__depart__ligne_id=int(parametres["ligne"]))
        if parametres.get("chauffeur", "").isdigit():
            queryset = queryset.filter(feuille_de_route__chauffeur_id=int(parametres["chauffeur"]))
        if parametres.get("ouvert") == "1":
            queryset = queryset.filter(cloture_le__isnull=True)
        if parametres.get("infraction") == "1":
            queryset = queryset.filter(infraction_grave=True)
        return queryset.annotate(_nombre_verifications=Count("verifications"))

    def create(self, request, *args, **kwargs):
        """Ouvre un contrôle sur un trajet. Un contrôle déjà ouvert par ce contrôleur sur le même trajet est repris (pas de
        doublon si l'on rouvre l'écran)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feuille = serializer.validated_data["feuille_de_route"]
        existant = ControleLigne.objects.filter(
            feuille_de_route=feuille, controleur=request.user, cloture_le__isnull=True
        ).first()
        if existant is not None:
            return Response(self.get_serializer(existant).data, status=200)
        controle = ControleLigne.objects.create(
            company=request.user.company, controleur=request.user, feuille_de_route=feuille
        )
        return Response(self.get_serializer(controle).data, status=201)

    def _controle_du_controleur(self):
        controle = self.get_object()
        if controle.controleur_id != self.request.user.id:
            raise PermissionDenied("Ce contrôle est celui d'un autre contrôleur.")
        return controle

    @action(detail=True, methods=["post"], url_path="verifier")
    def verifier(self, request, pk=None):
        """Vérifie un billet (`{"code": "…"}`, saisi ou lu par un lecteur de code) : valide, déjà utilisé, annulé, inconnu, ou
        d'un autre départ. Un billet valide est marqué utilisé."""
        controle = self._controle_du_controleur()
        verification, ticket = controle_service.verifier_ticket(controle, request.data.get("code"))
        reponse = {
            "resultat": verification.resultat,
            "valide": verification.resultat == ResultatVerification.VALIDE,
            "message": controle_service.MESSAGES[verification.resultat],
            "code": verification.code,
            "verifie_le": verification.verifie_le,
        }
        if ticket is not None:
            reponse["ticket"] = {
                "id": ticket.id,
                "passager_nom": ticket.passager_nom,
                "depart": ticket.depart_id,
                "utilise_le": ticket.utilise_le,
                "utilise_par_nom": nom_complet(ticket.utilise_par) if ticket.utilise_par else None,
            }
        return Response(reponse, status=200)

    @action(detail=True, methods=["get"], url_path="rapport")
    def rapport(self, request, pk=None):
        """Le rapport du contrôle, généré en un geste : celui de la clôture, ou un aperçu en direct tant qu'il est ouvert."""
        controle = self.get_object()
        if not controle.est_ouvert:
            return Response(controle.rapport)
        return Response(json.loads(json.dumps(controle_service.generer_rapport(controle), cls=DjangoJSONEncoder)))

    @action(detail=True, methods=["post"], url_path="cloturer")
    def cloturer(self, request, pk=None):
        """Clôture le contrôle avec les constats : `passagers_constates`, `charge_constatee_kg`, `commentaire`,
        `infraction_grave` (+ `motif_infraction`). Génère le rapport ; une infraction grave alerte directement la direction
        et le QHSE."""
        controle = self._controle_du_controleur()
        donnees = request.data

        def nombre(champ, type_):
            valeur = donnees.get(champ)
            if valeur in (None, ""):
                return None
            try:
                resultat = type_(str(valeur))
            except (ValueError, InvalidOperation):
                raise ValidationError({champ: "Nombre attendu."})
            if resultat < 0:
                raise ValidationError({champ: "Ne peut pas être négatif."})
            return resultat

        controle_service.cloturer(
            controle,
            passagers_constates=nombre("passagers_constates", int),
            charge_constatee_kg=nombre("charge_constatee_kg", Decimal),
            commentaire=str(donnees.get("commentaire", "")).strip(),
            infraction_grave=bool(donnees.get("infraction_grave")),
            motif=str(donnees.get("motif_infraction", "")).strip(),
        )
        return Response(self.get_serializer(controle).data)


class CarnetDeRouteView(APIView):
    """Le carnet de route numérique du conducteur connecté : ses trajets récents et les documents du véhicule qu'il conduit."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role not in suivi.CHAUFFEURS or user.company_id is None:
            raise PermissionDenied("Le carnet de route est celui des conducteurs.")
        return Response(carnet_service.carnet_de_route(user))
