import re

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billetterie.models import DepartStatut
from colis import services
from colis.models import MAX_TENTATIVES_CODE, Colis, StatutColis, generer_code
from colis.permissions import ROLES_SUPERVISION_COLIS, CanUseColis
from colis.serializers import ColisSerializer
from configuration.services import exiger_fonction
from core.entiers import lire_entier
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role
from core.permissions import IsSameCompany
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import AffectationGare

CLE_IDEMPOTENCE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
MOTIF_MIN = 5


class ColisViewSet(
    CompanyScopedQuerysetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Bagages et colis, de l'enregistrement au retrait. Un colis enregistré ne se modifie pas : chaque étape est une
    action (charger, arriver, retirer, annuler), datée et attribuée."""

    queryset = Colis.objects.select_related(
        "depart__ligne__gare_depart", "depart__ligne__gare_arrivee", "ticket", "enregistre_par", "company"
    )
    serializer_class = ColisSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, CanUseColis]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # Le bagagiste travaille dans sa gare : ce qui part de chez lui et ce qui y arrive. Sans affectation, il voit
        # toute la compagnie (le chef de gare n'a pas encore composé son équipe).
        if user.role == Role.BAGAGISTE:
            affectation = AffectationGare.objects.filter(agent=user).first()
            if affectation is not None:
                queryset = queryset.filter(
                    Q(depart__ligne__gare_depart=affectation.gare_id) | Q(depart__ligne__gare_arrivee=affectation.gare_id)
                )
        parametres = self.request.query_params
        if parametres.get("depart"):
            depart = lire_entier(parametres["depart"])
            queryset = queryset.filter(depart_id=depart) if depart is not None else queryset.none()
        if parametres.get("statut"):
            queryset = queryset.filter(statut__in=parametres["statut"].split(","))
        if parametres.get("gare"):  # ce qui part de cette gare ou y arrive (l'écran du chef de gare)
            gare = lire_entier(parametres["gare"])
            queryset = (
                queryset.filter(Q(depart__ligne__gare_depart=gare) | Q(depart__ligne__gare_arrivee=gare))
                if gare is not None
                else queryset.none()
            )
        return queryset

    # --- enregistrement ---------------------------------------------------------------------------------------

    def create(self, request, *args, **kwargs):
        """Enregistre un colis et envoie son code de retrait au destinataire. Rejouable (en-tête Idempotency-Key)."""
        exiger_fonction(request.user, "enregistrement_colis")
        cle = request.headers.get("Idempotency-Key")
        if cle is not None and not CLE_IDEMPOTENCE_RE.match(cle):
            raise ValidationError({"Idempotency-Key": "1 à 64 caractères : lettres, chiffres, tirets et underscores."})
        if cle is None:
            return super().create(request, *args, **kwargs)

        existant = Colis.objects.filter(enregistre_par=request.user, cle_idempotence=cle).first()
        if existant is None:
            try:
                return super().create(request, *args, **kwargs)
            except IntegrityError:
                existant = Colis.objects.filter(enregistre_par=request.user, cle_idempotence=cle).first()
                if existant is None:
                    raise
        if str(request.data.get("depart")) != str(existant.depart_id) or (
            str(request.data.get("description", "")).strip() != existant.description
        ):
            raise ValidationError({"Idempotency-Key": "Cette clé a déjà servi pour un autre colis."}, code="conflit")
        return Response(
            self.get_serializer(existant).data, status=200, headers={"Idempotent-Replayed": "true"}
        )

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas enregistrer de colis.")
        code = generer_code()
        colis = Colis(**serializer.validated_data, company=user.company, enregistre_par=user, cle_idempotence=self.request.headers.get("Idempotency-Key"))
        colis.definir_code(code)
        colis.save()
        serializer.instance = colis
        services.notifier(colis, "enregistre", code=code)

    # --- étapes ------------------------------------------------------------------------------------------------

    def _verrouiller(self, pk):
        """Le colis à jour, sous verrou : deux agents ne le font pas avancer en même temps."""
        colis = self.get_object()
        return Colis.objects.select_for_update().select_related("depart__ligne__gare_arrivee", "company").get(pk=colis.pk)

    @action(detail=True, methods=["post"], url_path="charger")
    def charger(self, request, pk=None):
        with transaction.atomic():
            colis = self._verrouiller(pk)
            if colis.statut != StatutColis.ENREGISTRE:
                raise ValidationError(f"Ce colis est « {colis.get_statut_display().lower()} » : il ne peut plus être chargé.")
            depart = colis.depart
            if depart.statut != DepartStatut.PLANIFIE or FeuilleDeRoute.objects.filter(
                depart=depart, heure_depart_reelle__isnull=False
            ).exists():
                raise ValidationError("Ce départ est déjà parti : on ne charge plus de colis.")
            colis.statut, colis.charge_par, colis.charge_le = StatutColis.CHARGE, request.user, timezone.now()
            colis.save(update_fields=["statut", "charge_par", "charge_le"])
        services.notifier(colis, "charge")
        return Response(self.get_serializer(colis).data)

    @action(detail=True, methods=["post"], url_path="arriver")
    def arriver(self, request, pk=None):
        """Marque le colis arrivé quand le car est arrivé (la feuille de route le fait déjà pour tous les colis
        chargés ; ceci rattrape un colis resté « chargé » si ce n'a pas été fait)."""
        with transaction.atomic():
            colis = self._verrouiller(pk)
            if colis.statut != StatutColis.CHARGE:
                raise ValidationError(f"Ce colis est « {colis.get_statut_display().lower()} » : il n'est pas en route.")
            if colis.depart.statut != DepartStatut.TERMINE:
                raise ValidationError("Le car n'est pas encore arrivé.")
            colis.statut, colis.arrive_le = StatutColis.ARRIVE, timezone.now()
            colis.save(update_fields=["statut", "arrive_le"])
        services.notifier(colis, "arrive")
        return Response(self.get_serializer(colis).data)

    @action(detail=True, methods=["post"], url_path="retirer")
    def retirer(self, request, pk=None):
        """Remet le colis à celui qui présente le bon code. Cinq codes faux verrouillent le colis : seul un responsable
        renvoie alors un nouveau code (un colis ne se remet pas au hasard des essais)."""
        code = str(request.data.get("code", ""))
        if not code.strip():
            raise ValidationError({"code": "Saisissez le code de retrait présenté par le client."})
        refus = None
        with transaction.atomic():
            colis = self._verrouiller(pk)
            if colis.statut != StatutColis.ARRIVE:
                raise ValidationError(f"Ce colis est « {colis.get_statut_display().lower()} » : il n'est pas à retirer.")
            if colis.code_verrouille:
                refus = "Trop d'essais : ce colis est verrouillé. Demandez un nouveau code à votre chef de gare."
            elif not colis.code_correspond(code):
                colis.tentatives_code += 1
                colis.save(update_fields=["tentatives_code"])  # l'essai compte même si la réponse est un refus
                restants = MAX_TENTATIVES_CODE - colis.tentatives_code
                refus = (
                    "Code incorrect. " + (f"Il reste {restants} essai(s)." if restants else "Le colis est maintenant verrouillé.")
                )
            else:
                colis.statut, colis.retire_le, colis.retire_par = StatutColis.RETIRE, timezone.now(), request.user
                colis.retire_par_nom = str(request.data.get("retire_par_nom", "")).strip()[:255]
                colis.save(update_fields=["statut", "retire_le", "retire_par", "retire_par_nom"])
        if refus:
            raise ValidationError({"code": refus})
        services.notifier(colis, "retire")
        return Response(self.get_serializer(colis).data)

    @action(detail=True, methods=["post"], url_path="annuler")
    def annuler(self, request, pk=None):
        """Annule un enregistrement (motif obligatoire) : les frais sont à rendre, le colis sort du fret encaissé."""
        if request.user.role not in ROLES_SUPERVISION_COLIS:
            raise PermissionDenied("Seule la supervision annule un colis.")
        motif = str(request.data.get("motif", "")).strip()
        if len(motif) < MOTIF_MIN:
            raise ValidationError({"motif": f"Indiquez le motif de l'annulation ({MOTIF_MIN} caractères au moins)."})
        with transaction.atomic():
            colis = self._verrouiller(pk)
            if colis.statut not in (StatutColis.ENREGISTRE, StatutColis.CHARGE):
                raise ValidationError(f"Ce colis est « {colis.get_statut_display().lower()} » : il ne s'annule plus.")
            colis.statut, colis.annule_par, colis.annule_le = StatutColis.ANNULE, request.user, timezone.now()
            colis.motif_annulation = motif[:255]
            colis.save(update_fields=["statut", "annule_par", "annule_le", "motif_annulation"])
        services.notifier(colis, "annule")
        return Response(self.get_serializer(colis).data)

    @action(detail=True, methods=["post"], url_path="renvoyer-code")
    def renvoyer_code(self, request, pk=None):
        """Génère un nouveau code (l'ancien cesse de fonctionner, le verrouillage est levé) et l'envoie au destinataire :
        SMS perdu, code oublié, colis verrouillé."""
        if request.user.role not in ROLES_SUPERVISION_COLIS:
            raise PermissionDenied("Seule la supervision renvoie un code de retrait.")
        with transaction.atomic():
            colis = self._verrouiller(pk)
            if colis.statut not in (StatutColis.ENREGISTRE, StatutColis.CHARGE, StatutColis.ARRIVE):
                raise ValidationError(f"Ce colis est « {colis.get_statut_display().lower()} » : il n'a plus de code à renvoyer.")
            code = generer_code()
            colis.definir_code(code)
            colis.save(update_fields=["code_retrait_hash", "tentatives_code"])
        services.notifier(colis, "nouveau_code", code=code)
        return Response(self.get_serializer(colis).data)
