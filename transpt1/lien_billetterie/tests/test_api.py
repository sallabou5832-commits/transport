"""Le lien avec le logiciel de billetterie de la compagnie, par son API : clés, planning, ventes, annulations."""

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from billetterie.caisse import calculer_caisse
from billetterie.models import ReservationHorsLigne, SourceTicket, StatutTicket, Ticket
from core.models import Role
from lien_billetterie.models import CleLienBilletterie, ModeBilletterie
from lien_billetterie.tests.conftest import avec_cle, passer_en, vente
from notifications.models import NotificationLog


def envoyer(api_client, cle, *ventes):
    return avec_cle(api_client, cle).post("/api/lien-billetterie/ventes/", {"ventes": list(ventes)}, format="json")


def annuler(api_client, cle, *annulations):
    return avec_cle(api_client, cle).post("/api/lien-billetterie/annulations/", {"annulations": list(annulations)}, format="json")


@pytest.mark.django_db
class TestCles:
    URL = "/api/lien-billetterie/cles/"

    @pytest.mark.parametrize("role", ["pdg", "directeur_exploitation"])
    def test_la_cle_n_est_montree_qu_une_fois(self, api_client, agents, company_a, role):
        api_client.force_authenticate(user=agents[role])

        creee = api_client.post(self.URL, {"logiciel": "BilletPro"}, format="json")

        assert creee.status_code == 201
        assert creee.data["cle"].startswith("lb_") and creee.data["debut_cle"] == creee.data["cle"][:10]
        stockee = CleLienBilletterie.objects.get(company=company_a)
        assert stockee.cle_hachee == CleLienBilletterie.hacher(creee.data["cle"]) and creee.data["cle"] not in str(stockee.__dict__)
        assert all("cle" not in cle for cle in api_client.get(self.URL).data)

    @pytest.mark.parametrize("role", ["chef_gare", "guichetier", "directeur_financier"])
    def test_les_autres_postes_ne_gerent_pas_les_cles(self, api_client, agents, role):
        api_client.force_authenticate(user=agents[role])

        assert api_client.post(self.URL, {"logiciel": "BilletPro"}, format="json").status_code == 403
        assert api_client.get(self.URL).status_code == 403

    def test_le_nom_du_logiciel_est_obligatoire(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.post(self.URL, {"logiciel": " "}, format="json").status_code == 400

    def test_une_cle_revoquee_n_ouvre_plus_rien(self, api_client, agents, cle, reseau):
        stockee = CleLienBilletterie.objects.get()
        api_client.force_authenticate(user=agents["directeur_exploitation"])
        assert api_client.post(f"{self.URL}{stockee.id}/revoquer/").status_code == 200
        assert api_client.post(f"{self.URL}{stockee.id}/revoquer/").status_code == 400

        assert envoyer(api_client, cle, vente(reseau["depart"])).status_code == 401
        stockee.refresh_from_db()
        assert stockee.revoquee_par == agents["directeur_exploitation"]

    def test_les_cles_d_une_autre_compagnie_sont_invisibles(self, api_client, agents, cle, company_b, user_factory):
        api_client.force_authenticate(user=user_factory("pdg_b_lien", Role.PDG, company=company_b))

        assert api_client.get(self.URL).data == []
        assert api_client.post(f"{self.URL}{CleLienBilletterie.objects.get().id}/revoquer/").status_code == 404


@pytest.mark.django_db
class TestAuthentification:
    def test_sans_cle_ou_avec_une_fausse_cle(self, api_client, reseau):
        assert api_client.get("/api/lien-billetterie/departs/").status_code == 401
        assert avec_cle(api_client, "lb_inventee").get("/api/lien-billetterie/departs/").status_code == 401

    def test_le_jeton_d_un_agent_n_ouvre_pas_le_lien(self, api_client, agents, cle):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.get("/api/lien-billetterie/departs/").status_code == 403

    def test_la_cle_n_ouvre_aucune_autre_route(self, api_client, cle):
        assert avec_cle(api_client, cle).get("/api/tickets/").status_code == 401
        assert avec_cle(api_client, cle).get("/api/lien-billetterie/reglage/").status_code == 401

    def test_en_billetterie_integree_le_lien_est_ferme(self, api_client, company_a, cle, reseau):
        passer_en(company_a, ModeBilletterie.INTEGRE)

        reponse = envoyer(api_client, cle, vente(reseau["depart"]))

        assert reponse.status_code == 403 and "intégrée" in str(reponse.data["detail"])
        assert not Ticket.objects.exists()

    def test_la_derniere_utilisation_est_notee(self, api_client, cle, reseau):
        avec_cle(api_client, cle).get("/api/lien-billetterie/departs/")

        assert CleLienBilletterie.objects.get().derniere_utilisation is not None


@pytest.mark.django_db
class TestPlanning:
    def test_le_logiciel_lit_les_departs_et_les_places_qu_il_peut_vendre(self, api_client, agents, cle, reseau):
        ReservationHorsLigne.objects.create(
            depart=reseau["depart"], guichetier=agents["guichetier"], company=reseau["depart"].company, places=1,
            expire_le=timezone.now() + datetime.timedelta(hours=2),
        )

        departs = {d["id"]: d for d in avec_cle(api_client, cle).get("/api/lien-billetterie/departs/").data}

        depart = departs[reseau["depart"].id]
        assert depart["ligne_nom"] == "Adjamé-Bouaké" and depart["gare_depart"] == "Adjamé"
        assert depart["capacite"] == 3 and depart["places_vendues"] == 0
        assert depart["places_disponibles"] == 2  # une place est gardée pour la vente hors ligne d'un guichet
        assert Decimal(depart["tarif"]) == 5000

    def test_la_periode_se_choisit(self, api_client, cle, reseau):
        hier = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        aujourd_hui = timezone.localdate().isoformat()
        lien = avec_cle(api_client, cle)

        assert lien.get(f"/api/lien-billetterie/departs/?du={hier}&au={aujourd_hui}").data == []
        assert lien.get("/api/lien-billetterie/departs/?du=demain").status_code == 400
        assert lien.get(f"/api/lien-billetterie/departs/?du={aujourd_hui}&au={hier}").status_code == 400
        loin = (timezone.localdate() + datetime.timedelta(days=40)).isoformat()
        assert lien.get(f"/api/lien-billetterie/departs/?au={loin}").status_code == 400

    def test_les_departs_d_une_autre_compagnie_ne_sortent_pas(self, api_client, company_b, user_factory, reseau):
        passer_en(company_b, ModeBilletterie.MIXTE)
        _, cle_b = CleLienBilletterie.creer(company=company_b, logiciel="Autre", par=None)

        assert avec_cle(api_client, cle_b).get("/api/lien-billetterie/departs/").data == []


@pytest.mark.django_db
class TestVentes:
    def test_une_vente_recue_devient_un_vrai_billet(self, api_client, agents, cle, reseau):
        reponse = envoyer(api_client, cle, vente(reseau["depart"], reference="bp-0001"))

        assert reponse.status_code == 200 and reponse.data["creee"] == 1
        ticket = Ticket.objects.get()
        assert reponse.data["resultats"][0] == {"reference": "bp-0001", "statut": "creee", "ticket": ticket.id, "code": ticket.code}
        assert ticket.source == SourceTicket.LIEN and ticket.logiciel == "BilletPro" and ticket.vendu_par is None
        assert ticket.prix == Decimal("5000") and ticket.prix_tarif == Decimal("5000") and ticket.motif_derogation == ""
        assert ticket.reference_externe == "bp-0001" and ticket.code_externe == "BP0001"
        reseau["depart"].refresh_from_db()
        assert reseau["depart"].places_vendues == 1

    def test_recevoir_deux_fois_la_meme_vente_ne_cree_rien_de_plus(self, api_client, cle, reseau):
        envoyer(api_client, cle, vente(reseau["depart"]))

        reponse = envoyer(api_client, cle, vente(reseau["depart"]), vente(reseau["depart"]))

        assert reponse.data["deja_recue"] == 2 and reponse.data["creee"] == 0
        assert Ticket.objects.count() == 1
        reseau["depart"].refresh_from_db()
        assert reseau["depart"].places_vendues == 1

    def test_le_depart_se_designe_aussi_par_sa_ligne_et_son_heure(self, api_client, cle, reseau):
        heure = timezone.localtime(reseau["demain_8h"])
        par_nom = vente(reseau["depart"], reference="A1", depart=None, ligne="adjamé-bouaké", date_heure=f"{heure:%d/%m/%Y %H:%M}")
        par_id = vente(reseau["depart"], reference="A2", depart=None, ligne=str(reseau["ligne"].id), date_heure=heure.isoformat())

        reponse = envoyer(api_client, cle, par_nom, par_id)

        assert reponse.data["creee"] == 2
        assert set(Ticket.objects.values_list("depart_id", flat=True)) == {reseau["depart"].id}

    def test_le_prix_du_logiciel_est_garde_et_l_ecart_au_tarif_se_voit(self, api_client, cle, reseau):
        envoyer(api_client, cle, vente(reseau["depart"], prix="4500"))

        ticket = Ticket.objects.get()
        assert ticket.prix == Decimal("4500") and ticket.motif_derogation == "Prix fixé par BilletPro"

    def test_la_date_de_la_vente_est_celle_du_logiciel(self, api_client, cle, reseau):
        hier = timezone.now() - datetime.timedelta(days=1)

        envoyer(api_client, cle, vente(reseau["depart"], vendu_le=hier.isoformat()))

        assert abs(Ticket.objects.get().date_vente - hier) < datetime.timedelta(seconds=1)

    @pytest.mark.parametrize(
        "champs,champ_en_erreur",
        [
            ({"depart": 999999}, "depart"),
            ({"depart": None}, "depart"),
            ({"mode_paiement": "cheque"}, "mode_paiement"),
            ({"prix": "-5"}, "prix"),
            ({"passager_nom": ""}, "passager_nom"),
            ({"reference": ""}, "reference"),
            ({"vendu_le": "2999-01-01T10:00:00Z"}, "vendu_le"),
        ],
    )
    def test_une_vente_invalide_est_refusee_avec_sa_raison(self, api_client, cle, reseau, champs, champ_en_erreur):
        reponse = envoyer(api_client, cle, vente(reseau["depart"], **champs))

        assert reponse.status_code == 200 and reponse.data["refusee"] == 1
        assert champ_en_erreur in reponse.data["resultats"][0]["erreurs"]
        assert not Ticket.objects.exists()

    def test_un_lot_traite_chaque_vente_a_part(self, api_client, cle, reseau):
        reponse = envoyer(api_client, cle, vente(reseau["depart"], reference="OK-1"), vente(reseau["depart"], reference="KO", depart=1_000_000), "pas un objet")

        assert [r["statut"] for r in reponse.data["resultats"]] == ["creee", "refusee", "refusee"]

    def test_un_depart_complet_refuse_la_vente(self, api_client, cle, reseau):
        reponse = envoyer(api_client, cle, *[vente(reseau["depart"], reference=f"P{n}") for n in range(4)])

        assert [r["statut"] for r in reponse.data["resultats"]] == ["creee", "creee", "creee", "refusee"]
        assert "place" in str(reponse.data["resultats"][3]["erreurs"]["depart"])

    def test_les_places_gardees_pour_les_guichets_ne_sont_pas_vendues_par_le_logiciel(self, api_client, agents, cle, reseau):
        ReservationHorsLigne.objects.create(
            depart=reseau["depart"], guichetier=agents["guichetier"], company=reseau["depart"].company, places=2,
            expire_le=timezone.now() + datetime.timedelta(hours=2),
        )

        reponse = envoyer(api_client, cle, vente(reseau["depart"], reference="P1"), vente(reseau["depart"], reference="P2"))

        assert [r["statut"] for r in reponse.data["resultats"]] == ["creee", "refusee"]

    def test_un_depart_d_une_autre_compagnie_est_introuvable(self, api_client, company_b, reseau):
        passer_en(company_b, ModeBilletterie.MIXTE)
        _, cle_b = CleLienBilletterie.creer(company=company_b, logiciel="Autre", par=None)

        reponse = envoyer(api_client, cle_b, vente(reseau["depart"]))

        assert reponse.data["refusee"] == 1 and not Ticket.objects.exists()

    def test_une_reference_deja_prise_dans_une_autre_compagnie_ne_compte_pas(self, api_client, company_b, user_factory, cle, reseau):
        # Le même numéro de billet chez une autre compagnie (son logiciel numérote à sa façon) n'est pas « déjà reçu ». Le
        # billet de B est posé directement : seule compte ici sa compagnie.
        Ticket.objects.create(
            depart=reseau["depart"], company=company_b, passager_nom="B", passager_telephone="+225", prix=1000,
            mode_paiement="especes", reference_externe="R-1",
        )

        assert envoyer(api_client, cle, vente(reseau["depart"], reference="R-1")).data["resultats"][0]["statut"] == "creee"
        assert Ticket.objects.filter(reference_externe="R-1").count() == 2

    def test_aucun_sms_n_est_envoye_et_la_caisse_du_guichetier_n_est_pas_touchee(self, api_client, agents, cle, reseau):
        envoyer(api_client, cle, vente(reseau["depart"]))

        assert not NotificationLog.objects.exists()
        jour = timezone.localdate()
        assert calculer_caisse(reseau["depart"].company_id, agents["guichetier"].id, jour, jour)["nombre_tickets"] == 0

    def test_la_cloture_automatique_des_caisses_ignore_les_billets_externes(self, api_client, cle, reseau):
        from django.core.management import call_command

        envoyer(api_client, cle, vente(reseau["depart"]))

        call_command("cloturer_caisses")  # ne lève pas : un billet sans vendeur n'est la caisse de personne

    def test_un_lot_trop_gros_ou_mal_forme_est_refuse(self, api_client, cle, reseau):
        lien = avec_cle(api_client, cle)

        assert lien.post("/api/lien-billetterie/ventes/", {"ventes": []}, format="json").status_code == 400
        assert lien.post("/api/lien-billetterie/ventes/", {"ventes": "x"}, format="json").status_code == 400
        trop = {"ventes": [vente(reseau["depart"], reference=f"T{n}") for n in range(501)]}
        assert lien.post("/api/lien-billetterie/ventes/", trop, format="json").status_code == 400

    def test_la_vente_recue_se_lit_comme_les_autres_billets(self, api_client, agents, cle, reseau):
        envoyer(api_client, cle, vente(reseau["depart"]))
        api_client.credentials()
        api_client.force_authenticate(user=agents["chef_gare"])

        billet = api_client.get("/api/tickets/").data[0]

        assert billet["source"] == "lien" and billet["logiciel"] == "BilletPro" and billet["vendu_par"] is None


@pytest.mark.django_db
class TestAnnulations:
    def test_le_logiciel_annule_une_vente_et_la_place_revient(self, api_client, cle, reseau):
        envoyer(api_client, cle, vente(reseau["depart"]))

        reponse = annuler(api_client, cle, {"reference": "BP-0001", "motif": "client absent"})

        assert reponse.data["annulee"] == 1
        ticket = Ticket.objects.get()
        assert ticket.statut == StatutTicket.ANNULE and ticket.annule_par is None
        assert ticket.motif_annulation == "Annulé dans BilletPro : client absent"
        reseau["depart"].refresh_from_db()
        assert reseau["depart"].places_vendues == 0

    def test_annuler_deux_fois_ou_une_vente_inconnue(self, api_client, cle, reseau):
        envoyer(api_client, cle, vente(reseau["depart"]))
        annuler(api_client, cle, {"reference": "BP-0001"})

        reponse = annuler(api_client, cle, {"reference": "BP-0001"}, {"reference": "INCONNUE"}, {})

        assert [r["statut"] for r in reponse.data["resultats"]] == ["deja_annulee", "refusee", "refusee"]
        reseau["depart"].refresh_from_db()
        assert reseau["depart"].places_vendues == 0

    def test_un_billet_vendu_au_guichet_ne_s_annule_pas_par_le_lien(self, api_client, agents, cle, reseau):
        Ticket.objects.create(
            depart=reseau["depart"], company=reseau["depart"].company, passager_nom="Yao", passager_telephone="+225",
            prix=5000, mode_paiement="especes", vendu_par=agents["guichetier"],
        )

        reponse = annuler(api_client, cle, {"reference": Ticket.objects.get().code})

        assert reponse.data["refusee"] == 1
        assert Ticket.objects.get().statut == StatutTicket.VALIDE
