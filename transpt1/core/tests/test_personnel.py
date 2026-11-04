"""Personnel et comptes (`/api/comptes/`) : le PDG crée les comptes, les modifie et réinitialise un mot de passe ; le DRH aussi si le
règlement intérieur le lui permet (non par défaut, comme avant). Un mot de passe provisoire ne sert qu'à choisir le sien."""

import datetime

import pytest
from rest_framework.test import APIClient

from alertes.models import Alerte
from audit.models import JournalAudit
from configuration.models import ReglementInterieur
from core.models import Role, User
from reseau.models import AffectationGare, Gare
from supports.models import DossierAgent


@pytest.fixture
def pdg(user_factory, company_a):
    return user_factory("pdg_personnel", Role.PDG, company=company_a)


@pytest.fixture
def drh(user_factory, company_a):
    return user_factory("drh_personnel", Role.DRH, company=company_a)


@pytest.fixture
def guichetier(user_factory, company_a):
    return user_factory("guichetier_personnel", Role.GUICHETIER, company=company_a, first_name="Rose", last_name="Kouamé")


@pytest.fixture
def gare(company_a):
    return Gare.objects.create(nom="Gare Adjamé", ville="Abidjan", company=company_a)


@pytest.fixture
def gare_b(company_b):
    return Gare.objects.create(nom="Gare Bouaké", ville="Bouaké", company=company_b)


def client_de(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def permettre_au_drh(company):
    ReglementInterieur.objects.create(company=company, regles={"drh_gere_les_comptes": True})


NOUVEAU = {
    "username": "awa.kone",
    "first_name": "Awa",
    "last_name": "Koné",
    "role": "guichetier",
    "telephone": "07 07 12 34 56",
    "matricule": "STC-0042",
    "email": "awa.kone@stc.ci",
}


def creer(user, **corps):
    return client_de(user).post("/api/comptes/", {**NOUVEAU, **corps}, format="json")


def connecter(username, password):
    return APIClient().post("/api/auth/login/", {"username": username, "password": password})


@pytest.mark.django_db
class TestCreerUnCompte:
    def test_le_pdg_cree_un_compte_avec_un_mot_de_passe_provisoire(self, pdg, company_a):
        reponse = creer(pdg)

        assert reponse.status_code == 201
        provisoire = reponse.data["mot_de_passe_provisoire"]
        assert len(provisoire) == 14 and provisoire.count("-") == 2
        agent = User.objects.get(username="awa.kone")
        assert (agent.company_id, agent.role, agent.telephone, agent.matricule) == (
            company_a.id, "guichetier", "07 07 12 34 56", "STC-0042"
        )
        assert agent.doit_changer_mot_de_passe and agent.check_password(provisoire)
        assert reponse.data["doit_changer_mot_de_passe"] is True and reponse.data["nom"] == "Awa Koné"

    def test_le_mot_de_passe_provisoire_n_est_jamais_relu(self, pdg):
        creer(pdg)

        compte = next(c for c in client_de(pdg).get("/api/comptes/").data if c["username"] == "awa.kone")
        assert "mot_de_passe_provisoire" not in compte
        entree = JournalAudit.objects.get(objet_type="core.user", action="creation", objet_repr="awa.kone")
        assert entree.changements["password"] == "défini" and entree.acteur_id == pdg.id

    def test_avec_une_gare_le_guichetier_rejoint_son_equipe(self, pdg, gare):
        creer(pdg, gare=gare.id)

        assert AffectationGare.objects.get(agent__username="awa.kone").gare == gare

    def test_une_gare_d_une_autre_compagnie_est_refusee(self, pdg, gare_b):
        reponse = creer(pdg, gare=gare_b.id)

        assert reponse.status_code == 400 and "gare" in reponse.data
        assert not User.objects.filter(username="awa.kone").exists()

    def test_la_gare_ne_vaut_que_pour_l_equipe_locale(self, pdg, gare):
        reponse = creer(pdg, role="chef_ligne", gare=gare.id)

        assert reponse.status_code == 400
        assert "Gares et quais" in str(reponse.data["gare"])

    def test_avec_la_date_d_embauche_le_dossier_agent_est_ouvert(self, pdg):
        creer(pdg, date_embauche="2026-11-01")

        dossier = DossierAgent.objects.get(agent__username="awa.kone")
        assert dossier.date_embauche == datetime.date(2026, 11, 1) and dossier.poste == "Guichetier"

    def test_sans_date_d_embauche_pas_de_dossier(self, pdg):
        creer(pdg)

        assert not DossierAgent.objects.filter(agent__username="awa.kone").exists()

    def test_l_identifiant_est_unique_sur_toute_la_plateforme(self, pdg, user_factory, company_b):
        user_factory("Awa.Kone", Role.BAGAGISTE, company=company_b)

        reponse = creer(pdg)

        assert reponse.status_code == 400
        assert "déjà pris" in str(reponse.data["username"])
        assert "Express" not in str(reponse.data)  # rien ne dit à quelle compagnie il appartient

    def test_un_identifiant_avec_espace_est_refuse(self, pdg):
        assert creer(pdg, username="awa kone").status_code == 400

    def test_le_matricule_est_unique_dans_la_compagnie_seulement(self, pdg, guichetier, user_factory, company_b):
        guichetier.matricule = "STC-0042"
        guichetier.save()
        user_factory("autre_b", Role.GUICHETIER, company=company_b, matricule="STC-0043")

        doublon = creer(pdg)
        ailleurs = creer(pdg, username="yao", matricule="STC-0043")

        assert doublon.status_code == 400 and "Rose Kouamé" in str(doublon.data["matricule"])
        assert ailleurs.status_code == 201

    def test_un_telephone_invalide_est_refuse(self, pdg):
        assert creer(pdg, telephone="abc").status_code == 400

    @pytest.mark.parametrize("role", ["pdg", "superadmin", "inconnu"])
    def test_on_ne_cree_ni_pdg_ni_operateur_de_la_plateforme(self, pdg, role):
        assert creer(pdg, role=role).status_code == 400

    def test_le_nom_et_le_prenom_sont_obligatoires(self, pdg):
        assert creer(pdg, first_name="", last_name="").status_code == 400

    def test_le_drh_est_prevenu_de_la_creation_par_le_pdg(self, pdg, drh):
        creer(pdg)

        alerte = Alerte.objects.get(titre__startswith="Compte créé")
        assert alerte.roles_destinataires == ["drh"]


@pytest.mark.django_db
class TestLeDrhSelonLeReglement:
    def test_par_defaut_le_drh_ne_gere_pas_les_comptes_comme_avant(self, drh):
        assert client_de(drh).get("/api/comptes/").status_code == 403
        assert creer(drh).status_code == 403

    def test_le_refus_dit_que_c_est_le_reglement_interieur(self, drh, company_a):
        ReglementInterieur.objects.create(company=company_a, regles={"drh_gere_les_comptes": False})

        reponse = client_de(drh).get("/api/comptes/")

        assert reponse.status_code == 403 and "règlement intérieur" in str(reponse.data["detail"])

    def test_permis_par_le_pdg_le_drh_cree_et_le_pdg_est_prevenu(self, drh, pdg, company_a):
        permettre_au_drh(company_a)

        reponse = creer(drh)

        assert reponse.status_code == 201
        assert Alerte.objects.get(titre__startswith="Compte créé").roles_destinataires == ["pdg"]

    def test_le_drh_ne_suspend_toujours_pas(self, drh, guichetier, company_a):
        permettre_au_drh(company_a)

        reponse = client_de(drh).post(f"/api/comptes/{guichetier.id}/suspendre/", {"motif": "Absences répétées"}, format="json")

        assert reponse.status_code == 403

    def test_le_pdg_regle_la_regle_et_le_drh_non(self, drh, pdg):
        assert client_de(drh).patch("/api/configuration/reglement/", {"drh_gere_les_comptes": True}, format="json").status_code == 403
        assert client_de(pdg).patch("/api/configuration/reglement/", {"drh_gere_les_comptes": True}, format="json").status_code == 200
        assert client_de(drh).get("/api/comptes/").status_code == 200

    def test_une_autre_compagnie_n_est_pas_touchee(self, user_factory, company_a, company_b):
        permettre_au_drh(company_a)
        drh_b = user_factory("drh_b", Role.DRH, company=company_b)

        assert client_de(drh_b).get("/api/comptes/").status_code == 403


@pytest.mark.django_db
class TestModifierUnCompte:
    def test_le_pdg_complete_la_fiche(self, pdg, guichetier):
        reponse = client_de(pdg).patch(
            f"/api/comptes/{guichetier.id}/", {"telephone": "0505050505", "matricule": "STC-7"}, format="json"
        )

        assert reponse.status_code == 200
        guichetier.refresh_from_db()
        assert (guichetier.telephone, guichetier.matricule, guichetier.role) == ("0505050505", "STC-7", "guichetier")

    def test_l_identifiant_ne_change_pas(self, pdg, guichetier):
        client_de(pdg).patch(f"/api/comptes/{guichetier.id}/", {"username": "autre"}, format="json")

        guichetier.refresh_from_db()
        assert guichetier.username == "guichetier_personnel"

    def test_changer_de_poste_ferme_ses_sessions_et_previent(self, pdg, drh, guichetier):
        session = connecter("guichetier_personnel", "Demo!2024").data

        reponse = client_de(pdg).patch(f"/api/comptes/{guichetier.id}/", {"role": "bagagiste"}, format="json")

        assert reponse.status_code == 200 and reponse.data["role"] == "bagagiste"
        assert APIClient().post("/api/auth/refresh/", {"refresh": session["refresh"]}).status_code == 401
        assert Alerte.objects.get(titre__startswith="Changement de poste").message.startswith("Guichetier → Bagagiste")

    def test_un_agent_d_une_equipe_de_gare_n_en_change_pas_sans_en_sortir(self, pdg, guichetier, gare, company_a):
        AffectationGare.objects.create(agent=guichetier, gare=gare, company=company_a)

        reponse = client_de(pdg).patch(f"/api/comptes/{guichetier.id}/", {"role": "chef_ligne"}, format="json")

        assert reponse.status_code == 400 and "Gare Adjamé" in str(reponse.data["role"])

    def test_un_chef_de_gare_en_poste_ne_change_pas_de_poste(self, pdg, user_factory, company_a, gare):
        chef = user_factory("chef_personnel", Role.CHEF_GARE, company=company_a)
        gare.chef = chef
        gare.save()

        reponse = client_de(pdg).patch(f"/api/comptes/{chef.id}/", {"role": "chef_ligne"}, format="json")

        assert reponse.status_code == 400 and "désignez-lui d'abord un autre chef" in str(reponse.data["role"])

    def test_le_drh_ne_change_pas_son_propre_poste(self, drh, company_a):
        permettre_au_drh(company_a)

        reponse = client_de(drh).patch(f"/api/comptes/{drh.id}/", {"role": "directeur_financier"}, format="json")

        assert reponse.status_code == 400
        drh.refresh_from_db()
        assert drh.role == "drh"

    def test_un_pdg_ne_se_modifie_pas_ici(self, pdg, user_factory, company_a):
        autre_pdg = user_factory("pdg_bis", Role.PDG, company=company_a)

        assert client_de(pdg).patch(f"/api/comptes/{autre_pdg.id}/", {"telephone": "0101010101"}, format="json").status_code == 404

    def test_un_compte_d_une_autre_compagnie_est_introuvable(self, pdg, user_factory, company_b):
        etranger = user_factory("etranger", Role.GUICHETIER, company=company_b)

        assert client_de(pdg).patch(f"/api/comptes/{etranger.id}/", {"telephone": "0101010101"}, format="json").status_code == 404

    @pytest.mark.parametrize("role", [Role.SECRETAIRE_GENERAL, Role.CHEF_GARE, Role.GUICHETIER, Role.DIRECTEUR_EXPLOITATION])
    def test_les_autres_postes_ne_touchent_pas_aux_comptes(self, role, user_factory, company_a, guichetier):
        intrus = user_factory(f"intrus_{role}", role, company=company_a)

        assert client_de(intrus).patch(f"/api/comptes/{guichetier.id}/", {"telephone": "0101010101"}, format="json").status_code == 403
        assert creer(intrus).status_code == 403


@pytest.mark.django_db
class TestMotDePasseProvisoire:
    def test_reinitialiser_donne_un_nouveau_provisoire_et_ferme_les_sessions(self, pdg, guichetier):
        session = connecter("guichetier_personnel", "Demo!2024").data

        reponse = client_de(pdg).post(f"/api/comptes/{guichetier.id}/reinitialiser-mot-de-passe/")

        assert reponse.status_code == 200
        guichetier.refresh_from_db()
        assert guichetier.doit_changer_mot_de_passe and guichetier.check_password(reponse.data["mot_de_passe_provisoire"])
        assert APIClient().post("/api/auth/refresh/", {"refresh": session["refresh"]}).status_code == 401
        assert connecter("guichetier_personnel", "Demo!2024").status_code == 401

    def test_on_ne_reinitialise_pas_le_sien_ici(self, drh, company_a):
        permettre_au_drh(company_a)

        reponse = client_de(drh).post(f"/api/comptes/{drh.id}/reinitialiser-mot-de-passe/")

        assert reponse.status_code == 400 and "Mes paramètres" in str(reponse.data)

    def test_avec_un_provisoire_on_ne_fait_que_changer_son_mot_de_passe(self, pdg):
        provisoire = creer(pdg).data["mot_de_passe_provisoire"]
        session = connecter("awa.kone", provisoire)
        assert session.status_code == 200
        agent = APIClient()
        agent.credentials(HTTP_AUTHORIZATION=f"Bearer {session.data['access']}")

        assert agent.get("/api/auth/me/").data["doit_changer_mot_de_passe"] is True
        assert agent.get("/api/configuration/moi/").status_code == 200
        refus = agent.get("/api/departs/")
        assert refus.status_code == 403 and "provisoire" in str(refus.data["detail"])
        # Le code dit au mobile d'attendre (ventes hors ligne gardées en file) au lieu de lire un refus définitif.
        assert refus.data["code"] == "mot_de_passe_provisoire"
        vente = agent.post("/api/tickets/", {}, format="json")
        assert vente.status_code == 403 and vente.data["code"] == "mot_de_passe_provisoire"
        assert agent.post("/api/auth/fermer-autres-sessions/", {"refresh": session.data["refresh"]}).status_code == 403

        change = agent.post(
            "/api/auth/mot-de-passe/",
            {"ancien": provisoire, "nouveau": "Riviera-Palmeraie-26", "refresh": session.data["refresh"]},
        )

        assert change.status_code == 200
        libre = APIClient()
        libre.credentials(HTTP_AUTHORIZATION=f"Bearer {change.data['access']}")
        assert libre.get("/api/auth/me/").data["doit_changer_mot_de_passe"] is False
        assert libre.get("/api/departs/").status_code == 200

    def test_on_ne_garde_pas_le_provisoire_comme_mot_de_passe(self, pdg):
        provisoire = creer(pdg).data["mot_de_passe_provisoire"]
        session = connecter("awa.kone", provisoire).data
        agent = APIClient()
        agent.credentials(HTTP_AUTHORIZATION=f"Bearer {session['access']}")

        reponse = agent.post("/api/auth/mot-de-passe/", {"ancien": provisoire, "nouveau": provisoire, "refresh": session["refresh"]})

        assert reponse.status_code == 400


@pytest.mark.django_db
class TestListe:
    def test_la_liste_donne_la_fiche_et_l_etat_du_compte(self, pdg, guichetier):
        guichetier.matricule, guichetier.telephone = "STC-1", "0707070707"
        guichetier.save()

        vue = next(c for c in client_de(pdg).get("/api/comptes/").data if c["username"] == "guichetier_personnel")

        assert (vue["matricule"], vue["telephone"], vue["doit_changer_mot_de_passe"], vue["a_un_dossier"]) == (
            "STC-1", "0707070707", False, False
        )

    def test_la_derniere_connexion_est_relevee_sans_encombrer_le_journal(self, pdg, guichetier):
        assert next(c for c in client_de(pdg).get("/api/comptes/").data if c["id"] == guichetier.id)["last_login"] is None

        connecter("guichetier_personnel", "Demo!2024")

        vue = next(c for c in client_de(pdg).get("/api/comptes/").data if c["id"] == guichetier.id)
        assert vue["last_login"] is not None
        assert not JournalAudit.objects.filter(objet_type="core.user", objet_id=str(guichetier.id), action="modification").exists()

    def test_la_recherche_trouve_aussi_le_matricule(self, pdg, guichetier):
        guichetier.matricule = "STC-0099"
        guichetier.save()

        assert [c["username"] for c in client_de(pdg).get("/api/comptes/?q=0099").data] == ["guichetier_personnel"]
