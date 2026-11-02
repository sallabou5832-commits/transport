"""Ce que le règlement intérieur de la compagnie permet aux chauffeurs sur leurs propres feuilles de route et incidents. Par
défaut, rien ne change ; une compagnie peut l'interdire, sans toucher à la régulation."""

import pytest

from configuration.models import ReglementInterieur
from personnel_roulant.models import FeuilleDeRoute, GraviteIncident, Incident, TypeIncident


def interdire(company, *codes):
    ReglementInterieur.objects.create(company=company, regles={code: False for code in codes})


@pytest.fixture
def incident_a(db, company_a, feuille_a, chauffeur_a):
    return Incident.objects.create(
        feuille_de_route=feuille_a,
        vehicule=feuille_a.depart.vehicule,
        chauffeur=chauffeur_a,
        company=company_a,
        type_incident=TypeIncident.RETARD,
        description="Retard de 20 minutes.",
        gravite=GraviteIncident.FAIBLE,
    )


@pytest.mark.django_db
class TestFeuillesDeRoute:
    def test_par_defaut_le_chauffeur_supprime_sa_feuille(self, api_client, chauffeur_a, feuille_a):
        api_client.force_authenticate(user=chauffeur_a)

        assert api_client.delete(f"/api/feuilles-de-route/{feuille_a.id}/").status_code == 204

    def test_le_reglement_peut_l_interdire(self, api_client, company_a, chauffeur_a, feuille_a):
        interdire(company_a, "chauffeur_supprime_ses_feuilles")
        api_client.force_authenticate(user=chauffeur_a)

        reponse = api_client.delete(f"/api/feuilles-de-route/{feuille_a.id}/")

        assert reponse.status_code == 403
        assert "règlement intérieur" in str(reponse.data["detail"])
        assert FeuilleDeRoute.objects.filter(pk=feuille_a.pk).exists()

    def test_l_interdiction_ne_vise_que_les_chauffeurs(self, api_client, company_a, chef_ligne_a, feuille_a):
        interdire(company_a, "chauffeur_supprime_ses_feuilles")
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.delete(f"/api/feuilles-de-route/{feuille_a.id}/").status_code == 204


@pytest.mark.django_db
class TestIncidents:
    def test_par_defaut_le_chauffeur_supprime_son_incident(self, api_client, chauffeur_a, incident_a):
        api_client.force_authenticate(user=chauffeur_a)

        assert api_client.delete(f"/api/incidents/{incident_a.id}/").status_code == 204

    def test_le_reglement_peut_l_interdire(self, api_client, company_a, chauffeur_a, incident_a):
        interdire(company_a, "chauffeur_supprime_ses_incidents")
        api_client.force_authenticate(user=chauffeur_a)

        reponse = api_client.delete(f"/api/incidents/{incident_a.id}/")

        assert reponse.status_code == 403
        assert Incident.objects.filter(pk=incident_a.pk).exists()

    def test_l_interdiction_n_empeche_pas_de_corriger_son_incident(self, api_client, company_a, chauffeur_a, incident_a):
        interdire(company_a, "chauffeur_supprime_ses_incidents")
        api_client.force_authenticate(user=chauffeur_a)

        reponse = api_client.patch(f"/api/incidents/{incident_a.id}/", {"description": "Retard de 35 minutes."}, format="json")

        assert reponse.status_code == 200

    def test_l_interdiction_ne_vise_que_les_chauffeurs(self, api_client, company_a, chef_ligne_a, incident_a):
        interdire(company_a, "chauffeur_supprime_ses_incidents")
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.delete(f"/api/incidents/{incident_a.id}/").status_code == 204
