import pytest

from alertes.models import Alerte, GraviteAlerte, TypeAlerte
from alertes.services import alerter
from alertes.tests.conftest import alertes_de


@pytest.fixture
def alerte_pour_les_chefs_de_ligne(company_a, agents):
    return alerter(company_a, type=TypeAlerte.INCIDENT, titre="Panne", roles=["chef_ligne"])


@pytest.mark.django_db
class TestLecture:
    def test_on_ne_voit_que_les_alertes_de_son_poste(self, api_client, agents, alerte_pour_les_chefs_de_ligne):
        assert [a["id"] for a in alertes_de(api_client, agents["chef_ligne"])] == [alerte_pour_les_chefs_de_ligne.id]
        assert alertes_de(api_client, agents["guichetier"]) == []

    def test_une_alerte_adressee_a_un_agent_precis_n_est_vue_que_par_lui(self, api_client, agents, company_a):
        alerter(company_a, titre="Pour toi", destinataires=[agents["guichetier"]])

        assert len(alertes_de(api_client, agents["guichetier"])) == 1
        assert alertes_de(api_client, agents["chef_gare"]) == []

    def test_les_alertes_d_une_autre_compagnie_sont_invisibles(
        self, api_client, agents, company_b, user_factory, alerte_pour_les_chefs_de_ligne
    ):
        chef_ligne_b = user_factory("chef_ligne_b", "chef_ligne", company=company_b)

        assert alertes_de(api_client, chef_ligne_b) == []

    def test_le_compteur_de_non_lues_et_le_filtre(self, api_client, agents, company_a):
        for numero in range(3):
            alerter(company_a, titre=f"Alerte {numero}", roles=["qhse"])
        api_client.force_authenticate(user=agents["qhse"])

        reponse = api_client.get("/api/alertes/?limit=2")

        assert reponse.data["non_lues"] == 3
        assert len(reponse.data["alertes"]) == 2
        assert reponse.data["alertes"][0]["titre"] == "Alerte 2"  # la plus récente d'abord

    def test_une_limite_invalide_est_ignoree(self, api_client, agents, alerte_pour_les_chefs_de_ligne):
        api_client.force_authenticate(user=agents["chef_ligne"])

        assert api_client.get("/api/alertes/?limit=beaucoup").status_code == 200

    def test_le_superadmin_sans_compagnie_n_a_aucune_alerte(self, api_client, superadmin_user, alerte_pour_les_chefs_de_ligne):
        assert alertes_de(api_client, superadmin_user) == []

    def test_refuse_sans_authentification(self, api_client):
        assert api_client.get("/api/alertes/").status_code == 401

    def test_aucune_ecriture_par_l_api(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.post("/api/alertes/", {"titre": "Faux"}).status_code == 405


@pytest.mark.django_db
class TestMarquerLu:
    def test_la_lecture_est_personnelle(self, api_client, agents, company_a, user_factory):
        autre = user_factory("chef_ligne_bis", "chef_ligne", company=company_a)
        alerte = alerter(company_a, titre="Panne", roles=["chef_ligne"])
        api_client.force_authenticate(user=agents["chef_ligne"])

        reponse = api_client.post(f"/api/alertes/{alerte.id}/lire/")

        assert reponse.status_code == 200 and reponse.data["lue"] is True
        assert api_client.get("/api/alertes/").data["non_lues"] == 0
        assert alertes_de(api_client, autre)[0]["lue"] is False

    def test_lire_deux_fois_ne_change_rien(self, api_client, agents, alerte_pour_les_chefs_de_ligne):
        api_client.force_authenticate(user=agents["chef_ligne"])
        api_client.post(f"/api/alertes/{alerte_pour_les_chefs_de_ligne.id}/lire/")

        assert api_client.post(f"/api/alertes/{alerte_pour_les_chefs_de_ligne.id}/lire/").status_code == 200

    def test_on_ne_lit_pas_l_alerte_d_un_autre_poste(self, api_client, agents, alerte_pour_les_chefs_de_ligne):
        api_client.force_authenticate(user=agents["guichetier"])

        assert api_client.post(f"/api/alertes/{alerte_pour_les_chefs_de_ligne.id}/lire/").status_code == 404

    def test_tout_marquer_comme_lu(self, api_client, agents, company_a):
        for numero in range(4):
            alerter(company_a, titre=f"Alerte {numero}", roles=["qhse"])
        api_client.force_authenticate(user=agents["qhse"])

        reponse = api_client.post("/api/alertes/lire-tout/")

        assert reponse.data == {"marquees": 4}
        assert api_client.get("/api/alertes/").data["non_lues"] == 0
        assert api_client.post("/api/alertes/lire-tout/").data == {"marquees": 0}


@pytest.mark.django_db
class TestService:
    def test_sans_destinataire_aucune_alerte(self, company_a):
        assert alerter(company_a, titre="Personne") is None
        assert Alerte.objects.count() == 0

    def test_un_agent_d_une_autre_compagnie_n_est_jamais_destinataire(self, company_a, company_b, user_factory):
        etranger = user_factory("etranger", "chef_gare", company=company_b)

        assert alerter(company_a, titre="Fuite", destinataires=[etranger]) is None

    def test_la_meme_cle_ne_cree_qu_une_alerte(self, company_a):
        premiere = alerter(company_a, titre="A", roles=["pdg"], cle="seuil:retards:2030-01-01")
        seconde = alerter(company_a, titre="A", roles=["pdg"], cle="seuil:retards:2030-01-01")

        assert premiere is not None and seconde is None
        assert Alerte.objects.count() == 1

    def test_la_meme_cle_dans_deux_compagnies_est_permise(self, company_a, company_b):
        assert alerter(company_a, titre="A", roles=["pdg"], cle="k") is not None
        assert alerter(company_b, titre="A", roles=["pdg"], cle="k") is not None

    def test_une_panne_de_l_alerte_ne_leve_jamais(self, company_a, monkeypatch):
        def casse(**_):
            raise RuntimeError("base indisponible")

        monkeypatch.setattr(Alerte.objects, "create", casse)

        assert alerter(company_a, titre="A", roles=["pdg"]) is None

    def test_les_champs_sont_normalises(self, company_a, agents):
        alerte = alerter(
            company_a, titre="x" * 500, roles=["qhse", "qhse", "chef_ligne"], gravite=GraviteAlerte.CRITIQUE,
            cree_par=agents["pdg"],
        )

        assert len(alerte.titre) == 200
        assert alerte.roles_destinataires == ["chef_ligne", "qhse"]
