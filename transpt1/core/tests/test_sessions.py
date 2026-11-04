"""Accès aux comptes (`core.sessions`) : « rester connecté » sous le plafond de la compagnie et du poste, changement de mot de
passe, fermeture des autres sessions. Sans réglage ni choix, tout se passe comme avant : session de 1 jour."""

import datetime
import time

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from audit.models import JournalAudit
from conftest import DEMO_PASSWORD
from configuration.models import ConfigurationCompagnie, ConfigurationPoste
from core.models import Role

JOUR = 86400
NOUVEAU = "Sel-de-Grand-Bassam-2026"


@pytest.fixture
def guichetier(user_factory, company_a):
    return user_factory("guichetier_session", Role.GUICHETIER, company=company_a)


@pytest.fixture
def chef_gare(user_factory, company_a):
    return user_factory("chef_gare_session", Role.CHEF_GARE, company=company_a)


@pytest.fixture
def pdg(user_factory, company_a):
    return user_factory("pdg_session", Role.PDG, company=company_a)


@pytest.fixture
def guichetier_b(user_factory, company_b):
    return user_factory("guichetier_session_b", Role.GUICHETIER, company=company_b)


def connecter(user, **corps):
    return APIClient().post("/api/auth/login/", {"username": user.username, "password": DEMO_PASSWORD, **corps})


def duree_du_jeton(brut):
    jeton = RefreshToken(brut)
    return jeton["exp"] - jeton["iat"]


def client_de(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def renouveler(refresh):
    return APIClient().post("/api/auth/refresh/", {"refresh": refresh})


@pytest.mark.django_db
class TestResterConnecte:
    def test_sans_choix_la_session_dure_un_jour_comme_avant(self, guichetier):
        reponse = connecter(guichetier)

        assert reponse.status_code == 200
        assert reponse.data["duree_session"] == "jour"
        assert duree_du_jeton(reponse.data["refresh"]) == JOUR
        assert reponse.data["session_expire_le"] == RefreshToken(reponse.data["refresh"])["exp"]

    @pytest.mark.parametrize(("duree", "jours"), [("jour", 1), ("semaine", 7), ("mois", 30), ("deconnexion", 365)])
    def test_chaque_duree_est_accordee_sans_reglage_de_la_compagnie(self, guichetier, duree, jours):
        reponse = connecter(guichetier, duree_session=duree)

        assert reponse.status_code == 200
        assert reponse.data["duree_session"] == duree
        assert duree_du_jeton(reponse.data["refresh"]) == jours * JOUR

    def test_une_duree_inconnue_est_refusee(self, guichetier):
        reponse = connecter(guichetier, duree_session="toujours")

        assert reponse.status_code == 400
        assert "duree_session" in reponse.data

    def test_le_jeton_d_acces_dure_toujours_30_minutes(self, guichetier):
        access = AccessToken(connecter(guichetier, duree_session="deconnexion").data["access"])

        assert access["exp"] - access["iat"] == 30 * 60

    def test_le_plafond_de_la_compagnie_ramene_la_duree_demandee(self, guichetier, company_a):
        ConfigurationCompagnie.objects.create(company=company_a, duree_session_max="semaine")

        reponse = connecter(guichetier, duree_session="deconnexion")

        assert reponse.data["duree_session"] == "semaine"
        assert duree_du_jeton(reponse.data["refresh"]) == 7 * JOUR

    def test_un_poste_reduit_ne_touche_que_ce_poste(self, guichetier, chef_gare, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, duree_session_max="jour")

        assert connecter(guichetier, duree_session="mois").data["duree_session"] == "jour"
        assert connecter(chef_gare, duree_session="mois").data["duree_session"] == "mois"

    def test_le_plafond_d_une_compagnie_ne_touche_pas_l_autre(self, guichetier_b, company_a):
        ConfigurationCompagnie.objects.create(company=company_a, duree_session_max="jour")

        assert connecter(guichetier_b, duree_session="deconnexion").data["duree_session"] == "deconnexion"

    def test_le_poste_ne_depasse_jamais_le_plafond_de_la_compagnie(self, guichetier, company_a):
        ConfigurationCompagnie.objects.create(company=company_a, duree_session_max="semaine")
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, duree_session_max="deconnexion")

        assert connecter(guichetier, duree_session="deconnexion").data["duree_session"] == "semaine"

    def test_les_identifiants_refuses_restent_401_et_traces(self, guichetier):
        reponse = APIClient().post(
            "/api/auth/login/", {"username": guichetier.username, "password": "faux", "duree_session": "mois"}
        )

        assert reponse.status_code == 401
        assert JournalAudit.objects.filter(action="connexion_echec", objet_repr=guichetier.username).exists()


@pytest.mark.django_db
class TestRenouvellement:
    def test_une_session_longue_se_renouvelle(self, guichetier):
        refresh = connecter(guichetier, duree_session="mois").data["refresh"]

        reponse = renouveler(refresh)

        assert reponse.status_code == 200
        assert client_de(reponse.data["access"]).get("/api/auth/me/").status_code == 200

    def test_un_plafond_abaisse_ferme_les_sessions_ouvertes_depuis_plus_longtemps(self, guichetier, company_a):
        ancienne = RefreshToken.for_user(guichetier)
        ancienne["iat"] = int(time.time()) - 8 * JOUR
        ancienne.set_exp(lifetime=datetime.timedelta(days=365))
        recente = connecter(guichetier, duree_session="mois").data["refresh"]
        ConfigurationCompagnie.objects.create(company=company_a, duree_session_max="semaine")

        refusee = renouveler(str(ancienne))

        assert refusee.status_code == 401
        assert "raccourci" in str(refusee.data["detail"])
        assert renouveler(recente).status_code == 200  # ouverte depuis moins de 7 jours

    def test_un_compte_supprime_repond_401_et_non_500(self, guichetier):
        refresh = connecter(guichetier).data["refresh"]
        guichetier.delete()

        assert renouveler(refresh).status_code == 401

    def test_un_compte_suspendu_ne_renouvelle_plus(self, guichetier):
        refresh = connecter(guichetier).data["refresh"]
        guichetier.is_active = False
        guichetier.save()

        assert renouveler(refresh).status_code == 401

    def test_un_jeton_emis_avant_la_version_de_session_vaut_la_version_0(self, guichetier):
        sans_version = RefreshToken.for_user(guichetier)  # sans `vs` : émis avant ce lot

        reponse = renouveler(str(sans_version))

        assert reponse.status_code == 200
        assert client_de(str(sans_version.access_token)).get("/api/auth/me/").status_code == 200


@pytest.mark.django_db
class TestChangerSonMotDePasse:
    def changer(self, session, **corps):
        return client_de(session["access"]).post(
            "/api/auth/mot-de-passe/", {"ancien": DEMO_PASSWORD, "nouveau": NOUVEAU, "refresh": session["refresh"], **corps}
        )

    def test_le_mot_de_passe_change_et_les_autres_sessions_sont_fermees(self, guichetier):
        ce_poste = connecter(guichetier, duree_session="semaine").data
        autre_appareil = connecter(guichetier, duree_session="mois").data

        reponse = self.changer(ce_poste)

        assert reponse.status_code == 200
        guichetier.refresh_from_db()
        assert guichetier.check_password(NOUVEAU)
        # L'autre appareil est déconnecté : ni son jeton d'accès, ni son renouvellement ne valent plus.
        assert client_de(autre_appareil["access"]).get("/api/auth/me/").status_code == 401
        assert renouveler(autre_appareil["refresh"]).status_code == 401
        # Cet appareil reste connecté, avec une session de même durée que la sienne.
        assert client_de(reponse.data["access"]).get("/api/auth/me/").status_code == 200
        assert reponse.data["duree_session"] == "semaine"
        assert duree_du_jeton(reponse.data["refresh"]) == 7 * JOUR
        assert renouveler(reponse.data["refresh"]).status_code == 200

    def test_on_se_reconnecte_avec_le_nouveau_mot_de_passe_seulement(self, guichetier):
        self.changer(connecter(guichetier).data)

        assert connecter(guichetier).status_code == 401
        assert (
            APIClient().post("/api/auth/login/", {"username": guichetier.username, "password": NOUVEAU}).status_code == 200
        )

    def test_sans_jeton_de_renouvellement_la_nouvelle_session_dure_un_jour(self, guichetier):
        session = connecter(guichetier, duree_session="mois").data

        reponse = self.changer(session, refresh="")

        assert reponse.status_code == 200
        assert reponse.data["duree_session"] == "jour"

    def test_l_ancien_mot_de_passe_faux_est_refuse(self, guichetier):
        reponse = self.changer(connecter(guichetier).data, ancien="faux")

        assert reponse.status_code == 400
        assert "ancien" in reponse.data
        guichetier.refresh_from_db()
        assert guichetier.check_password(DEMO_PASSWORD)

    def test_le_meme_mot_de_passe_est_refuse(self, guichetier):
        reponse = self.changer(connecter(guichetier).data, nouveau=DEMO_PASSWORD)

        assert reponse.status_code == 400
        assert "différent" in str(reponse.data["nouveau"])

    @pytest.mark.parametrize("faible", ["court1", "12345678901", "password123", "guichetier_session"])
    def test_un_mot_de_passe_faible_est_refuse_avec_un_message_en_francais(self, guichetier, faible):
        reponse = self.changer(connecter(guichetier).data, nouveau=faible)

        assert reponse.status_code == 400
        assert reponse.data["nouveau"]
        assert "mot de passe" in " ".join(reponse.data["nouveau"]).lower()

    def test_le_changement_est_trace_sans_le_mot_de_passe(self, guichetier):
        self.changer(connecter(guichetier).data)

        entree = JournalAudit.objects.filter(objet_type="core.user", objet_id=str(guichetier.pk), action="modification").get()
        assert entree.acteur_id == guichetier.pk
        assert entree.changements["password"] == "modifié"
        assert entree.changements["version_session"] == [0, 1]
        assert NOUVEAU not in str(entree.changements)

    def test_sans_connexion_c_est_401(self):
        assert APIClient().post("/api/auth/mot-de-passe/", {"ancien": "a", "nouveau": "b"}).status_code == 401

    def test_les_essais_trop_rapproches_sont_freines(self, guichetier, settings):
        settings.CONNEXION_LIMITE_COMPTE = "3/min"
        session = connecter(guichetier).data

        codes = [self.changer(session, ancien="faux").status_code for _ in range(4)]

        assert codes == [400, 400, 400, 429]

    def test_le_superadmin_change_aussi_son_mot_de_passe(self, superadmin_user):
        session = connecter(superadmin_user).data

        assert self.changer(session).status_code == 200


@pytest.mark.django_db
class TestFermerLesAutresSessions:
    def test_les_autres_appareils_sont_deconnectes_et_celui_ci_garde_son_echeance(self, guichetier):
        ce_poste = connecter(guichetier, duree_session="semaine").data
        autre = connecter(guichetier, duree_session="mois").data

        reponse = client_de(ce_poste["access"]).post("/api/auth/fermer-autres-sessions/", {"refresh": ce_poste["refresh"]})

        assert reponse.status_code == 200
        assert renouveler(autre["refresh"]).status_code == 401
        assert client_de(autre["access"]).get("/api/auth/me/").status_code == 401
        assert renouveler(ce_poste["refresh"]).status_code == 401  # l'ancien jeton de cet appareil aussi
        avant, apres = RefreshToken(ce_poste["refresh"]), RefreshToken(reponse.data["refresh"])
        assert (apres["iat"], apres["exp"]) == (avant["iat"], avant["exp"])  # rien n'est prolongé sans mot de passe
        assert reponse.data["duree_session"] == "semaine"
        assert renouveler(reponse.data["refresh"]).status_code == 200

    def test_sans_le_jeton_de_cet_appareil_rien_n_est_ferme(self, guichetier):
        session = connecter(guichetier).data

        reponse = client_de(session["access"]).post("/api/auth/fermer-autres-sessions/", {})

        assert reponse.status_code == 400
        assert renouveler(session["refresh"]).status_code == 200

    def test_le_jeton_d_un_autre_compte_est_refuse(self, guichetier, chef_gare):
        session = connecter(guichetier).data
        autre = connecter(chef_gare).data

        reponse = client_de(session["access"]).post("/api/auth/fermer-autres-sessions/", {"refresh": autre["refresh"]})

        assert reponse.status_code == 400
        assert renouveler(autre["refresh"]).status_code == 200


@pytest.mark.django_db
class TestReglages:
    def test_ma_configuration_dit_la_politique_de_session(self, api_client, guichetier, company_a):
        api_client.force_authenticate(user=guichetier)
        assert api_client.get("/api/configuration/moi/").data["session"] == {
            "duree_max": "deconnexion", "code_court_exige": False
        }

        ConfigurationCompagnie.objects.create(company=company_a, duree_session_max="mois", code_court_exige=True)
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, duree_session_max="semaine")

        assert api_client.get("/api/configuration/moi/").data["session"] == {"duree_max": "semaine", "code_court_exige": True}

    def test_le_pdg_fixe_le_plafond_et_le_code_court(self, api_client, pdg, company_a):
        api_client.force_authenticate(user=pdg)

        reponse = api_client.patch(
            "/api/configuration/compagnie/", {"duree_session_max": "semaine", "code_court_exige": True}, format="json"
        )

        assert reponse.status_code == 200
        cadre = ConfigurationCompagnie.objects.get(company=company_a)
        assert (cadre.duree_session_max, cadre.code_court_exige) == ("semaine", True)

    def test_un_autre_poste_ne_fixe_pas_le_plafond(self, api_client, chef_gare):
        api_client.force_authenticate(user=chef_gare)

        reponse = api_client.patch("/api/configuration/compagnie/", {"duree_session_max": "jour"}, format="json")

        assert reponse.status_code == 403

    def test_le_chef_de_gare_reduit_la_session_du_guichetier(self, api_client, chef_gare, company_a):
        api_client.force_authenticate(user=chef_gare)

        reponse = api_client.patch("/api/configuration/postes/guichetier/", {"duree_session_max": "jour"}, format="json")

        assert reponse.status_code == 200
        assert reponse.data["effectif"]["duree_session_max"] == "jour"

    def test_un_poste_ne_s_allonge_pas_au_dela_du_plafond(self, api_client, chef_gare, company_a):
        ConfigurationCompagnie.objects.create(company=company_a, duree_session_max="semaine")
        api_client.force_authenticate(user=chef_gare)

        reponse = api_client.patch("/api/configuration/postes/guichetier/", {"duree_session_max": "mois"}, format="json")

        assert reponse.status_code == 400
        assert "7 jours" in str(reponse.data["duree_session_max"])

    def test_le_catalogue_liste_les_durees(self, api_client, guichetier):
        api_client.force_authenticate(user=guichetier)

        durees = api_client.get("/api/configuration/catalogue/").data["durees_session"]

        assert [d["valeur"] for d in durees] == ["jour", "semaine", "mois", "deconnexion"]
