"""Aide au chargement : répartition du poids des colis en soute (avant, milieu, arrière)."""

from decimal import Decimal

import pytest

from colis.tests.conftest import agir, enregistrer


def poids(reponse):
    return {zone["nom"]: zone["poids_kg"] for zone in reponse.data["zones"]}


@pytest.mark.django_db
class TestPlanDeChargement:
    def enregistrer_des_colis(self, api_client, agents, monde, kilos):
        for numero, kg in enumerate(kilos):
            assert enregistrer(api_client, agents["bagagiste"], monde, poids_kg=str(kg), description=f"Colis {numero}").status_code == 201

    def plan(self, api_client, utilisateur, monde):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get(f"/api/departs/{monde['depart'].id}/plan-chargement/")

    def test_le_poids_est_reparti_entre_les_trois_zones(self, api_client, agents, monde):
        self.enregistrer_des_colis(api_client, agents, monde, [40, 30, 30, 20, 10, 10])

        reponse = self.plan(api_client, agents["bagagiste"], monde)

        assert reponse.status_code == 200
        assert [z["nom"] for z in reponse.data["zones"]] == ["avant", "milieu", "arrière"]
        assert Decimal(reponse.data["poids_total_kg"]) == 140
        assert all(Decimal(z["poids_kg"]) > 0 for z in reponse.data["zones"])
        assert Decimal(reponse.data["ecart_max_kg"]) <= 10  # 40 | 30+10 | 30+10 sur ce jeu : très équilibré
        assert sum(len(z["colis"]) for z in reponse.data["zones"]) == 6

    def test_les_plus_lourds_se_chargent_en_premier(self, api_client, agents, monde):
        self.enregistrer_des_colis(api_client, agents, monde, [5, 50, 20])

        ordre = self.plan(api_client, agents["bagagiste"], monde).data["ordre_chargement"]

        assert [Decimal(c["poids_kg"]) for c in ordre] == [50, 20, 5]
        assert [c["zone"] for c in ordre] == ["avant", "milieu", "arrière"]  # chaque gros colis dans une zone vide

    def test_un_seul_colis_va_dans_la_premiere_zone(self, api_client, agents, monde):
        self.enregistrer_des_colis(api_client, agents, monde, [12])

        assert poids(self.plan(api_client, agents["bagagiste"], monde))["avant"] == Decimal("12.00")

    def test_le_plan_est_stable_d_un_appel_a_l_autre(self, api_client, agents, monde):
        self.enregistrer_des_colis(api_client, agents, monde, [7, 7, 7, 7])

        assert self.plan(api_client, agents["bagagiste"], monde).data == self.plan(api_client, agents["bagagiste"], monde).data

    def test_un_depart_sans_colis_a_un_plan_vide(self, api_client, agents, monde):
        reponse = self.plan(api_client, agents["bagagiste"], monde)

        assert reponse.data["ordre_chargement"] == [] and Decimal(reponse.data["poids_total_kg"]) == 0
        assert reponse.data["depasse"] is False

    def test_le_depassement_de_la_charge_maximale_est_signale(self, api_client, agents, monde, settings):
        settings.COLIS_SOUTE_CHARGE_MAX_KG = 100
        self.enregistrer_des_colis(api_client, agents, monde, [60, 50])

        reponse = self.plan(api_client, agents["bagagiste"], monde)

        assert reponse.data["depasse"] is True and Decimal(reponse.data["charge_max_kg"]) == 100

    def test_un_colis_deja_remis_ne_compte_plus(self, api_client, agents, monde):
        self.enregistrer_des_colis(api_client, agents, monde, [10, 20])
        premier = enregistrer(api_client, agents["bagagiste"], monde, poids_kg="99").data
        agir(api_client, agents["chef_gare"], premier["id"], "annuler", motif="Colis refusé par le transporteur")

        assert Decimal(self.plan(api_client, agents["bagagiste"], monde).data["poids_total_kg"]) == 30

    @pytest.mark.parametrize("role", ["guichetier", "controleur_ligne", "chauffeur_principal", "chef_ligne"])
    def test_ces_postes_consultent_le_plan(self, api_client, agents, monde, role):
        assert self.plan(api_client, agents[role], monde).status_code == 200

    @pytest.mark.parametrize("role", ["drh", "directeur_financier", "magasinier"])
    def test_les_autres_postes_n_y_ont_pas_acces(self, api_client, agents, monde, role):
        assert self.plan(api_client, agents[role], monde).status_code == 403

    def test_le_plan_d_un_depart_d_une_autre_compagnie_est_introuvable(self, api_client, agents, monde, company_b, user_factory):
        api_client.force_authenticate(user=user_factory("chef_gare_plan_b", "chef_gare", company=company_b))

        assert api_client.get(f"/api/departs/{monde['depart'].id}/plan-chargement/").status_code == 404
