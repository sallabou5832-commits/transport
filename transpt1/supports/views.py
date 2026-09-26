import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billetterie.models import ModePaiement, StatutTicket, Ticket
from colis.models import Colis, StatutColis
from core.dates import lire_date
from communication.poles import POLES
from core.fichiers import nom_affichable, reponse_en_telechargement, verifier_fichier
from core.mixins import ActeurAuditeMixin, CompanyScopedQuerysetMixin
from configuration.regles import roles_configurables_par
from core.models import Role
from core.permissions import IsSameCompany
from core.serializers import nom_complet
from supports.conformite import tableau_conformite
from supports.models import Assurance, CategorieModele, DossierAgent, ModeleJuridique, PieceSinistre, Sinistre, StatutSinistre
from supports.reporting_juridique import reporting_juridique
from supports.permissions import (
    IsDrh,
    IsDrhOrOwnerReadOnly,
    IsFinance,
    IsResponsableJuridiqueOuDirecteurTechnique,
    PeutGererLesModeles,
    PeutVoirLaConformite,
    PeutVoirLeReportingJuridique,
)
from rh.serializers import ContratAgentSerializer, EvaluationAgentSerializer, MesureDisciplinaireSerializer
from rh.services import suivi_formations
from supports.serializers import (
    AssuranceSerializer,
    DossierAgentSerializer,
    ModeleJuridiqueSerializer,
    PieceSinistreSerializer,
    SinistreSerializer,
)


def pole_de(role):
    """La clé du pôle d'un poste (`communication.poles`)."""
    return next((cle for cle, (_, postes) in POLES.items() if role in postes), None)


class SupportsViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class DossierAgentViewSet(SupportsViewSet):
    queryset = DossierAgent.objects.select_related("agent", "company")
    serializer_class = DossierAgentSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsDrhOrOwnerReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role in (Role.DRH, Role.SUPERADMIN):
            return queryset
        # Le sien, et ceux des postes placés sous son autorité (le PDG règle tous les postes).
        return queryset.filter(Q(agent_id=user.id) | Q(agent__role__in=roles_configurables_par(user.role)))

    @action(detail=True, methods=["get"], url_path="fiche")
    def fiche(self, request, pk=None):
        """Le dossier complet de l'agent : contrats, évaluations, mesures disciplinaires, formations obligatoires. Les notes internes du
        DRH et celles des contrats ne sont lues que par le DRH et par l'agent."""
        dossier = self.get_object()
        agent = dossier.agent
        confidentiel = request.user.role not in (Role.DRH, Role.SUPERADMIN) and agent.pk != request.user.pk
        contrats = ContratAgentSerializer(agent.contrats.all(), many=True, context={"request": request}).data
        if confidentiel:
            contrats = [{k: v for k, v in c.items() if k != "notes"} for c in contrats]
        return Response(
            {
                "dossier": self.get_serializer(dossier).data,
                "contrats": contrats,
                "evaluations": EvaluationAgentSerializer(agent.evaluations.all(), many=True, context={"request": request}).data,
                "mesures": MesureDisciplinaireSerializer(agent.mesures_disciplinaires.all(), many=True, context={"request": request}).data,
                "formations": suivi_formations(dossier.company, agent=agent),
            }
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="agents-sans-dossier",
        permission_classes=[IsAuthenticated, IsDrh],
    )
    def agents_sans_dossier(self, request):
        """Agents de la compagnie qui n'ont pas encore de dossier (pour en ouvrir un)."""
        agents = (
            get_user_model()
            .objects.filter(company_id=request.user.company_id, dossier_agent__isnull=True)
            .order_by("username")
        )
        return Response(
            [
                {"id": agent.id, "username": agent.username, "nom": nom_complet(agent), "role": agent.role}
                for agent in agents
            ]
        )


class AssuranceViewSet(SupportsViewSet):
    queryset = Assurance.objects.select_related("vehicule", "company")
    serializer_class = AssuranceSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsResponsableJuridiqueOuDirecteurTechnique]

    @action(detail=False, methods=["get"], url_path="echeance-proche")
    def echeance_proche(self, request):
        limite = timezone.localdate() + datetime.timedelta(days=30)
        queryset = self.filter_queryset(self.get_queryset()).filter(date_echeance__lte=limite)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SinistreViewSet(SupportsViewSet):
    """Les sinistres. Un accident déclaré ouvre le sien tout seul (`supports.services`) ; le responsable juridique le suit jusqu'à la
    clôture (statut, montants, pièces jointes)."""

    queryset = Sinistre.objects.select_related("vehicule", "incident", "company").prefetch_related("pieces")
    serializer_class = SinistreSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsResponsableJuridiqueOuDirecteurTechnique]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("statut") in StatutSinistre.values:
            queryset = queryset.filter(statut=self.request.query_params["statut"])
        return queryset

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._dater_la_cloture(serializer.instance)

    def perform_update(self, serializer):
        serializer.save()
        self._dater_la_cloture(serializer.instance)

    @staticmethod
    def _dater_la_cloture(sinistre):
        """La date de clôture suit le statut : posée à la clôture, retirée si le dossier est rouvert."""
        if sinistre.statut == StatutSinistre.CLOS and sinistre.clos_le is None:
            sinistre.clos_le = timezone.now()
            sinistre.save(update_fields=["clos_le"])
        elif sinistre.statut != StatutSinistre.CLOS and sinistre.clos_le is not None:
            sinistre.clos_le = None
            sinistre.save(update_fields=["clos_le"])


class PieceSinistreViewSet(SupportsViewSet):
    """Les pièces jointes des sinistres (`?sinistre=`) : envoi en multipart (`sinistre`, `fichier`, `libelle`), téléchargement par l'API."""

    queryset = PieceSinistre.objects.select_related("sinistre", "ajoute_par")
    serializer_class = PieceSinistreSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsResponsableJuridiqueOuDirecteurTechnique]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]  # on corrige le libellé ; le fichier ne change pas
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("sinistre", "").isdigit():
            queryset = queryset.filter(sinistre_id=int(self.request.query_params["sinistre"]))
        return queryset

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company, ajoute_par=self.request.user)

    def perform_destroy(self, instance):
        instance.fichier.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["get"], url_path="telecharger")
    def telecharger(self, request, pk=None):
        piece = self.get_object()
        return reponse_en_telechargement(piece.fichier, piece.nom_fichier)


class ModeleJuridiqueViewSet(SupportsViewSet):
    """La bibliothèque de documents juridiques types, accessible aux autres pôles : chaque poste voit les modèles ouverts à son pôle
    (ou à tous), le responsable juridique les tient. `?categorie=`, `?q=` (recherche dans le titre, la description et le texte)."""

    queryset = ModeleJuridique.objects.select_related("auteur")
    serializer_class = ModeleJuridiqueSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, PeutGererLesModeles]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role != Role.RESPONSABLE_JURIDIQUE:
            pole = pole_de(user.role)
            queryset = queryset.filter(Q(poles=[]) | Q(poles__contains=[pole]))
        parametres = self.request.query_params
        if parametres.get("categorie") in CategorieModele.values:
            queryset = queryset.filter(categorie=parametres["categorie"])
        recherche = parametres.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(Q(titre__icontains=recherche) | Q(description__icontains=recherche) | Q(contenu__icontains=recherche))
        return queryset

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company, auteur=self.request.user)

    def perform_destroy(self, instance):
        if instance.fichier:
            instance.fichier.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="fichier", parser_classes=[MultiPartParser, FormParser])
    def fichier(self, request, pk=None):
        """Joint (ou remplace) le fichier du modèle : champ `fichier` en multipart."""
        modele = self.get_object()
        envoye = request.FILES.get("fichier")
        if envoye is None:
            raise ValidationError({"fichier": "Joignez un fichier."})
        verifier_fichier(envoye)
        if modele.fichier:
            modele.fichier.delete(save=False)
        modele.fichier, modele.nom_fichier, modele.taille = envoye, nom_affichable(envoye.name), envoye.size
        modele.save()
        return Response(self.get_serializer(modele).data)

    @action(detail=True, methods=["post"], url_path="retirer-fichier")
    def retirer_fichier(self, request, pk=None):
        """Retire le fichier du modèle (le texte reste)."""
        modele = self.get_object()
        if modele.fichier:
            modele.fichier.delete(save=False)
        modele.fichier, modele.nom_fichier, modele.taille = None, "", None
        modele.save()
        return Response(self.get_serializer(modele).data)

    @action(detail=True, methods=["get"], url_path="telecharger")
    def telecharger(self, request, pk=None):
        modele = self.get_object()
        if not modele.fichier:
            raise NotFound("Ce modèle n'a pas de fichier joint.")
        return reponse_en_telechargement(modele.fichier, modele.nom_fichier)


class ReportingJuridiqueView(ActeurAuditeMixin, APIView):
    """Synthèse juridique pour la Direction Générale : assurances, sinistres, litiges sociaux (comptés seulement), conformité."""

    permission_classes = [IsAuthenticated, PeutVoirLeReportingJuridique]

    def get(self, request):
        return Response(reporting_juridique(request.user.company))


class SyntheseFinanciereView(APIView):
    permission_classes = [IsAuthenticated, IsFinance]

    def get(self, request):
        user = request.user
        date_debut = lire_date(request.query_params.get("date_debut"))
        date_fin = lire_date(request.query_params.get("date_fin"))

        if date_debut is None or date_fin is None:
            raise ValidationError(
                "Les paramètres date_debut et date_fin (format AAAA-MM-JJ) sont requis."
            )

        # Seules les ventes valides sont des recettes : un ticket annulé (remboursé) n'en est pas une.
        tickets = Ticket.objects.filter(
            date_vente__date__gte=date_debut, date_vente__date__lte=date_fin, statut=StatutTicket.VALIDE
        )
        if user.role != Role.SUPERADMIN:
            tickets = tickets.filter(company_id=user.company_id)

        rows = (
            tickets.annotate(gare_id=F("depart__ligne__gare_depart_id"))
            .values("gare_id", "depart__ligne__gare_depart__nom")
            .annotate(nombre_tickets=Count("id"), montant_total=Sum("prix"))
            .order_by("depart__ligne__gare_depart__nom")
        )

        gares = [
            {
                "gare_id": row["gare_id"],
                "gare_nom": row["depart__ligne__gare_depart__nom"],
                "nombre_tickets": row["nombre_tickets"],
                "montant_total": row["montant_total"] or Decimal("0"),
            }
            for row in rows
        ]

        # Même périmètre (compagnie, période) que `gares`, vu sous deux autres angles : le mode
        # d'encaissement et l'évolution jour par jour. Calculés ici plutôt que côté client parce
        # que la liste des tickets est lisible par tous les rôles alors que ces montants ne le
        # sont pas (finance uniquement).
        total = tickets.aggregate(nombre=Count("id"), montant=Sum("prix"))

        par_mode = {
            row["mode_paiement"]: row
            for row in tickets.values("mode_paiement").annotate(
                nombre=Count("id"), montant=Sum("prix")
            ).order_by()
        }
        par_mode_paiement = [
            {
                "mode": mode,
                "nombre_tickets": par_mode.get(mode, {}).get("nombre", 0),
                "montant_total": par_mode.get(mode, {}).get("montant") or Decimal("0"),
            }
            for mode in ModePaiement.values
        ]

        par_jour = [
            {
                "date": row["jour"],
                "nombre_tickets": row["nombre"],
                "montant_total": row["montant"] or Decimal("0"),
            }
            for row in tickets.annotate(jour=TruncDate("date_vente"))
            .values("jour")
            .annotate(nombre=Count("id"), montant=Sum("prix"))
            .order_by("jour")
        ]

        # Le fret (frais des colis et bagages) est une recette aussi, encaissée comme un billet : espèces ou mobile money.
        # Un colis annulé n'en est pas une (les frais sont rendus). Présenté à part pour ne pas fausser les billets.
        fret_colis = Colis.objects.filter(
            enregistre_le__date__gte=date_debut, enregistre_le__date__lte=date_fin, frais__gt=0
        ).exclude(statut=StatutColis.ANNULE)
        if user.role != Role.SUPERADMIN:
            fret_colis = fret_colis.filter(company_id=user.company_id)
        fret = fret_colis.aggregate(nombre=Count("id"), montant=Sum("frais"))
        fret_par_mode = {
            row["mode_paiement"]: row
            for row in fret_colis.values("mode_paiement").annotate(nombre=Count("id"), montant=Sum("frais")).order_by()
        }
        montant_fret = fret["montant"] or Decimal("0")

        return Response(
            {
                "date_debut": date_debut,
                "date_fin": date_fin,
                "total": {
                    "nombre_tickets": total["nombre"] or 0,
                    "montant_total": total["montant"] or Decimal("0"),
                },
                "fret": {
                    "nombre_colis": fret["nombre"] or 0,
                    "montant_total": montant_fret,
                    "par_mode_paiement": [
                        {
                            "mode": mode,
                            "nombre_colis": fret_par_mode.get(mode, {}).get("nombre", 0),
                            "montant_total": fret_par_mode.get(mode, {}).get("montant") or Decimal("0"),
                        }
                        for mode in ModePaiement.values
                    ],
                },
                # Billets + fret : ce que la finance encaisse réellement sur la période.
                "total_general": {"montant_total": (total["montant"] or Decimal("0")) + montant_fret},
                "gares": gares,
                "par_mode_paiement": par_mode_paiement,
                "par_jour": par_jour,
            }
        )


class ConformiteView(APIView):
    """Tableau de conformité réglementaire de la flotte : assurance, contrôle technique et autres obligations, défauts de sécurité
    ouverts, blocages. Partagé par le QHSE et le juridique."""

    permission_classes = [IsAuthenticated, PeutVoirLaConformite]

    def get(self, request):
        return Response(tableau_conformite(request.user.company))
