from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billetterie.permissions import DISPATCH_ROLES
from core.mixins import CompanyScopedQuerysetMixin
from core.permissions import IsSameCompany
from core.serializers import nom_complet
from reseau import lignes as service_lignes
from reseau.models import AffectationGare, ChangementLigne, Gare, Ligne, StatutChangementLigne, Vehicule, VehiculeStatut
from reseau.permissions import (
    CanManageAffectation,
    CanManageOwnGare,
    IsGareManagerOrReadOnly,
    IsLigneManagerOrReadOnly,
    IsVehiculeManagerOrReadOnly,
    PeutArbitrer,
    PeutChangerLigne,
    PeutVoirLesChangements,
)
from reseau.serializers import (
    AffectationGareSerializer,
    ChangementLigneSerializer,
    GareSerializer,
    LigneSerializer,
    VehiculeSerializer,
)
from reseau.team import ROLES_AFFECTATION, ROLES_EQUIPE_LOCALE


class CompanyOwnedViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSameCompany]

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError(
                "Un compte sans compagnie ne peut pas créer cet objet."
            )
        serializer.save(company=user.company)


class GareViewSet(CompanyOwnedViewSet):
    queryset = Gare.objects.select_related("company", "chef")
    serializer_class = GareSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsGareManagerOrReadOnly, CanManageOwnGare]


class LigneViewSet(CompanyOwnedViewSet):
    queryset = Ligne.objects.select_related("company", "gare_depart", "gare_arrivee")
    serializer_class = LigneSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsLigneManagerOrReadOnly]

    @action(
        detail=True, methods=["post"], url_path="changement", permission_classes=[IsAuthenticated, IsSameCompany, PeutChangerLigne]
    )
    def changement(self, request, pk=None):
        """Ferme ou rouvre la ligne (`action`, `motif`, `jusqu_au` facultatif). Le directeur des opérations et le PDG
        l'appliquent aussitôt ; le chef de ligne et le chef de gare déposent une demande à valider."""
        ligne = self.get_object()
        brut = request.data.get("jusqu_au")
        jusqu_au = None
        if brut not in (None, ""):
            jusqu_au = parse_date(str(brut))
            if jusqu_au is None:
                raise ValidationError({"jusqu_au": "Date attendue (AAAA-MM-JJ)."})
        changement = service_lignes.enregistrer(
            ligne, request.user, action=request.data.get("action"), motif=request.data.get("motif"), jusqu_au=jusqu_au
        )
        return Response(ChangementLigneSerializer(changement).data, status=201)


class ChangementLigneViewSet(
    CompanyScopedQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Demandes de fermeture ou de réouverture de ligne. Le décideur les voit toutes ; un chef de ligne ou de gare, les siennes."""

    queryset = ChangementLigne.objects.select_related("ligne", "demandeur", "decide_par")
    serializer_class = ChangementLigneSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutVoirLesChangements]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role not in service_lignes.DECIDEURS:
            queryset = queryset.filter(demandeur=user)
        parametres = self.request.query_params
        if parametres.get("statut") in StatutChangementLigne.values:
            queryset = queryset.filter(statut=parametres["statut"])
        if parametres.get("ligne", "").isdigit():
            queryset = queryset.filter(ligne_id=int(parametres["ligne"]))
        return queryset

    @action(detail=True, methods=["post"], url_path="decider", permission_classes=[IsAuthenticated, IsSameCompany, PeutArbitrer])
    def decider(self, request, pk=None):
        """Valide ou refuse une demande (`decision` : « valider » ou « refuser », `commentaire` facultatif)."""
        changement = service_lignes.decider(
            self.get_object(), request.user, decision=request.data.get("decision"), commentaire=request.data.get("commentaire")
        )
        return Response(self.get_serializer(changement).data)


class VehiculeViewSet(CompanyOwnedViewSet):
    queryset = Vehicule.objects.select_related("company", "gare")
    serializer_class = VehiculeSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsVehiculeManagerOrReadOnly]

    @action(
        detail=True, methods=["post"], url_path="reaffecter-gare", permission_classes=[IsAuthenticated, IsSameCompany, PeutArbitrer]
    )
    def reaffecter_gare(self, request, pk=None):
        """Arbitrage entre gares : rattache le véhicule à une autre gare d'attache (`gare`, `motif`). Les chefs des deux gares
        et la régulation en sont prévenus."""
        vehicule = self.get_object()
        brut = str(request.data.get("gare", "")).strip()
        gare = Gare.objects.filter(pk=int(brut), company_id=request.user.company_id).first() if brut.isdigit() else None
        if gare is None:
            raise ValidationError({"gare": "Choisissez une gare de votre compagnie."})
        motif = str(request.data.get("motif", "")).strip()
        if len(motif) < service_lignes.MOTIF_MIN:
            raise ValidationError({"motif": f"Indiquez le motif ({service_lignes.MOTIF_MIN} caractères au moins)."})
        if vehicule.gare_id == gare.pk:
            raise ValidationError({"gare": "Ce véhicule est déjà rattaché à cette gare."})
        if vehicule.statut == VehiculeStatut.EN_LIGNE:
            raise ValidationError("Ce véhicule est en ligne : il ne peut être rattaché à une autre gare qu'à son retour.")
        ancienne = vehicule.gare
        vehicule.gare = gare
        vehicule.save(update_fields=["gare"])
        service_lignes.annoncer_reaffectation(vehicule, ancienne, gare, motif, request.user)
        return Response(self.get_serializer(vehicule).data)


class AffectationGareViewSet(CompanyOwnedViewSet):
    """Équipes locales des gares (guichetiers, bagagistes). Le chef de gare compose celle de sa gare."""

    queryset = AffectationGare.objects.select_related("agent", "gare", "company")
    serializer_class = AffectationGareSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, CanManageAffectation]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role in DISPATCH_ROLES:
            return queryset
        return queryset.filter(agent_id=user.id)  # un agent voit son propre rattachement, pas les équipes des autres

    @action(detail=False, methods=["get"], url_path="agents-affectables", permission_classes=[IsAuthenticated])
    def agents_affectables(self, request):
        """Guichetiers et bagagistes de la compagnie, avec leur gare actuelle (annuaire réservé à ceux qui composent
        les équipes : il n'y a pas d'annuaire général des agents)."""
        if request.user.role not in ROLES_AFFECTATION:
            self.permission_denied(request)
        agents = (
            get_user_model()
            .objects.filter(company_id=request.user.company_id, role__in=ROLES_EQUIPE_LOCALE)
            .select_related("affectation_gare__gare")
            .order_by("username")
        )
        return Response(
            [
                {
                    "id": agent.id,
                    "nom": nom_complet(agent),
                    "role": agent.role,
                    "gare": (
                        {"id": agent.affectation_gare.gare_id, "nom": agent.affectation_gare.gare.nom}
                        if hasattr(agent, "affectation_gare")
                        else None
                    ),
                }
                for agent in agents
            ]
        )
