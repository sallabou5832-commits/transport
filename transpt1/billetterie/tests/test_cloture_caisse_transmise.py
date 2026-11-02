"""Clôture de caisse : manuelle, assistée ou automatique selon le niveau du guichetier, transmise au chef de gare
(cahier des charges : « clôture de caisse automatique en fin de service transmise au chef de gare »)."""

import datetime
import io
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from alertes.models import Alerte
from alertes.tests.conftest import alertes_de
from billetterie.models import ClotureCaisse, ModePaiement, Ticket
from configuration.models import ConfigurationAgent, ConfigurationPoste
from core.models import Role
from reseau.models import AffectationGare, Gare


@pytest.fixture
def equipe(user_factory, company_a, gare_depart_a):
    chef = user_factory("chef_gare_caisse", Role.CHEF_GARE, company=company_a)
    gare_depart_a.chef = chef
    gare_depart_a.save()
    guichetier = user_factory("guichetier_caisse", Role.GUICHETIER, company=company_a)
    AffectationGare.objects.create(agent=guichetier, gare=gare_depart_a, company=company_a)
    return {"chef": chef, "guichetier": guichetier}


@pytest.fixture
def ventes(equipe, depart_a, company_a):
    def vendre(prix, mode=ModePaiement.ESPECES, statut="valide"):
        ticket = Ticket.objects.create(
            depart=depart_a, company=company_a, passager_nom="P", passager_telephone="+225", prix=Decimal(prix),
            mode_paiement=mode, vendu_par=equipe["guichetier"],
        )
        if statut != "valide":
            Ticket.objects.filter(pk=ticket.pk).update(statut=statut)
        return ticket

    vendre("5000")
    vendre("7000", ModePaiement.MOBILE_MONEY)
    vendre("3000", statut="annule")


def niveau(company, role, valeur):
    ConfigurationPoste.objects.update_or_create(company=company, role=role, defaults={"niveau_automatisation": valeur})


@pytest.mark.django_db
class TestClotureParLeGuichetier:
    def test_en_mode_assiste_le_guichetier_cloture_d_un_geste_et_le_chef_de_gare_est_prevenu(
        self, api_client, equipe, ventes
    ):
        api_client.force_authenticate(user=equipe["guichetier"])

        reponse = api_client.post("/api/clotures-caisse/", {})

        assert reponse.status_code == 201
        assert Decimal(reponse.data["montant_total"]) == 12000 and reponse.data["nombre_tickets"] == 2
        assert Decimal(reponse.data["especes_montant"]) == 5000 and Decimal(reponse.data["mobile_montant"]) == 7000
        assert reponse.data["annulations_nombre"] == 1 and Decimal(reponse.data["annulations_montant"]) == 3000
        assert reponse.data["automatique"] is False and reponse.data["cloture_par"] == equipe["guichetier"].id
        alerte = alertes_de(api_client, equipe["chef"])[0]
        assert alerte["titre"] == "Caisse clôturée : guichetier_caisse — 12 000 FCFA"
        assert "1 annulation(s)" in alerte["message"] and "Clôture faite par le guichetier" in alerte["message"]

    def test_on_ne_cloture_qu_une_fois_par_jour(self, api_client, equipe, ventes):
        api_client.force_authenticate(user=equipe["guichetier"])
        api_client.post("/api/clotures-caisse/", {})

        reponse = api_client.post("/api/clotures-caisse/", {})

        assert reponse.status_code == 400 and "déjà clôturée" in str(reponse.data)
        assert ClotureCaisse.objects.count() == 1

    def test_les_ventes_apres_la_cloture_ne_changent_pas_la_photo(self, api_client, equipe, ventes, depart_a, company_a):
        api_client.force_authenticate(user=equipe["guichetier"])
        cloture = api_client.post("/api/clotures-caisse/", {}).data
        Ticket.objects.create(
            depart=depart_a, company=company_a, passager_nom="Tard", passager_telephone="+225", prix=Decimal("9000"),
            mode_paiement=ModePaiement.ESPECES, vendu_par=equipe["guichetier"],
        )

        assert Decimal(api_client.get(f"/api/clotures-caisse/{cloture['id']}/").data["montant_total"]) == 12000

    def test_en_mode_manuel_le_guichetier_ne_cloture_pas_lui_meme(self, api_client, equipe, ventes, company_a):
        niveau(company_a, Role.GUICHETIER, "manuel")
        api_client.force_authenticate(user=equipe["guichetier"])

        reponse = api_client.post("/api/clotures-caisse/", {})

        assert reponse.status_code == 403 and "remettez votre caisse à votre chef de gare" in reponse.data["detail"]

    def test_un_agent_plus_a_l_aise_que_son_poste_peut_clôturer(self, api_client, equipe, ventes, company_a):
        niveau(company_a, Role.GUICHETIER, "manuel")
        ConfigurationAgent.objects.create(agent=equipe["guichetier"], company=company_a, niveau_automatisation="assiste")
        api_client.force_authenticate(user=equipe["guichetier"])

        assert api_client.post("/api/clotures-caisse/", {}).status_code == 201

    def test_la_fonction_retiree_bloque_meme_le_mode_assiste(self, api_client, equipe, ventes, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, fonctions_desactivees=["cloture_caisse"])
        api_client.force_authenticate(user=equipe["guichetier"])

        assert api_client.post("/api/clotures-caisse/", {}).status_code == 403

    def test_on_ne_cloture_pas_un_jour_a_venir(self, api_client, equipe, ventes):
        api_client.force_authenticate(user=equipe["guichetier"])
        demain = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()

        assert api_client.post("/api/clotures-caisse/", {"date": demain}).status_code == 400

    def test_une_caisse_sans_vente_se_cloture_a_zero(self, api_client, equipe):
        api_client.force_authenticate(user=equipe["guichetier"])

        reponse = api_client.post("/api/clotures-caisse/", {})

        assert reponse.status_code == 201 and reponse.data["nombre_tickets"] == 0 and Decimal(reponse.data["montant_total"]) == 0


@pytest.mark.django_db
class TestCloturePourUnAutre:
    def test_le_chef_de_gare_cloture_la_caisse_d_un_guichetier_en_mode_manuel(self, api_client, equipe, ventes, company_a):
        niveau(company_a, Role.GUICHETIER, "manuel")
        api_client.force_authenticate(user=equipe["chef"])

        reponse = api_client.post("/api/clotures-caisse/", {"guichetier": equipe["guichetier"].id})

        assert reponse.status_code == 201 and reponse.data["cloture_par"] == equipe["chef"].id
        assert Decimal(reponse.data["montant_total"]) == 12000

    def test_il_faut_designer_un_guichetier_de_sa_compagnie(self, api_client, equipe, company_b, user_factory):
        etranger = user_factory("guichetier_caisse_b", Role.GUICHETIER, company=company_b)
        api_client.force_authenticate(user=equipe["chef"])

        assert api_client.post("/api/clotures-caisse/", {}).status_code == 400
        assert api_client.post("/api/clotures-caisse/", {"guichetier": etranger.id}).status_code == 400
        assert api_client.post("/api/clotures-caisse/", {"guichetier": equipe["chef"].id}).status_code == 400

    def test_le_chef_de_gare_ne_cloture_que_la_caisse_des_guichetiers_de_sa_gare(
        self, api_client, equipe, user_factory, company_a, gare_arrivee_a
    ):
        sans_gare = user_factory("guichetier_cloture_2", Role.GUICHETIER, company=company_a)
        ailleurs = user_factory("guichetier_cloture_3", Role.GUICHETIER, company=company_a)
        AffectationGare.objects.create(agent=ailleurs, gare=gare_arrivee_a, company=company_a)
        api_client.force_authenticate(user=equipe["chef"])

        for guichetier in (ailleurs, sans_gare):
            reponse = api_client.post("/api/clotures-caisse/", {"guichetier": guichetier.id})
            assert reponse.status_code == 403 and "votre gare" in str(reponse.data["detail"])
        assert not ClotureCaisse.objects.exists()
        # Le reste de la supervision clôture celle de tout guichetier de la compagnie.
        api_client.force_authenticate(user=user_factory("dirops_cloture", Role.DIRECTEUR_EXPLOITATION, company=company_a))
        assert api_client.post("/api/clotures-caisse/", {"guichetier": ailleurs.id}).status_code == 201

    @pytest.mark.parametrize("role", ["bagagiste", "chauffeur_principal", "drh", "magasinier"])
    def test_les_postes_hors_billetterie_ne_cloturent_pas(self, api_client, equipe, role, user_factory, company_a):
        api_client.force_authenticate(user=user_factory(f"{role}_caisse", role, company=company_a))

        assert api_client.post("/api/clotures-caisse/", {"guichetier": equipe["guichetier"].id}).status_code == 403


@pytest.mark.django_db
class TestConsultation:
    def test_le_guichetier_ne_voit_que_sa_caisse_le_chef_de_gare_celles_de_sa_gare(
        self, api_client, equipe, ventes, user_factory, company_a, gare_arrivee_a
    ):
        sans_gare = user_factory("guichetier_caisse_2", Role.GUICHETIER, company=company_a)
        gare_arrivee_a.chef = user_factory("chef_gare_caisse_2", Role.CHEF_GARE, company=company_a)
        gare_arrivee_a.save()
        ailleurs = user_factory("guichetier_caisse_3", Role.GUICHETIER, company=company_a)
        AffectationGare.objects.create(agent=ailleurs, gare=gare_arrivee_a, company=company_a)
        for guichetier in (equipe["guichetier"], sans_gare, ailleurs):
            api_client.force_authenticate(user=guichetier)
            api_client.post("/api/clotures-caisse/", {})
        cloture_ailleurs = ClotureCaisse.objects.get(guichetier=ailleurs)

        api_client.force_authenticate(user=equipe["guichetier"])
        assert len(api_client.get("/api/clotures-caisse/").data) == 1
        # Sa gare seulement : ni l'autre gare, ni le guichetier sans gare.
        api_client.force_authenticate(user=equipe["chef"])
        vues = {c["guichetier"] for c in api_client.get("/api/clotures-caisse/").data}
        assert vues == {equipe["guichetier"].id}
        assert api_client.get(f"/api/clotures-caisse/?guichetier={ailleurs.id}").data == []
        assert api_client.get(f"/api/clotures-caisse/{cloture_ailleurs.id}/").status_code == 404
        # Le reste de la supervision voit toutes celles de la compagnie.
        api_client.force_authenticate(user=user_factory("dirops_caisse_liste", Role.DIRECTEUR_EXPLOITATION, company=company_a))
        assert len(api_client.get("/api/clotures-caisse/").data) == 3

    def test_les_clotures_d_une_autre_compagnie_sont_invisibles(self, api_client, equipe, ventes, company_b, user_factory):
        api_client.force_authenticate(user=equipe["guichetier"])
        cloture = api_client.post("/api/clotures-caisse/", {}).data
        chef_b = user_factory("chef_gare_caisse_b", Role.CHEF_GARE, company=company_b)
        api_client.force_authenticate(user=chef_b)

        assert api_client.get("/api/clotures-caisse/").data == []
        assert api_client.get(f"/api/clotures-caisse/{cloture['id']}/").status_code == 404

    @pytest.mark.parametrize(
        "role",
        [Role.DIRECTEUR_EXPLOITATION, Role.CHEF_LIGNE, Role.SECRETAIRE_GENERAL, Role.PDG, Role.QHSE],
    )
    def test_la_supervision_ne_voit_et_ne_cloture_que_sa_propre_compagnie(
        self, api_client, equipe, ventes, company_a, company_b, user_factory, role
    ):
        api_client.force_authenticate(user=equipe["guichetier"])
        cloture = api_client.post("/api/clotures-caisse/", {}).data
        autre = user_factory("guichetier_caisse_4", Role.GUICHETIER, company=company_a)
        aujourd_hui = timezone.localdate().isoformat()
        caisse_en_direct = (
            f"/api/tickets/cloture-caisse/?guichetier={equipe['guichetier'].id}"
            f"&date_debut={aujourd_hui}&date_fin={aujourd_hui}"
        )

        # Le même poste dans la compagnie voisine : rien de la compagnie A, ni en lecture ni en clôture.
        api_client.force_authenticate(user=user_factory(f"{role}_caisse_b", role, company=company_b))
        assert api_client.get("/api/clotures-caisse/").data == []
        assert api_client.get(f"/api/clotures-caisse/{cloture['id']}/").status_code == 404
        assert api_client.get("/api/clotures-caisse/etat/").data == []
        en_direct = api_client.get(caisse_en_direct).data
        assert en_direct["nombre_tickets"] == 0 and en_direct["montant_total"] == 0
        assert en_direct["annulations"]["nombre"] == 0
        assert api_client.post("/api/clotures-caisse/", {"guichetier": autre.id}).status_code == 400
        assert ClotureCaisse.objects.count() == 1
        # Dans sa propre compagnie, il voit et clôture toutes les caisses.
        api_client.force_authenticate(user=user_factory(f"{role}_caisse_a", role, company=company_a))
        assert [c["id"] for c in api_client.get("/api/clotures-caisse/").data] == [cloture["id"]]
        assert api_client.get(caisse_en_direct).data["nombre_tickets"] == 2
        assert api_client.post("/api/clotures-caisse/", {"guichetier": autre.id}).status_code == 201

    def test_une_cloture_ne_se_modifie_ni_ne_se_supprime(self, api_client, equipe, ventes):
        api_client.force_authenticate(user=equipe["guichetier"])
        cloture = api_client.post("/api/clotures-caisse/", {}).data

        assert api_client.patch(f"/api/clotures-caisse/{cloture['id']}/", {"montant_total": "1"}).status_code == 405
        assert api_client.delete(f"/api/clotures-caisse/{cloture['id']}/").status_code == 405

    def test_la_cloture_est_tracee(self, api_client, equipe, ventes):
        from audit.models import JournalAudit

        api_client.force_authenticate(user=equipe["guichetier"])
        api_client.post("/api/clotures-caisse/", {})

        assert JournalAudit.objects.filter(objet_type="billetterie.cloturecaisse", action="creation").exists()


@pytest.mark.django_db
class TestClotureAutomatique:
    def lancer(self, **options):
        sortie = io.StringIO()
        call_command("cloturer_caisses", stdout=sortie, **options)
        return sortie.getvalue()

    def test_seuls_les_guichetiers_en_mode_automatique_avec_des_ventes_sont_clotures(
        self, equipe, ventes, company_a, user_factory
    ):
        niveau(company_a, Role.GUICHETIER, "automatique")
        sans_vente = user_factory("guichetier_sans_vente", Role.GUICHETIER, company=company_a)
        manuel = user_factory("guichetier_manuel", Role.GUICHETIER, company=company_a)
        ConfigurationAgent.objects.create(agent=manuel, company=company_a, niveau_automatisation="manuel")

        sortie = self.lancer()

        assert "1 caisse(s) clôturée(s) automatiquement" in sortie
        cloture = ClotureCaisse.objects.get()
        assert cloture.guichetier == equipe["guichetier"] and cloture.automatique is True and cloture.cloture_par is None
        assert not ClotureCaisse.objects.filter(guichetier__in=[sans_vente, manuel]).exists()

    def test_en_mode_assiste_la_commande_ne_cloture_rien(self, equipe, ventes):
        assert "0 caisse(s)" in self.lancer()
        assert not ClotureCaisse.objects.exists()

    def test_la_commande_est_rejouable_sans_doublon(self, equipe, ventes, company_a):
        niveau(company_a, Role.GUICHETIER, "automatique")
        self.lancer()

        assert "0 caisse(s)" in self.lancer()
        assert ClotureCaisse.objects.count() == 1

    def test_une_caisse_deja_cloturee_a_la_main_n_est_pas_recloturee(self, api_client, equipe, ventes, company_a):
        niveau(company_a, Role.GUICHETIER, "automatique")
        api_client.force_authenticate(user=equipe["guichetier"])
        api_client.post("/api/clotures-caisse/", {})

        assert "0 caisse(s)" in self.lancer()
        assert ClotureCaisse.objects.get().automatique is False

    def test_le_chef_de_gare_est_prevenu_de_la_cloture_automatique(self, api_client, equipe, ventes, company_a):
        niveau(company_a, Role.GUICHETIER, "automatique")

        self.lancer()

        alerte = alertes_de(api_client, equipe["chef"])[0]
        assert "Clôture automatique de fin de service" in alerte["message"]

    def test_l_option_date_clot_un_jour_passe(self, equipe, ventes, company_a):
        niveau(company_a, Role.GUICHETIER, "automatique")
        hier = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()

        assert "0 caisse(s)" in self.lancer(date=hier)  # aucune vente hier

    def test_sans_chef_de_gare_affecte_tous_les_chefs_sont_prevenus(self, api_client, company_a, user_factory, depart_a):
        guichetier = user_factory("guichetier_libre", Role.GUICHETIER, company=company_a)
        chef = user_factory("chef_gare_libre", Role.CHEF_GARE, company=company_a)
        Ticket.objects.create(
            depart=depart_a, company=company_a, passager_nom="P", passager_telephone="+225", prix=Decimal("1000"),
            mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
        )
        api_client.force_authenticate(user=guichetier)

        api_client.post("/api/clotures-caisse/", {})

        assert Alerte.objects.get().roles_destinataires == ["chef_gare"]
        assert len(alertes_de(api_client, chef)) == 1


@pytest.mark.django_db
class TestEtatDesCaisses:
    def test_le_guichetier_voit_sa_caisse_en_direct_puis_sa_cloture(self, api_client, equipe, ventes):
        api_client.force_authenticate(user=equipe["guichetier"])

        avant = api_client.get("/api/clotures-caisse/etat/").data
        assert len(avant) == 1 and avant[0]["cloture"] is None and avant[0]["niveau_automatisation"] == "assiste"
        assert Decimal(avant[0]["caisse"]["montant_total"]) == 12000 and avant[0]["caisse"]["annulations"]["nombre"] == 1

        api_client.post("/api/clotures-caisse/", {})
        apres = api_client.get("/api/clotures-caisse/etat/").data
        assert apres[0]["cloture"]["automatique"] is False and Decimal(apres[0]["cloture"]["montant_total"]) == 12000

    def test_le_chef_de_gare_voit_l_equipe_de_sa_gare_seulement(
        self, api_client, equipe, ventes, user_factory, company_a
    ):
        user_factory("guichetier_autre_gare", Role.GUICHETIER, company=company_a)  # pas affecté à sa gare
        api_client.force_authenticate(user=equipe["chef"])

        etat = api_client.get("/api/clotures-caisse/etat/").data

        assert [e["guichetier"] for e in etat] == [equipe["guichetier"].id]

    def test_la_direction_des_operations_voit_tous_les_guichetiers(self, api_client, equipe, user_factory, company_a):
        user_factory("guichetier_autre_gare", Role.GUICHETIER, company=company_a)
        api_client.force_authenticate(user=user_factory("dirops_caisse", Role.DIRECTEUR_EXPLOITATION, company=company_a))

        assert len(api_client.get("/api/clotures-caisse/etat/").data) == 2

    def test_l_etat_d_un_autre_jour(self, api_client, equipe, ventes):
        hier = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        api_client.force_authenticate(user=equipe["chef"])

        etat = api_client.get(f"/api/clotures-caisse/etat/?date={hier}").data

        assert etat[0]["caisse"]["nombre_tickets"] == 0 and str(etat[0]["date"]) == hier

    def test_l_etat_d_une_autre_compagnie_est_invisible(self, api_client, equipe, ventes, company_b, user_factory):
        api_client.force_authenticate(user=user_factory("chef_gare_etat_b", Role.CHEF_GARE, company=company_b))

        assert api_client.get("/api/clotures-caisse/etat/").data == []
