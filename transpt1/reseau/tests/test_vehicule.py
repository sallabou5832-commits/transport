import pytest
from django.db import IntegrityError, transaction

from reseau.models import Vehicule, VehiculeStatut


@pytest.mark.django_db
class TestVehiculeCRUD:
    def test_create_vehicule(self, api_client, company_a_manager, company_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/vehicules/",
            {"immatriculation": "CI-9999-XY", "capacite": 60, "statut": VehiculeStatut.DISPONIBLE},
        )

        assert response.status_code == 201
        assert response.data["company"]["id"] == company_a.id

    def test_duplicate_immatriculation_rejected(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/vehicules/",
            {
                "immatriculation": vehicule_a.immatriculation,
                "capacite": 40,
                "statut": VehiculeStatut.DISPONIBLE,
            },
        )

        assert response.status_code == 400
        assert "immatriculation" in response.data

    def test_la_meme_plaque_est_acceptee_dans_une_autre_compagnie(
        self, api_client, company_b_manager, company_b, vehicule_a
    ):
        # Avant : l'unicité valait pour toute la plateforme, donc la compagnie B apprenait que la plaque existait chez A.
        api_client.force_authenticate(user=company_b_manager)

        response = api_client.post(
            "/api/vehicules/",
            {"immatriculation": vehicule_a.immatriculation, "capacite": 40, "statut": VehiculeStatut.DISPONIBLE},
        )

        assert response.status_code == 201
        assert response.data["company"]["id"] == company_b.id
        assert Vehicule.objects.filter(immatriculation=vehicule_a.immatriculation).count() == 2

    def test_la_plaque_d_une_autre_compagnie_ne_bloque_pas_la_creation(
        self, api_client, company_a_manager, company_b, vehicule_a
    ):
        Vehicule.objects.create(immatriculation="CI-7777-ZZ", capacite=30, company=company_b)
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/vehicules/", {"immatriculation": "CI-7777-ZZ", "capacite": 40, "statut": VehiculeStatut.DISPONIBLE}
        )

        assert response.status_code == 201

    def test_renommer_un_vehicule_avec_la_plaque_d_un_autre_vehicule_de_la_compagnie_est_refuse(
        self, api_client, company_a_manager, company_a, vehicule_a
    ):
        autre = Vehicule.objects.create(immatriculation="CI-8888-QQ", capacite=30, company=company_a)
        api_client.force_authenticate(user=company_a_manager)

        refuse = api_client.patch(f"/api/vehicules/{autre.id}/", {"immatriculation": vehicule_a.immatriculation})
        # Garder sa propre plaque en modifiant autre chose n'est pas un doublon.
        accepte = api_client.patch(f"/api/vehicules/{autre.id}/", {"immatriculation": "CI-8888-QQ", "capacite": 35})

        assert refuse.status_code == 400 and "immatriculation" in refuse.data
        assert accepte.status_code == 200 and accepte.data["capacite"] == 35

    def test_la_base_refuse_le_doublon_dans_une_meme_compagnie(self, company_a, vehicule_a):
        # Filet de sécurité sous la validation de l'API : une création hors API (script, administration) échoue aussi.
        with pytest.raises(IntegrityError), transaction.atomic():
            Vehicule.objects.create(immatriculation=vehicule_a.immatriculation, capacite=10, company=company_a)

    def test_list_only_shows_own_company(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.get("/api/vehicules/")

        ids = [v["id"] for v in response.data]
        assert vehicule_a.id in ids

    def test_update_statut(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.patch(
            f"/api/vehicules/{vehicule_a.id}/", {"statut": VehiculeStatut.EN_MAINTENANCE}
        )

        assert response.status_code == 200
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.EN_MAINTENANCE

    def test_delete_vehicule(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.delete(f"/api/vehicules/{vehicule_a.id}/")

        assert response.status_code == 204
        assert not Vehicule.objects.filter(id=vehicule_a.id).exists()
