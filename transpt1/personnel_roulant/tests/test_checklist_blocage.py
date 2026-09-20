import pytest

from personnel_roulant.models import EtatChecklist
from reseau.models import VehiculeStatut


@pytest.mark.django_db
class TestBlocageSecuriteChecklist:
    def test_defaut_securite_bloque_le_vehicule(self, api_client, chauffeur_a, feuille_a, vehicule_a):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.post(
            "/api/checklists/",
            {"feuille_de_route": feuille_a.id, "item": "freins", "etat": EtatChecklist.DEFAUT},
        )

        assert response.status_code == 201
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.BLOQUE_SECURITE

    def test_defaut_non_securite_ne_bloque_pas(self, api_client, chauffeur_a, feuille_a, vehicule_a):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.post(
            "/api/checklists/",
            {"feuille_de_route": feuille_a.id, "item": "carburant", "etat": EtatChecklist.DEFAUT},
        )

        assert response.status_code == 201
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_item_securite_ok_ne_bloque_pas(self, api_client, chauffeur_a, feuille_a, vehicule_a):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.post(
            "/api/checklists/",
            {"feuille_de_route": feuille_a.id, "item": "pneus", "etat": EtatChecklist.OK},
        )

        assert response.status_code == 201
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_feuille_ne_peut_pas_demarrer_apres_defaut_securite(
        self, api_client, chauffeur_a, feuille_a
    ):
        api_client.force_authenticate(user=chauffeur_a)

        api_client.post(
            "/api/checklists/",
            {"feuille_de_route": feuille_a.id, "item": "pneus", "etat": EtatChecklist.DEFAUT},
        )

        response = api_client.post(f"/api/feuilles-de-route/{feuille_a.id}/demarrer/")

        assert response.status_code == 400
        feuille_a.refresh_from_db()
        assert feuille_a.heure_depart_reelle is None

    def test_feuille_peut_demarrer_sans_defaut(self, api_client, chauffeur_a, feuille_a):
        api_client.force_authenticate(user=chauffeur_a)

        api_client.post(
            "/api/checklists/",
            {"feuille_de_route": feuille_a.id, "item": "pneus", "etat": EtatChecklist.OK},
        )

        response = api_client.post(f"/api/feuilles-de-route/{feuille_a.id}/demarrer/")

        assert response.status_code == 200
        feuille_a.refresh_from_db()
        assert feuille_a.heure_depart_reelle is not None

    def test_feuille_bloquee_si_vehicule_deja_bloque_meme_sans_nouvelle_checklist(
        self, api_client, chauffeur_a, feuille_a, vehicule_a
    ):
        vehicule_a.statut = VehiculeStatut.BLOQUE_SECURITE
        vehicule_a.save()

        api_client.force_authenticate(user=chauffeur_a)
        response = api_client.post(f"/api/feuilles-de-route/{feuille_a.id}/demarrer/")

        assert response.status_code == 400
        feuille_a.refresh_from_db()
        assert feuille_a.heure_depart_reelle is None
