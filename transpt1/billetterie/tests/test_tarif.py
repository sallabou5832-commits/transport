"""Le prix d'un billet est le tarif de sa ligne (faille S4 de l'analyse : le guichetier saisissait librement le prix,
et une sous-facturation était indétectable)."""

from decimal import Decimal

import pytest

from audit.models import JournalAudit
from billetterie.models import Ticket


@pytest.fixture
def ligne_a_tarif(ligne_a):
    ligne_a.tarif = Decimal("5000")
    ligne_a.save()
    return ligne_a


def vendre(api_client, utilisateur, depart, **champs):
    api_client.force_authenticate(user=utilisateur)
    corps = {
        "depart": depart.id, "passager_nom": "Awa", "passager_telephone": "+2250700000001",
        "mode_paiement": "especes", **champs,
    }
    return api_client.post("/api/tickets/", corps)


@pytest.mark.django_db
class TestPrixImpose:
    def test_sans_prix_dans_la_requete_c_est_le_tarif(self, api_client, guichetier_a, depart_a, ligne_a_tarif):
        reponse = vendre(api_client, guichetier_a, depart_a)

        assert reponse.status_code == 201
        assert Decimal(reponse.data["prix"]) == 5000 and Decimal(reponse.data["prix_tarif"]) == 5000
        assert reponse.data["motif_derogation"] == ""

    def test_le_prix_egal_au_tarif_est_accepte(self, api_client, guichetier_a, depart_a, ligne_a_tarif):
        assert vendre(api_client, guichetier_a, depart_a, prix="5000").status_code == 201

    def test_un_guichetier_ne_peut_pas_vendre_a_un_autre_prix(self, api_client, guichetier_a, depart_a, ligne_a_tarif):
        reponse = vendre(api_client, guichetier_a, depart_a, prix="1", motif_derogation="Je fais un geste")

        assert reponse.status_code == 400
        assert "5000 FCFA" in str(reponse.data["prix"])
        assert not Ticket.objects.exists()
        depart_a.refresh_from_db()
        assert depart_a.places_vendues == 0

    def test_le_chef_de_gare_peut_deroger_avec_un_motif(self, api_client, chef_gare_billetterie_a, depart_a, ligne_a_tarif):
        reponse = vendre(
            api_client, chef_gare_billetterie_a, depart_a, prix="2500", motif_derogation="Enfant de moins de 5 ans"
        )

        assert reponse.status_code == 201
        assert Decimal(reponse.data["prix"]) == 2500 and Decimal(reponse.data["prix_tarif"]) == 5000
        assert reponse.data["motif_derogation"] == "Enfant de moins de 5 ans"

    def test_la_derogation_sans_motif_est_refusee(self, api_client, chef_gare_billetterie_a, depart_a, ligne_a_tarif):
        reponse = vendre(api_client, chef_gare_billetterie_a, depart_a, prix="2500")

        assert reponse.status_code == 400
        assert "motif" in str(reponse.data["motif_derogation"])

    def test_la_derogation_est_tracee_dans_le_journal_d_audit(self, api_client, chef_gare_billetterie_a, depart_a, ligne_a_tarif):
        vendre(api_client, chef_gare_billetterie_a, depart_a, prix="2500", motif_derogation="Enfant de moins de 5 ans")

        entree = JournalAudit.objects.get(objet_type="billetterie.ticket", action="creation")
        assert entree.changements["prix"] == "2500.00" and entree.changements["prix_tarif"] == "5000.00"
        assert entree.changements["motif_derogation"] == "Enfant de moins de 5 ans"

    def test_un_motif_sans_derogation_n_est_pas_conserve(self, api_client, guichetier_a, depart_a, ligne_a_tarif):
        reponse = vendre(api_client, guichetier_a, depart_a, motif_derogation="inutile")

        assert reponse.data["motif_derogation"] == ""

    def test_le_tarif_d_un_ticket_deja_vendu_ne_change_pas_si_la_ligne_change(
        self, api_client, guichetier_a, depart_a, ligne_a_tarif
    ):
        ticket = vendre(api_client, guichetier_a, depart_a).data
        ligne_a_tarif.tarif = Decimal("9000")
        ligne_a_tarif.save()

        assert Decimal(api_client.get(f"/api/tickets/{ticket['id']}/").data["prix"]) == 5000

    def test_le_prix_tarif_ne_se_fixe_pas_a_la_vente(self, api_client, guichetier_a, depart_a, ligne_a_tarif):
        reponse = vendre(api_client, guichetier_a, depart_a, prix_tarif="1")

        assert Decimal(reponse.data["prix_tarif"]) == 5000


@pytest.mark.django_db
class TestLigneSansTarif:
    def test_le_prix_reste_obligatoire(self, api_client, guichetier_a, depart_a):
        reponse = vendre(api_client, guichetier_a, depart_a)

        assert reponse.status_code == 400
        assert "pas de tarif" in str(reponse.data["prix"])

    def test_le_prix_saisi_est_accepte_comme_avant(self, api_client, guichetier_a, depart_a):
        reponse = vendre(api_client, guichetier_a, depart_a, prix="3000")

        assert reponse.status_code == 201
        assert reponse.data["prix_tarif"] is None


@pytest.mark.django_db
class TestRejeuIdempotent:
    def test_rejouer_une_vente_sans_prix_renvoie_le_meme_ticket(self, api_client, guichetier_a, depart_a, ligne_a_tarif):
        api_client.force_authenticate(user=guichetier_a)
        corps = {
            "depart": depart_a.id, "passager_nom": "Awa", "passager_telephone": "+2250700000001",
            "mode_paiement": "especes",
        }

        premiere = api_client.post("/api/tickets/", corps, HTTP_IDEMPOTENCY_KEY="cle-1")
        seconde = api_client.post("/api/tickets/", corps, HTTP_IDEMPOTENCY_KEY="cle-1")

        assert premiere.status_code == 201 and seconde.status_code == 200
        assert seconde.data["id"] == premiere.data["id"]
        assert Ticket.objects.count() == 1


@pytest.mark.django_db
class TestExpositionDuTarif:
    def test_le_depart_expose_le_tarif_de_sa_ligne(self, api_client, guichetier_a, depart_a, ligne_a_tarif):
        api_client.force_authenticate(user=guichetier_a)

        assert Decimal(api_client.get(f"/api/departs/{depart_a.id}/").data["tarif"]) == 5000

    def test_sans_tarif_le_champ_est_vide(self, api_client, guichetier_a, depart_a):
        api_client.force_authenticate(user=guichetier_a)

        assert api_client.get(f"/api/departs/{depart_a.id}/").data["tarif"] is None

    def test_seuls_les_roles_de_ligne_fixent_le_tarif(self, api_client, user_factory, company_a, ligne_a):
        chef_ligne = user_factory("chef_ligne_tarif", "chef_ligne", company=company_a)

        api_client.force_authenticate(user=chef_ligne)
        assert api_client.patch(f"/api/lignes/{ligne_a.id}/", {"tarif": "6500"}).status_code == 200
        api_client.force_authenticate(user=user_factory("guichetier_tarif", "guichetier", company=company_a))
        assert api_client.patch(f"/api/lignes/{ligne_a.id}/", {"tarif": "1"}).status_code == 403
        ligne_a.refresh_from_db()
        assert ligne_a.tarif == Decimal("6500")

    def test_un_tarif_nul_ou_negatif_est_refuse(self, api_client, user_factory, company_a, ligne_a):
        api_client.force_authenticate(user=user_factory("chef_ligne_tarif", "chef_ligne", company=company_a))

        assert api_client.patch(f"/api/lignes/{ligne_a.id}/", {"tarif": "0"}).status_code == 400
        assert api_client.patch(f"/api/lignes/{ligne_a.id}/", {"tarif": "-100"}).status_code == 400
