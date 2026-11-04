"""Le guide d'utilisation de chaque poste, rangé par pôle : lisible par tous, le règlement intérieur cité est celui de la
compagnie du lecteur. La concordance avec les pages du site est vérifiée par role_coverage_tests/test_guides.py."""

import pytest
from rest_framework.test import APIClient

from communication.guides import COMMUNS, FICHES, MOMENTS, PLATEFORME
from communication.poles import POLES, TOUS_LES_POSTES
from configuration.models import ReglementInterieur
from configuration.regles import REGLEMENT
from core.models import Role
from core.tests.test_sessions import connecter


def lire(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    reponse = api_client.get("/api/guides/")
    assert reponse.status_code == 200
    return reponse.data


def fiche(guide, poste):
    return next(f for pole in guide["poles"] for f in pole["postes"] if f["poste"] == poste)


@pytest.mark.django_db
class TestLecture:
    def test_il_faut_etre_connecte(self):
        assert APIClient().get("/api/guides/").status_code == 401

    @pytest.mark.parametrize("role", TOUS_LES_POSTES)
    def test_chaque_poste_lit_les_guides_de_tous_les_postes(self, api_client, user_factory, company_a, role):
        guide = lire(api_client, user_factory(f"{role}_guide", role, company=company_a))

        assert [pole["pole"] for pole in guide["poles"]] == list(POLES)
        assert [f["poste"] for pole in guide["poles"] for f in pole["postes"]] == [r.value for r in TOUS_LES_POSTES]
        assert guide["mon_poste"] == role
        assert guide["mon_pole"] == next(cle for cle, (_, roles) in POLES.items() if role in roles)
        assert [t["titre"] for t in guide["communs"]["taches"]] == [t["titre"] for t in COMMUNS["taches"]]
        assert [m["code"] for m in guide["moments"]] == list(MOMENTS)

    def test_la_fiche_de_la_plateforme_n_est_montree_qu_a_son_operateur(self, api_client, superadmin_user, company_a_user):
        guide = lire(api_client, superadmin_user)

        assert guide["poles"][-1]["pole"] == "plateforme" and guide["mon_pole"] == "plateforme"
        assert [f["poste"] for f in guide["poles"][-1]["postes"]] == ["superadmin"]
        assert "plateforme" not in [pole["pole"] for pole in lire(api_client, company_a_user)["poles"]]

    def test_le_mot_de_passe_provisoire_ferme_aussi_le_guide(self, user_factory, company_a):
        agent = user_factory("guide_provisoire", Role.GUICHETIER, company=company_a, doit_changer_mot_de_passe=True)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {connecter(agent).data['access']}")

        assert client.get("/api/guides/").status_code == 403


class TestContenu:
    def test_chaque_poste_d_une_compagnie_a_sa_fiche_complete(self):
        assert set(FICHES) == set(TOUS_LES_POSTES)
        for role, contenu in {**FICHES, Role.SUPERADMIN: PLATEFORME["fiche"]}.items():
            assert contenu["mission"] and contenu["ecrans"] and contenu["taches"], role
            for tache in contenu["taches"]:
                assert tache["titre"] and tache["etapes"], (role, tache["titre"])

    def test_les_taches_suivent_le_deroule_d_une_journee(self):
        ordre = list(MOMENTS)
        for role, contenu in {**FICHES, Role.SUPERADMIN: PLATEFORME["fiche"], "communs": COMMUNS}.items():
            rangs = [ordre.index(t["moment"]) for t in contenu["taches"]]
            assert rangs == sorted(rangs), role

    def test_tout_passage_de_relais_est_decrit_des_deux_cotes(self):
        cites = {role: {r for t in contenu["taches"] for r in t["avec"]} for role, contenu in FICHES.items()}
        for role, autres in cites.items():
            assert role not in autres, role
            for autre in autres:
                assert autre in FICHES, (role, autre)
                assert role in cites[autre], f"La fiche {role.label} cite {autre.label}, qui ne la cite pas en retour."

    def test_une_tache_ne_depend_que_d_une_regle_du_reglement_qui_vise_son_poste(self):
        for role, contenu in FICHES.items():
            for tache in contenu["taches"]:
                if tache["regle"]:
                    assert role in REGLEMENT[tache["regle"]].roles, (role, tache["regle"])


@pytest.mark.django_db
class TestCeQuiDependDeLaCompagnie:
    def test_qui_regle_le_poste_et_ce_qu_il_regle(self, api_client, company_a_user):
        guide = lire(api_client, company_a_user)

        assert fiche(guide, "guichetier")["regle_par"] == ["Chef de gare", "PDG"]
        assert fiche(guide, "chef_gare")["regle"] == ["Guichetier", "Bagagiste"]
        assert fiche(guide, "drh")["regle_par"] == ["PDG"] and fiche(guide, "drh")["regle"] == []
        assert fiche(guide, "pdg")["regle_par"] == []

    def test_une_tache_nomme_les_postes_avec_qui_elle_se_coordonne(self, api_client, company_a_user):
        caisse = next(t for t in fiche(lire(api_client, company_a_user), "guichetier")["taches"] if t["titre"] == "Clôturer sa caisse")

        assert caisse["avec"] == [{"poste": "chef_gare", "libelle": "Chef de gare"}]
        assert caisse["moment"] == "fin" and caisse["moment_libelle"] == "En fin de journée"

    def test_chaque_fiche_cite_les_regles_du_reglement_qui_visent_son_poste(self, api_client, company_a_user):
        guide = lire(api_client, company_a_user)

        for code, regle in REGLEMENT.items():
            for role in TOUS_LES_POSTES:
                assert (code in [r["code"] for r in fiche(guide, role.value)["reglement"]]) == (role in regle.roles), (code, role)

    def test_sans_reglement_le_guide_dit_le_defaut_du_socle(self, api_client, company_a_user):
        drh = fiche(lire(api_client, company_a_user), "drh")

        assert drh["reglement"] == [
            {"code": "drh_gere_les_comptes", "libelle": REGLEMENT["drh_gere_les_comptes"].libelle, "permis": False, "decide": "PDG"}
        ]
        assert [t["permise"] for t in drh["taches"] if t["regle"]] == [False]
        assert {t["permise"] for t in drh["taches"] if not t["regle"]} == {None}

    def test_le_guide_suit_le_reglement_de_la_compagnie_du_lecteur_et_d_elle_seule(
        self, api_client, company_a_user, company_b_user
    ):
        ReglementInterieur.objects.create(
            company=company_a_user.company, regles={"drh_gere_les_comptes": True, "mecanicien_supprime_ses_ordres": False}
        )

        guide_a = lire(api_client, company_a_user)
        assert fiche(guide_a, "drh")["reglement"][0]["permis"] is True
        mecanicien = fiche(guide_a, "mecanicien")
        assert {r["code"]: r["permis"] for r in mecanicien["reglement"]} == {
            "mecanicien_confie_ses_ordres": True, "mecanicien_supprime_ses_ordres": False, "reparation_leve_le_blocage_qhse": True,
        }
        guide_b = lire(api_client, company_b_user)
        assert fiche(guide_b, "drh")["reglement"][0]["permis"] is False
        assert all(r["permis"] for r in fiche(guide_b, "mecanicien")["reglement"])

    def test_l_operateur_lit_le_defaut_du_socle(self, api_client, superadmin_user, company_a):
        ReglementInterieur.objects.create(company=company_a, regles={"drh_gere_les_comptes": True})

        assert fiche(lire(api_client, superadmin_user), "drh")["reglement"][0]["permis"] is False
