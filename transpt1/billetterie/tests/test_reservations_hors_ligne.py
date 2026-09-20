"""Places réservées pour la vente hors ligne : le guichetier hors ligne ne peut pas voir sa
vente refusée à la synchronisation parce qu'un autre guichet a pris la dernière place."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, ReservationHorsLigne, Ticket
from core.models import Role

RESERVER = "/api/tickets/reserver-hors-ligne/"


def vendre(api_client, depart, nom="Awa", **extra):
    return api_client.post(
        "/api/tickets/",
        {
            "depart": depart.id,
            "passager_nom": nom,
            "passager_telephone": "+2250700000000",
            "prix": "5000.00",
            "mode_paiement": ModePaiement.ESPECES,
        },
        **extra,
    )


def reserver(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client.post(RESERVER)


def places_reservees(user, depart):
    r = ReservationHorsLigne.objects.filter(guichetier=user, depart=depart).first()
    return r.places if r else 0


def autre_depart(depart_a, **modifs):
    valeurs = {
        "ligne": depart_a.ligne,
        "vehicule": depart_a.vehicule,
        "chauffeur": depart_a.chauffeur,
        "company": depart_a.company,
        "date_heure": timezone.now() + datetime.timedelta(hours=4),
        "statut": DepartStatut.PLANIFIE,
    }
    return Depart.objects.create(**{**valeurs, **modifs})


@pytest.mark.django_db
class TestAttributionDesReservations:
    def test_le_guichetier_recoit_le_quota_sur_les_departs_a_venir(
        self, api_client, guichetier_a, depart_a
    ):
        response = reserver(api_client, guichetier_a)

        assert response.status_code == 200
        assert len(response.data) == 1
        reservation = response.data[0]
        assert reservation["depart"] == depart_a.id
        assert reservation["places"] == 2  # quota par défaut
        assert places_reservees(guichetier_a, depart_a) == 2

    def test_jamais_plus_que_les_places_libres(
        self, api_client, guichetier_a, depart_a, vehicule_a
    ):
        depart_a.places_vendues = vehicule_a.capacite - 1  # une seule place libre
        depart_a.save()

        reserver(api_client, guichetier_a)

        assert places_reservees(guichetier_a, depart_a) == 1

    def test_un_depart_complet_ne_donne_rien(self, api_client, guichetier_a, depart_a, vehicule_a):
        depart_a.places_vendues = vehicule_a.capacite
        depart_a.save()

        response = reserver(api_client, guichetier_a)

        assert response.data == []
        assert not ReservationHorsLigne.objects.exists()

    def test_deux_guichetiers_se_partagent_les_places_sans_les_depasser(
        self, api_client, guichetier_a, guichetier_a2, depart_a, vehicule_a
    ):
        # Capacité 3, quota 2 : le premier prend 2, le second ne peut prendre que la dernière.
        reserver(api_client, guichetier_a)
        reserver(api_client, guichetier_a2)

        assert places_reservees(guichetier_a, depart_a) == 2
        assert places_reservees(guichetier_a2, depart_a) == 1
        total = sum(ReservationHorsLigne.objects.values_list("places", flat=True))
        depart_a.refresh_from_db()
        assert depart_a.places_vendues + total <= vehicule_a.capacite

    def test_rappeler_complete_sans_doubler_et_prolonge(self, api_client, guichetier_a, depart_a):
        reserver(api_client, guichetier_a)
        avant = ReservationHorsLigne.objects.get().expire_le

        reserver(api_client, guichetier_a)

        assert ReservationHorsLigne.objects.count() == 1
        assert places_reservees(guichetier_a, depart_a) == 2
        assert ReservationHorsLigne.objects.get().expire_le >= avant

    def test_seuls_les_departs_planifies_a_venir_et_dans_l_horizon(
        self, api_client, guichetier_a, depart_a, company_b
    ):
        termine = autre_depart(depart_a, statut=DepartStatut.TERMINE)
        en_cours = autre_depart(depart_a, statut=DepartStatut.EN_COURS)
        passe = autre_depart(depart_a, date_heure=timezone.now() - datetime.timedelta(hours=1))
        lointain = autre_depart(depart_a, date_heure=timezone.now() + datetime.timedelta(hours=48))

        response = reserver(api_client, guichetier_a)

        assert [r["depart"] for r in response.data] == [depart_a.id]
        exclus = {termine.id, en_cours.id, passe.id, lointain.id}
        assert not ReservationHorsLigne.objects.filter(depart_id__in=exclus).exists()

    def test_les_departs_d_une_autre_compagnie_sont_ignores(
        self, api_client, guichetier_a, depart_a, company_b, chauffeur_a
    ):
        from reseau.models import Gare, Ligne, Vehicule

        gare = Gare.objects.create(nom="G", ville="V", company=company_b)
        ligne = Ligne.objects.create(nom="L", gare_depart=gare, gare_arrivee=gare, company=company_b)
        vehicule = Vehicule.objects.create(immatriculation="CI-9-ZZ", capacite=30, company=company_b)
        autre = Depart.objects.create(
            ligne=ligne, vehicule=vehicule, chauffeur=chauffeur_a, company=company_b,
            date_heure=timezone.now() + datetime.timedelta(hours=3),
        )

        reserver(api_client, guichetier_a)

        assert not ReservationHorsLigne.objects.filter(depart=autre).exists()

    def test_expiration_est_la_plus_proche_du_depart_et_de_la_duree_maximale(
        self, api_client, guichetier_a, depart_a, settings
    ):
        proche = depart_a  # dans 2 h : expire au départ
        lointain = autre_depart(depart_a, date_heure=timezone.now() + datetime.timedelta(hours=20))

        reserver(api_client, guichetier_a)

        r_proche = ReservationHorsLigne.objects.get(depart=proche)
        r_lointain = ReservationHorsLigne.objects.get(depart=lointain)
        assert r_proche.expire_le == proche.date_heure
        ttl = datetime.timedelta(hours=settings.BILLETTERIE_RESERVATION_TTL_HEURES)
        assert abs((r_lointain.expire_le - (timezone.now() + ttl)).total_seconds()) < 30

    def test_quota_zero_desactive_la_fonction(self, api_client, guichetier_a, depart_a, settings):
        settings.BILLETTERIE_QUOTA_HORS_LIGNE = 0

        response = reserver(api_client, guichetier_a)

        assert response.data == []
        assert not ReservationHorsLigne.objects.exists()

    def test_liberer_rend_les_places(self, api_client, guichetier_a, guichetier_a2, depart_a):
        reserver(api_client, guichetier_a)

        response = api_client.delete(RESERVER)

        assert response.status_code == 204
        assert not ReservationHorsLigne.objects.exists()
        reserver(api_client, guichetier_a2)
        assert places_reservees(guichetier_a2, depart_a) == 2  # le quota complet est de nouveau libre

    def test_liberer_ne_touche_pas_les_reservations_des_autres(
        self, api_client, guichetier_a, guichetier_a2, depart_a
    ):
        reserver(api_client, guichetier_a)
        reserver(api_client, guichetier_a2)

        api_client.force_authenticate(user=guichetier_a)
        api_client.delete(RESERVER)

        assert places_reservees(guichetier_a2, depart_a) == 1


@pytest.mark.django_db
class TestVenteAvecReservations:
    def test_la_vente_du_titulaire_consomme_sa_reservation(
        self, api_client, guichetier_a, depart_a
    ):
        reserver(api_client, guichetier_a)

        assert vendre(api_client, depart_a).status_code == 201

        assert places_reservees(guichetier_a, depart_a) == 1
        depart_a.refresh_from_db()
        assert depart_a.places_vendues == 1

    def test_derniere_place_reservee_puis_reservation_supprimee(
        self, api_client, guichetier_a, depart_a
    ):
        reserver(api_client, guichetier_a)
        vendre(api_client, depart_a, "A")
        vendre(api_client, depart_a, "B")

        assert not ReservationHorsLigne.objects.exists()

    def test_LA_GARANTIE_un_autre_guichet_ne_peut_pas_prendre_les_places_reservees(
        self, api_client, guichetier_a, guichetier_a2, depart_a
    ):
        # Capacité 3 : A réserve 2 places (hors ligne). B, en ligne, ne peut vendre que la 3e.
        reserver(api_client, guichetier_a)
        api_client.force_authenticate(user=guichetier_a2)

        assert vendre(api_client, depart_a, "B1").status_code == 201
        refus = vendre(api_client, depart_a, "B2")

        assert refus.status_code == 400
        assert "réservées" in str(refus.data["depart"])

        # A vend hors ligne, plus tard, à la synchronisation : ses 2 ventes sont acceptées.
        api_client.force_authenticate(user=guichetier_a)
        assert vendre(api_client, depart_a, "A1").status_code == 201
        assert vendre(api_client, depart_a, "A2").status_code == 201
        assert Ticket.objects.filter(depart=depart_a).count() == 3
        depart_a.refresh_from_db()
        assert depart_a.places_vendues == depart_a.vehicule.capacite

    def test_sans_reservation_le_depart_complet_garde_son_message(
        self, api_client, guichetier_a, depart_a, vehicule_a
    ):
        depart_a.places_vendues = vehicule_a.capacite
        depart_a.save()
        api_client.force_authenticate(user=guichetier_a)

        refus = vendre(api_client, depart_a)

        assert refus.status_code == 400
        assert "Plus aucune place disponible" in str(refus.data["depart"])

    def test_le_titulaire_peut_aussi_vendre_au_dela_de_sa_reservation_s_il_reste_de_la_place(
        self, api_client, guichetier_a, depart_a
    ):
        reserver(api_client, guichetier_a)  # 2 places sur 3
        for nom in ("A1", "A2", "A3"):
            assert vendre(api_client, depart_a, nom).status_code == 201  # la 3e est libre
        assert vendre(api_client, depart_a, "A4").status_code == 400  # complet

    def test_une_reservation_expiree_ne_bloque_personne_et_n_est_pas_consommee(
        self, api_client, guichetier_a, guichetier_a2, depart_a
    ):
        ReservationHorsLigne.objects.create(
            depart=depart_a, guichetier=guichetier_a, company=depart_a.company,
            places=2, expire_le=timezone.now() - datetime.timedelta(minutes=1),
        )
        api_client.force_authenticate(user=guichetier_a2)

        for nom in ("B1", "B2", "B3"):  # les 3 places sont vendables : rien n'est retenu
            assert vendre(api_client, depart_a, nom).status_code == 201

        assert places_reservees(guichetier_a, depart_a) == 2  # intacte, mais sans effet

    def test_un_rejeu_idempotent_ne_consomme_pas_de_reservation(
        self, api_client, guichetier_a, depart_a
    ):
        reserver(api_client, guichetier_a)
        cle = {"HTTP_IDEMPOTENCY_KEY": "cle-rejeu-1"}
        vendre(api_client, depart_a, **cle)

        assert vendre(api_client, depart_a, **cle).status_code == 200

        assert places_reservees(guichetier_a, depart_a) == 1  # consommée une seule fois

    def test_une_vente_refusee_ne_consomme_pas_la_reservation(
        self, api_client, guichetier_a, depart_a
    ):
        reserver(api_client, guichetier_a)
        depart_a.statut = DepartStatut.TERMINE
        depart_a.save()

        assert vendre(api_client, depart_a).status_code == 400

        assert places_reservees(guichetier_a, depart_a) == 2

    def test_rappeler_apres_des_ventes_reconstitue_la_reservation(
        self, api_client, guichetier_a, depart_a, vehicule_a
    ):
        vehicule_a.capacite = 10
        vehicule_a.save()
        reserver(api_client, guichetier_a)
        vendre(api_client, depart_a, "A1")
        vendre(api_client, depart_a, "A2")
        assert places_reservees(guichetier_a, depart_a) == 0

        reserver(api_client, guichetier_a)

        assert places_reservees(guichetier_a, depart_a) == 2


@pytest.mark.django_db
class TestExpositionEtPermissions:
    def test_l_api_des_departs_expose_les_places_reservees_et_disponibles(
        self, api_client, guichetier_a, guichetier_a2, depart_a
    ):
        reserver(api_client, guichetier_a)
        api_client.force_authenticate(user=guichetier_a2)

        liste = api_client.get("/api/departs/").data
        detail = api_client.get(f"/api/departs/{depart_a.id}/").data
        jauge = api_client.get(f"/api/departs/{depart_a.id}/places-restantes/").data

        for donnees in (liste[0], detail, jauge):
            assert donnees["places_restantes"] == 3  # physiquement libres
            assert donnees["places_reservees"] == 2
            assert donnees["places_disponibles"] == 1  # vendables sans réservation

    def test_places_reservees_expirees_non_comptees(self, api_client, guichetier_a, depart_a):
        ReservationHorsLigne.objects.create(
            depart=depart_a, guichetier=guichetier_a, company=depart_a.company,
            places=2, expire_le=timezone.now() - datetime.timedelta(minutes=1),
        )
        api_client.force_authenticate(user=guichetier_a)

        assert api_client.get(f"/api/departs/{depart_a.id}/").data["places_disponibles"] == 3

    def test_le_nombre_de_requetes_ne_depend_pas_du_nombre_de_departs(
        self, api_client, guichetier_a, depart_a, django_assert_max_num_queries
    ):
        for heures in range(3, 10):
            autre_depart(depart_a, date_heure=timezone.now() + datetime.timedelta(hours=heures))
        api_client.force_authenticate(user=guichetier_a)

        with django_assert_max_num_queries(12):
            assert len(api_client.get("/api/departs/").data) == 8

    def test_les_roles_sous_le_guichetier_ne_peuvent_pas_reserver(
        self, api_client, user_factory, company_a, depart_a
    ):
        bagagiste = user_factory("bagagiste_res", Role.BAGAGISTE, company=company_a)
        api_client.force_authenticate(user=bagagiste)

        assert api_client.post(RESERVER).status_code == 403
        assert api_client.delete(RESERVER).status_code == 403

    def test_un_role_superieur_peut_reserver(self, api_client, user_factory, company_a, depart_a):
        chef = user_factory("chef_gare_res", Role.CHEF_GARE, company=company_a)

        assert reserver(api_client, chef).status_code == 200

    def test_authentification_requise(self, api_client, depart_a):
        assert api_client.post(RESERVER).status_code == 401
