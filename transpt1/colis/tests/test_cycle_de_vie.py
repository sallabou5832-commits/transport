"""Suivi de bout en bout : enregistré → chargé → (le car part, arrive) → arrivé → retiré, avec le client prévenu à
chaque étape et la gare d'arrivée alertée au départ du car (cahier des charges, poste Bagagiste)."""

import re

import pytest

from alertes.models import Alerte
from alertes.tests.conftest import alertes_de
from colis.models import Colis, StatutColis
from colis.tests.conftest import agir, enregistrer
from notifications.models import NotificationLog


def code_envoye(numero="+2250700000003"):
    message = NotificationLog.objects.filter(destinataire=numero, contenu__contains="Code de retrait").first().contenu
    return re.search(r"Code de retrait : ([A-Z0-9]{6})", message).group(1)


def messages(numero):
    return list(NotificationLog.objects.filter(destinataire=numero, canal="sms").values_list("contenu", flat=True))


@pytest.fixture
def colis(api_client, agents, monde):
    return enregistrer(api_client, agents["bagagiste"], monde).data


def faire_partir_et_arriver(api_client, agents, monde):
    api_client.force_authenticate(user=agents["chauffeur_principal"])
    api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/")
    api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/arriver/")


@pytest.mark.django_db
class TestChargement:
    def test_le_bagagiste_charge_et_le_client_est_prevenu(self, api_client, agents, monde, colis):
        reponse = agir(api_client, agents["bagagiste"], colis["id"], "charger")

        assert reponse.status_code == 200 and reponse.data["statut"] == StatutColis.CHARGE
        assert reponse.data["charge_le"] is not None
        assert any("chargé" in m for m in messages("+2250700000003"))
        assert any("chargé" in m for m in messages("+2250700000002"))

    def test_on_ne_charge_pas_deux_fois(self, api_client, agents, colis):
        agir(api_client, agents["bagagiste"], colis["id"], "charger")

        assert agir(api_client, agents["bagagiste"], colis["id"], "charger").status_code == 400

    def test_on_ne_charge_plus_apres_le_depart_du_car(self, api_client, agents, monde, colis):
        api_client.force_authenticate(user=agents["chauffeur_principal"])
        api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/")

        reponse = agir(api_client, agents["bagagiste"], colis["id"], "charger")

        assert reponse.status_code == 400 and "déjà parti" in str(reponse.data)

    @pytest.mark.parametrize("role", ["guichetier", "chauffeur_principal", "qhse", "drh"])
    def test_seuls_les_postes_de_colis_chargent(self, api_client, agents, colis, role):
        assert agir(api_client, agents[role], colis["id"], "charger").status_code == 403


@pytest.mark.django_db
class TestRestitution:
    def test_au_depart_la_gare_d_arrivee_est_prevenue_du_nombre_de_colis_a_restituer(
        self, api_client, agents, monde, colis
    ):
        agir(api_client, agents["bagagiste"], colis["id"], "charger")
        api_client.force_authenticate(user=agents["chauffeur_principal"])

        api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/")

        for role in ("bagagiste_arrivee", "chef_gare_arrivee"):
            visibles = [a for a in alertes_de(api_client, agents[role]) if a["type"] == "colis"]
            assert len(visibles) == 1, role
            assert visibles[0]["titre"] == "1 colis à restituer : Adjamé-Bouaké"
            assert "Bouaké" in visibles[0]["message"] and "12" in visibles[0]["message"]
        # La gare de départ, elle, n'est pas dérangée : tout est chargé.
        assert [a for a in alertes_de(api_client, agents["bagagiste"]) if a["type"] == "colis"] == []

    def test_un_colis_enregistre_mais_jamais_charge_est_signale_a_la_gare_de_depart(
        self, api_client, agents, monde, colis
    ):
        api_client.force_authenticate(user=agents["chauffeur_principal"])

        api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/")

        for role in ("bagagiste", "chef_gare"):
            visibles = [a for a in alertes_de(api_client, agents[role]) if a["type"] == "colis"]
            assert [a["titre"] for a in visibles] == ["1 colis enregistré(s) non chargé(s) : Adjamé-Bouaké"], role

    def test_sans_colis_le_depart_ne_declenche_aucune_alerte_de_colis(self, api_client, agents, monde):
        api_client.force_authenticate(user=agents["chauffeur_principal"])

        api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/")

        assert not Alerte.objects.filter(type="colis").exists()

    def test_un_bagagiste_non_affecte_ne_recoit_pas_l_alerte_de_restitution_d_une_autre_gare(
        self, api_client, agents, monde, colis
    ):
        agir(api_client, agents["bagagiste"], colis["id"], "charger")
        api_client.force_authenticate(user=agents["chauffeur_principal"])
        api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/")

        assert [a for a in alertes_de(api_client, agents["bagagiste"]) if "restituer" in a["titre"]] == []

    def test_a_l_arrivee_les_colis_charges_deviennent_arrives_et_les_clients_sont_prevenus(
        self, api_client, agents, monde, colis
    ):
        agir(api_client, agents["bagagiste"], colis["id"], "charger")

        faire_partir_et_arriver(api_client, agents, monde)

        colis_arrive = Colis.objects.get(pk=colis["id"])
        assert colis_arrive.statut == StatutColis.ARRIVE and colis_arrive.arrive_le is not None
        assert any("arrivé à la gare de Bouaké" in m for m in messages("+2250700000003"))
        titres = [a["titre"] for a in alertes_de(api_client, agents["bagagiste_arrivee"])]
        assert "1 colis arrivé(s) à retirer : Bouaké" in titres

    def test_un_colis_jamais_charge_reste_enregistre_a_l_arrivee(self, api_client, agents, monde, colis):
        faire_partir_et_arriver(api_client, agents, monde)

        assert Colis.objects.get(pk=colis["id"]).statut == StatutColis.ENREGISTRE

    def test_un_echec_cote_colis_n_empeche_pas_le_car_de_partir_ni_d_arriver(
        self, api_client, agents, monde, colis, monkeypatch
    ):
        def casse(_):
            raise RuntimeError("panne")

        monkeypatch.setattr("colis.services.annoncer_restitution", casse)
        monkeypatch.setattr("colis.services.marquer_arrives", casse)
        api_client.force_authenticate(user=agents["chauffeur_principal"])

        assert api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/").status_code == 200
        assert api_client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/arriver/").status_code == 200

    def test_arriver_a_la_main_rattrape_un_colis_reste_en_route(self, api_client, agents, monde, colis):
        agir(api_client, agents["bagagiste"], colis["id"], "charger")
        assert agir(api_client, agents["bagagiste_arrivee"], colis["id"], "arriver").status_code == 400  # car pas arrivé

        monde["depart"].statut = "termine"
        monde["depart"].save()
        reponse = agir(api_client, agents["bagagiste_arrivee"], colis["id"], "arriver")

        assert reponse.status_code == 200 and reponse.data["statut"] == StatutColis.ARRIVE


@pytest.mark.django_db
class TestRetrait:
    @pytest.fixture
    def colis_arrive(self, api_client, agents, monde, colis):
        agir(api_client, agents["bagagiste"], colis["id"], "charger")
        faire_partir_et_arriver(api_client, agents, monde)
        return colis

    def test_le_bon_code_remet_le_colis(self, api_client, agents, colis_arrive):
        reponse = agir(
            api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer",
            code=code_envoye(), retire_par_nom="Mariam Toure",
        )

        assert reponse.status_code == 200 and reponse.data["statut"] == StatutColis.RETIRE
        assert reponse.data["retire_par_nom"] == "Mariam Toure" and reponse.data["retire_le"] is not None
        assert Colis.objects.get(pk=colis_arrive["id"]).retire_par == agents["bagagiste_arrivee"]
        assert any("retiré par Mariam Toure" in m for m in messages("+2250700000002"))  # l'expéditeur
        assert any("remis à Mariam Toure" in m for m in messages("+2250700000003"))  # le destinataire

    def test_le_code_est_tolerant_sur_la_casse_et_les_separateurs(self, api_client, agents, colis_arrive):
        code = code_envoye()

        reponse = agir(
            api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code=f" {code[:3].lower()}-{code[3:].lower()} "
        )

        assert reponse.status_code == 200

    def test_un_mauvais_code_est_refuse_et_compte_les_essais(self, api_client, agents, colis_arrive):
        reponse = agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code="AAAAAA")

        assert reponse.status_code == 400 and "Il reste 4 essai" in str(reponse.data["code"])
        assert Colis.objects.get(pk=colis_arrive["id"]).tentatives_code == 1
        assert Colis.objects.get(pk=colis_arrive["id"]).statut == StatutColis.ARRIVE

    def test_cinq_essais_faux_verrouillent_meme_le_bon_code(self, api_client, agents, colis_arrive):
        bon_code = code_envoye()
        for _ in range(5):
            agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code="AAAAAA")

        reponse = agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code=bon_code)

        assert reponse.status_code == 400 and "verrouillé" in str(reponse.data["code"])
        assert Colis.objects.get(pk=colis_arrive["id"]).statut == StatutColis.ARRIVE
        api_client.force_authenticate(user=agents["chef_gare_arrivee"])
        assert api_client.get(f"/api/colis/{colis_arrive['id']}/").data["code_verrouille"] is True

    def test_le_code_est_obligatoire(self, api_client, agents, colis_arrive):
        assert agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer").status_code == 400

    def test_on_ne_retire_qu_un_colis_arrive(self, api_client, agents, colis):
        assert agir(api_client, agents["bagagiste_arrivee"], colis["id"], "retirer", code=code_envoye()).status_code == 400

    def test_on_ne_retire_pas_deux_fois(self, api_client, agents, colis_arrive):
        code = code_envoye()
        agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code=code)

        assert agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code=code).status_code == 400

    def test_renvoyer_le_code_leve_le_verrou_et_invalide_l_ancien(self, api_client, agents, colis_arrive):
        ancien = code_envoye()
        for _ in range(5):
            agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code="AAAAAA")

        reponse = agir(api_client, agents["chef_gare_arrivee"], colis_arrive["id"], "renvoyer-code")

        assert reponse.status_code == 200 and reponse.data["code_verrouille"] is False
        message = next(m for m in messages("+2250700000003") if "nouveau code" in m)
        nouveau = re.search(r"nouveau code de retrait est ([A-Z0-9]{6})", message).group(1)
        assert agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code=ancien).status_code == 400
        assert agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "retirer", code=nouveau).status_code == 200

    def test_seule_la_supervision_renvoie_un_code(self, api_client, agents, colis_arrive):
        assert agir(api_client, agents["bagagiste_arrivee"], colis_arrive["id"], "renvoyer-code").status_code == 403

    def test_le_nouveau_code_ne_va_qu_au_destinataire(self, api_client, agents, colis_arrive):
        agir(api_client, agents["chef_gare_arrivee"], colis_arrive["id"], "renvoyer-code")

        assert not any("nouveau code" in m for m in messages("+2250700000002"))


@pytest.mark.django_db
class TestAnnulation:
    def test_la_supervision_annule_avec_un_motif(self, api_client, agents, colis):
        reponse = agir(api_client, agents["chef_gare"], colis["id"], "annuler", motif="Colis refusé par le transporteur")

        assert reponse.status_code == 200 and reponse.data["statut"] == StatutColis.ANNULE
        assert reponse.data["motif_annulation"] == "Colis refusé par le transporteur"
        assert any("annulé" in m and "frais vous seront rendus" in m for m in messages("+2250700000002"))

    def test_le_bagagiste_n_annule_pas(self, api_client, agents, colis):
        assert agir(api_client, agents["bagagiste"], colis["id"], "annuler", motif="Je change d'avis").status_code == 403

    def test_le_motif_est_obligatoire(self, api_client, agents, colis):
        assert agir(api_client, agents["chef_gare"], colis["id"], "annuler", motif="ok").status_code == 400

    def test_un_colis_arrive_ne_s_annule_plus(self, api_client, agents, monde, colis):
        agir(api_client, agents["bagagiste"], colis["id"], "charger")
        faire_partir_et_arriver(api_client, agents, monde)

        assert agir(api_client, agents["chef_gare"], colis["id"], "annuler", motif="Trop tard pour ça").status_code == 400

    def test_un_colis_annule_ne_se_charge_plus_et_sort_du_plan_de_chargement(self, api_client, agents, monde, colis):
        agir(api_client, agents["chef_gare"], colis["id"], "annuler", motif="Colis refusé par le transporteur")

        assert agir(api_client, agents["bagagiste"], colis["id"], "charger").status_code == 400
        api_client.force_authenticate(user=agents["bagagiste"])
        assert api_client.get(f"/api/departs/{monde['depart'].id}/plan-chargement/").data["ordre_chargement"] == []
