"""Ce que l'écran du chef de gare lit des colis : ceux qui partent de sa gare ou y arrivent (`?gare=`), avec l'état du départ,
pour renvoyer un code, annuler un enregistrement ou marquer arrivé un colis resté « chargé »."""

import pytest

from billetterie.models import DepartStatut
from colis.tests.conftest import agir, enregistrer
from reseau.models import Gare


@pytest.mark.django_db
class TestColisDeLaGare:
    def test_la_gare_voit_ce_qui_part_de_chez_elle_et_ce_qui_y_arrive(self, api_client, agents, monde, company_a):
        colis = enregistrer(api_client, agents["bagagiste"], monde).data
        autre = Gare.objects.create(nom="Yamoussoukro", ville="Yamoussoukro", company=company_a)
        api_client.force_authenticate(user=agents["chef_gare"])

        depart = api_client.get(f"/api/colis/?gare={monde['gare_depart'].id}").data
        arrivee = api_client.get(f"/api/colis/?gare={monde['gare_arrivee'].id}").data
        ailleurs = api_client.get(f"/api/colis/?gare={autre.id}").data

        assert [c["id"] for c in depart] == [colis["id"]] == [c["id"] for c in arrivee]
        assert ailleurs == []
        assert api_client.get("/api/colis/?gare=abc").data == []

    def test_la_reponse_dit_la_gare_de_depart_et_l_etat_du_depart(self, api_client, agents, monde):
        colis = enregistrer(api_client, agents["bagagiste"], monde).data

        assert colis["gare_depart"] == monde["gare_depart"].id
        assert colis["depart_statut"] == DepartStatut.PLANIFIE

    def test_le_chef_de_gare_renvoie_le_code_d_un_colis_verrouille(self, api_client, agents, monde):
        colis = enregistrer(api_client, agents["bagagiste"], monde).data
        agir(api_client, agents["bagagiste"], colis["id"], "charger")
        monde["depart"].statut = DepartStatut.TERMINE
        monde["depart"].save()
        assert agir(api_client, agents["chef_gare"], colis["id"], "arriver").data["statut"] == "arrive"
        for _ in range(5):
            agir(api_client, agents["bagagiste_arrivee"], colis["id"], "retirer", code="000000")
        api_client.force_authenticate(user=agents["chef_gare"])
        assert api_client.get(f"/api/colis/{colis['id']}/").data["code_verrouille"] is True

        reponse = agir(api_client, agents["chef_gare_arrivee"], colis["id"], "renvoyer-code")

        assert reponse.status_code == 200 and reponse.data["code_verrouille"] is False

    def test_le_chef_de_gare_annule_un_enregistrement_avec_un_motif(self, api_client, agents, monde):
        colis = enregistrer(api_client, agents["bagagiste"], monde).data

        assert agir(api_client, agents["chef_gare"], colis["id"], "annuler", motif="").status_code == 400
        reponse = agir(api_client, agents["chef_gare"], colis["id"], "annuler", motif="Client parti sans payer")

        assert reponse.status_code == 200 and reponse.data["statut"] == "annule"
