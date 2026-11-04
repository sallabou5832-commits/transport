"""Préférences personnelles (`/configuration/mes-preferences/`) : chacun règle son mode vocal, sauf si son supérieur l'a imposé, et
la façon d'être prévenu d'une alerte critique sur le site. Rien de réglé : comme avant."""

import pytest
from rest_framework.test import APIClient

from configuration.models import ConfigurationAgent, ConfigurationPoste, PreferencePersonnelle
from configuration.services import configuration_effective
from core.models import Role

URL = "/api/configuration/mes-preferences/"


@pytest.fixture
def guichetier(user_factory, company_a):
    return user_factory("guichetier_preferences", Role.GUICHETIER, company=company_a)


@pytest.fixture
def chef_gare(user_factory, company_a):
    return user_factory("chef_preferences", Role.CHEF_GARE, company=company_a)


def client_de(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestMesPreferences:
    def test_rien_de_regle_comme_avant(self, guichetier):
        reponse = client_de(guichetier).get(URL)

        assert reponse.status_code == 200
        assert reponse.data == {
            "prefere_vocal": None, "son_alertes": False, "notifications_navigateur": False, "vocal_impose": False,
            "modifie_le": None,
        }
        assert not PreferencePersonnelle.objects.exists()  # lire ne crée rien
        assert configuration_effective(guichetier)["prefere_vocal"] is False

    def test_chacun_regle_les_siennes(self, guichetier, chef_gare):
        reponse = client_de(guichetier).patch(URL, {"prefere_vocal": True, "son_alertes": True}, format="json")

        assert reponse.status_code == 200
        assert (reponse.data["prefere_vocal"], reponse.data["son_alertes"]) == (True, True)
        assert client_de(chef_gare).get(URL).data["son_alertes"] is False  # les siennes seulement

    def test_le_choix_de_l_agent_l_emporte_sur_le_reglage_du_superieur(self, guichetier, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, prefere_vocal=True)
        ConfigurationAgent.objects.create(agent=guichetier, company=company_a, prefere_vocal=True)
        assert configuration_effective(guichetier)["prefere_vocal"] is True

        client_de(guichetier).patch(URL, {"prefere_vocal": False}, format="json")

        assert configuration_effective(guichetier)["prefere_vocal"] is False

    def test_revenir_a_comme_son_superieur(self, guichetier, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, prefere_vocal=True)
        client_de(guichetier).patch(URL, {"prefere_vocal": False}, format="json")

        client_de(guichetier).patch(URL, {"prefere_vocal": None}, format="json")

        assert configuration_effective(guichetier)["prefere_vocal"] is True

    @pytest.mark.parametrize("par", ["poste", "agent"])
    def test_impose_par_le_superieur_l_agent_ne_le_change_pas(self, guichetier, company_a, par):
        if par == "poste":
            ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, prefere_vocal=True, prefere_vocal_impose=True)
        else:
            ConfigurationAgent.objects.create(agent=guichetier, company=company_a, prefere_vocal=True, prefere_vocal_impose=True)
        client = client_de(guichetier)

        assert client.get(URL).data["vocal_impose"] is True
        assert client.get("/api/configuration/moi/").data["vocal_impose"] is True
        refus = client.patch(URL, {"prefere_vocal": False}, format="json")
        assert refus.status_code == 400 and "supérieur" in str(refus.data["prefere_vocal"])
        assert client.patch(URL, {"son_alertes": True}, format="json").status_code == 200  # le reste se règle
        assert configuration_effective(guichetier)["prefere_vocal"] is True

    def test_impose_apres_coup_le_choix_deja_fait_ne_compte_plus(self, guichetier, company_a):
        client_de(guichetier).patch(URL, {"prefere_vocal": False}, format="json")

        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, prefere_vocal=True, prefere_vocal_impose=True)

        assert configuration_effective(guichetier)["prefere_vocal"] is True

    def test_le_superieur_impose_par_l_ecran_de_configuration(self, chef_gare, guichetier):
        reponse = client_de(chef_gare).patch(
            "/api/configuration/postes/guichetier/", {"prefere_vocal": True, "prefere_vocal_impose": True}, format="json"
        )

        assert reponse.status_code == 200 and reponse.data["prefere_vocal_impose"] is True
        assert client_de(guichetier).get(URL).data["vocal_impose"] is True

    def test_un_agent_ne_s_impose_rien_a_lui_meme(self, guichetier):
        client_de(guichetier).patch(URL, {"vocal_impose": True}, format="json")

        assert client_de(guichetier).get(URL).data["vocal_impose"] is False

    def test_l_operateur_de_la_plateforme_a_aussi_les_siennes(self, superadmin_user):
        reponse = client_de(superadmin_user).patch(URL, {"notifications_navigateur": True}, format="json")

        assert reponse.status_code == 200 and reponse.data["vocal_impose"] is False

    def test_sans_connexion_c_est_401(self):
        assert APIClient().get(URL).status_code == 401
