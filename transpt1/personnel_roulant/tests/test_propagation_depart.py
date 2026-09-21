import pytest

from billetterie.models import DepartStatut
from core.models import Role
from reseau.models import VehiculeStatut


def _demarrer(api_client, feuille):
    return api_client.post(f"/api/feuilles-de-route/{feuille.id}/demarrer/")


def _arriver(api_client, feuille):
    return api_client.post(f"/api/feuilles-de-route/{feuille.id}/arriver/")


@pytest.mark.django_db
class TestPropagationDuDepartEtDuVehicule:
    """Ce que fait le chauffeur doit se voir chez le régulateur et à la direction : départ en cours,
    véhicule en ligne, puis départ terminé et véhicule à nouveau disponible."""

    def test_demarrer_passe_le_depart_en_cours_et_le_vehicule_en_ligne(
        self, api_client, chauffeur_a, feuille_a, depart_a, vehicule_a
    ):
        api_client.force_authenticate(user=chauffeur_a)

        assert _demarrer(api_client, feuille_a).status_code == 200

        depart_a.refresh_from_db()
        vehicule_a.refresh_from_db()
        assert depart_a.statut == DepartStatut.EN_COURS
        assert vehicule_a.statut == VehiculeStatut.EN_LIGNE

    def test_un_vehicule_deja_en_maintenance_n_est_pas_remis_en_ligne(
        self, api_client, chauffeur_a, feuille_a, vehicule_a
    ):
        vehicule_a.statut = VehiculeStatut.EN_MAINTENANCE
        vehicule_a.save()
        api_client.force_authenticate(user=chauffeur_a)

        _demarrer(api_client, feuille_a)

        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.EN_MAINTENANCE

    def test_un_demarrage_refuse_ne_change_rien(self, api_client, chauffeur_a, feuille_a, depart_a, vehicule_a):
        vehicule_a.statut = VehiculeStatut.BLOQUE_SECURITE
        vehicule_a.save()
        api_client.force_authenticate(user=chauffeur_a)

        assert _demarrer(api_client, feuille_a).status_code == 400

        depart_a.refresh_from_db()
        vehicule_a.refresh_from_db()
        assert depart_a.statut == DepartStatut.PLANIFIE
        assert vehicule_a.statut == VehiculeStatut.BLOQUE_SECURITE

    def test_arriver_termine_le_depart_et_libere_le_vehicule(
        self, api_client, chauffeur_a, feuille_a, depart_a, vehicule_a
    ):
        api_client.force_authenticate(user=chauffeur_a)
        _demarrer(api_client, feuille_a)

        assert _arriver(api_client, feuille_a).status_code == 200

        depart_a.refresh_from_db()
        vehicule_a.refresh_from_db()
        assert depart_a.statut == DepartStatut.TERMINE
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_un_vehicule_tombe_en_panne_en_route_ne_redevient_pas_disponible(
        self, api_client, chauffeur_a, feuille_a, depart_a, vehicule_a
    ):
        api_client.force_authenticate(user=chauffeur_a)
        _demarrer(api_client, feuille_a)
        vehicule_a.refresh_from_db()
        vehicule_a.statut = VehiculeStatut.EN_MAINTENANCE  # l'atelier l'a immobilisé pendant le trajet
        vehicule_a.save()

        _arriver(api_client, feuille_a)

        vehicule_a.refresh_from_db()
        depart_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.EN_MAINTENANCE
        assert depart_a.statut == DepartStatut.TERMINE

    def test_arriver_avant_d_etre_parti_est_refuse_et_ne_change_rien(
        self, api_client, chauffeur_a, feuille_a, depart_a
    ):
        api_client.force_authenticate(user=chauffeur_a)

        assert _arriver(api_client, feuille_a).status_code == 400

        depart_a.refresh_from_db()
        assert depart_a.statut == DepartStatut.PLANIFIE

    def test_apres_l_arrivee_on_ne_vend_plus_de_place_sur_ce_depart(
        self, api_client, user_factory, company_a, chauffeur_a, feuille_a, depart_a
    ):
        api_client.force_authenticate(user=chauffeur_a)
        _demarrer(api_client, feuille_a)
        _arriver(api_client, feuille_a)
        guichetier = user_factory("guichetier_propagation", Role.GUICHETIER, company=company_a)
        api_client.force_authenticate(user=guichetier)

        reponse = api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id, "passager_nom": "Retardataire", "passager_telephone": "+2250700000000",
                "prix": "5000", "mode_paiement": "especes",
            },
        )

        assert reponse.status_code == 400
