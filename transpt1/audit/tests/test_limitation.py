"""Limitation des tentatives de connexion (faille S3 de l'analyse : 40 mots de passe faux d'affilée étaient tous traités)."""

import pytest

from core.models import Role

URL = "/api/auth/login/"


def se_connecter(api_client, username, mot_de_passe="mauvais", adresse="203.0.113.7"):
    return api_client.post(URL, {"username": username, "password": mot_de_passe}, REMOTE_ADDR=adresse)


@pytest.mark.django_db
class TestLimitationDesConnexions:
    def test_au_dela_de_la_limite_par_compte_les_essais_sont_refuses(self, api_client, user_factory, company_a):
        user_factory("cible", Role.GUICHETIER, company=company_a)

        statuts = [se_connecter(api_client, "cible").status_code for _ in range(12)]

        assert statuts == [401] * 10 + [429] * 2

    def test_le_message_est_en_francais_et_donne_le_delai(self, api_client):
        for _ in range(10):
            se_connecter(api_client, "cible")

        reponse = se_connecter(api_client, "cible")

        assert reponse.status_code == 429
        assert reponse.data["detail"].startswith("Trop de tentatives de connexion. Réessayez dans ")
        assert "seconde" in reponse.data["detail"]
        assert int(reponse["Retry-After"]) > 0

    def test_le_bon_mot_de_passe_est_lui_aussi_refuse_une_fois_la_limite_atteinte(
        self, api_client, user_factory, company_a
    ):
        # Sinon l'attaquant qui a trouvé le mot de passe au 11e essai gagnerait quand même.
        user_factory("cible", Role.GUICHETIER, company=company_a)
        for _ in range(10):
            se_connecter(api_client, "cible")

        assert se_connecter(api_client, "cible", "Demo!2024").status_code == 429

    def test_un_autre_identifiant_depuis_la_meme_adresse_n_est_pas_bloque(self, api_client, user_factory, company_a):
        user_factory("autre", Role.GUICHETIER, company=company_a)
        for _ in range(10):
            se_connecter(api_client, "cible")

        assert se_connecter(api_client, "autre", "Demo!2024").status_code == 200

    def test_la_meme_cible_depuis_une_autre_adresse_n_est_pas_bloquee(self, api_client, user_factory, company_a):
        user_factory("cible", Role.GUICHETIER, company=company_a)
        for _ in range(10):
            se_connecter(api_client, "cible")

        assert se_connecter(api_client, "cible", "Demo!2024", adresse="198.51.100.9").status_code == 200

    def test_la_casse_de_l_identifiant_ne_contourne_pas_la_limite(self, api_client):
        for nom in ["Cible", "CIBLE", "cible", "cIbLe", "Cible", "CIBLE", "cible", "cIbLe", "Cible", "CIBLE"]:
            se_connecter(api_client, nom)

        assert se_connecter(api_client, "cible").status_code == 429

    def test_beaucoup_d_identifiants_depuis_une_meme_adresse_sont_freines(self, api_client, settings):
        settings.CONNEXION_LIMITE_ADRESSE = "5/min"

        statuts = [se_connecter(api_client, f"agent{i}").status_code for i in range(7)]

        assert statuts == [401] * 5 + [429] * 2

    def test_un_usage_normal_n_est_jamais_freine(self, api_client, user_factory, company_a):
        user_factory("agent", Role.GUICHETIER, company=company_a)

        statuts = [se_connecter(api_client, "agent", "Demo!2024").status_code for _ in range(5)]

        assert statuts == [200] * 5

    def test_le_reglage_s_adapte(self, api_client, settings):
        settings.CONNEXION_LIMITE_COMPTE = "2/min"

        statuts = [se_connecter(api_client, "cible").status_code for _ in range(3)]

        assert statuts == [401, 401, 429]

    def test_les_autres_routes_ne_sont_pas_limitees(self, api_client, user_factory, company_a):
        agent = user_factory("agent", Role.GUICHETIER, company=company_a)
        api_client.force_authenticate(user=agent)

        assert all(api_client.get("/api/auth/me/").status_code == 200 for _ in range(40))
