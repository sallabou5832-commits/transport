import datetime

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billetterie.models import Depart, SourceTicket
from core.dates import lire_date
from core.mixins import ActeurAuditeMixin
from core.models import Role
from lien_billetterie import services
from lien_billetterie.authentication import CleLienAuthentication
from lien_billetterie.fichiers import lire_ventes
from lien_billetterie.models import CleLienBilletterie, ImportVentes, ModeBilletterie, ReglageBilletterie
from lien_billetterie.permissions import (
    ROLES_GESTION_LIEN,
    EstLeLogicielDeLaCompagnie,
    PeutGererLesCles,
    PeutImporterDesVentes,
    PeutVoirOuReglerLeModeDeBilletterie,
)
from lien_billetterie.serializers import CleLienSerializer, ImportVentesDetailSerializer, ImportVentesSerializer

MAX_PAR_ENVOI = 500
JOURS_MAX_PLANNING = 31
JOURS_PLANNING_PAR_DEFAUT = 7


# --- Ce que voit et fait le logiciel de la compagnie (clé d'API) ----------------------------------------------------------


class _VueDuLogiciel(APIView):
    """Les routes du logiciel de billetterie de la compagnie : sa clé seule les ouvre, et seulement si la compagnie a passé
    sa billetterie en mode externe ou mixte."""

    authentication_classes = [CleLienAuthentication]
    permission_classes = [EstLeLogicielDeLaCompagnie]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        services.exiger_lien_ouvert(request.user.company_id)

    @staticmethod
    def _liste(request, champ):
        elements = request.data.get(champ)
        if not isinstance(elements, list) or not elements:
            raise ValidationError({champ: f"Liste attendue : {{\"{champ}\": [ ... ]}}."})
        if len(elements) > MAX_PAR_ENVOI:
            raise ValidationError({champ: f"{MAX_PAR_ENVOI} au plus par envoi : découpez le lot."})
        return elements


class DepartsDuLienView(_VueDuLogiciel):
    """Le planning, pour vendre sur nos départs : `?du=AAAA-MM-JJ&au=AAAA-MM-JJ` (aujourd'hui et les 7 jours suivants par
    défaut, 31 jours au plus). `places_disponibles` est ce qu'une vente du logiciel peut prendre maintenant (les places
    réservées pour la vente hors ligne des guichets n'en font pas partie)."""

    def get(self, request):
        du = self._jour(request, "du") or timezone.localdate()
        au = self._jour(request, "au") or du + datetime.timedelta(days=JOURS_PLANNING_PAR_DEFAUT)
        if au < du:
            raise ValidationError({"au": "La fin de la période précède son début."})
        if (au - du).days > JOURS_MAX_PLANNING:
            raise ValidationError({"au": f"{JOURS_MAX_PLANNING} jours au plus par demande."})
        debut = timezone.make_aware(datetime.datetime.combine(du, datetime.time.min))
        fin = timezone.make_aware(datetime.datetime.combine(au + datetime.timedelta(days=1), datetime.time.min))
        departs = (
            Depart.objects.filter(company_id=request.user.company_id, date_heure__gte=debut, date_heure__lt=fin)
            .select_related("ligne", "ligne__gare_depart", "ligne__gare_arrivee", "vehicule")
            .annotate(
                _places_reservees=Coalesce(
                    Sum("reservations_hors_ligne__places", filter=Q(reservations_hors_ligne__expire_le__gt=timezone.now())),
                    0,
                )
            )
            .order_by("date_heure", "id")
        )
        return Response([self._depart(depart) for depart in departs])

    @staticmethod
    def _jour(request, parametre):
        if parametre not in request.query_params:
            return None
        jour = lire_date(request.query_params[parametre])
        if jour is None:
            raise ValidationError({parametre: "Date attendue au format AAAA-MM-JJ."})
        return jour

    @staticmethod
    def _depart(depart):
        ligne = depart.ligne
        return {
            "id": depart.id,
            "ligne": ligne.id,
            "ligne_nom": ligne.nom,
            "gare_depart": ligne.gare_depart.nom,
            "gare_arrivee": ligne.gare_arrivee.nom,
            "date_heure": depart.date_heure,
            "statut": depart.statut,
            "ligne_fermee": ligne.est_fermee,
            "capacite": depart.vehicule.capacite,
            "places_vendues": depart.places_vendues,
            "places_disponibles": depart.places_disponibles,
            "tarif": ligne.tarif,
        }


class VentesDuLienView(_VueDuLogiciel):
    """Le logiciel envoie ses ventes : `{"ventes": [{reference, depart | ligne + date_heure, passager_nom,
    passager_telephone, prix, mode_paiement, vendu_le}, ...]}` (500 au plus). Chaque vente est traitée à part : le compte
    rendu dit, pour chacune, si elle est créée, déjà reçue (rejouer un lot est sans effet) ou refusée, et pourquoi."""

    def post(self, request):
        cle = request.user
        resultats = [
            services.enregistrer_vente(cle.company, vente, source=SourceTicket.LIEN, logiciel=cle.logiciel)
            for vente in self._liste(request, "ventes")
        ]
        return Response(services.bilan(resultats))


class AnnulationsDuLienView(_VueDuLogiciel):
    """Le logiciel annule des ventes qu'il a envoyées : `{"annulations": [{reference, motif}, ...]}`."""

    def post(self, request):
        cle = request.user
        resultats = [
            services.annuler_vente(cle.company, annulation, logiciel=cle.logiciel)
            for annulation in self._liste(request, "annulations")
        ]
        return Response(services.bilan(resultats))


# --- Ce que règle la compagnie (agents connectés) -------------------------------------------------------------------------


class ReglageBilletterieView(ActeurAuditeMixin, APIView):
    """Le mode de billetterie de la compagnie : `integre` (défaut), `externe` (la vente au guichet est fermée, les ventes
    arrivent du logiciel de la compagnie) ou `mixte` (les deux). Tous le lisent ; le PDG et le directeur des opérations le
    règlent (`PATCH {"mode": ...}`)."""

    permission_classes = [IsAuthenticated, PeutVoirOuReglerLeModeDeBilletterie]

    def get(self, request):
        return Response(self._donnees(request.user))

    def patch(self, request):
        mode = request.data.get("mode")
        if mode not in ModeBilletterie.values:
            raise ValidationError({"mode": f"Modes possibles : {', '.join(ModeBilletterie.values)}."})
        ReglageBilletterie.objects.update_or_create(
            company_id=request.user.company_id,
            defaults={"mode": mode, "modifie_par": request.user, "modifie_le": timezone.now()},
        )
        return Response(self._donnees(request.user))

    @staticmethod
    def _donnees(user):
        mode = services.mode_billetterie(user.company_id)
        return {
            "mode": mode,
            "libelle": ModeBilletterie(mode).label,
            "vente_au_guichet": mode != ModeBilletterie.EXTERNE,
            "ventes_externes": mode != ModeBilletterie.INTEGRE,
            "modes": [{"valeur": valeur, "libelle": libelle} for valeur, libelle in ModeBilletterie.choices],
            "modifiable": user.role in ROLES_GESTION_LIEN,
        }


class CleLienViewSet(ActeurAuditeMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Les clés d'API du lien : en créer une pour un logiciel (`{"logiciel": ...}`, la clé en clair n'est montrée qu'une
    fois, dans la réponse), les lister (sans la clé), en révoquer une (`POST /{id}/revoquer/`). Ni modification ni
    suppression : une clé révoquée reste dans l'historique."""

    serializer_class = CleLienSerializer
    permission_classes = [IsAuthenticated, PeutGererLesCles]

    def get_queryset(self):
        return CleLienBilletterie.objects.filter(company_id=self.request.user.company_id).select_related("creee_par")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cle, en_clair = CleLienBilletterie.creer(
            company=request.user.company, logiciel=serializer.validated_data["logiciel"], par=request.user
        )
        return Response({**self.get_serializer(cle).data, "cle": en_clair}, status=201)

    @action(detail=True, methods=["post"], url_path="revoquer")
    def revoquer(self, request, pk=None):
        cle = self.get_object()
        if not cle.active:
            raise ValidationError("Cette clé est déjà révoquée.")
        cle.active, cle.revoquee_par, cle.revoquee_le = False, request.user, timezone.now()
        cle.save(update_fields=["active", "revoquee_par", "revoquee_le"])
        return Response(self.get_serializer(cle).data)


class ImportVentesViewSet(
    ActeurAuditeMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Déposer le fichier de ventes exporté par le logiciel de la compagnie (CSV ou Excel, champ `fichier`, avec le nom du
    `logiciel`) : chaque ligne est traitée comme une vente reçue par l'API, et le compte rendu dit ce qui a été fait de
    chacune. Le chef de gare n'importe que des départs de sa gare et ne voit que ses propres imports."""

    permission_classes = [IsAuthenticated, PeutImporterDesVentes]

    def get_serializer_class(self):
        return ImportVentesSerializer if self.action == "list" else ImportVentesDetailSerializer

    def get_queryset(self):
        user = self.request.user
        imports = ImportVentes.objects.filter(company_id=user.company_id).select_related("depose_par")
        return imports.filter(depose_par=user) if user.role == Role.CHEF_GARE else imports

    def create(self, request, *args, **kwargs):
        user = request.user
        services.exiger_lien_ouvert(user.company_id)
        fichier = request.FILES.get("fichier")
        if fichier is None:
            raise ValidationError({"fichier": "Joignez le fichier des ventes (CSV ou Excel)."})
        logiciel = str(request.data.get("logiciel") or "").strip()[:100]
        if len(logiciel) < 2:
            raise ValidationError({"logiciel": "Indiquez le nom du logiciel qui a produit ce fichier."})
        chef_de_gare_id = user.pk if user.role == Role.CHEF_GARE else None

        rapport = []
        for numero, vente in lire_ventes(fichier):
            resultat = services.enregistrer_vente(
                user.company, vente, source=SourceTicket.IMPORT, logiciel=logiciel, chef_de_gare_id=chef_de_gare_id
            )
            rapport.append({"ligne": numero, **resultat})
        nombres = services.bilan(rapport)
        importation = ImportVentes.objects.create(
            company=user.company,
            logiciel=logiciel,
            fichier=(fichier.name or "")[:255],
            depose_par=user,
            lignes=len(rapport),
            creees=nombres["creee"],
            deja_recues=nombres["deja_recue"],
            refusees=nombres["refusee"],
            rapport=rapport,
        )
        return Response(ImportVentesDetailSerializer(importation).data, status=201)
