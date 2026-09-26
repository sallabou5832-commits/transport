"""Le fret (frais des colis et bagages) est une recette de la compagnie : la synthèse financière le présente à part,
sans fausser le total des billets, et le compte dans le total général."""

from decimal import Decimal

import pytest
from django.utils import timezone

from colis.models import Colis, StatutColis
from colis.tests.conftest import agents, monde  # noqa: F401 — fixtures du module colis


def periode():
    aujourdhui = timezone.localdate().isoformat()
    return f"date_debut={aujourdhui}&date_fin={aujourdhui}"


def creer_colis(monde, agents, frais, mode="especes", statut=StatutColis.ENREGISTRE):  # noqa: F811
    colis = Colis(
        company=monde["depart"].company, depart=monde["depart"], description="Carton", poids_kg=5, frais=frais,
        mode_paiement=mode if frais else "", expediteur_nom="A", destinataire_nom="B", destinataire_telephone="0700000003",
        enregistre_par=agents["bagagiste"], statut=statut,
    )
    colis.definir_code("ABC234")
    colis.save()
    return colis


@pytest.mark.django_db
class TestFretDansLaSynthese:
    def synthese(self, api_client, agents):  # noqa: F811
        api_client.force_authenticate(user=agents["pdg"])
        return api_client.get(f"/api/synthese-financiere/?{periode()}").data

    def test_le_fret_apparait_a_part_et_dans_le_total_general(self, api_client, agents, monde):  # noqa: F811
        creer_colis(monde, agents, "2000", "especes")
        creer_colis(monde, agents, "3000", "mobile_money")

        donnees = self.synthese(api_client, agents)

        assert donnees["fret"]["nombre_colis"] == 2 and Decimal(donnees["fret"]["montant_total"]) == 5000
        par_mode = {m["mode"]: Decimal(m["montant_total"]) for m in donnees["fret"]["par_mode_paiement"]}
        assert par_mode == {"especes": 2000, "mobile_money": 3000}
        # Le total des billets ne change pas ; le total général ajoute le fret (le billet de la fixture vaut 5 000).
        assert Decimal(donnees["total"]["montant_total"]) == 5000
        assert Decimal(donnees["total_general"]["montant_total"]) == 10000

    def test_un_colis_annule_n_est_pas_une_recette(self, api_client, agents, monde):  # noqa: F811
        creer_colis(monde, agents, "2000")
        creer_colis(monde, agents, "9000", statut=StatutColis.ANNULE)

        assert Decimal(self.synthese(api_client, agents)["fret"]["montant_total"]) == 2000

    def test_un_colis_sans_frais_ne_compte_pas(self, api_client, agents, monde):  # noqa: F811
        creer_colis(monde, agents, "0")

        assert self.synthese(api_client, agents)["fret"]["nombre_colis"] == 0

    def test_sans_fret_les_totaux_sont_a_zero(self, api_client, agents, monde):  # noqa: F811
        donnees = self.synthese(api_client, agents)

        assert donnees["fret"]["nombre_colis"] == 0 and Decimal(donnees["fret"]["montant_total"]) == 0
        assert [m["mode"] for m in donnees["fret"]["par_mode_paiement"]] == ["especes", "mobile_money"]

    def test_le_fret_d_une_autre_compagnie_n_est_pas_compte(
        self, api_client, agents, monde, company_b, user_factory  # noqa: F811
    ):
        creer_colis(monde, agents, "2000")
        pdg_b = user_factory("pdg_fret_b", "pdg", company=company_b)
        api_client.force_authenticate(user=pdg_b)

        donnees = api_client.get(f"/api/synthese-financiere/?{periode()}").data

        assert donnees["fret"]["nombre_colis"] == 0

    def test_le_directeur_financier_le_voit_aussi(self, api_client, agents, monde, user_factory, company_a):  # noqa: F811
        creer_colis(monde, agents, "2000")
        api_client.force_authenticate(user=user_factory("dirfin_fret", "directeur_financier", company=company_a))

        assert api_client.get(f"/api/synthese-financiere/?{periode()}").data["fret"]["nombre_colis"] == 1
