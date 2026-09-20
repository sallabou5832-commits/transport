import pytest

from supports.models import Assurance, Sinistre


@pytest.mark.django_db
class TestPermissionsAssuranceSinistre:
    @pytest.mark.parametrize(
        "role_fixture", ["responsable_juridique_a", "directeur_technique_a"]
    )
    def test_roles_autorises_peuvent_creer_une_assurance(
        self, api_client, request, role_fixture, vehicule_a
    ):
        user = request.getfixturevalue(role_fixture)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            "/api/assurances/",
            {
                "vehicule": vehicule_a.id,
                "compagnie_assurance": "SAAR Assurances",
                "numero_police": "POL-2024-999",
                "date_echeance": "2027-01-01",
            },
        )

        assert response.status_code == 201

    def test_role_non_autorise_ne_peut_pas_creer_une_assurance(
        self, api_client, drh_a, vehicule_a
    ):
        api_client.force_authenticate(user=drh_a)

        response = api_client.post(
            "/api/assurances/",
            {
                "vehicule": vehicule_a.id,
                "compagnie_assurance": "SAAR Assurances",
                "numero_police": "POL-2024-999",
                "date_echeance": "2027-01-01",
            },
        )

        assert response.status_code == 403
        assert not Assurance.objects.filter(numero_police="POL-2024-999").exists()

    def test_role_non_autorise_ne_peut_pas_lister_les_assurances(
        self, api_client, drh_a, assurance_proche_a
    ):
        api_client.force_authenticate(user=drh_a)

        response = api_client.get("/api/assurances/")

        assert response.status_code == 403

    def test_role_non_autorise_ne_peut_pas_creer_un_sinistre(
        self, api_client, drh_a, vehicule_a
    ):
        api_client.force_authenticate(user=drh_a)

        response = api_client.post(
            "/api/sinistres/",
            {"vehicule": vehicule_a.id, "description": "Accrochage léger au dépôt."},
        )

        assert response.status_code == 403
        assert not Sinistre.objects.filter(vehicule=vehicule_a).exists()

    def test_directeur_technique_peut_creer_un_sinistre(
        self, api_client, directeur_technique_a, vehicule_a
    ):
        api_client.force_authenticate(user=directeur_technique_a)

        response = api_client.post(
            "/api/sinistres/",
            {"vehicule": vehicule_a.id, "description": "Accrochage léger au dépôt."},
        )

        assert response.status_code == 201


@pytest.mark.django_db
class TestEcheanceProche:
    def test_liste_uniquement_les_assurances_dont_lecheance_est_proche(
        self, api_client, responsable_juridique_a, assurance_proche_a, assurance_lointaine_a
    ):
        api_client.force_authenticate(user=responsable_juridique_a)

        response = api_client.get("/api/assurances/echeance-proche/")

        assert response.status_code == 200
        ids = [a["id"] for a in response.data]
        assert ids == [assurance_proche_a.id]
