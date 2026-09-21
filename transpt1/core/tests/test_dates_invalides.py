import pytest

from core.dates import lire_date
from core.models import Role

# Bien formées mais impossibles : `parse_date` lève ValueError au lieu de renvoyer None.
DATES_IMPOSSIBLES = ["2030-13-45", "2030-02-31", "2030-00-10"]


class TestLireDate:
    def test_une_date_valide(self):
        assert str(lire_date("2030-05-17")) == "2030-05-17"

    @pytest.mark.parametrize("valeur", [None, "", "hier", "17/05/2030", *DATES_IMPOSSIBLES])
    def test_tout_le_reste_donne_none_sans_exception(self, valeur):
        assert lire_date(valeur) is None


@pytest.mark.django_db
class TestEndpointsAvecDates:
    """Un paramètre fantaisiste est une erreur 400 claire, jamais une erreur serveur."""

    @pytest.mark.parametrize("impossible", DATES_IMPOSSIBLES)
    def test_synthese_financiere(self, api_client, user_factory, company_a, impossible):
        api_client.force_authenticate(user=user_factory("daf_dates", Role.DIRECTEUR_FINANCIER, company=company_a))

        reponse = api_client.get(f"/api/synthese-financiere/?date_debut={impossible}&date_fin=2030-01-01")

        assert reponse.status_code == 400

    @pytest.mark.parametrize("impossible", DATES_IMPOSSIBLES)
    def test_cloture_de_caisse(self, api_client, user_factory, company_a, impossible):
        api_client.force_authenticate(user=user_factory("guichetier_dates", Role.GUICHETIER, company=company_a))

        reponse = api_client.get(f"/api/tickets/cloture-caisse/?date_debut=2030-01-01&date_fin={impossible}")

        assert reponse.status_code == 400

    @pytest.mark.parametrize("impossible", DATES_IMPOSSIBLES)
    def test_journal_d_audit(self, api_client, user_factory, company_a, impossible):
        api_client.force_authenticate(user=user_factory("pdg_dates", Role.PDG, company=company_a))

        assert api_client.get(f"/api/audit/?date_debut={impossible}").status_code == 400
