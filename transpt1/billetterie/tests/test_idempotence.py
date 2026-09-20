"""Vente de ticket idempotente : rejouer la même vente ne crée pas de doublon."""

from unittest.mock import patch

import pytest
from django.db import IntegrityError

from billetterie.models import DepartStatut, ModePaiement, Ticket
from billetterie.views import TicketViewSet
from notifications.models import NotificationLog

VENTE = {
    "passager_nom": "Awa Koné",
    "passager_telephone": "+2250700000000",
    "prix": "5000.00",
    "mode_paiement": ModePaiement.ESPECES,
}
CLE = "7f4b2c1e-0a8d-4a52-9d55-1f2f5c0e9a11"


def vendre(api_client, depart, cle=CLE, **modifs):
    donnees = {"depart": depart.id, **VENTE, **modifs}
    extra = {"HTTP_IDEMPOTENCY_KEY": cle} if cle is not None else {}
    return api_client.post("/api/tickets/", donnees, **extra)


@pytest.mark.django_db
class TestIdempotence:
    def test_la_premiere_vente_cree_le_ticket_et_memorise_la_cle(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)

        response = vendre(api_client, depart_a)

        assert response.status_code == 201
        assert "Idempotent-Replayed" not in response
        assert Ticket.objects.get().cle_idempotence == CLE

    def test_rejouer_la_meme_vente_renvoie_le_meme_ticket_sans_doublon(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        premiere = vendre(api_client, depart_a)

        rejeu = vendre(api_client, depart_a)

        assert rejeu.status_code == 200
        assert rejeu["Idempotent-Replayed"] == "true"
        assert rejeu.data["id"] == premiere.data["id"]
        assert Ticket.objects.count() == 1
        depart_a.refresh_from_db()
        assert depart_a.places_vendues == 1  # la place n'est décomptée qu'une fois

    def test_le_rejeu_n_envoie_pas_une_seconde_notification_au_client(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        vendre(api_client, depart_a)
        avant = NotificationLog.objects.count()
        assert avant > 0

        vendre(api_client, depart_a)
        vendre(api_client, depart_a)

        assert NotificationLog.objects.count() == avant

    def test_le_rejeu_reussit_meme_si_le_depart_est_devenu_complet(
        self, api_client, guichetier_a, depart_a, vehicule_a
    ):
        # Dernière place vendue : un rejeu (réponse perdue) ne doit pas être refusé « complet ».
        vehicule_a.capacite = 1
        vehicule_a.save()
        api_client.force_authenticate(user=guichetier_a)
        vendre(api_client, depart_a)

        rejeu = vendre(api_client, depart_a)

        assert rejeu.status_code == 200
        assert Ticket.objects.count() == 1

    def test_le_rejeu_reussit_meme_si_le_depart_est_termine_entre_temps(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        vendre(api_client, depart_a)
        depart_a.statut = DepartStatut.TERMINE
        depart_a.save()

        rejeu = vendre(api_client, depart_a)

        assert rejeu.status_code == 200
        assert Ticket.objects.count() == 1

    def test_meme_cle_avec_une_vente_differente_est_refusee(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        vendre(api_client, depart_a)

        for changement in (
            {"prix": "6000.00"},
            {"passager_nom": "Koffi Yao"},
            {"passager_telephone": "+2250500000000"},
            {"mode_paiement": ModePaiement.MOBILE_MONEY},
        ):
            reponse = vendre(api_client, depart_a, **changement)
            assert reponse.status_code == 409, changement

        assert Ticket.objects.count() == 1

    def test_prix_equivalent_ecrit_autrement_est_le_meme_rejeu(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        vendre(api_client, depart_a, prix="5000.00")

        assert vendre(api_client, depart_a, prix="5000").status_code == 200

    def test_sans_cle_chaque_requete_cree_un_ticket_comme_avant(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)

        assert vendre(api_client, depart_a, cle=None).status_code == 201
        assert vendre(api_client, depart_a, cle=None).status_code == 201

        assert Ticket.objects.count() == 2
        assert set(Ticket.objects.values_list("cle_idempotence", flat=True)) == {None}

    def test_la_cle_est_propre_a_chaque_vendeur(
        self, api_client, guichetier_a, guichetier_a2, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        vendre(api_client, depart_a)
        api_client.force_authenticate(user=guichetier_a2)

        reponse = vendre(api_client, depart_a)  # même clé, autre guichetier

        assert reponse.status_code == 201
        assert Ticket.objects.count() == 2

    @pytest.mark.parametrize("cle", ["", "a" * 65, "clé avec espaces", "a/b", "x;y"])
    def test_cle_invalide_refusee(self, api_client, guichetier_a, depart_a, cle):
        api_client.force_authenticate(user=guichetier_a)

        reponse = vendre(api_client, depart_a, cle=cle)

        assert reponse.status_code == 400
        assert "Idempotency-Key" in reponse.data
        assert not Ticket.objects.exists()

    def test_deux_requetes_simultanees_ne_creent_qu_un_ticket(
        self, api_client, guichetier_a, depart_a
    ):
        # La requête « perdante » voit d'abord l'absence de ticket, puis se heurte à la
        # contrainte d'unicité posée par la gagnante : elle doit rendre ce ticket.
        api_client.force_authenticate(user=guichetier_a)
        gagnante = vendre(api_client, depart_a)
        recherche = TicketViewSet._ticket_idempotent
        appels = []

        def recherche_tardive(self, user, cle):
            appels.append(1)
            return None if len(appels) == 1 else recherche(self, user, cle)

        with patch.object(TicketViewSet, "_ticket_idempotent", recherche_tardive), patch.object(
            TicketViewSet, "perform_create", side_effect=IntegrityError("doublon")
        ):
            perdante = vendre(api_client, depart_a)

        assert perdante.status_code == 200
        assert perdante.data["id"] == gagnante.data["id"]
        assert Ticket.objects.count() == 1

    def test_une_autre_violation_d_integrite_n_est_pas_masquee(
        self, api_client, guichetier_a, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        api_client.raise_request_exception = False

        with patch.object(TicketViewSet, "perform_create", side_effect=IntegrityError("autre")):
            reponse = vendre(api_client, depart_a)

        assert reponse.status_code == 500
        assert not Ticket.objects.exists()

    def test_les_clients_web_peuvent_envoyer_l_en_tete(self, api_client, settings):
        # Sans cela, la requête préalable CORS d'un navigateur refuserait Idempotency-Key.
        settings.CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]

        reponse = api_client.options(
            "/api/tickets/",
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="idempotency-key,content-type,authorization",
        )

        assert reponse.status_code == 200
        assert "idempotency-key" in reponse["Access-Control-Allow-Headers"].lower()
