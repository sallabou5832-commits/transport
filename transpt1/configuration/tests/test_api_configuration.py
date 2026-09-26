import pytest

from audit.models import JournalAudit
from configuration.models import ConfigurationPoste
from configuration.tests.conftest import ma_configuration, regler_agent, regler_poste


@pytest.mark.django_db
class TestConfigurationEffective:
    def test_un_poste_non_regle_suit_les_defauts_du_socle(self, api_client, agents):
        config = ma_configuration(api_client, agents["guichetier"])

        assert config["niveau_automatisation"] == "assiste" and config["niveau_gamification"] == "complet"
        assert config["fonctions_desactivees"] == [] and config["prefere_vocal"] is False
        assert config["cadre"] == {"automatisation_max": "automatique", "gamification_max": "complet"}

    def test_direction_support_et_juridique_demarrent_sobres(self, api_client, agents):
        assert ma_configuration(api_client, agents["drh"])["niveau_gamification"] == "sobre"
        assert ma_configuration(api_client, agents["secretaire_general"])["niveau_gamification"] == "sobre"

    def test_le_superadmin_n_a_pas_de_jeu(self, api_client, superadmin_user):
        config = ma_configuration(api_client, superadmin_user)

        assert config["niveau_gamification"] == "aucun" and config["peut_configurer"] == []

    def test_chacun_sait_ce_qu_il_peut_regler(self, api_client, agents):
        assert ma_configuration(api_client, agents["chef_gare"])["peut_configurer"] == ["bagagiste", "guichetier"]
        assert ma_configuration(api_client, agents["guichetier"])["peut_configurer"] == []
        assert ma_configuration(api_client, agents["pdg"])["peut_fixer_le_cadre"] is True
        assert ma_configuration(api_client, agents["chef_gare"])["peut_fixer_le_cadre"] is False

    def test_refuse_sans_authentification(self, api_client):
        assert api_client.get("/api/configuration/moi/").status_code == 401


@pytest.mark.django_db
class TestReglerUnPoste:
    def test_le_chef_de_gare_regle_le_guichetier_et_le_guichetier_le_voit(self, api_client, agents):
        reponse = regler_poste(
            api_client, agents["chef_gare"], "guichetier",
            niveau_automatisation="manuel", niveau_gamification="sobre", prefere_vocal=True,
            fonctions_desactivees=["planification_departs"],
        )

        assert reponse.status_code == 200
        assert reponse.data["effectif"] == {"niveau_automatisation": "manuel", "niveau_gamification": "sobre"}
        config = ma_configuration(api_client, agents["guichetier"])
        assert config["niveau_automatisation"] == "manuel" and config["niveau_gamification"] == "sobre"
        assert config["prefere_vocal"] is True and config["fonctions_desactivees"] == ["planification_departs"]

    def test_le_reglage_d_un_poste_ne_touche_pas_les_autres(self, api_client, agents):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="manuel")

        assert ma_configuration(api_client, agents["bagagiste"])["niveau_automatisation"] == "assiste"
        assert ma_configuration(api_client, agents["chef_gare"])["niveau_automatisation"] == "assiste"

    @pytest.mark.parametrize(
        "demandeur,role",
        [
            ("chef_gare", "chef_ligne"),  # pas son subordonné
            ("chef_gare", "chef_gare"),  # pas lui-même
            ("chef_gare", "directeur_exploitation"),  # pas son supérieur
            ("guichetier", "bagagiste"),
            ("drh", "guichetier"),
            ("directeur_exploitation", "guichetier"),  # pas un subordonné DIRECT : c'est l'affaire du chef de gare
            ("chef_ligne", "guichetier"),
        ],
    )
    def test_on_ne_regle_que_ses_subordonnes_directs(self, api_client, agents, demandeur, role):
        reponse = regler_poste(api_client, agents[demandeur], role, niveau_automatisation="manuel")

        assert reponse.status_code == 403
        assert not ConfigurationPoste.objects.exists()

    def test_le_directeur_des_operations_regle_les_chefs_de_gare(self, api_client, agents):
        assert regler_poste(api_client, agents["directeur_exploitation"], "chef_gare", niveau_gamification="sobre").status_code == 200
        assert ma_configuration(api_client, agents["chef_gare"])["niveau_gamification"] == "sobre"

    def test_le_pdg_regle_n_importe_quel_poste_mais_pas_le_sien(self, api_client, agents):
        for role in ("guichetier", "chef_atelier", "drh", "mecanicien", "qhse"):
            assert regler_poste(api_client, agents["pdg"], role, niveau_automatisation="manuel").status_code == 200, role
        assert regler_poste(api_client, agents["pdg"], "pdg", niveau_automatisation="manuel").status_code == 403

    def test_un_poste_inconnu_est_introuvable(self, api_client, agents):
        assert regler_poste(api_client, agents["pdg"], "inconnu", niveau_automatisation="manuel").status_code == 404
        assert regler_poste(api_client, agents["pdg"], "superadmin", niveau_automatisation="manuel").status_code == 404

    @pytest.mark.parametrize(
        "corps,champ",
        [
            ({"niveau_automatisation": "turbo"}, "niveau_automatisation"),
            ({"niveau_gamification": "enorme"}, "niveau_gamification"),
            ({"fonctions_desactivees": ["voler_la_caisse"]}, "fonctions_desactivees"),
        ],
    )
    def test_les_valeurs_invalides_sont_refusees(self, api_client, agents, corps, champ):
        reponse = regler_poste(api_client, agents["chef_gare"], "guichetier", **corps)

        assert reponse.status_code == 400 and champ in reponse.data

    def test_une_valeur_vide_rend_le_defaut(self, api_client, agents):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="manuel")

        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation=None)

        assert ma_configuration(api_client, agents["guichetier"])["niveau_automatisation"] == "assiste"

    def test_la_liste_ne_montre_que_les_postes_sous_son_autorite(self, api_client, agents):
        api_client.force_authenticate(user=agents["chef_gare"])
        liste = api_client.get("/api/configuration/postes/").data
        assert [p["role"] for p in liste] == ["guichetier", "bagagiste"]
        assert liste[0]["role_libelle"] == "Guichetier" and liste[0]["effectif"]["niveau_gamification"] == "complet"

        api_client.force_authenticate(user=agents["guichetier"])
        assert api_client.get("/api/configuration/postes/").data == []

    def test_la_lecture_d_un_poste_hors_autorite_est_refusee(self, api_client, agents):
        api_client.force_authenticate(user=agents["chef_gare"])

        assert api_client.get("/api/configuration/postes/chef_ligne/").status_code == 403
        assert api_client.get("/api/configuration/postes/guichetier/").status_code == 200

    def test_patch_ne_change_que_ce_qui_est_envoye(self, api_client, agents):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="manuel", prefere_vocal=True)
        api_client.force_authenticate(user=agents["chef_gare"])

        api_client.patch("/api/configuration/postes/guichetier/", {"niveau_gamification": "sobre"}, format="json")

        config = ma_configuration(api_client, agents["guichetier"])
        assert config["niveau_automatisation"] == "manuel" and config["niveau_gamification"] == "sobre"
        assert config["prefere_vocal"] is True

    def test_le_reglage_est_trace_avec_son_auteur(self, api_client, agents):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="manuel")

        entree = JournalAudit.objects.get(objet_type="configuration.configurationposte", action="creation")
        assert entree.acteur == agents["chef_gare"] and entree.changements["niveau_automatisation"] == "manuel"


@pytest.mark.django_db
class TestCadreDeLaCompagnie:
    def test_le_pdg_fixe_le_cadre_et_tous_le_voient(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])

        reponse = api_client.patch(
            "/api/configuration/compagnie/", {"automatisation_max": "assiste", "gamification_max": "sobre"}, format="json"
        )

        assert reponse.status_code == 200
        assert ma_configuration(api_client, agents["guichetier"])["cadre"] == {
            "automatisation_max": "assiste", "gamification_max": "sobre",
        }

    def test_le_cadre_plafonne_les_niveaux_effectifs(self, api_client, agents):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="automatique", niveau_gamification="complet")
        api_client.force_authenticate(user=agents["pdg"])
        api_client.patch("/api/configuration/compagnie/", {"automatisation_max": "manuel", "gamification_max": "aucun"}, format="json")

        config = ma_configuration(api_client, agents["guichetier"])

        assert config["niveau_automatisation"] == "manuel" and config["niveau_gamification"] == "aucun"

    def test_on_ne_peut_pas_regler_un_poste_au_dessus_du_cadre(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])
        api_client.patch("/api/configuration/compagnie/", {"automatisation_max": "assiste"}, format="json")

        reponse = regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="automatique")

        assert reponse.status_code == 400 and "plafonne" in str(reponse.data["niveau_automatisation"])

    @pytest.mark.parametrize("role", ["chef_gare", "directeur_exploitation", "drh", "guichetier"])
    def test_seul_le_pdg_fixe_le_cadre(self, api_client, agents, role):
        api_client.force_authenticate(user=agents[role])

        assert api_client.patch("/api/configuration/compagnie/", {"automatisation_max": "manuel"}, format="json").status_code == 403
        assert api_client.get("/api/configuration/compagnie/").status_code == 200

    def test_le_cadre_d_une_compagnie_ne_touche_pas_l_autre(self, api_client, agents, company_b, user_factory):
        api_client.force_authenticate(user=agents["pdg"])
        api_client.patch("/api/configuration/compagnie/", {"automatisation_max": "manuel"}, format="json")
        guichetier_b = user_factory("guichetier_b_config", "guichetier", company=company_b)

        assert ma_configuration(api_client, guichetier_b)["niveau_automatisation"] == "assiste"

    def test_les_reglages_d_une_compagnie_sont_invisibles_pour_l_autre(self, api_client, agents, company_b, user_factory):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="manuel")
        chef_b = user_factory("chef_gare_b_config", "chef_gare", company=company_b)
        api_client.force_authenticate(user=chef_b)

        liste = api_client.get("/api/configuration/postes/").data

        assert [p["niveau_automatisation"] for p in liste] == [None, None]


@pytest.mark.django_db
class TestReglerUnAgent:
    def test_l_ajustement_d_un_agent_l_emporte_sur_celui_du_poste(self, api_client, agents):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="automatique")

        reponse = regler_agent(
            api_client, agents["chef_gare"], agents["guichetier"],
            niveau_automatisation="manuel", prefere_vocal=True, aisance_numerique="faible",
        )

        assert reponse.status_code == 200 and reponse.data["aisance_numerique"] == "faible"
        config = ma_configuration(api_client, agents["guichetier"])
        assert config["niveau_automatisation"] == "manuel" and config["prefere_vocal"] is True
        assert config["aisance_numerique"] == "faible"

    def test_les_collegues_du_meme_poste_ne_sont_pas_touches(self, api_client, agents, user_factory, company_a):
        autre = user_factory("guichetier_config_bis", "guichetier", company=company_a)
        regler_agent(api_client, agents["chef_gare"], agents["guichetier"], niveau_automatisation="manuel")

        assert ma_configuration(api_client, autre)["niveau_automatisation"] == "assiste"

    def test_l_agent_sans_ajustement_suit_son_poste(self, api_client, agents):
        regler_poste(api_client, agents["chef_gare"], "guichetier", niveau_automatisation="manuel", prefere_vocal=True)
        regler_agent(api_client, agents["chef_gare"], agents["guichetier"], aisance_numerique="elevee")

        config = ma_configuration(api_client, agents["guichetier"])

        assert config["niveau_automatisation"] == "manuel" and config["prefere_vocal"] is True
        assert config["aisance_numerique"] == "elevee"

    def test_l_ajustement_reste_sous_le_cadre(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])
        api_client.patch("/api/configuration/compagnie/", {"automatisation_max": "assiste"}, format="json")

        assert regler_agent(api_client, agents["chef_gare"], agents["guichetier"], niveau_automatisation="automatique").status_code == 400

    def test_on_ne_regle_que_les_agents_de_ses_subordonnes_directs(self, api_client, agents):
        assert regler_agent(api_client, agents["chef_gare"], agents["chauffeur_principal"], aisance_numerique="faible").status_code == 404
        assert regler_agent(api_client, agents["chef_gare"], agents["chef_gare"], aisance_numerique="faible").status_code == 404
        assert regler_agent(api_client, agents["guichetier"], agents["bagagiste"], aisance_numerique="faible").status_code == 404

    def test_on_ne_regle_pas_un_agent_d_une_autre_compagnie(self, api_client, agents, company_b, user_factory):
        etranger = user_factory("guichetier_b_agent", "guichetier", company=company_b)

        assert regler_agent(api_client, agents["chef_gare"], etranger, aisance_numerique="faible").status_code == 404

    def test_la_liste_des_agents_est_celle_de_ses_subordonnes(self, api_client, agents):
        api_client.force_authenticate(user=agents["chef_gare"])

        liste = api_client.get("/api/configuration/agents/").data

        assert {a["agent_role"] for a in liste} == {"guichetier", "bagagiste"}
        assert all(a["aisance_numerique"] == "moyenne" for a in liste)

    def test_le_catalogue_decrit_les_niveaux_et_les_fonctions(self, api_client, agents):
        api_client.force_authenticate(user=agents["guichetier"])

        catalogue = api_client.get("/api/configuration/catalogue/").data

        assert [n["valeur"] for n in catalogue["niveaux_automatisation"]] == ["manuel", "assiste", "automatique"]
        assert [n["valeur"] for n in catalogue["niveaux_gamification"]] == ["aucun", "sobre", "complet"]
        assert "vente_ticket" in [f["code"] for f in catalogue["fonctions"]]
