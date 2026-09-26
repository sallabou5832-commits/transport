import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from billetterie.models import Depart
from core.models import Company, Role
from finance.analyses import rentabilite, suivi_budget_carburant, tresorerie
from finance.models import Facture, StatutFacture

COMMANDES = ["seed_demo_users", "seed_demo_reseau", "seed_demo_operations", "seed_demo_tableaux"]


def _lancer_toutes():
    for commande in COMMANDES:
        call_command(commande, stdout=io.StringIO())


@pytest.mark.django_db
class TestGardeProduction:
    """Ces commandes créent des comptes au mot de passe public, dont un superadmin."""

    @pytest.mark.parametrize("commande", COMMANDES)
    def test_refusee_hors_developpement_sans_rien_creer(self, settings, commande):
        settings.DEBUG = False

        with pytest.raises(CommandError, match="réservée au développement"):
            call_command(commande, stdout=io.StringIO())

        assert not get_user_model().objects.exists()

    def test_le_message_indique_comment_creer_les_vrais_comptes(self, settings):
        settings.DEBUG = False

        with pytest.raises(CommandError, match="administration Django"):
            call_command("seed_demo_users", stdout=io.StringIO())


@pytest.mark.django_db
class TestChaineDeDonneesDeDemo:
    def test_un_compte_par_role_du_cahier_des_charges(self, settings):
        settings.DEBUG = True

        _lancer_toutes()

        roles = set(get_user_model().objects.values_list("role", flat=True))
        assert roles == {role.value for role in Role}

    def test_rejouer_les_commandes_ne_duplique_rien(self, settings):
        settings.DEBUG = True
        _lancer_toutes()
        utilisateurs, departs = get_user_model().objects.count(), Depart.objects.count()

        _lancer_toutes()

        assert get_user_model().objects.count() == utilisateurs
        assert Depart.objects.count() == departs

    def test_la_comptabilite_de_demonstration_montre_un_budget_a_risque_et_des_factures_a_echeances_variees(self, settings):
        settings.DEBUG = True
        _lancer_toutes()
        stc = Company.objects.get(name="STC Voyages")

        etats = {ligne["nom"]: ligne["etat"] for ligne in suivi_budget_carburant(stc, timezone.localdate())["lignes"]}
        cash = tresorerie(stc)

        assert etats == {"Abidjan-Bouaké": "ok", "Yopougon-Yamoussoukro": "alerte", "Abidjan-Yamoussoukro": "depasse"}
        assert cash["a_payer"]["factures_en_retard"] == 1 and cash["a_payer"]["sous_7_jours"] == 480000
        payee = Facture.objects.get(company=stc, statut=StatutFacture.PAYEE)
        assert payee.depense.montant == payee.montant and payee.payee_le == payee.depense.date
        # Salaires, pneus payés au garage et vidange d'un véhicule (qui sert plusieurs lignes) : aucune n'est rattachée à une ligne ni à une gare.
        assert rentabilite(stc, timezone.localdate().replace(day=1), timezone.localdate())["charges_communes"] == 600000 + 210000 + 180000

    def test_le_depart_de_demonstration_tombe_toujours_aujourd_hui(self, settings, monkeypatch):
        settings.DEBUG = True
        tard_le_soir = timezone.localtime().replace(hour=22, minute=30, second=0, microsecond=0)
        monkeypatch.setattr(timezone, "now", lambda: tard_le_soir)  # +3 h franchirait minuit

        for commande in COMMANDES[:3]:
            call_command(commande, stdout=io.StringIO())

        depart = Depart.objects.get(company__name="STC Voyages")
        assert timezone.localtime(depart.date_heure).date() == tard_le_soir.date()
