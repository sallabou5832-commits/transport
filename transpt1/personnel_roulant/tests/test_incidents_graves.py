import pytest

from personnel_roulant.models import GraviteIncident, Incident, TypeIncident


@pytest.fixture
def incidents_mixtes(db, company_a, vehicule_a, chauffeur_a):
    Incident.objects.create(
        vehicule=vehicule_a,
        chauffeur=chauffeur_a,
        company=company_a,
        type_incident=TypeIncident.RETARD,
        description="Retard de 20 minutes.",
        gravite=GraviteIncident.FAIBLE,
    )
    Incident.objects.create(
        vehicule=vehicule_a,
        chauffeur=chauffeur_a,
        company=company_a,
        type_incident=TypeIncident.PANNE,
        description="Panne moteur légère.",
        gravite=GraviteIncident.MOYENNE,
    )
    grave = Incident.objects.create(
        vehicule=vehicule_a,
        chauffeur=chauffeur_a,
        company=company_a,
        type_incident=TypeIncident.ACCIDENT,
        description="Collision avec un autre véhicule.",
        gravite=GraviteIncident.GRAVE,
    )
    return grave


@pytest.mark.django_db
class TestVisibiliteIncidentsGraves:
    def test_qhse_voit_uniquement_les_incidents_graves(
        self, api_client, qhse_a, incidents_mixtes
    ):
        api_client.force_authenticate(user=qhse_a)

        response = api_client.get("/api/incidents/graves/")

        assert response.status_code == 200
        ids = [i["id"] for i in response.data]
        assert ids == [incidents_mixtes.id]

    def test_directeur_exploitation_voit_les_incidents_graves(
        self, api_client, directeur_exploitation_a, incidents_mixtes
    ):
        api_client.force_authenticate(user=directeur_exploitation_a)

        response = api_client.get("/api/incidents/graves/")

        assert response.status_code == 200
        ids = [i["id"] for i in response.data]
        assert ids == [incidents_mixtes.id]

    def test_chauffeur_ne_peut_pas_consulter_lendpoint_graves(
        self, api_client, chauffeur_a, incidents_mixtes
    ):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.get("/api/incidents/graves/")

        assert response.status_code == 403

    def test_chef_ligne_ne_peut_pas_consulter_lendpoint_graves(
        self, api_client, chef_ligne_a, incidents_mixtes
    ):
        api_client.force_authenticate(user=chef_ligne_a)

        response = api_client.get("/api/incidents/graves/")

        assert response.status_code == 403
