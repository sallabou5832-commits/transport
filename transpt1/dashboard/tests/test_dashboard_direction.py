import pytest

from core.models import Role


EXPECTED = {
    "vehicules_par_statut": {
        "disponible": 1,
        "en_ligne": 1,
        "en_maintenance": 1,
        "bloque_securite": 1,
    },
    "incidents_ouverts_par_gravite_7_jours": {"faible": 1, "moyenne": 1, "grave": 1},
    "recettes_du_jour": 8000.00,
    "pieces_sous_seuil": 1,
    "assurances_echeance_proche": 1,
}


def _assert_matches_expected(data):
    assert data["vehicules_par_statut"] == EXPECTED["vehicules_par_statut"]
    assert data["incidents_ouverts_par_gravite_7_jours"] == EXPECTED["incidents_ouverts_par_gravite_7_jours"]
    assert float(data["recettes_du_jour"]) == EXPECTED["recettes_du_jour"]
    assert data["pieces_sous_seuil"] == EXPECTED["pieces_sous_seuil"]
    assert data["assurances_echeance_proche"] == EXPECTED["assurances_echeance_proche"]


@pytest.mark.django_db
class TestDashboardDirection:
    @pytest.mark.parametrize("role_fixture", ["pdg_a", "secretaire_general_a", "qhse_a"])
    def test_roles_autorises_recoivent_les_bons_agregats(
        self, api_client, request, role_fixture, scenario_a, scenario_b_decoy
    ):
        user = request.getfixturevalue(role_fixture)
        api_client.force_authenticate(user=user)

        response = api_client.get("/api/dashboard/direction/")

        assert response.status_code == 200
        _assert_matches_expected(response.data)

    def test_les_donnees_dune_autre_compagnie_ne_fuient_pas(
        self, api_client, pdg_b, scenario_a, scenario_b_decoy
    ):
        api_client.force_authenticate(user=pdg_b)

        response = api_client.get("/api/dashboard/direction/")

        assert response.status_code == 200
        _assert_matches_expected(response.data)

    def test_role_non_autorise_ne_peut_pas_consulter(self, api_client, user_factory, company_a, scenario_a):
        guichetier = user_factory("guichetier_dashboard_test", Role.GUICHETIER, company=company_a)
        api_client.force_authenticate(user=guichetier)

        response = api_client.get("/api/dashboard/direction/")

        assert response.status_code == 403

    def test_utilisateur_non_authentifie_refuse(self, api_client, scenario_a):
        response = api_client.get("/api/dashboard/direction/")

        assert response.status_code == 401


@pytest.mark.django_db
class TestDisponibiliteDeLaFlotte:
    def test_part_des_vehicules_en_etat_de_rouler(self, api_client, user_factory, company_a):
        from core.models import Role
        from reseau.models import Vehicule, VehiculeStatut

        for numero, statut in enumerate(
            [VehiculeStatut.DISPONIBLE, VehiculeStatut.EN_LIGNE, VehiculeStatut.EN_MAINTENANCE, VehiculeStatut.BLOQUE_SECURITE]
        ):
            Vehicule.objects.create(immatriculation=f"CI-70{numero}0-AA", capacite=30, statut=statut, company=company_a)
        api_client.force_authenticate(user=user_factory("pdg_flotte", Role.PDG, company=company_a))

        assert api_client.get("/api/dashboard/direction/").data["disponibilite_flotte_pourcent"] == 50

    def test_sans_vehicule_le_score_est_vide(self, api_client, user_factory, company_a):
        from core.models import Role

        api_client.force_authenticate(user=user_factory("pdg_flotte2", Role.PDG, company=company_a))

        assert api_client.get("/api/dashboard/direction/").data["disponibilite_flotte_pourcent"] is None
