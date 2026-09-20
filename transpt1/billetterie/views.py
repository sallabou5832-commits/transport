import re
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billetterie import reservations
from billetterie.models import Depart, ModePaiement, ReservationHorsLigne, Ticket
from billetterie.permissions import (
    IsDispatchManagerOrReadOnly,
    IsGuichetierOrAboveAlways,
    IsGuichetierOrAboveWrite,
)
from billetterie.serializers import DepartSerializer, TicketSerializer
from core.mixins import CompanyScopedQuerysetMixin
from core.models import Role
from core.permissions import IsSameCompany
from notifications.services import notifier_vente_ticket


CLE_IDEMPOTENCE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


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


class TicketViewSet(BilletterieViewSet):
    queryset = Ticket.objects.select_related("depart", "depart__vehicule", "company", "vendu_par")
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated, IsSameCompany, IsGuichetierOrAboveWrite]

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
                and Decimal(str(data.get("prix"))) == ticket.prix
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
        date_debut = parse_date(request.query_params.get("date_debut") or "")
        date_fin = parse_date(request.query_params.get("date_fin") or "")

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

        base_qs = self.get_queryset().filter(
            vendu_par_id=guichetier_id,
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
        )

        def totals(queryset):
            agg = queryset.aggregate(nombre=Count("id"), montant=Sum("prix"))
            return agg["nombre"] or 0, agg["montant"] or Decimal("0")

        nombre_tickets, montant_total = totals(base_qs)
        nombre_especes, montant_especes = totals(
            base_qs.filter(mode_paiement=ModePaiement.ESPECES)
        )
        nombre_mobile, montant_mobile = totals(
            base_qs.filter(mode_paiement=ModePaiement.MOBILE_MONEY)
        )

        return Response(
            {
                "guichetier": guichetier_id,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "nombre_tickets": nombre_tickets,
                "montant_total": montant_total,
                "especes": {"nombre": nombre_especes, "montant": montant_especes},
                "mobile_money": {"nombre": nombre_mobile, "montant": montant_mobile},
            }
        )
