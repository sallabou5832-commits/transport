"""Le chef de gare compose l'équipe locale de SA gare (cahier des charges : « affectation des équipes locales »)."""

import pytest

from core.models import Role
from reseau.models import AffectationGare, Gare


@pytest.fixture
def equipe(user_factory, company_a):
    return {
        "chef": user_factory("chef_gare_equipe", Role.CHEF_GARE, company=company_a),
        "chef_autre": user_factory("chef_gare_equipe2", Role.CHEF_GARE, company=company_a),
        "guichetier": user_factory("guichetier_equipe", Role.GUICHETIER, company=company_a),
        "bagagiste": user_factory("bagagiste_equipe", Role.BAGAGISTE, company=company_a),
        "chauffeur": user_factory("chauffeur_equipe", Role.CHAUFFEUR_PRINCIPAL, company=company_a),
        "dirops": user_factory("dirops_equipe", Role.DIRECTEUR_EXPLOITATION, company=company_a),
    }


@pytest.fixture
def gares(company_a, equipe):
    return {
        "mienne": Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=equipe["chef"]),
        "autre": Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a, chef=equipe["chef_autre"]),
    }


def affecter(api_client, utilisateur, agent, gare):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/affectations-gare/", {"agent": agent.id, "gare": gare.id})


@pytest.mark.django_db
class TestComposerUneEquipe:
    def test_le_chef_de_gare_affecte_un_guichetier_et_un_bagagiste_a_sa_gare(self, api_client, equipe, gares):
        for role in ("guichetier", "bagagiste"):
            reponse = affecter(api_client, equipe["chef"], equipe[role], gares["mienne"])

            assert reponse.status_code == 201
            assert reponse.data["gare_nom"] == "Adjamé" and reponse.data["agent_role"] == role

    def test_il_n_affecte_pas_a_la_gare_d_un_autre_chef(self, api_client, equipe, gares):
        reponse = affecter(api_client, equipe["chef"], equipe["guichetier"], gares["autre"])

        assert reponse.status_code == 400
        assert "gare que vous dirigez" in str(reponse.data["gare"])
        assert not AffectationGare.objects.exists()

    def test_la_direction_des_operations_affecte_n_importe_quelle_gare(self, api_client, equipe, gares):
        assert affecter(api_client, equipe["dirops"], equipe["guichetier"], gares["autre"]).status_code == 201

    @pytest.mark.parametrize("role", [Role.CHAUFFEUR_PRINCIPAL, Role.CHEF_LIGNE, Role.MAGASINIER, Role.DRH])
    def test_seuls_les_postes_d_equipe_locale_sont_affectables(
        self, api_client, equipe, gares, user_factory, company_a, role
    ):
        agent = user_factory(f"{role}_affectable", role, company=company_a)

        reponse = affecter(api_client, equipe["chef"], agent, gares["mienne"])

        assert reponse.status_code == 400
        assert "guichetiers et les bagagistes" in str(reponse.data["agent"])

    @pytest.mark.parametrize("role", ["guichetier", "bagagiste", "chauffeur", "dirops_pas"])
    def test_les_autres_postes_ne_composent_pas_d_equipe(self, api_client, equipe, gares, user_factory, company_a, role):
        auteur = equipe.get(role) or user_factory("magasinier_equipe", Role.MAGASINIER, company=company_a)

        assert affecter(api_client, auteur, equipe["guichetier"], gares["mienne"]).status_code == 403

    def test_un_agent_n_est_affecte_qu_a_une_gare(self, api_client, equipe, gares):
        affecter(api_client, equipe["chef"], equipe["guichetier"], gares["mienne"])

        reponse = affecter(api_client, equipe["dirops"], equipe["guichetier"], gares["autre"])

        assert reponse.status_code == 400
        assert "déjà affecté à la gare Adjamé" in str(reponse.data["agent"])

    def test_on_n_affecte_pas_un_agent_ni_une_gare_d_une_autre_compagnie(
        self, api_client, equipe, gares, company_b, user_factory
    ):
        etranger = user_factory("guichetier_b", Role.GUICHETIER, company=company_b)
        gare_b = Gare.objects.create(nom="Korhogo", ville="Korhogo", company=company_b)

        assert affecter(api_client, equipe["dirops"], etranger, gares["mienne"]).status_code == 400
        assert affecter(api_client, equipe["dirops"], equipe["guichetier"], gare_b).status_code == 400

    def test_le_chef_ne_retire_que_les_agents_de_sa_gare(self, api_client, equipe, gares):
        affecter(api_client, equipe["dirops"], equipe["guichetier"], gares["autre"])
        affectation = AffectationGare.objects.get()
        api_client.force_authenticate(user=equipe["chef"])

        assert api_client.delete(f"/api/affectations-gare/{affectation.id}/").status_code == 403

        api_client.force_authenticate(user=equipe["chef_autre"])
        assert api_client.delete(f"/api/affectations-gare/{affectation.id}/").status_code == 204

    def test_l_affectation_est_tracee(self, api_client, equipe, gares):
        from audit.models import JournalAudit

        affecter(api_client, equipe["chef"], equipe["guichetier"], gares["mienne"])

        entree = JournalAudit.objects.get(objet_type="reseau.affectationgare")
        assert entree.acteur == equipe["chef"] and entree.action == "creation"


@pytest.mark.django_db
class TestLecture:
    def test_un_agent_ne_voit_que_son_propre_rattachement(self, api_client, equipe, gares):
        affecter(api_client, equipe["chef"], equipe["guichetier"], gares["mienne"])
        affecter(api_client, equipe["chef"], equipe["bagagiste"], gares["mienne"])

        api_client.force_authenticate(user=equipe["guichetier"])
        vus = api_client.get("/api/affectations-gare/").data

        assert [a["agent"] for a in vus] == [equipe["guichetier"].id]

    def test_le_chef_de_gare_voit_les_equipes(self, api_client, equipe, gares):
        affecter(api_client, equipe["chef"], equipe["guichetier"], gares["mienne"])
        api_client.force_authenticate(user=equipe["chef"])

        assert len(api_client.get("/api/affectations-gare/").data) == 1

    def test_les_equipes_d_une_autre_compagnie_sont_invisibles(self, api_client, equipe, gares, company_b, user_factory):
        affecter(api_client, equipe["chef"], equipe["guichetier"], gares["mienne"])
        chef_b = user_factory("chef_gare_b2", Role.CHEF_GARE, company=company_b)
        api_client.force_authenticate(user=chef_b)

        assert api_client.get("/api/affectations-gare/").data == []

    def test_l_annuaire_des_agents_affectables_est_reserve_a_ceux_qui_composent_les_equipes(
        self, api_client, equipe, gares
    ):
        affecter(api_client, equipe["chef"], equipe["guichetier"], gares["mienne"])
        api_client.force_authenticate(user=equipe["chef"])
        annuaire = {a["id"]: a for a in api_client.get("/api/affectations-gare/agents-affectables/").data}

        assert set(annuaire) == {equipe["guichetier"].id, equipe["bagagiste"].id}
        assert annuaire[equipe["guichetier"].id]["gare"]["nom"] == "Adjamé"
        assert annuaire[equipe["bagagiste"].id]["gare"] is None

        for role in ("guichetier", "chauffeur"):
            api_client.force_authenticate(user=equipe[role])
            assert api_client.get("/api/affectations-gare/agents-affectables/").status_code == 403
