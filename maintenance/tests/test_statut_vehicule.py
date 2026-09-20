import pytest

from maintenance.models import OrdreReparation, StatutOrdreReparation
from reseau.models import VehiculeStatut


@pytest.mark.django_db
class TestStatutVehiculeSurOrdreReparation:
    def test_creation_ordre_sur_vehicule_bloque_passe_en_maintenance(
        self, api_client, chef_atelier_a, vehicule_bloque_a, mecanicien_a
    ):
        api_client.force_authenticate(user=chef_atelier_a)

        response = api_client.post(
            "/api/ordres-reparation/",
            {
                "vehicule": vehicule_bloque_a.id,
                "description": "Remplacement des plaquettes de frein.",
                "mecanicien": mecanicien_a.id,
            },
        )

        assert response.status_code == 201
        vehicule_bloque_a.refresh_from_db()
        assert vehicule_bloque_a.statut == VehiculeStatut.EN_MAINTENANCE

    def test_creation_ordre_sur_vehicule_disponible_ne_change_pas_son_statut(
        self, api_client, chef_atelier_a, vehicule_a, mecanicien_a
    ):
        api_client.force_authenticate(user=chef_atelier_a)

        response = api_client.post(
            "/api/ordres-reparation/",
            {
                "vehicule": vehicule_a.id,
                "description": "Entretien préventif planifié.",
                "mecanicien": mecanicien_a.id,
            },
        )

        assert response.status_code == 201
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_ordre_termine_remet_le_vehicule_disponible(
        self, api_client, chef_atelier_a, vehicule_bloque_a, mecanicien_a
    ):
        ordre = OrdreReparation.objects.create(
            vehicule=vehicule_bloque_a,
            company=vehicule_bloque_a.company,
            description="Remplacement des freins.",
            statut=StatutOrdreReparation.EN_COURS,
            mecanicien=mecanicien_a,
        )
        vehicule_bloque_a.refresh_from_db()
        assert vehicule_bloque_a.statut == VehiculeStatut.EN_MAINTENANCE

        api_client.force_authenticate(user=chef_atelier_a)
        response = api_client.patch(
            f"/api/ordres-reparation/{ordre.id}/", {"statut": StatutOrdreReparation.TERMINE}
        )

        assert response.status_code == 200
        vehicule_bloque_a.refresh_from_db()
        assert vehicule_bloque_a.statut == VehiculeStatut.DISPONIBLE

        ordre.refresh_from_db()
        assert ordre.date_cloture is not None
