"""Enregistrer un bagage ou un colis : validation, code de retrait envoyé au client, droits, isolation."""

import re
from decimal import Decimal

import pytest

from audit.models import JournalAudit
from colis.models import Colis, StatutColis
from colis.tests.conftest import corps_colis, enregistrer
from notifications.models import NotificationLog


def texte_pour(numero):
    return [log.contenu for log in NotificationLog.objects.filter(destinataire=numero)]


@pytest.mark.django_db
class TestEnregistrement:
    def test_le_bagagiste_enregistre_un_colis(self, api_client, agents, monde):
        reponse = enregistrer(api_client, agents["bagagiste"], monde)

        assert reponse.status_code == 201
        assert reponse.data["reference"].startswith("COL-")
        assert reponse.data["statut"] == StatutColis.ENREGISTRE
        assert Decimal(reponse.data["poids_kg"]) == Decimal("12.5")
        assert reponse.data["gare_arrivee_nom"] == "Bouaké" and reponse.data["gare_depart_nom"] == "Adjamé"
        assert reponse.data["enregistre_par"] == agents["bagagiste"].id

    def test_le_code_de_retrait_n_est_jamais_renvoye_par_l_api(self, api_client, agents, monde):
        reponse = enregistrer(api_client, agents["bagagiste"], monde)

        assert not [champ for champ in reponse.data if "code" in champ and champ != "code_verrouille"]
        api_client.force_authenticate(user=agents["chef_gare"])
        detail = api_client.get(f"/api/colis/{reponse.data['id']}/").data
        assert not [champ for champ in detail if "code" in champ and champ != "code_verrouille"]

    def test_le_code_part_par_sms_au_destinataire_et_seule_son_empreinte_est_conservee(
        self, api_client, agents, monde
    ):
        reponse = enregistrer(api_client, agents["bagagiste"], monde)

        message = texte_pour("+2250700000003")[0]
        code = re.search(r"Code de retrait : ([A-Z0-9]{6})", message).group(1)
        colis = Colis.objects.get(pk=reponse.data["id"])
        assert code not in colis.code_retrait_hash and colis.code_correspond(code)
        assert "Bouaké" in message and colis.reference in message
        # Le code n'est pas non plus dans le journal d'audit (que lisent la direction et le QHSE).
        entree = JournalAudit.objects.get(objet_type="colis.colis", action="creation")
        assert code not in str(entree.changements) and "code_retrait_hash" not in entree.changements

    def test_l_expediteur_est_prevenu_sans_le_code(self, api_client, agents, monde):
        enregistrer(api_client, agents["bagagiste"], monde)

        message = texte_pour("+2250700000002")[0]
        assert "Frais : 2000 FCFA" in message and "Code de retrait" not in message

    def test_les_deux_canaux_sont_utilises(self, api_client, agents, monde):
        enregistrer(api_client, agents["bagagiste"], monde)

        canaux = set(NotificationLog.objects.filter(destinataire="+2250700000003").values_list("canal", flat=True))
        assert canaux == {"sms", "whatsapp"}

    def test_le_meme_numero_pour_l_expediteur_et_le_destinataire_ne_recoit_qu_un_message_par_canal(
        self, api_client, agents, monde
    ):
        enregistrer(api_client, agents["bagagiste"], monde, expediteur_telephone="0700000003")

        assert NotificationLog.objects.filter(destinataire="+2250700000003", canal="sms").count() == 1
        assert "Code de retrait" in texte_pour("+2250700000003")[0]

    def test_un_echec_d_envoi_n_empeche_pas_l_enregistrement(self, api_client, agents, monde, monkeypatch):
        def casse(*_, **__):
            raise RuntimeError("fournisseur indisponible")

        monkeypatch.setattr("colis.services.envoyer_sms", casse)

        assert enregistrer(api_client, agents["bagagiste"], monde).status_code == 201
        assert Colis.objects.count() == 1


@pytest.mark.django_db
class TestBagageDUnVoyageur:
    def test_le_bagage_lie_a_un_billet_reprend_les_coordonnees_du_voyageur(self, api_client, agents, monde):
        reponse = enregistrer(
            api_client, agents["bagagiste"], monde, ticket=monde["ticket"].id, description="Valise bleue",
            type_colis=None, expediteur_nom=None, expediteur_telephone=None, destinataire_nom=None,
            destinataire_telephone=None,
        )

        assert reponse.status_code == 201
        assert reponse.data["type_colis"] == "bagage"
        assert reponse.data["destinataire_nom"] == "Awa Kone" and reponse.data["expediteur_nom"] == "Awa Kone"
        assert "Code de retrait" in texte_pour("+2250700000001")[0]

    def test_un_billet_d_un_autre_depart_est_refuse(self, api_client, agents, monde, company_a):
        import datetime

        from django.utils import timezone

        from billetterie.models import Depart, ModePaiement, Ticket

        autre = Depart.objects.create(
            ligne=monde["ligne"], vehicule=monde["vehicule"], chauffeur=agents["chauffeur_principal"], company=company_a,
            date_heure=timezone.now() + datetime.timedelta(hours=9),
        )
        ticket = Ticket.objects.create(
            depart=autre, company=company_a, passager_nom="X", passager_telephone="0700000009", prix=1000,
            mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"],
        )

        reponse = enregistrer(api_client, agents["bagagiste"], monde, ticket=ticket.id)

        assert reponse.status_code == 400 and "voyageur de ce départ" in str(reponse.data["ticket"])

    def test_un_billet_annule_est_refuse(self, api_client, agents, monde):
        monde["ticket"].statut = "annule"
        monde["ticket"].save()

        reponse = enregistrer(api_client, agents["bagagiste"], monde, ticket=monde["ticket"].id)

        assert reponse.status_code == 400 and "annulé" in str(reponse.data["ticket"])


@pytest.mark.django_db
class TestValidation:
    @pytest.mark.parametrize(
        "champs,champ",
        [
            ({"destinataire_telephone": ""}, "destinataire_telephone"),
            ({"destinataire_telephone": "abc"}, "destinataire_telephone"),
            ({"destinataire_telephone": "123"}, "destinataire_telephone"),
            ({"expediteur_telephone": "12"}, "expediteur_telephone"),
            ({"destinataire_nom": ""}, "destinataire_nom"),
            ({"expediteur_nom": " "}, "expediteur_nom"),
            ({"poids_kg": "0"}, "poids_kg"),
            ({"poids_kg": "-3"}, "poids_kg"),
            ({"frais": "-1"}, "frais"),
            ({"valeur_declaree": "-10"}, "valeur_declaree"),
            ({"frais": "1500", "mode_paiement": ""}, "mode_paiement"),
            ({"description": ""}, "description"),
        ],
    )
    def test_les_saisies_invalides_sont_refusees(self, api_client, agents, monde, champs, champ):
        reponse = enregistrer(api_client, agents["bagagiste"], monde, **champs)

        assert reponse.status_code == 400 and champ in reponse.data
        assert not Colis.objects.exists()

    def test_sans_frais_le_mode_de_paiement_est_inutile(self, api_client, agents, monde):
        reponse = enregistrer(api_client, agents["bagagiste"], monde, frais="0", mode_paiement="")

        assert reponse.status_code == 201 and reponse.data["mode_paiement"] == ""

    def test_un_numero_ivoirien_sans_indicatif_est_accepte(self, api_client, agents, monde):
        assert enregistrer(api_client, agents["bagagiste"], monde, destinataire_telephone="07 00 00 00 03").status_code == 201

    def test_on_n_enregistre_pas_sur_un_depart_deja_parti_ou_termine(self, api_client, agents, monde):
        monde["feuille"].heure_depart_reelle = monde["depart"].date_heure
        monde["feuille"].save()

        reponse = enregistrer(api_client, agents["bagagiste"], monde)

        assert reponse.status_code == 400 and "déjà parti" in str(reponse.data["depart"])

    def test_on_n_enregistre_pas_sur_le_depart_d_une_autre_compagnie(self, api_client, agents, monde, company_b):
        from django.utils import timezone

        from billetterie.models import Depart
        from core.models import Role
        from reseau.models import Gare, Ligne, Vehicule

        gare = Gare.objects.create(nom="G", ville="V", company=company_b)
        gare2 = Gare.objects.create(nom="G2", ville="V2", company=company_b)
        ligne = Ligne.objects.create(nom="L", gare_depart=gare, gare_arrivee=gare2, company=company_b)
        vehicule = Vehicule.objects.create(immatriculation="CI-7777-ZZ", capacite=10, company=company_b)
        from django.contrib.auth import get_user_model

        chauffeur = get_user_model().objects.create_user("chauffeur_b", password="x", role=Role.CHAUFFEUR_PRINCIPAL, company=company_b)
        etranger = Depart.objects.create(
            ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company_b, date_heure=timezone.now()
        )

        reponse = enregistrer(api_client, agents["bagagiste"], monde, depart=etranger.id)

        assert reponse.status_code == 400 and "depart" in reponse.data

    def test_un_colis_enregistre_ne_se_modifie_pas(self, api_client, agents, monde):
        colis = enregistrer(api_client, agents["bagagiste"], monde).data

        assert api_client.patch(f"/api/colis/{colis['id']}/", {"poids_kg": "1"}).status_code == 405
        assert api_client.delete(f"/api/colis/{colis['id']}/").status_code == 405


@pytest.mark.django_db
class TestDroits:
    @pytest.mark.parametrize("role", ["bagagiste", "chef_gare", "chef_ligne", "directeur_exploitation", "pdg"])
    def test_ces_postes_enregistrent(self, api_client, agents, monde, role):
        assert enregistrer(api_client, agents[role], monde).status_code == 201

    @pytest.mark.parametrize(
        "role", ["guichetier", "controleur_ligne", "chauffeur_principal", "qhse", "drh", "directeur_financier", "magasinier"]
    )
    def test_les_autres_postes_n_enregistrent_pas(self, api_client, agents, monde, role):
        assert enregistrer(api_client, agents[role], monde).status_code == 403
        assert not Colis.objects.exists()

    @pytest.mark.parametrize("role", ["guichetier", "controleur_ligne", "chauffeur_principal", "qhse", "chef_gare"])
    def test_ces_postes_consultent_les_colis(self, api_client, agents, monde, role):
        enregistrer(api_client, agents["bagagiste"], monde)
        api_client.force_authenticate(user=agents[role])

        assert len(api_client.get("/api/colis/").data) == 1

    @pytest.mark.parametrize("role", ["drh", "directeur_financier", "magasinier"])
    def test_les_donnees_des_clients_restent_cloisonnees(self, api_client, agents, monde, role):
        enregistrer(api_client, agents["bagagiste"], monde)
        api_client.force_authenticate(user=agents[role])

        assert api_client.get("/api/colis/").status_code == 403

    def test_les_colis_d_une_autre_compagnie_sont_invisibles(self, api_client, agents, monde, company_b, user_factory):
        colis = enregistrer(api_client, agents["bagagiste"], monde).data
        chef_b = user_factory("chef_gare_colis_b", "chef_gare", company=company_b)
        api_client.force_authenticate(user=chef_b)

        assert api_client.get("/api/colis/").data == []
        assert api_client.get(f"/api/colis/{colis['id']}/").status_code == 404
        assert api_client.post(f"/api/colis/{colis['id']}/charger/").status_code == 404

    def test_le_bagagiste_affecte_ne_voit_que_les_colis_de_sa_gare(self, api_client, agents, monde, company_a):
        import datetime

        from django.utils import timezone

        from billetterie.models import Depart
        from reseau.models import Gare, Ligne

        enregistrer(api_client, agents["bagagiste"], monde)  # Adjamé -> Bouaké : concerne les deux gares
        autre_gare, encore = Gare.objects.create(nom="Yamoussoukro", ville="Y", company=company_a), Gare.objects.create(nom="Korhogo", ville="K", company=company_a)
        ligne = Ligne.objects.create(nom="Yakro-Korhogo", gare_depart=autre_gare, gare_arrivee=encore, company=company_a)
        depart = Depart.objects.create(
            ligne=ligne, vehicule=monde["vehicule"], chauffeur=agents["chauffeur_principal"], company=company_a,
            date_heure=timezone.now() + datetime.timedelta(days=1),
        )
        api_client.force_authenticate(user=agents["chef_gare"])
        api_client.post("/api/colis/", corps_colis(monde, depart=depart.id))

        api_client.force_authenticate(user=agents["bagagiste"])
        vus = api_client.get("/api/colis/").data

        assert len(vus) == 1 and vus[0]["gare_depart_nom"] == "Adjamé"

    def test_filtres_par_depart_et_par_statut(self, api_client, agents, monde):
        enregistrer(api_client, agents["bagagiste"], monde)
        api_client.force_authenticate(user=agents["chef_gare"])

        assert len(api_client.get(f"/api/colis/?depart={monde['depart'].id}&statut=enregistre").data) == 1
        assert api_client.get("/api/colis/?statut=retire").data == []
        assert api_client.get("/api/colis/?depart=abc").data == []


@pytest.mark.django_db
class TestIdempotence:
    def test_rejouer_l_enregistrement_ne_cree_pas_de_doublon_ni_de_nouveau_sms(self, api_client, agents, monde):
        api_client.force_authenticate(user=agents["bagagiste"])
        premiere = api_client.post("/api/colis/", corps_colis(monde), HTTP_IDEMPOTENCY_KEY="cle-colis-1")
        sms = NotificationLog.objects.count()

        seconde = api_client.post("/api/colis/", corps_colis(monde), HTTP_IDEMPOTENCY_KEY="cle-colis-1")

        assert premiere.status_code == 201 and seconde.status_code == 200
        assert seconde.data["id"] == premiere.data["id"] and seconde["Idempotent-Replayed"] == "true"
        assert Colis.objects.count() == 1 and NotificationLog.objects.count() == sms

    def test_la_meme_cle_pour_un_autre_colis_est_refusee(self, api_client, agents, monde):
        api_client.force_authenticate(user=agents["bagagiste"])
        api_client.post("/api/colis/", corps_colis(monde), HTTP_IDEMPOTENCY_KEY="cle-colis-2")

        reponse = api_client.post(
            "/api/colis/", corps_colis(monde, description="Autre chose"), HTTP_IDEMPOTENCY_KEY="cle-colis-2"
        )

        assert reponse.status_code == 400 and Colis.objects.count() == 1

    def test_une_cle_mal_formee_est_refusee(self, api_client, agents, monde):
        api_client.force_authenticate(user=agents["bagagiste"])

        assert api_client.post("/api/colis/", corps_colis(monde), HTTP_IDEMPOTENCY_KEY="clé invalide!").status_code == 400
