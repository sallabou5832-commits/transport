import pytest

from personnel_roulant.models import ChecklistDepart, EtatChecklist
from reseau.models import VehiculeStatut


def _envoyer(api_client, feuille, item, etat, commentaire=""):
    return api_client.post(
        "/api/checklists/",
        {"feuille_de_route": feuille.id, "item": item, "etat": etat, "commentaire": commentaire},
    )


@pytest.mark.django_db
class TestUnItemParFeuille:
    def test_un_nouvel_item_est_cree(self, api_client, chauffeur_a, feuille_a):
        api_client.force_authenticate(user=chauffeur_a)

        reponse = _envoyer(api_client, feuille_a, "pneus", EtatChecklist.OK)

        assert reponse.status_code == 201

    def test_renvoyer_un_item_met_a_jour_l_existant_sans_doublon(self, api_client, chauffeur_a, feuille_a):
        api_client.force_authenticate(user=chauffeur_a)
        premier = _envoyer(api_client, feuille_a, "carburant", EtatChecklist.DEFAUT, "presque vide")

        second = _envoyer(api_client, feuille_a, "carburant", EtatChecklist.OK, "plein fait")

        assert second.status_code == 200
        assert second.data["id"] == premier.data["id"]
        assert ChecklistDepart.objects.filter(feuille_de_route=feuille_a, item="carburant").count() == 1
        assert second.data["etat"] == EtatChecklist.OK and second.data["commentaire"] == "plein fait"

    def test_la_casse_et_les_espaces_ne_creent_pas_de_doublon(self, api_client, chauffeur_a, feuille_a):
        api_client.force_authenticate(user=chauffeur_a)
        _envoyer(api_client, feuille_a, "freins", EtatChecklist.OK)

        _envoyer(api_client, feuille_a, "  Freins ", EtatChecklist.OK)

        assert ChecklistDepart.objects.filter(feuille_de_route=feuille_a).count() == 1

    def test_le_meme_item_sur_deux_feuilles_reste_distinct(self, api_client, chauffeur_a, feuille_a, chauffeur_a2, feuille_a2):
        api_client.force_authenticate(user=chauffeur_a)
        _envoyer(api_client, feuille_a, "pneus", EtatChecklist.OK)
        api_client.force_authenticate(user=chauffeur_a2)

        reponse = _envoyer(api_client, feuille_a2, "pneus", EtatChecklist.OK)

        assert reponse.status_code == 201

    def test_un_chauffeur_ne_peut_pas_ecraser_la_checklist_d_un_autre(
        self, api_client, chauffeur_a, feuille_a, chauffeur_a2
    ):
        api_client.force_authenticate(user=chauffeur_a)
        _envoyer(api_client, feuille_a, "freins", EtatChecklist.DEFAUT)
        api_client.force_authenticate(user=chauffeur_a2)

        reponse = _envoyer(api_client, feuille_a, "freins", EtatChecklist.OK)

        assert reponse.status_code == 400
        assert ChecklistDepart.objects.get(feuille_de_route=feuille_a, item="freins").etat == EtatChecklist.DEFAUT

    def test_un_defaut_de_securite_renvoye_rebloque_le_vehicule(self, api_client, chauffeur_a, feuille_a, vehicule_a):
        api_client.force_authenticate(user=chauffeur_a)
        _envoyer(api_client, feuille_a, "freins", EtatChecklist.OK)

        _envoyer(api_client, feuille_a, "freins", EtatChecklist.DEFAUT)

        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.BLOQUE_SECURITE


@pytest.mark.django_db
class TestReprendreApresUnDefaut:
    """Le cas du pilote : défaut de sécurité, réparation, puis le chauffeur repart."""

    def test_apres_reparation_refaire_la_checklist_debloque_le_depart(
        self, api_client, chauffeur_a, feuille_a, vehicule_a
    ):
        api_client.force_authenticate(user=chauffeur_a)
        _envoyer(api_client, feuille_a, "freins", EtatChecklist.DEFAUT)
        assert api_client.post(f"/api/feuilles-de-route/{feuille_a.id}/demarrer/").status_code == 400

        vehicule_a.statut = VehiculeStatut.DISPONIBLE  # l'atelier a clôturé la réparation (voir test_scenario_pilote)
        vehicule_a.save()
        # Véhicule libéré mais défaut toujours inscrit sur la feuille : le départ reste refusé.
        assert api_client.post(f"/api/feuilles-de-route/{feuille_a.id}/demarrer/").status_code == 400

        _envoyer(api_client, feuille_a, "freins", EtatChecklist.OK, "remplacés")
        reponse = api_client.post(f"/api/feuilles-de-route/{feuille_a.id}/demarrer/")

        assert reponse.status_code == 200
