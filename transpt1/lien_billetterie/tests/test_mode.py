"""Le mode de billetterie d'une compagnie : intégrée (défaut, rien ne change), externe (la vente au guichet est fermée) ou mixte
(les deux). Le PDG et le directeur des opérations le règlent ; tous le lisent."""

import pytest

from billetterie.models import ReservationHorsLigne
from core.models import Role
from lien_billetterie.models import ModeBilletterie, ReglageBilletterie
from lien_billetterie.tests.conftest import passer_en

URL = "/api/lien-billetterie/reglage/"


def vendre_au_guichet(api_client, guichetier, depart):
    api_client.force_authenticate(user=guichetier)
    return api_client.post(
        "/api/tickets/",
        {"depart": depart.id, "passager_nom": "Yao", "passager_telephone": "+2250700000002", "mode_paiement": "especes"},
        format="json",
    )


@pytest.mark.django_db
class TestReglage:
    def test_sans_reglage_la_billetterie_est_integree(self, api_client, agents):
        api_client.force_authenticate(user=agents["guichetier"])

        reponse = api_client.get(URL)

        assert reponse.status_code == 200
        assert reponse.data["mode"] == "integre"
        assert reponse.data["vente_au_guichet"] is True and reponse.data["ventes_externes"] is False
        assert reponse.data["modifiable"] is False

    @pytest.mark.parametrize("role", ["pdg", "directeur_exploitation"])
    def test_le_pdg_et_le_directeur_des_operations_reglent_le_mode(self, api_client, agents, company_a, role):
        api_client.force_authenticate(user=agents[role])

        reponse = api_client.patch(URL, {"mode": "mixte"}, format="json")

        assert reponse.status_code == 200 and reponse.data["mode"] == "mixte"
        reglage = ReglageBilletterie.objects.get(company=company_a)
        assert reglage.mode == ModeBilletterie.MIXTE and reglage.modifie_par == agents[role]

    @pytest.mark.parametrize("role", ["chef_gare", "guichetier", "chef_ligne", "directeur_financier", "qhse"])
    def test_les_autres_postes_ne_reglent_pas_le_mode(self, api_client, agents, role):
        api_client.force_authenticate(user=agents[role])

        assert api_client.patch(URL, {"mode": "externe"}, format="json").status_code == 403
        assert not ReglageBilletterie.objects.exists()

    def test_un_mode_inconnu_est_refuse(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.patch(URL, {"mode": "les_deux"}, format="json").status_code == 400

    def test_le_superadmin_sans_compagnie_n_a_pas_de_billetterie(self, api_client, superadmin_user):
        api_client.force_authenticate(user=superadmin_user)

        assert api_client.get(URL).status_code == 403

    def test_le_mode_d_une_compagnie_ne_touche_pas_une_autre(self, api_client, agents, company_b, user_factory):
        passer_en(agents["pdg"].company, ModeBilletterie.EXTERNE)
        api_client.force_authenticate(user=user_factory("guichetier_b_lien", Role.GUICHETIER, company=company_b))

        assert api_client.get(URL).data["mode"] == "integre"


@pytest.mark.django_db
class TestVenteAuGuichet:
    def test_les_ecrans_du_guichet_savent_si_la_vente_est_ouverte(self, api_client, agents, company_a, company_b, user_factory):
        def ouverte(user):
            api_client.force_authenticate(user=user)
            return api_client.get("/api/configuration/moi/").data["vente_au_guichet"]

        assert ouverte(agents["guichetier"]) is True
        passer_en(company_a, ModeBilletterie.MIXTE)
        assert ouverte(agents["guichetier"]) is True
        passer_en(company_a, ModeBilletterie.EXTERNE)
        assert ouverte(agents["guichetier"]) is False
        # La compagnie d'à côté n'en est pas touchée.
        assert ouverte(user_factory("guichetier_b_vente", Role.GUICHETIER, company=company_b)) is True

    def test_en_billetterie_integree_le_guichet_vend(self, api_client, agents, reseau):
        assert vendre_au_guichet(api_client, agents["guichetier"], reseau["depart"]).status_code == 201

    def test_en_billetterie_mixte_le_guichet_vend_toujours(self, api_client, agents, reseau, company_a):
        passer_en(company_a, ModeBilletterie.MIXTE)

        assert vendre_au_guichet(api_client, agents["guichetier"], reseau["depart"]).status_code == 201

    def test_en_billetterie_externe_le_guichet_ne_vend_plus(self, api_client, agents, reseau, company_a):
        passer_en(company_a, ModeBilletterie.EXTERNE)

        reponse = vendre_au_guichet(api_client, agents["guichetier"], reseau["depart"])

        assert reponse.status_code == 403
        assert "propre logiciel" in str(reponse.data["detail"])
        reseau["depart"].refresh_from_db()
        assert reseau["depart"].places_vendues == 0

    def test_en_billetterie_externe_plus_de_places_mises_de_cote_pour_le_hors_ligne(
        self, api_client, agents, reseau, company_a, settings
    ):
        settings.BILLETTERIE_HORIZON_HORS_LIGNE_HEURES = 72  # le départ de demain 8 h, quelle que soit l'heure du test
        api_client.force_authenticate(user=agents["guichetier"])
        assert api_client.post("/api/tickets/reserver-hors-ligne/").data != []
        passer_en(company_a, ModeBilletterie.EXTERNE)

        assert api_client.post("/api/tickets/reserver-hors-ligne/").data == []
        assert not ReservationHorsLigne.objects.exists()
