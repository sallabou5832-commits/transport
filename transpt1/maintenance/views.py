from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role, User
from core.permissions import IsSameCompany
from core.serializers import nom_complet
from maintenance import analyses, preventif, stock
from maintenance.models import (
    DemandePiece,
    OrdreReparation,
    Piece,
    PlanEntretien,
    SortiePiece,
    StatutDemandePiece,
    StatutOrdreReparation,
    UrgenceReparation,
)
from maintenance.permissions import (
    CanCreateOrdreReparation,
    CanManageOrdreReparation,
    CanManagePiece,
    CanManageStockMovement,
    PeutGererLesPlans,
    PeutPiloterLAtelier,
    PeutServirLesDemandes,
    PeutUtiliserLesDemandesDePieces,
    PeutVoirLaFicheVehicule,
    PeutVoirLeBesoinDeRenouvellement,
    PeutVoirLesSuggestionsDeCommande,
)
from maintenance.serializers import (
    ROLES_INTERVENANTS,
    DemandePieceSerializer,
    OrdreReparationSerializer,
    PieceSerializer,
    PlanEntretienSerializer,
    SortiePieceSerializer,
)
from reseau.models import Vehicule


class MaintenanceViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class PieceViewSet(MaintenanceViewSet):
    queryset = Piece.objects.select_related("company")
    serializer_class = PieceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, CanManagePiece]

    @action(detail=False, methods=["get"], url_path="sous-seuil")
    def sous_seuil(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            quantite_stock__lte=F("seuil_alerte")
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="suggestions-commande",
        permission_classes=[IsAuthenticated, IsSameCompany, PeutVoirLesSuggestionsDeCommande],
    )
    def suggestions_commande(self, request):
        """Les pièces à commander d'après la consommation habituelle (90 derniers jours) : sous le seuil d'alerte, ou à moins
        d'un mois de la rupture. La quantité suggérée couvre deux mois et reconstitue le stock de sécurité."""
        return Response(analyses.suggestions_commande(request.user.company))


class OrdreReparationViewSet(MaintenanceViewSet):
    queryset = OrdreReparation.objects.select_related("vehicule", "mecanicien", "company")
    serializer_class = OrdreReparationSerializer
    permission_classes = [
        IsAuthenticated,
        IsSameCompany,
        CanCreateOrdreReparation,
        CanManageOrdreReparation,
    ]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        ordre = serializer.instance
        alerter(
            ordre.company,
            type=TypeAlerte.ORDRE_REPARATION,
            gravite=GraviteAlerte.ATTENTION if ordre.urgence in (UrgenceReparation.CRITIQUE, UrgenceReparation.HAUTE) else GraviteAlerte.INFO,
            titre=f"Nouvel ordre de réparation : {ordre.vehicule.immatriculation}",
            message=f"{ordre.description} (urgence {ordre.get_urgence_display().lower()}).",
            destinataires=[ordre.mecanicien],
            objet=ordre,
            cree_par=self.request.user,
        )

    @action(detail=False, methods=["get"], url_path="file-attente", permission_classes=[IsAuthenticated, IsSameCompany])
    def file_attente(self, request):
        """La file d'attente de l'atelier : les réparations à faire, la plus urgente d'abord (puis la position choisie par le
        directeur technique, puis l'ancienneté). Chaque ordre porte son retour estimé, pour la régulation."""
        return Response(self.get_serializer(analyses.file_attente(request.user.company) if request.user.company_id else [], many=True).data)

    @action(
        detail=False, methods=["post"], url_path="reordonner", permission_classes=[IsAuthenticated, IsSameCompany, PeutPiloterLAtelier]
    )
    def reordonner(self, request):
        """Valide ou réordonne la file (`ordres` : la liste des identifiants dans l'ordre voulu). À urgence égale, la position
        posée passe avant l'ancienneté ; l'urgence, elle, prime toujours (pour passer devant, on l'élève)."""
        ids = request.data.get("ordres")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            raise ValidationError({"ordres": "Donnez la liste des identifiants d'ordres, dans l'ordre voulu."})
        if len(set(ids)) != len(ids):
            raise ValidationError({"ordres": "Un ordre ne figure qu'une fois."})
        ordres = {
            o.pk: o
            for o in OrdreReparation.objects.filter(
                company=request.user.company, pk__in=ids, statut__in=analyses.EN_ATTENTE_OU_EN_COURS
            )
        }
        if len(ordres) != len(ids):
            raise ValidationError({"ordres": "Ordre inconnu, ou déjà terminé."})
        with transaction.atomic():
            for position, pk in enumerate(ids, start=1):
                ordre = ordres[pk]
                if ordre.position != position:
                    ordre.position = position
                    ordre.save(update_fields=["position"])
        return Response(self.get_serializer(analyses.file_attente(request.user.company), many=True).data)

    @action(detail=True, methods=["post"], url_path="prioriser", permission_classes=[IsAuthenticated, IsSameCompany, PeutPiloterLAtelier])
    def prioriser(self, request, pk=None):
        """Fixe l'urgence (`urgence`) et/ou le délai estimé en heures (`delai_estime_heures`, remonté au régulateur)."""
        ordre = self.get_object()
        if ordre.statut == StatutOrdreReparation.TERMINE:
            raise ValidationError("Cet ordre est terminé.")
        urgence, delai = request.data.get("urgence"), request.data.get("delai_estime_heures")
        if urgence is None and delai is None:
            raise ValidationError("Indiquez l'urgence et/ou le délai estimé.")
        if urgence is not None:
            if urgence not in UrgenceReparation.values:
                raise ValidationError({"urgence": f"Urgences possibles : {', '.join(UrgenceReparation.values)}."})
        if delai is not None:
            try:
                delai = int(delai)
            except (TypeError, ValueError):
                raise ValidationError({"delai_estime_heures": "Nombre d'heures attendu."})
            if delai < 1:
                raise ValidationError({"delai_estime_heures": "Au moins une heure."})
        devenue_critique = urgence == UrgenceReparation.CRITIQUE and ordre.urgence != UrgenceReparation.CRITIQUE
        if urgence is not None:
            ordre.urgence = urgence
        if delai is not None:
            ordre.delai_estime_heures = delai
        ordre.save(update_fields=[c for c, v in (("urgence", urgence), ("delai_estime_heures", delai)) if v is not None])
        if devenue_critique:
            alerter(
                ordre.company,
                type=TypeAlerte.ORDRE_REPARATION,
                gravite=GraviteAlerte.CRITIQUE,
                titre=f"Réparation critique : {ordre.vehicule.immatriculation}",
                message=f"{ordre.description}. À traiter en premier.",
                roles=[Role.CHEF_ATELIER, Role.CHEF_LIGNE],
                destinataires=[ordre.mecanicien],
                objet=ordre,
                cree_par=request.user,
            )
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=["post"], url_path="reaffecter", permission_classes=[IsAuthenticated, IsSameCompany, PeutPiloterLAtelier])
    def reaffecter(self, request, pk=None):
        """Confie l'ordre à un autre intervenant (`mecanicien`) : la répartition des interventions, avec la vue de charge."""
        ordre = self.get_object()
        if ordre.statut == StatutOrdreReparation.TERMINE:
            raise ValidationError("Cet ordre est terminé.")
        brut = str(request.data.get("mecanicien", "")).strip()
        nouveau = User.objects.filter(pk=int(brut), company=request.user.company, is_active=True).first() if brut.isdigit() else None
        if nouveau is None or nouveau.role not in ROLES_INTERVENANTS:
            raise ValidationError({"mecanicien": "Choisissez un mécanicien (ou le chef d'atelier) de votre compagnie."})
        if nouveau.pk == ordre.mecanicien_id:
            raise ValidationError({"mecanicien": "Cet ordre est déjà confié à cet intervenant."})
        ancien = ordre.mecanicien
        ordre.mecanicien = nouveau
        ordre.save(update_fields=["mecanicien"])
        alerter(
            ordre.company,
            type=TypeAlerte.ORDRE_REPARATION,
            gravite=GraviteAlerte.INFO,
            titre=f"Ordre de réparation confié : {ordre.vehicule.immatriculation}",
            message=f"{ordre.description}. Confié à {nom_complet(nouveau)} (avant : {nom_complet(ancien)}).",
            destinataires=[nouveau, ancien],
            objet=ordre,
            cree_par=request.user,
        )
        return Response(self.get_serializer(ordre).data)


class SortiePieceViewSet(MaintenanceViewSet):
    queryset = SortiePiece.objects.select_related("ordre_reparation", "piece", "company")
    serializer_class = SortiePieceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, CanManageStockMovement]

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.instance = stock.sortir_piece(
            ordre=serializer.validated_data["ordre_reparation"],
            piece=serializer.validated_data["piece"],
            quantite=serializer.validated_data["quantite"],
            company=user.company,
            auteur=user,
        )


class PlanEntretienViewSet(MaintenanceViewSet):
    """Les plans d'entretien préventif des véhicules. Lecture pour tous ; les déclarer, les modifier ou les retirer : le technique."""

    queryset = PlanEntretien.objects.select_related("vehicule", "company")
    serializer_class = PlanEntretienSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutGererLesPlans]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("vehicule", "").isdigit():
            queryset = queryset.filter(vehicule_id=int(self.request.query_params["vehicule"]))
        return queryset

    @action(detail=False, methods=["get"], url_path="echeances")
    def echeances(self, request):
        """Les plans actifs par échéance : les entretiens en retard d'abord, puis ceux qui approchent."""
        if request.user.company_id is None:
            return Response([])
        plans = [plan for plan, _ in preventif.plans_par_echeance(request.user.company)]
        return Response(self.get_serializer(plans, many=True).data)

    @action(detail=True, methods=["post"], url_path="realise")
    def realise(self, request, pk=None):
        """Note qu'un entretien a été fait hors ordre de réparation (`date` et `km` facultatifs : aujourd'hui, kilométrage actuel)."""
        plan = self.get_object()
        brut = request.data.get("date")
        date = None
        if brut not in (None, ""):
            date = parse_date(str(brut))
            if date is None or date > timezone.localdate():
                raise ValidationError({"date": "Date passée attendue (AAAA-MM-JJ)."})
        km = request.data.get("km")
        if km not in (None, ""):
            if not str(km).isdigit():
                raise ValidationError({"km": "Kilométrage attendu."})
            km = int(km)
        else:
            km = None
        preventif.renouveler(plan, date=date, km=km)
        return Response(self.get_serializer(plan).data)


class DemandePieceViewSet(
    CompanyScopedQuerysetMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Demandes de pièces de l'atelier au magasinier. Le mécanicien voit les siennes ; le magasinier, le chef d'atelier et le
    directeur technique, toutes. Le magasinier les sert (la sortie est enregistrée sur l'ordre, le stock baisse) ou les refuse."""

    queryset = DemandePiece.objects.select_related("ordre_reparation__vehicule", "piece", "demandeur", "traitee_par")
    serializer_class = DemandePieceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutUtiliserLesDemandesDePieces]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == Role.MECANICIEN:
            queryset = queryset.filter(demandeur=self.request.user)
        statut = self.request.query_params.get("statut")
        if statut in StatutDemandePiece.values:
            queryset = queryset.filter(statut=statut)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        piece, quantite = serializer.validated_data["piece"], serializer.validated_data["quantite"]
        demande = serializer.save(company=user.company, demandeur=user, disponible_a_la_demande=piece.quantite_stock >= quantite)
        alerter(
            demande.company,
            type=TypeAlerte.DEMANDE_PIECE,
            gravite=GraviteAlerte.INFO if demande.disponible_a_la_demande else GraviteAlerte.ATTENTION,
            titre=f"Demande de pièce : {quantite} x {piece.nom}",
            message=(
                f"Pour l'ordre {demande.ordre_reparation_id} ({demande.ordre_reparation.vehicule.immatriculation}), par {nom_complet(user)}. "
                + (f"En stock : {piece.quantite_stock}." if demande.disponible_a_la_demande else f"Stock insuffisant ({piece.quantite_stock} en stock).")
            ),
            roles=[Role.MAGASINIER],
            objet=demande,
            cree_par=user,
        )

    def _demande_en_attente(self):
        demande = self.get_object()
        if demande.statut != StatutDemandePiece.DEMANDEE:
            raise ValidationError("Cette demande a déjà été traitée.")
        return demande

    def _informer(self, demande, *, titre, message, gravite):
        alerter(
            demande.company,
            type=TypeAlerte.DEMANDE_PIECE,
            gravite=gravite,
            titre=titre,
            message=message,
            destinataires=[demande.demandeur],
            objet=demande,
            cree_par=self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="servir", permission_classes=[IsAuthenticated, IsSameCompany, PeutServirLesDemandes])
    def servir(self, request, pk=None):
        """Le magasinier sert la demande : la sortie de pièce est enregistrée sur l'ordre de réparation et le stock baisse."""
        demande = self._demande_en_attente()
        with transaction.atomic():
            sortie = stock.sortir_piece(
                ordre=demande.ordre_reparation, piece=demande.piece, quantite=demande.quantite, company=demande.company, auteur=request.user
            )
            demande.statut, demande.sortie = StatutDemandePiece.SERVIE, sortie
            demande.traitee_par, demande.traitee_le = request.user, timezone.now()
            demande.save(update_fields=["statut", "sortie", "traitee_par", "traitee_le"])
        self._informer(
            demande,
            titre=f"Pièce servie : {demande.quantite} x {demande.piece.nom}",
            message=f"Pour l'ordre {demande.ordre_reparation_id}, servie par {nom_complet(request.user)}.",
            gravite=GraviteAlerte.INFO,
        )
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=["post"], url_path="refuser", permission_classes=[IsAuthenticated, IsSameCompany, PeutServirLesDemandes])
    def refuser(self, request, pk=None):
        """Le magasinier ne peut pas servir (rupture, commande en cours…) : `commentaire` obligatoire, le demandeur est prévenu."""
        demande = self._demande_en_attente()
        commentaire = str(request.data.get("commentaire", "")).strip()[:255]
        if len(commentaire) < 3:
            raise ValidationError({"commentaire": "Dites pourquoi la pièce n'est pas disponible."})
        demande.statut, demande.commentaire = StatutDemandePiece.REFUSEE, commentaire
        demande.traitee_par, demande.traitee_le = request.user, timezone.now()
        demande.save(update_fields=["statut", "commentaire", "traitee_par", "traitee_le"])
        self._informer(
            demande,
            titre=f"Pièce indisponible : {demande.piece.nom}",
            message=f"{commentaire}. Ordre {demande.ordre_reparation_id}.",
            gravite=GraviteAlerte.ATTENTION,
        )
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=["post"], url_path="annuler")
    def annuler(self, request, pk=None):
        """Le demandeur (ou le chef d'atelier) retire une demande pas encore traitée."""
        demande = self._demande_en_attente()
        if request.user.role != Role.CHEF_ATELIER and demande.demandeur_id != request.user.id:
            raise PermissionDenied("Vous ne pouvez annuler que vos propres demandes.")
        demande.statut = StatutDemandePiece.ANNULEE
        demande.traitee_par, demande.traitee_le = request.user, timezone.now()
        demande.save(update_fields=["statut", "traitee_par", "traitee_le"])
        return Response(self.get_serializer(demande).data)


class FicheVehiculeView(APIView):
    """La fiche complète d'un véhicule : historique des interventions, pièces montées, pannes récurrentes, entretiens à venir."""

    permission_classes = [IsAuthenticated, PeutVoirLaFicheVehicule]

    def get(self, request, pk):
        vehicule = get_object_or_404(Vehicule.objects.select_related("gare"), pk=pk, company=request.user.company)
        return Response(analyses.fiche_vehicule(vehicule))


class ChargeMecaniciensView(APIView):
    """La charge de chaque intervenant de l'atelier, le moins chargé étant suggéré pour le prochain ordre."""

    permission_classes = [IsAuthenticated, PeutPiloterLAtelier]

    def get(self, request):
        return Response(analyses.charge_mecaniciens(request.user.company))


class BesoinRenouvellementView(APIView):
    """Le rapport de besoin de renouvellement de la flotte, généré à la demande pour la Direction Générale."""

    permission_classes = [IsAuthenticated, PeutVoirLeBesoinDeRenouvellement]

    def get(self, request):
        return Response(analyses.besoin_renouvellement(request.user.company))
