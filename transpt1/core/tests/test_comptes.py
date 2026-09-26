"""Le PDG suspend le compte d'un agent (cahier des charges : « bloquer un compte guichetier ») : l'agent ne se connecte plus,
ses sessions ouvertes sont coupées, rien de ce qu'il a fait n'est perdu, et la réactivation le rend tel qu'il était."""

import pytest
from rest_framework.test import APIClient

from alertes.models import Alerte, TypeAlerte
from audit.models import JournalAudit
from billetterie.models import Depart, Ticket
from core.models import Role
from reseau.models import AffectationGare, Gare, Ligne, Vehicule

MOT_DE_PASSE = "Demo!2024"


@pytest.fixture
def equipe(user_factory, company_a):
    return {
        "pdg": user_factory("pdg_comptes", Role.PDG, company=company_a),
        "pdg2": user_factory("pdg_comptes2", Role.PDG, company=company_a),
        "guichetier": user_factory("guichetier_comptes", Role.GUICHETIER, company=company_a, first_name="Rose", last_name="Kouame"),
        "bagagiste": user_factory("bagagiste_comptes", Role.BAGAGISTE, company=company_a),
        "chef_gare": user_factory("chef_gare_comptes", Role.CHEF_GARE, company=company_a),
        "drh": user_factory("drh_comptes", Role.DRH, company=company_a),
        "dirops": user_factory("dirops_comptes", Role.DIRECTEUR_EXPLOITATION, company=company_a),
        "sg": user_factory("sg_comptes", Role.SECRETAIRE_GENERAL, company=company_a),
    }


def suspendre(api_client, utilisateur, cible, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"/api/comptes/{cible.id}/suspendre/", corps, format="json")


def se_connecter(username):
    return APIClient().post("/api/auth/login/", {"username": username, "password": MOT_DE_PASSE}, format="json")


@pytest.mark.django_db
class TestSuspension:
    def test_le_pdg_suspend_un_compte_avec_son_motif(self, api_client, equipe):
        reponse = suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        assert reponse.status_code == 200
        assert reponse.data["actif"] is False and reponse.data["motif_suspension"] == "Écart de caisse répété"
        assert reponse.data["suspendu_par_nom"] == "pdg_comptes" and reponse.data["suspendu_le"] is not None
        equipe["guichetier"].refresh_from_db()
        assert not equipe["guichetier"].is_active
        assert equipe["guichetier"].suspendu_par == equipe["pdg"]

    def test_un_compte_suspendu_ne_se_connecte_plus(self, api_client, equipe):
        assert se_connecter("guichetier_comptes").status_code == 200

        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        assert se_connecter("guichetier_comptes").status_code == 401

    def test_ses_sessions_ouvertes_sont_coupees_tout_de_suite(self, api_client, equipe):
        jetons = se_connecter("guichetier_comptes").data
        agent = APIClient()
        agent.credentials(HTTP_AUTHORIZATION=f"Bearer {jetons['access']}")
        assert agent.get("/api/auth/me/").status_code == 200

        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        assert agent.get("/api/auth/me/").status_code == 401
        assert agent.get("/api/tickets/").status_code == 401
        assert APIClient().post("/api/auth/refresh/", {"refresh": jetons["refresh"]}, format="json").status_code == 401

    def test_la_reactivation_rend_le_compte_tel_qu_il_etait(self, api_client, equipe):
        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        reponse = api_client.post(f"/api/comptes/{equipe['guichetier'].id}/reactiver/", {"motif": "Situation éclaircie"}, format="json")

        assert reponse.status_code == 200 and reponse.data["actif"] is True
        equipe["guichetier"].refresh_from_db()
        assert equipe["guichetier"].is_active
        assert equipe["guichetier"].suspendu_le is None and equipe["guichetier"].suspendu_par is None
        assert equipe["guichetier"].motif_suspension == ""
        assert se_connecter("guichetier_comptes").status_code == 200

    def test_les_ventes_de_l_agent_suspendu_restent(self, api_client, equipe, company_a):
        gare = Gare.objects.create(nom="A", ville="V", company=company_a)
        arrivee = Gare.objects.create(nom="B", ville="W", company=company_a)
        ligne = Ligne.objects.create(nom="A-B", gare_depart=gare, gare_arrivee=arrivee, company=company_a)
        bus = Vehicule.objects.create(immatriculation="CI-COMPTE-1", capacite=50, company=company_a)
        depart = Depart.objects.create(ligne=ligne, vehicule=bus, chauffeur=equipe["bagagiste"], company=company_a, date_heure="2031-01-01T08:00:00Z")
        Ticket.objects.create(
            depart=depart, company=company_a, passager_nom="Awa", passager_telephone="+225", prix=5000,
            mode_paiement="especes", vendu_par=equipe["guichetier"],
        )

        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        assert Ticket.objects.filter(vendu_par=equipe["guichetier"]).count() == 1

    def test_la_suspension_est_tracee_au_journal_avec_le_pdg_comme_acteur(self, api_client, equipe):
        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        entree = JournalAudit.objects.filter(objet_type="core.user", objet_id=str(equipe["guichetier"].id)).latest("id")
        assert entree.acteur == equipe["pdg"]
        assert entree.changements["is_active"] == [True, False]
        assert entree.changements["motif_suspension"] == ["", "Écart de caisse répété"]


@pytest.mark.django_db
class TestAlertes:
    def test_le_chef_de_la_gare_de_l_agent_et_le_drh_sont_prevenus(self, api_client, equipe, company_a):
        gare = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=equipe["chef_gare"])
        AffectationGare.objects.create(agent=equipe["guichetier"], gare=gare, company=company_a)

        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        alerte = Alerte.objects.get(type=TypeAlerte.COMPTE)
        assert "Rose Kouame" in alerte.titre and "Écart de caisse répété" in alerte.message
        assert list(alerte.destinataires.all()) == [equipe["chef_gare"]]
        assert alerte.roles_destinataires == [Role.DRH]

    def test_un_agent_sans_gare_previent_au_moins_le_drh(self, api_client, equipe):
        suspendre(api_client, equipe["pdg"], equipe["dirops"], motif="Enquête interne en cours")

        alerte = Alerte.objects.get(type=TypeAlerte.COMPTE)
        assert alerte.roles_destinataires == [Role.DRH] and not alerte.destinataires.exists()

    def test_la_reactivation_previent_aussi(self, api_client, equipe):
        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")
        api_client.post(f"/api/comptes/{equipe['guichetier'].id}/reactiver/", {}, format="json")

        assert Alerte.objects.filter(type=TypeAlerte.COMPTE, titre__startswith="Compte réactivé").exists()


@pytest.mark.django_db
class TestGardeFous:
    def test_le_motif_est_obligatoire(self, api_client, equipe):
        assert suspendre(api_client, equipe["pdg"], equipe["guichetier"]).status_code == 400
        assert suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="  ").status_code == 400
        assert suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Non").status_code == 400
        equipe["guichetier"].refresh_from_db()
        assert equipe["guichetier"].is_active

    def test_on_ne_suspend_pas_deux_fois(self, api_client, equipe):
        suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Écart de caisse répété")

        reponse = suspendre(api_client, equipe["pdg"], equipe["guichetier"], motif="Encore une fois")

        assert reponse.status_code == 400 and "déjà suspendu" in str(reponse.data)

    def test_on_ne_reactive_pas_un_compte_actif(self, api_client, equipe):
        api_client.force_authenticate(user=equipe["pdg"])

        reponse = api_client.post(f"/api/comptes/{equipe['guichetier'].id}/reactiver/", {}, format="json")

        assert reponse.status_code == 400 and "n'est pas suspendu" in str(reponse.data)

    def test_le_pdg_ne_se_suspend_pas_lui_meme_ni_un_autre_pdg(self, api_client, equipe):
        assert suspendre(api_client, equipe["pdg"], equipe["pdg"], motif="Par erreur, sans doute").status_code == 404
        assert suspendre(api_client, equipe["pdg"], equipe["pdg2"], motif="Tentative de prise de pouvoir").status_code == 404
        equipe["pdg2"].refresh_from_db()
        assert equipe["pdg2"].is_active

    def test_un_agent_d_une_autre_compagnie_est_introuvable(self, api_client, equipe, user_factory, company_b):
        etranger = user_factory("guichetier_b", Role.GUICHETIER, company=company_b)

        assert suspendre(api_client, equipe["pdg"], etranger, motif="Tentative hors compagnie").status_code == 404
        etranger.refresh_from_db()
        assert etranger.is_active

    @pytest.mark.parametrize("role", ["drh", "dirops", "sg", "chef_gare", "guichetier"])
    def test_seul_le_pdg_suspend(self, api_client, equipe, role):
        reponse = suspendre(api_client, equipe[role], equipe["bagagiste"], motif="Sans en avoir le droit")

        assert reponse.status_code == 403
        equipe["bagagiste"].refresh_from_db()
        assert equipe["bagagiste"].is_active

    def test_sans_authentification_rien_n_est_possible(self, api_client, equipe):
        assert api_client.get("/api/comptes/").status_code == 401
        assert api_client.post(f"/api/comptes/{equipe['guichetier'].id}/suspendre/", {}).status_code == 401


@pytest.mark.django_db
class TestListeDesComptes:
    def test_le_pdg_voit_les_agents_de_sa_compagnie_sans_les_pdg(self, api_client, equipe, user_factory, company_b):
        user_factory("guichetier_b", Role.GUICHETIER, company=company_b)
        api_client.force_authenticate(user=equipe["pdg"])

        vus = {compte["username"] for compte in api_client.get("/api/comptes/").data}

        assert vus == {"guichetier_comptes", "bagagiste_comptes", "chef_gare_comptes", "drh_comptes", "dirops_comptes", "sg_comptes"}

    def test_les_filtres_par_role_par_recherche_et_par_suspension(self, api_client, equipe):
        suspendre(api_client, equipe["pdg"], equipe["bagagiste"], motif="Absences injustifiées")

        assert [c["username"] for c in api_client.get("/api/comptes/?role=guichetier").data] == ["guichetier_comptes"]
        assert [c["username"] for c in api_client.get("/api/comptes/?q=kouame").data] == ["guichetier_comptes"]
        assert [c["username"] for c in api_client.get("/api/comptes/?q=BAGAGISTE").data] == ["bagagiste_comptes"]
        suspendus = api_client.get("/api/comptes/?suspendus=1").data
        assert [c["username"] for c in suspendus] == ["bagagiste_comptes"]
        assert suspendus[0]["motif_suspension"] == "Absences injustifiées" and suspendus[0]["actif"] is False

    def test_la_liste_donne_le_nom_le_role_et_la_gare(self, api_client, equipe, company_a):
        gare = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a)
        AffectationGare.objects.create(agent=equipe["guichetier"], gare=gare, company=company_a)
        api_client.force_authenticate(user=equipe["pdg"])

        vue = next(c for c in api_client.get("/api/comptes/").data if c["username"] == "guichetier_comptes")

        assert (vue["nom"], vue["role"], vue["role_libelle"], vue["gare"], vue["actif"]) == (
            "Rose Kouame", "guichetier", "Guichetier", "Adjamé", True,
        )

    @pytest.mark.parametrize("role", ["drh", "dirops", "sg", "chef_gare", "guichetier"])
    def test_les_autres_postes_ne_voient_pas_les_comptes(self, api_client, equipe, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/comptes/").status_code == 403
