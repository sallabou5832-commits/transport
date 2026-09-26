import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from configuration.regles import roles_configurables_par
from core.mixins import ActeurAuditeMixin, CompanyScopedQuerysetMixin
from core.models import Role
from core.serializers import nom_complet
from rh import fiches_types, services
from rh.alertes import PREAVIS_FIN_CONTRAT_JOURS, signaler_litige
from rh.models import (
    Candidature,
    ContratAgent,
    DemandeConge,
    Doleance,
    EvaluationAgent,
    FicheDePoste,
    FormationSuivie,
    GraviteDoleance,
    MesureDisciplinaire,
    ObligationFormation,
    OffreRecrutement,
    StatutCandidature,
    StatutConge,
    StatutDoleance,
    StatutOffre,
    SuiviDoleance,
    TypeContrat,
)
from rh.permissions import (
    DOSSIERS_LARGE,
    FORMATIONS_LARGE,
    EstDrh,
    EstUnAgentDeCompagnie,
    PeutVoirLaSyntheseRh,
    PeutVoirLesLitiges,
    PermissionContrats,
    PermissionFormations,
    PermissionMesures,
    PermissionObligations,
    PermissionRecrutement,
    agents_visibles,
    dans_une_compagnie,
    peut_evaluer,
    visibles,
)
from rh.serializers import (
    CandidatureSerializer,
    ContratAgentSerializer,
    DemandeCongeSerializer,
    DoleanceSerializer,
    EvaluationAgentSerializer,
    FicheDePosteSerializer,
    FormationSuivieSerializer,
    LitigeSerializer,
    MesureDisciplinaireSerializer,
    ObligationFormationSerializer,
    OffreRecrutementSerializer,
    SuiviDoleanceSerializer,
)

User = get_user_model()


class ConfirmationRequise(APIException):
    """Une action qui a des conséquences que l'appelant doit avoir vues (409) : il la renvoie avec `forcer`."""

    status_code = 409
    default_detail = "Confirmation requise."
    default_code = "confirmation_requise"


class RhViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    """Les données RH d'une compagnie ; l'accès dépend du modèle (voir `rh.permissions`)."""

    def perform_create(self, serializer):
        return serializer.save(company=self.request.user.company)

    def _filtrer(self, queryset, *champs):
        """Filtres d'URL sur des identifiants (`?agent=12`)."""
        for champ in champs:
            valeur = self.request.query_params.get(champ, "")
            if valeur.isdigit():
                queryset = queryset.filter(**{f"{champ}_id": int(valeur)})
        return queryset


# --- Formations obligatoires ------------------------------------------------------------------------------------------------


class ObligationFormationViewSet(RhViewSet):
    """Le catalogue des formations et documents obligatoires par poste (permis, visite médicale, OSER…)."""

    queryset = ObligationFormation.objects.all()
    serializer_class = ObligationFormationSerializer
    permission_classes = [PermissionObligations]

    def perform_destroy(self, instance):
        if instance.suivies.exists():
            raise ValidationError("Des sessions sont enregistrées pour cette obligation : elle reste au catalogue pour garder l'historique.")
        instance.delete()


class FormationSuivieViewSet(RhViewSet):
    """Les sessions suivies par les agents, chacun voyant les siennes et celles des postes sous son autorité."""

    queryset = FormationSuivie.objects.select_related("agent", "obligation")
    serializer_class = FormationSuivieSerializer
    permission_classes = [PermissionFormations]

    def get_queryset(self):
        return self._filtrer(visibles(FormationSuivie.objects.select_related("agent", "obligation"), self.request.user, FORMATIONS_LARGE), "agent", "obligation")

    def perform_create(self, serializer):
        return serializer.save(company=self.request.user.company, saisi_par=self.request.user)


class SuiviFormationsView(ActeurAuditeMixin, APIView):
    """L'état de chaque formation obligatoire pour chaque agent concerné (`?etat=`, `?agent=`), les plus urgentes d'abord."""

    permission_classes = [EstUnAgentDeCompagnie]

    def get(self, request):
        visibles_ids = set(agents_visibles(request.user, FORMATIONS_LARGE).values_list("pk", flat=True))
        lignes = [l for l in services.suivi_formations(request.user.company) if l["agent"] in visibles_ids]
        if request.query_params.get("agent", "").isdigit():
            lignes = [l for l in lignes if l["agent"] == int(request.query_params["agent"])]
        resume = services.resume_formations(lignes)
        if request.query_params.get("etat") in services.ORDRE_ETATS:
            lignes = [l for l in lignes if l["etat"] == request.query_params["etat"]]
        return Response({"resume": resume, "lignes": lignes})


# --- Dossier de l'agent : contrats, évaluations, discipline ---------------------------------------------------------------------


class ContratAgentViewSet(RhViewSet):
    queryset = ContratAgent.objects.select_related("agent")
    serializer_class = ContratAgentSerializer
    permission_classes = [PermissionContrats]

    def get_queryset(self):
        return self._filtrer(visibles(ContratAgent.objects.select_related("agent"), self.request.user, DOSSIERS_LARGE), "agent")


class MesureDisciplinaireViewSet(RhViewSet):
    queryset = MesureDisciplinaire.objects.select_related("agent")
    serializer_class = MesureDisciplinaireSerializer
    permission_classes = [PermissionMesures]

    def get_queryset(self):
        return self._filtrer(visibles(MesureDisciplinaire.objects.select_related("agent"), self.request.user, DOSSIERS_LARGE), "agent")

    def perform_create(self, serializer):
        return serializer.save(company=self.request.user.company, decidee_par=self.request.user)


class PeutEcrireUneEvaluation(BasePermission):
    """Le DRH, et tout échelon qui a des postes sous son autorité, évaluent ; les autres lisent seulement leurs évaluations."""

    def has_permission(self, request, view):
        user = request.user
        if not dans_une_compagnie(user):
            return False
        return request.method in SAFE_METHODS or user.role == Role.DRH or bool(roles_configurables_par(user.role))


class EvaluationAgentViewSet(RhViewSet):
    queryset = EvaluationAgent.objects.select_related("agent", "evaluateur")
    serializer_class = EvaluationAgentSerializer
    permission_classes = [PeutEcrireUneEvaluation]

    def get_queryset(self):
        return self._filtrer(
            visibles(EvaluationAgent.objects.select_related("agent", "evaluateur"), self.request.user, DOSSIERS_LARGE), "agent"
        )

    def perform_create(self, serializer):
        if not peut_evaluer(self.request.user, serializer.validated_data["agent"]):
            raise PermissionDenied("Vous n'évaluez que les postes placés sous votre autorité.")
        return serializer.save(company=self.request.user.company, evaluateur=self.request.user)

    def _verifier_auteur(self, evaluation):
        if self.request.user.role != Role.DRH and evaluation.evaluateur_id != self.request.user.id:
            raise PermissionDenied("Seul son auteur ou le DRH modifie une évaluation.")

    def perform_update(self, serializer):
        self._verifier_auteur(serializer.instance)
        if "agent" in serializer.validated_data and not peut_evaluer(self.request.user, serializer.validated_data["agent"]):
            raise PermissionDenied("Vous n'évaluez que les postes placés sous votre autorité.")
        serializer.save()

    def perform_destroy(self, instance):
        self._verifier_auteur(instance)
        instance.delete()


# --- Congés -----------------------------------------------------------------------------------------------------------------------


class PeutVoirLImpact(BasePermission):
    def has_permission(self, request, view):
        return dans_une_compagnie(request.user) and request.user.role in DOSSIERS_LARGE


class DemandeCongeViewSet(RhViewSet):
    """Les demandes de congé : chacun demande pour lui-même et voit les siennes (les échelons voient celles des postes sous leur
    autorité, le DRH et le PDG toutes) ; le DRH valide après avoir vu l'impact sur le personnel disponible."""

    queryset = DemandeConge.objects.select_related("agent", "decide_par")
    serializer_class = DemandeCongeSerializer
    permission_classes = [EstUnAgentDeCompagnie]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = visibles(DemandeConge.objects.select_related("agent", "decide_par"), self.request.user, DOSSIERS_LARGE)
        parametres = self.request.query_params
        if parametres.get("statut") in StatutConge.values:
            queryset = queryset.filter(statut=parametres["statut"])
        return self._filtrer(queryset, "agent")

    def perform_create(self, serializer):
        user = self.request.user
        agent = serializer.validated_data.get("agent") if user.role == Role.DRH else None
        agent = agent or user
        debut, fin = serializer.validated_data["debut"], serializer.validated_data["fin"]
        if services.conge_en_conflit(agent, debut, fin):
            raise ValidationError("Une autre demande de cet agent couvre déjà une partie de ces dates.")
        demande = serializer.save(company=user.company, agent=agent)
        alerter(
            user.company,
            type=TypeAlerte.CONGE,
            gravite=GraviteAlerte.INFO,
            titre=f"Demande de congé : {nom_complet(agent)}",
            message=f"{demande.get_type_display()} du {demande.debut:%d/%m/%Y} au {demande.fin:%d/%m/%Y}.",
            roles=[Role.DRH],
            objet=demande,
        )

    @action(detail=True, methods=["get"], url_path="impact", permission_classes=[PeutVoirLImpact])
    def impact(self, request, pk=None):
        """L'effet du congé sur le personnel disponible, jour par jour, avant de le valider."""
        demande = self.get_object()
        return Response(services.impact_conge(request.user.company, demande.agent, demande.debut, demande.fin, exclure_id=demande.pk))

    @action(detail=True, methods=["post"], url_path="approuver", permission_classes=[EstDrh])
    def approuver(self, request, pk=None):
        """Approuve la demande. Si l'impact est critique, ou si le conducteur a des départs à assurer, la validation demande une
        confirmation (`forcer`) : le DRH a vu ce qu'il décide."""
        demande = self.get_object()
        if demande.statut != StatutConge.EN_ATTENTE:
            raise ValidationError("Cette demande n'est plus en attente.")
        impact = services.impact_conge(request.user.company, demande.agent, demande.debut, demande.fin, exclure_id=demande.pk)
        forcer = request.data.get("forcer") in (True, "true", "1", 1)
        if not forcer:
            if impact["niveau"] == "critique":
                raise ConfirmationRequise(
                    f"Impact critique sur {impact['jours_critiques']} jour(s) : il ne resterait pas assez de personnel de ce poste. "
                    "Confirmez pour valider malgré tout."
                )
            if impact["departs_a_reaffecter"]:
                raise ConfirmationRequise(
                    f"{len(impact['departs_a_reaffecter'])} départ(s) sont planifiés avec cet agent pendant son congé et devront être réaffectés. "
                    "Confirmez pour valider malgré tout."
                )
        self._decider(demande, StatutConge.APPROUVE, str(request.data.get("motif", "")).strip())
        if impact["departs_a_reaffecter"]:
            alerter(
                demande.company,
                type=TypeAlerte.CONGE,
                gravite=GraviteAlerte.ATTENTION,
                titre=f"Départs à réaffecter : {nom_complet(demande.agent)} en congé",
                message=f"Congé du {demande.debut:%d/%m/%Y} au {demande.fin:%d/%m/%Y} : {len(impact['departs_a_reaffecter'])} départ(s) planifié(s) avec ce conducteur.",
                roles=[Role.DIRECTEUR_EXPLOITATION, Role.CHEF_LIGNE],
                objet=demande,
            )
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=["post"], url_path="refuser", permission_classes=[EstDrh])
    def refuser(self, request, pk=None):
        demande = self.get_object()
        if demande.statut != StatutConge.EN_ATTENTE:
            raise ValidationError("Cette demande n'est plus en attente.")
        motif = str(request.data.get("motif", "")).strip()
        if len(motif) < 3:
            raise ValidationError({"motif": "Indiquez pourquoi le congé est refusé."})
        self._decider(demande, StatutConge.REFUSE, motif)
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=["post"], url_path="annuler")
    def annuler(self, request, pk=None):
        """L'agent retire sa demande (ou son congé à venir) ; le DRH peut aussi le faire."""
        demande = self.get_object()
        if request.user.role != Role.DRH and demande.agent_id != request.user.id:
            raise PermissionDenied("Vous ne pouvez annuler que vos propres demandes.")
        if demande.statut not in (StatutConge.EN_ATTENTE, StatutConge.APPROUVE) or demande.fin < timezone.localdate():
            raise ValidationError("Cette demande ne peut plus être annulée.")
        demande.statut = StatutConge.ANNULE
        demande.save(update_fields=["statut"])
        return Response(self.get_serializer(demande).data)

    def _decider(self, demande, statut, motif):
        demande.statut, demande.decide_par, demande.decide_le, demande.motif_decision = statut, self.request.user, timezone.now(), motif
        demande.save(update_fields=["statut", "decide_par", "decide_le", "motif_decision"])
        approuve = statut == StatutConge.APPROUVE
        alerter(
            demande.company,
            type=TypeAlerte.CONGE,
            gravite=GraviteAlerte.INFO if approuve else GraviteAlerte.ATTENTION,
            titre=f"Congé {'approuvé' if approuve else 'refusé'} du {demande.debut:%d/%m/%Y} au {demande.fin:%d/%m/%Y}",
            message=motif,
            destinataires=[demande.agent],
            objet=demande,
        )


# --- Recrutement ---------------------------------------------------------------------------------------------------------------


def fiche_du_poste(company, role):
    """(fiche, personnalisée) : celle que la compagnie a écrite, sinon la fiche type du rôle."""
    fiche = FicheDePoste.objects.filter(company=company, role=role).first()
    if fiche is not None:
        return {"role": role, "intitule": fiche.intitule, "missions": fiche.missions, "profil": fiche.profil, "conditions": fiche.conditions}, True
    return {"role": role, **fiches_types.FICHES_TYPES[role]}, False


class FichesPosteView(ActeurAuditeMixin, APIView):
    """Les fiches de poste : une par rôle de l'organigramme, la fiche type tant que le DRH ne l'a pas personnalisée (PUT)."""

    permission_classes = [PermissionRecrutement]

    def get_serializer(self, *args, **kwargs):  # OPTIONS annonce ainsi le PUT à qui peut l'utiliser
        return FicheDePosteSerializer(*args, **kwargs)

    def get(self, request):
        fiches = []
        for role in fiches_types.FICHES_TYPES:
            fiche, personnalisee = fiche_du_poste(request.user.company, role)
            fiches.append({**fiche, "role_libelle": Role(role).label, "personnalisee": personnalisee})
        return Response(fiches)

    def put(self, request):
        role = request.data.get("role")
        if role not in fiches_types.FICHES_TYPES:
            raise ValidationError({"role": "Ce poste n'existe pas dans l'organigramme."})
        fiche = FicheDePoste.objects.filter(company=request.user.company, role=role).first() or FicheDePoste(company=request.user.company, role=role)
        serializer = FicheDePosteSerializer(fiche, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(modifie_par=request.user)
        return Response({**serializer.data, "role": role, "role_libelle": Role(role).label, "personnalisee": True})


class ReinitialiserFicheView(ActeurAuditeMixin, APIView):
    """Revient à la fiche type du rôle."""

    permission_classes = [PermissionRecrutement]

    def get_serializer(self, *args, **kwargs):
        from rest_framework import serializers

        class _Role(serializers.Serializer):
            role = serializers.ChoiceField(choices=list(fiches_types.FICHES_TYPES))

        return _Role(*args, **kwargs)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        FicheDePoste.objects.filter(company=request.user.company, role=role).delete()
        fiche, _ = fiche_du_poste(request.user.company, role)
        return Response({**fiche, "role_libelle": Role(role).label, "personnalisee": False})


def _texte_de_l_offre(fiche):
    return f"Missions\n{fiche['missions']}\n\nProfil recherché\n{fiche['profil']}" + (f"\n\nConditions\n{fiche['conditions']}" if fiche["conditions"] else "")


class OffreRecrutementViewSet(RhViewSet):
    """Les offres de recrutement. Une offre s'ouvre à partir de la fiche de poste du rôle recherché."""

    queryset = OffreRecrutement.objects.select_related("gare")
    serializer_class = OffreRecrutementSerializer
    permission_classes = [PermissionRecrutement]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("statut") in StatutOffre.values:
            queryset = queryset.filter(statut=self.request.query_params["statut"])
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        fiche, _ = fiche_du_poste(user.company, serializer.validated_data["role"])
        serializer.save(
            company=user.company, cree_par=user,
            intitule=serializer.validated_data.get("intitule") or fiche["intitule"],
            description=serializer.validated_data.get("description") or _texte_de_l_offre(fiche),
        )


class CandidatureViewSet(RhViewSet):
    """Les candidatures d'une offre, de la réception à la décision. Quand assez de candidats sont retenus, l'offre est pourvue."""

    queryset = Candidature.objects.select_related("offre")
    serializer_class = CandidatureSerializer
    permission_classes = [PermissionRecrutement]

    def get_queryset(self):
        queryset = self._filtrer(super().get_queryset(), "offre")
        if self.request.query_params.get("statut") in StatutCandidature.values:
            queryset = queryset.filter(statut=self.request.query_params["statut"])
        return queryset

    def perform_update(self, serializer):
        candidature = serializer.save()
        self._verifier_offre(candidature.offre)

    @staticmethod
    def _verifier_offre(offre):
        retenues = offre.candidatures.filter(statut=StatutCandidature.RETENUE).count()
        if offre.statut == StatutOffre.OUVERTE and retenues >= offre.nombre_postes:
            offre.statut = StatutOffre.POURVUE
            offre.save(update_fields=["statut"])


# --- Médiation sociale ---------------------------------------------------------------------------------------------------------


class DoleanceViewSet(RhViewSet):
    """Le canal de médiation sociale : tout agent y dépose une doléance et en suit le traitement ; le DRH les instruit (étapes de
    suivi, gravité, statut) et enregistre celles des syndicats. Une doléance qui atteint le seuil de gravité prévient le juridique."""

    queryset = Doleance.objects.select_related("auteur").prefetch_related("suivis__auteur")
    serializer_class = DoleanceSerializer
    permission_classes = [EstUnAgentDeCompagnie]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("update", "partial_update", "suivre"):
            return [EstDrh()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role != Role.DRH:
            queryset = queryset.filter(auteur=user)
        parametres = self.request.query_params
        if parametres.get("statut") in StatutDoleance.values:
            queryset = queryset.filter(statut=parametres["statut"])
        if parametres.get("gravite") in GraviteDoleance.values:
            queryset = queryset.filter(gravite=parametres["gravite"])
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == Role.DRH:
            if serializer.validated_data.get("origine") != "syndicat":
                raise ValidationError({"origine": "Le DRH enregistre les doléances des syndicats ; chaque agent dépose la sienne."})
            doleance = serializer.save(company=user.company, auteur=None)
        else:
            doleance = serializer.save(company=user.company, auteur=user, origine="agent")
        alerter(
            user.company,
            type=TypeAlerte.DOLEANCE,
            gravite=GraviteAlerte.INFO,
            titre=f"Nouvelle doléance : {doleance.objet}",
            message=f"Déposée par {'le syndicat ' + doleance.syndicat if doleance.origine == 'syndicat' else nom_complet(user)}, gravité « {doleance.get_gravite_display().lower()} ».",
            roles=[Role.DRH],
            objet=doleance,
        )
        if services.est_litige(doleance):
            signaler_litige(doleance)

    def perform_update(self, serializer):
        avant = (serializer.instance.gravite, serializer.instance.statut)
        doleance = serializer.save()
        if services.est_litige(doleance):
            signaler_litige(doleance)  # la clé d'alerte comprend la gravité : requalifier en « critique » prévient à nouveau
        if doleance.statut != avant[1] and doleance.auteur_id:
            self._prevenir_deposant(doleance, f"Votre doléance « {doleance.objet} » est maintenant : {doleance.get_statut_display().lower()}.")

    @staticmethod
    def _prevenir_deposant(doleance, message):
        alerter(
            doleance.company, type=TypeAlerte.DOLEANCE, gravite=GraviteAlerte.INFO, titre="Médiation sociale : votre doléance avance",
            message=message, destinataires=[doleance.auteur], objet=doleance,
        )

    @action(detail=True, methods=["post"], url_path="suivre")
    def suivre(self, request, pk=None):
        """Note une étape de la médiation ; `visible_du_deposant` la montre (ou non) à l'agent, `statut` fait avancer la doléance."""
        doleance = self.get_object()
        texte = str(request.data.get("texte", "")).strip()
        if len(texte) < 3:
            raise ValidationError({"texte": "Écrivez l'étape de la médiation."})
        visible = request.data.get("visible_du_deposant", True) in (True, "true", "1", 1)
        statut = request.data.get("statut")
        if statut is not None and statut not in StatutDoleance.values:
            raise ValidationError({"statut": "Statut inconnu."})
        with transaction.atomic():
            suivi = SuiviDoleance.objects.create(doleance=doleance, auteur=request.user, texte=texte, visible_du_deposant=visible)
            if statut and statut != doleance.statut:
                doleance.statut = statut
                doleance.save(update_fields=["statut", "modifie_le"])
        if visible and doleance.auteur_id:
            self._prevenir_deposant(doleance, f"Nouvelle étape de la médiation sur « {doleance.objet} » : {texte}")
        return Response(SuiviDoleanceSerializer(suivi, context=self.get_serializer_context()).data, status=201)


class LitigesSociauxView(ActeurAuditeMixin, APIView):
    """Les doléances qui ont atteint le seuil de litige social, vues du juridique (le poste de l'auteur, pas son identité)."""

    permission_classes = [PeutVoirLesLitiges]

    def get(self, request):
        litiges = Doleance.objects.filter(company=request.user.company, litige_signale_le__isnull=False).select_related("auteur")
        return Response({"seuil": services.seuil_litige(), "litiges": LitigeSerializer(litiges, many=True).data})


# --- Synthèse ------------------------------------------------------------------------------------------------------------------


class SyntheseRhView(ActeurAuditeMixin, APIView):
    """Les chiffres de la gestion RH : effectif, formations, congés, recrutement, médiation, contrats à terme."""

    permission_classes = [PeutVoirLaSyntheseRh]

    def get(self, request):
        company = request.user.company
        aujourdhui = timezone.localdate()
        par_role = {r["role"]: r["n"] for r in User.objects.filter(company=company, is_active=True).values("role").annotate(n=Count("id")).order_by()}
        conges = DemandeConge.objects.filter(company=company)
        ouvertes = Doleance.objects.filter(company=company).exclude(statut__in=(StatutDoleance.RESOLUE, StatutDoleance.SANS_SUITE))
        return Response(
            {
                "effectif": {"total": sum(par_role.values()), "par_role": par_role},
                "formations": services.resume_formations(services.suivi_formations(company, aujourdhui)),
                "conges": {
                    "en_attente": conges.filter(statut=StatutConge.EN_ATTENTE).count(),
                    "en_cours": conges.filter(statut=StatutConge.APPROUVE, debut__lte=aujourdhui, fin__gte=aujourdhui).count(),
                    "a_venir_30_jours": conges.filter(
                        statut=StatutConge.APPROUVE, debut__gt=aujourdhui, debut__lte=aujourdhui + datetime.timedelta(days=30)
                    ).count(),
                },
                "recrutement": {
                    "offres_ouvertes": OffreRecrutement.objects.filter(company=company, statut=StatutOffre.OUVERTE).count(),
                    "candidatures_a_traiter": Candidature.objects.filter(
                        company=company, offre__statut=StatutOffre.OUVERTE,
                        statut__in=(StatutCandidature.RECUE, StatutCandidature.PRESELECTIONNEE),
                    ).count(),
                },
                "mediation": {
                    "ouvertes": ouvertes.count(),
                    "litiges": ouvertes.filter(litige_signale_le__isnull=False).count(),
                    "a_traiter": ouvertes.filter(statut=StatutDoleance.DEPOSEE).count(),
                },
                "contrats": {
                    "a_terme": ContratAgent.objects.filter(
                        company=company, agent__is_active=True, date_fin__gte=aujourdhui,
                        date_fin__lte=aujourdhui + datetime.timedelta(days=PREAVIS_FIN_CONTRAT_JOURS),
                    ).exclude(type=TypeContrat.CDI).count(),
                },
            }
        )
