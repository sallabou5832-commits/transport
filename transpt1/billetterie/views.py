import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter, chef_de_gare_du_depart
from billetterie import planning, reservations
from billetterie.caisse import calculer_caisse, cloturer
from billetterie.models import (
    ClotureCaisse,
    Depart,
    DepartStatut,
    ModePaiement,
    ReservationHorsLigne,
    StatutTicket,
    Ticket,
)
from colis import services as colis_services
from colis.permissions import CanUseColis
from billetterie.permissions import (
    IsDispatchManagerAlways,
    IsDispatchManagerOrReadOnly,
    IsGuichetierOrAboveAlways,
    IsGuichetierOrAboveWrite,
)
from billetterie.serializers import ClotureCaisseSerializer, DepartSerializer, TicketSerializer
from configuration.regles import NiveauAutomatisation
from configuration.services import automatisation_au_moins, configuration_effective, exiger_fonction
from core.dates import lire_date, lire_date_heure
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role
from core.permissions import IsSameCompany
from core.serializers import nom_complet
from notifications.services import notifier_vente_ticket
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import VehiculeStatut


CLE_IDEMPOTENCE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

MOTIF_ANNULATION_MIN = 5


class ConflitIdempotence(APIException):
    status_code = 409
    default_detail = "Cette clé d'idempotence a déjà servi pour une vente différente."
    default_code = "conflit_idempotence"


class BilletterieViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")
        serializer.save(company=user.company)


class DepartViewSet(BilletterieViewSet):
    queryset = Depart.objects.select_related("ligne", "vehicule", "chauffeur", "company")
    serializer_class = DepartSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsDispatchManagerOrReadOnly]

    def get_queryset(self):
        # Places réservées par départ, calculées en une requête (évite un appel par départ).
        return super().get_queryset().annotate(
            _places_reservees=Coalesce(
                Sum(
                    "reservations_hors_ligne__places",
                    filter=Q(reservations_hors_ligne__expire_le__gt=timezone.now()),
                ),
                0,
            )
        )

    @action(detail=True, methods=["get"], url_path="places-restantes")
    def places_restantes(self, request, pk=None):
        depart = self.get_object()
        return Response(
            {
                "depart": depart.id,
                "capacite": depart.vehicule.capacite,
                "places_vendues": depart.places_vendues,
                "places_restantes": depart.places_restantes,
                "places_reservees": depart.places_reservees,
                "places_disponibles": depart.places_disponibles,
            }
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="remplacants-possibles",
        permission_classes=[IsAuthenticated, IsSameCompany, IsDispatchManagerAlways],
    )
    def remplacants_possibles(self, request, pk=None):
        """Véhicules et chauffeurs libres pouvant remplacer ceux de ce départ.

        Un véhicule proposé est disponible, assez grand pour les places déjà vendues ou
        réservées, et sans autre départ proche ; un chauffeur proposé n'a pas d'autre départ
        proche. Réservé aux rôles de planification (c'est un annuaire des chauffeurs libres).
        """
        # « Planning assisté » : le système propose, le régulateur valide. Optionnel, selon le niveau d'automatisation.
        if not automatisation_au_moins(request.user, NiveauAutomatisation.ASSISTE):
            raise PermissionDenied("Le planning assisté est désactivé pour votre poste : choisissez le remplaçant vous-même.")
        depart = self.get_object()
        vehicules = (
            planning.vehicules_disponibles(
                depart.company_id,
                depart.date_heure,
                places_min=depart.places_vendues + depart.places_reservees,
                exclure_depart_id=depart.pk,
            )
            .filter(statut=VehiculeStatut.DISPONIBLE)  # remplacement : on ne propose que ce qui est prêt à rouler
            .exclude(pk=depart.vehicule_id)
        )
        chauffeurs = planning.chauffeurs_disponibles(
            depart.company_id, depart.date_heure, exclure_depart_id=depart.pk
        ).exclude(pk=depart.chauffeur_id)
        self._alerter_penurie(depart, vehicules_trouves=bool(vehicules), chauffeurs_trouves=bool(chauffeurs))
        return Response(
            {
                "depart": depart.id,
                "vehicules": [
                    {"id": v.id, "immatriculation": v.immatriculation, "capacite": v.capacite}
                    for v in vehicules
                ],
                "chauffeurs": [
                    {"id": c.id, "nom": nom_complet(c), "role": c.role} for c in chauffeurs
                ],
            }
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="plan-chargement",
        permission_classes=[IsAuthenticated, IsSameCompany, CanUseColis],
    )
    def plan_chargement(self, request, pk=None):
        """Aide au chargement : répartition du poids des colis en soute (avant, milieu, arrière) pour équilibrer le car."""
        return Response(colis_services.plan_chargement(self.get_object()))

    @staticmethod
    def _alerter_penurie(depart, *, vehicules_trouves, chauffeurs_trouves):
        """Le régulateur cherche un remplaçant et il n'y en a aucun : c'est une pénurie, que le chef de gare et le
        directeur des opérations doivent connaître sans que le régulateur ait à les appeler. Une seule alerte par
        départ et par nature de pénurie."""
        for manque, trouve in (("véhicule", vehicules_trouves), ("chauffeur", chauffeurs_trouves)):
            if trouve:
                continue
            alerter(
                depart.company,
                type=TypeAlerte.PENURIE,
                gravite=GraviteAlerte.ATTENTION,
                titre=f"Pénurie de {manque} : {depart.ligne.nom}",
                message=(
                    f"Aucun {manque} libre pour remplacer sur le départ {depart.ligne.nom} du "
                    f"{timezone.localtime(depart.date_heure):%d/%m à %H:%M}. Un arbitrage est nécessaire."
                ),
                roles=[Role.DIRECTEUR_EXPLOITATION],
                destinataires=[chef_de_gare_du_depart(depart)],
                objet=depart,
                cle=f"penurie:{manque}:{depart.pk}",
            )

    @action(
        detail=False,
        methods=["get"],
        url_path="disponibilites",
        permission_classes=[IsAuthenticated, IsDispatchManagerAlways],
    )
    def disponibilites(self, request):
        """Véhicules et chauffeurs libres à une date et une heure données (`?date_heure=`, ISO 8601), pour planifier
        un nouveau départ. `?places_min=` ne garde que les véhicules assez grands. Mêmes règles que la création."""
        if request.user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne planifie pas de départ.")
        date_heure = lire_date_heure(request.query_params.get("date_heure"))
        if date_heure is None:
            raise ValidationError({"date_heure": "Date et heure requises (format ISO 8601, ex. 2030-05-17T08:30)."})
        try:
            places_min = int(request.query_params.get("places_min") or 0)
        except ValueError:
            raise ValidationError({"places_min": "Nombre entier attendu."})

        vehicules = planning.vehicules_disponibles(request.user.company_id, date_heure, places_min=places_min)
        chauffeurs = planning.chauffeurs_disponibles(request.user.company_id, date_heure)
        return Response(
            {
                "date_heure": date_heure,
                "vehicules": [
                    {"id": v.id, "immatriculation": v.immatriculation, "capacite": v.capacite, "statut": v.statut}
                    for v in vehicules
                ],
                "chauffeurs": [{"id": c.id, "nom": nom_complet(c), "role": c.role} for c in chauffeurs],
            }
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="planifier",
        permission_classes=[IsAuthenticated, IsDispatchManagerAlways],
    )
    def planifier(self, request):
        """Planifie un départ et sa feuille de route en une seule opération (tout ou rien) : le chauffeur voit sa
        feuille dès la planification. Corps : ligne, vehicule, chauffeur, date_heure. Mêmes règles que POST /departs/."""
        if request.user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas planifier de départ.")
        exiger_fonction(request.user, "planification_departs")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            depart = serializer.save(company=request.user.company)
            feuille = FeuilleDeRoute.objects.create(
                depart=depart, chauffeur=depart.chauffeur, company=depart.company, heure_depart_prevue=depart.date_heure
            )
        return Response({**self.get_serializer(depart).data, "feuille_de_route": feuille.id}, status=201)

    def perform_destroy(self, instance):
        """Seul un départ planifié, sans ticket (même annulé) et dont la feuille n'a pas démarré se supprime : c'est
        la correction d'une erreur de planning, pas un moyen d'effacer une vente ou un trajet."""
        if instance.statut != DepartStatut.PLANIFIE:
            raise ValidationError("Seul un départ planifié peut être supprimé.")
        if instance.tickets.exists():
            raise ValidationError(
                "Ce départ a des tickets (même annulés) : il ne peut pas être supprimé. Modifiez son heure ou son véhicule."
            )
        with transaction.atomic():
            feuille = FeuilleDeRoute.objects.filter(depart=instance).first()
            if feuille is not None:
                if feuille.heure_depart_reelle is not None:
                    raise ValidationError("Ce départ a déjà démarré : il ne peut pas être supprimé.")
                feuille.delete()
            instance.delete()


class TicketViewSet(BilletterieViewSet):
    queryset = Ticket.objects.select_related("depart", "depart__vehicule", "company", "vendu_par")
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsGuichetierOrAboveWrite]

    # Un ticket vendu est une pièce de caisse : ni modification (un prix ne se « corrige » pas après encaissement),
    # ni suppression, pour personne. Une erreur se corrige par une annulation tracée (`annuler`).
    def _verrouille(self, request):
        raise MethodNotAllowed(
            request.method, detail="Un ticket vendu ne se modifie ni ne se supprime : utilisez l'annulation."
        )

    def update(self, request, *args, **kwargs):
        self._verrouille(request)

    def partial_update(self, request, *args, **kwargs):
        self._verrouille(request)

    def destroy(self, request, *args, **kwargs):
        self._verrouille(request)

    @action(
        detail=True,
        methods=["post"],
        url_path="annuler",
        permission_classes=[IsAuthenticated, IsSameCompany, IsDispatchManagerAlways],
    )
    def annuler(self, request, pk=None):
        """Annule un ticket (motif obligatoire) : la place est libérée, la vente sort des recettes, le ticket
        reste visible avec l'auteur, la date et le motif. Réservé aux rôles de supervision : le guichetier qui a
        vendu ne peut pas annuler sa propre vente."""
        motif = str(request.data.get("motif", "")).strip()
        if len(motif) < MOTIF_ANNULATION_MIN:
            raise ValidationError(
                {"motif": f"Indiquez le motif de l'annulation ({MOTIF_ANNULATION_MIN} caractères au moins)."}
            )
        ticket = self.get_object()
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
            if ticket.statut == StatutTicket.ANNULE:
                raise ValidationError("Ce ticket est déjà annulé.")
            depart = Depart.objects.select_for_update().get(pk=ticket.depart_id)

            ticket.statut = StatutTicket.ANNULE
            ticket.annule_par = request.user
            ticket.annule_le = timezone.now()
            ticket.motif_annulation = motif[:255]
            ticket.save(update_fields=["statut", "annule_par", "annule_le", "motif_annulation"])

            # Un départ terminé n'a plus de places à rendre : l'annulation (remboursement) reste possible.
            if depart.statut != DepartStatut.TERMINE and depart.places_vendues > 0:
                depart.places_vendues -= 1
                depart.save(update_fields=["places_vendues"])
        return Response(self.get_serializer(ticket).data)

    @staticmethod
    def _cle_idempotence(request):
        """La clé d'idempotence de la requête (en-tête Idempotency-Key), ou None."""
        cle = request.headers.get("Idempotency-Key")
        if cle is None:
            return None
        if not CLE_IDEMPOTENCE_RE.match(cle):
            raise ValidationError(
                {"Idempotency-Key": "1 à 64 caractères : lettres, chiffres, tirets et underscores."}
            )
        return cle

    def _ticket_idempotent(self, user, cle):
        return Ticket.objects.filter(vendu_par=user, cle_idempotence=cle).first()

    @staticmethod
    def _meme_demande(ticket, data):
        try:
            return (
                int(data.get("depart")) == ticket.depart_id
                and str(data.get("passager_nom", "")).strip() == ticket.passager_nom
                and str(data.get("passager_telephone", "")).strip() == ticket.passager_telephone
                and (data.get("prix") in (None, "") or Decimal(str(data.get("prix"))) == ticket.prix)
                and data.get("mode_paiement") == ticket.mode_paiement
            )
        except (TypeError, ValueError, InvalidOperation):
            return False

    def create(self, request, *args, **kwargs):
        """Vente d'un ticket, idempotente si le client fournit un en-tête Idempotency-Key.

        Rejouer la même vente (réponse perdue, nouvelle tentative de synchronisation
        du mobile) renvoie le ticket déjà créé au lieu d'en créer un second, sans
        toucher au compteur de places ni renvoyer de notification. Le rejeu est
        traité AVANT toute validation : il doit réussir même si le départ est
        devenu complet ou terminé depuis la première vente.
        """
        exiger_fonction(request.user, "vente_ticket")
        cle = self._cle_idempotence(request)
        if cle is None:
            return super().create(request, *args, **kwargs)

        existant = self._ticket_idempotent(request.user, cle)
        if existant is None:
            try:
                return super().create(request, *args, **kwargs)
            except IntegrityError:
                # Deux requêtes simultanées avec la même clé : l'autre a gagné.
                existant = self._ticket_idempotent(request.user, cle)
                if existant is None:
                    raise

        if not self._meme_demande(existant, request.data):
            raise ConflitIdempotence()
        return Response(
            self.get_serializer(existant).data,
            status=200,
            headers={"Idempotent-Replayed": "true"},
        )

    def perform_create(self, serializer):
        user = self.request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas créer cet objet.")

        depart_pk = serializer.validated_data["depart"].pk
        with transaction.atomic():
            depart = (
                Depart.objects.select_for_update()
                .select_related("vehicule", "ligne")
                .get(pk=depart_pk)
            )
            self._reserver_une_place(depart, user)
            serializer.save(
                vendu_par=user,
                company=user.company,
                cle_idempotence=self._cle_idempotence(self.request),
            )
            depart.places_vendues += 1
            depart.save(update_fields=["places_vendues"])

        notifier_vente_ticket(serializer.instance, depart)

    @staticmethod
    def _reserver_une_place(depart, user):
        """Vérifie qu'une place existe pour `user` et la consomme (sous verrou du départ).

        Un guichetier qui a réservé des places pour la vente hors ligne les utilise en
        premier (elles lui sont garanties). Sinon il ne peut vendre que les places que
        personne d'autre n'a réservées.
        """
        maintenant = timezone.now()
        reservation = (
            ReservationHorsLigne.objects.select_for_update()
            .filter(depart=depart, guichetier=user, expire_le__gt=maintenant)
            .first()
        )
        if reservation is not None:
            if reservation.places > 1:
                reservation.places -= 1
                reservation.save(update_fields=["places", "mis_a_jour_le"])
            else:
                reservation.delete()
            return

        capacite = depart.vehicule.capacite
        if depart.places_vendues >= capacite:
            raise ValidationError({"depart": "Plus aucune place disponible sur ce départ."})
        reservees = (
            ReservationHorsLigne.objects.filter(depart=depart, expire_le__gt=maintenant).aggregate(
                total=Sum("places")
            )["total"]
            or 0
        )
        if depart.places_vendues + reservees >= capacite:
            raise ValidationError(
                {
                    "depart": "Les dernières places de ce départ sont réservées pour des "
                    "ventes hors ligne d'autres guichets."
                }
            )

    @action(
        detail=False,
        methods=["post", "delete"],
        url_path="reserver-hors-ligne",
        permission_classes=[IsAuthenticated, IsGuichetierOrAboveAlways],
    )
    def reserver_hors_ligne(self, request):
        """POST : met de côté des places pour la vente hors ligne du guichetier connecté.

        Retourne ses réservations actives ; à rappeler régulièrement tant que le réseau est
        disponible (complète après des ventes, prolonge l'expiration).
        DELETE : rend toutes ses places réservées (fin de service, déconnexion).
        """
        user = request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne peut pas réserver de places.")
        if request.method == "DELETE":
            reservations.liberer_reservations(user)
            return Response(status=204)
        accordees = reservations.accorder_reservations(user)
        return Response(
            [
                {"depart": r.depart_id, "places": r.places, "expire_le": r.expire_le}
                for r in accordees
            ]
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="cloture-caisse",
        permission_classes=[IsAuthenticated, IsSameCompany, IsGuichetierOrAboveAlways],
    )
    def cloture_caisse(self, request):
        user = request.user
        raw_guichetier_id = request.query_params.get("guichetier", user.id)
        date_debut = lire_date(request.query_params.get("date_debut"))
        date_fin = lire_date(request.query_params.get("date_fin"))

        if date_debut is None or date_fin is None:
            raise ValidationError(
                "Les paramètres date_debut et date_fin (format AAAA-MM-JJ) sont requis."
            )

        try:
            guichetier_id = int(raw_guichetier_id)
        except (TypeError, ValueError):
            raise ValidationError({"guichetier": "Identifiant invalide."})

        if user.role == Role.GUICHETIER and guichetier_id != user.id:
            raise PermissionDenied(
                "Vous ne pouvez consulter que votre propre clôture de caisse."
            )

        # La compagnie vient de l'utilisateur, pas de la requête : le superadmin (sans compagnie) voit toutes les caisses.
        caisse = calculer_caisse(
            None if user.company_id is None else user.company_id, guichetier_id, date_debut, date_fin
        )
        return Response({"guichetier": guichetier_id, "date_debut": date_debut, "date_fin": date_fin, **caisse})


class ClotureCaisseViewSet(
    CompanyScopedQuerysetMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Clôtures de caisse : la photo figée de la caisse d'un guichetier pour un jour, transmise à son chef de gare.

    Selon le niveau d'automatisation du guichetier : **manuel**, il ne clôture pas lui-même (son chef le fait pour lui) ;
    **assisté**, il clôture d'un geste (le système a déjà fait les totaux) ; **automatique**, la clôture se fait seule en
    fin de journée (`manage.py cloturer_caisses`) et le guichetier n'a plus qu'à vérifier."""

    queryset = ClotureCaisse.objects.select_related("guichetier", "company", "cloture_par")
    serializer_class = ClotureCaisseSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsGuichetierOrAboveAlways]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == Role.GUICHETIER:  # chacun ne voit que sa caisse ; la supervision voit celles de la compagnie
            queryset = queryset.filter(guichetier_id=user.id)
        elif self.request.query_params.get("guichetier", "").isdigit():
            queryset = queryset.filter(guichetier_id=int(self.request.query_params["guichetier"]))
        date = lire_date(self.request.query_params.get("date"))
        return queryset.filter(date=date) if date else queryset

    def create(self, request, *args, **kwargs):
        """Clôture la caisse du jour (ou de `date`). Le guichetier clôture la sienne ; la supervision clôture celle d'un
        guichetier (`guichetier` = son identifiant), par exemple s'il a oublié ou si son niveau est « manuel »."""
        user = request.user
        if user.company_id is None:
            raise ValidationError("Un compte sans compagnie ne clôture pas de caisse.")
        exiger_fonction(user, "cloture_caisse")
        date = lire_date(request.data.get("date")) or timezone.localdate()
        if date > timezone.localdate():
            raise ValidationError({"date": "On ne clôture pas la caisse d'un jour à venir."})

        if user.role == Role.GUICHETIER:
            if not automatisation_au_moins(user, NiveauAutomatisation.ASSISTE):
                raise PermissionDenied(
                    "Votre niveau est « manuel » : remettez votre caisse à votre chef de gare, qui la clôture."
                )
            guichetier = user
        else:
            try:
                guichetier = get_user_model().objects.get(
                    pk=int(request.data.get("guichetier")), company_id=user.company_id, role=Role.GUICHETIER
                )
            except (TypeError, ValueError, get_user_model().DoesNotExist):
                raise ValidationError({"guichetier": "Indiquez le guichetier dont vous clôturez la caisse."})

        cloture, creee = cloturer(guichetier, date, par=user)
        if not creee:
            raise ValidationError("La caisse de ce guichetier est déjà clôturée pour ce jour.")
        return Response(self.get_serializer(cloture).data, status=201)

    @action(detail=False, methods=["get"], url_path="etat")
    def etat(self, request):
        """L'état des caisses d'un jour (`?date=`, aujourd'hui par défaut) : pour chaque guichetier concerné, ses totaux en
        direct et sa clôture s'il y en a une. Le guichetier ne voit que la sienne ; le chef de gare, celles de son équipe ;
        les autres rôles de supervision, toute la compagnie."""
        user = request.user
        if user.company_id is None:
            return Response([])
        date = lire_date(request.query_params.get("date")) or timezone.localdate()
        guichetiers = get_user_model().objects.filter(company_id=user.company_id, role=Role.GUICHETIER)
        if user.role == Role.GUICHETIER:
            guichetiers = guichetiers.filter(pk=user.pk)
        elif user.role == Role.CHEF_GARE:
            guichetiers = guichetiers.filter(affectation_gare__gare__chef=user)
        clotures = {c.guichetier_id: c for c in ClotureCaisse.objects.filter(company_id=user.company_id, date=date)}
        etat = []
        for guichetier in guichetiers.order_by("username"):
            cloture = clotures.get(guichetier.pk)
            etat.append(
                {
                    "guichetier": guichetier.pk,
                    "guichetier_nom": nom_complet(guichetier),
                    "date": date,
                    "niveau_automatisation": configuration_effective(guichetier)["niveau_automatisation"],
                    "caisse": calculer_caisse(user.company_id, guichetier.pk, date, date),
                    "cloture": self.get_serializer(cloture).data if cloture else None,
                }
            )
        return Response(etat)
