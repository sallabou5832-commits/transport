"""Contrôle à bord : vérification des billets (un billet ne sert qu'une fois), voyageurs et charge comparés à ce qui a été
enregistré, rapport, alerte directe de la direction et du QHSE en cas d'infraction grave, historique par ligne et chauffeur."""

import pytest
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte
from alertes.tests.conftest import alertes_de
from billetterie.models import Depart, DepartStatut, ModePaiement, StatutTicket, Ticket
from colis.models import Colis, StatutColis
from personnel_roulant.models import ControleLigne, Incident, VerificationTicket
from personnel_roulant.tests.conftest_suivi import equipe, trajet  # noqa: F401


def vendre(trajet, equipe, nombre=1, **champs):  # noqa: F811
    tickets = []
    for numero in range(nombre):
        tickets.append(
            Ticket.objects.create(
                depart=champs.pop("depart", trajet["depart"]) if nombre == 1 else trajet["depart"],
                company=trajet["ligne"].company, passager_nom=f"Passager {numero}", passager_telephone="+225",
                prix=5000, mode_paiement=ModePaiement.ESPECES, vendu_par=equipe["guichetier"], **champs,
            )
        )
    return tickets


def ouvrir(api_client, equipe, trajet, role="controleur_ligne"):  # noqa: F811
    api_client.force_authenticate(user=equipe[role])
    return api_client.post("/api/controles/", {"feuille_de_route": trajet["feuille"].id}, format="json")


def verifier(api_client, equipe, controle_id, code, role="controleur_ligne"):  # noqa: F811
    api_client.force_authenticate(user=equipe[role])
    return api_client.post(f"/api/controles/{controle_id}/verifier/", {"code": code}, format="json")


def cloturer(api_client, equipe, controle_id, role="controleur_ligne", **corps):  # noqa: F811
    api_client.force_authenticate(user=equipe[role])
    return api_client.post(f"/api/controles/{controle_id}/cloturer/", corps, format="json")


@pytest.fixture
def controle(api_client, equipe, trajet):  # noqa: F811
    return ouvrir(api_client, equipe, trajet).data


@pytest.mark.django_db
class TestOuvrirUnControle:
    def test_le_controleur_ouvre_un_controle_sur_un_trajet(self, api_client, equipe, trajet):  # noqa: F811
        reponse = ouvrir(api_client, equipe, trajet)

        assert reponse.status_code == 201 and reponse.data["est_ouvert"] is True
        assert reponse.data["ligne_nom"] == "Adjamé-Bouaké" and reponse.data["vehicule"] == "CI-9100-AA"
        assert reponse.data["chauffeur_nom"] == "conducteur_suivi" and reponse.data["controleur"] == equipe["controleur_ligne"].id
        assert reponse.data["nombre_verifications"] == 0

    def test_rouvrir_l_ecran_reprend_le_controle_ouvert(self, api_client, equipe, trajet):  # noqa: F811
        premier = ouvrir(api_client, equipe, trajet).data

        second = ouvrir(api_client, equipe, trajet)

        assert second.status_code == 200 and second.data["id"] == premier["id"]
        assert ControleLigne.objects.count() == 1

    @pytest.mark.parametrize("role", ["guichetier", "chef_ligne", "qhse", "drh", "pdg", "conducteur"])
    def test_seul_le_controleur_controle(self, api_client, equipe, trajet, role):  # noqa: F811
        assert ouvrir(api_client, equipe, trajet, role).status_code == 403
        assert not ControleLigne.objects.exists()

    def test_on_ne_controle_pas_un_trajet_termine(self, api_client, equipe, trajet):  # noqa: F811
        trajet["feuille"].heure_arrivee_reelle = timezone.now()
        trajet["feuille"].save()

        assert ouvrir(api_client, equipe, trajet).status_code == 400

    def test_on_ne_controle_pas_le_trajet_d_une_autre_compagnie(self, api_client, equipe, trajet, company_b, user_factory):  # noqa: F811
        controleur_b = user_factory("controleur_b", "controleur_ligne", company=company_b)
        api_client.force_authenticate(user=controleur_b)

        reponse = api_client.post("/api/controles/", {"feuille_de_route": trajet["feuille"].id}, format="json")

        assert reponse.status_code == 400


@pytest.mark.django_db
class TestVerifierUnBillet:
    def test_un_billet_valide_est_accepte_et_marque_utilise(self, api_client, equipe, trajet, controle):  # noqa: F811
        ticket = vendre(trajet, equipe)[0]

        reponse = verifier(api_client, equipe, controle["id"], ticket.code)

        assert reponse.status_code == 200 and reponse.data["valide"] is True and reponse.data["resultat"] == "valide"
        assert reponse.data["ticket"]["passager_nom"] == "Passager 0"
        ticket.refresh_from_db()
        assert ticket.utilise_le is not None and ticket.utilise_par == equipe["controleur_ligne"]

    def test_un_billet_ne_sert_qu_une_fois(self, api_client, equipe, trajet, controle):  # noqa: F811
        ticket = vendre(trajet, equipe)[0]
        verifier(api_client, equipe, controle["id"], ticket.code)

        seconde = verifier(api_client, equipe, controle["id"], ticket.code)

        assert seconde.data["valide"] is False and seconde.data["resultat"] == "deja_utilise"
        assert "DÉJÀ UTILISÉ" in seconde.data["message"]
        assert seconde.data["ticket"]["utilise_par_nom"] == "controleur_ligne_suivi" and seconde.data["ticket"]["utilise_le"]

    def test_le_code_est_tolerant_sur_la_casse_et_les_separateurs(self, api_client, equipe, trajet, controle):  # noqa: F811
        ticket = vendre(trajet, equipe)[0]
        code = ticket.code

        reponse = verifier(api_client, equipe, controle["id"], f" {code[:5].lower()}-{code[5:].lower()} ")

        assert reponse.data["resultat"] == "valide"

    def test_un_code_inconnu_est_refuse(self, api_client, equipe, trajet, controle):  # noqa: F811
        reponse = verifier(api_client, equipe, controle["id"], "ZZZZZZZZZZ")

        assert reponse.data["valide"] is False and reponse.data["resultat"] == "inconnu" and "ticket" not in reponse.data

    def test_un_billet_annule_est_refuse(self, api_client, equipe, trajet, controle):  # noqa: F811
        ticket = vendre(trajet, equipe)[0]
        Ticket.objects.filter(pk=ticket.pk).update(statut=StatutTicket.ANNULE)

        reponse = verifier(api_client, equipe, controle["id"], ticket.code)

        assert reponse.data["resultat"] == "annule"
        ticket.refresh_from_db()
        assert ticket.utilise_le is None  # un billet refusé n'est pas consommé

    def test_un_billet_d_un_autre_depart_est_refuse_sans_etre_consomme(self, api_client, equipe, trajet, controle, company_a):  # noqa: F811
        import datetime

        autre = Depart.objects.create(
            ligne=trajet["ligne"], vehicule=trajet["vehicule"], chauffeur=equipe["autre"], company=company_a,
            date_heure=timezone.now() + datetime.timedelta(days=1),
        )
        ticket = vendre(trajet, equipe, depart=autre)[0]

        reponse = verifier(api_client, equipe, controle["id"], ticket.code)

        assert reponse.data["resultat"] == "autre_depart"
        ticket.refresh_from_db()
        assert ticket.utilise_le is None

    def test_le_billet_d_un_depart_termine_est_refuse(self, api_client, equipe, trajet, controle):  # noqa: F811
        ticket = vendre(trajet, equipe)[0]
        trajet["depart"].statut = DepartStatut.TERMINE
        trajet["depart"].save()

        assert verifier(api_client, equipe, controle["id"], ticket.code).data["resultat"] == "depart_termine"

    def test_le_billet_d_une_autre_compagnie_est_inconnu(self, api_client, equipe, trajet, controle, company_b, user_factory):  # noqa: F811
        from reseau.models import Gare, Ligne, Vehicule

        gare = Gare.objects.create(nom="G", ville="V", company=company_b)
        gare2 = Gare.objects.create(nom="G2", ville="V", company=company_b)
        ligne = Ligne.objects.create(nom="L", gare_depart=gare, gare_arrivee=gare2, company=company_b)
        vehicule = Vehicule.objects.create(immatriculation="CI-5-ZZ", capacite=10, company=company_b)
        chauffeur = user_factory("chauffeur_b_controle", "chauffeur_principal", company=company_b)
        depart = Depart.objects.create(ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company_b, date_heure=timezone.now())
        etranger = Ticket.objects.create(
            depart=depart, company=company_b, passager_nom="X", passager_telephone="+225", prix=1000,
            mode_paiement=ModePaiement.ESPECES, vendu_par=chauffeur,
        )

        assert verifier(api_client, equipe, controle["id"], etranger.code).data["resultat"] == "inconnu"

    def test_le_code_est_obligatoire(self, api_client, equipe, controle):  # noqa: F811
        assert verifier(api_client, equipe, controle["id"], "  ").status_code == 400

    def test_chaque_verification_est_enregistree(self, api_client, equipe, trajet, controle):  # noqa: F811
        ticket = vendre(trajet, equipe)[0]
        verifier(api_client, equipe, controle["id"], ticket.code)
        verifier(api_client, equipe, controle["id"], "ZZZZZZZZZZ")

        assert list(VerificationTicket.objects.values_list("resultat", flat=True)) == ["valide", "inconnu"]

    def test_le_controle_d_un_collegue_n_est_pas_le_sien(self, api_client, equipe, trajet, controle, user_factory, company_a):  # noqa: F811
        equipe["autre_controleur"] = user_factory("autre_controleur_suivi", "controleur_ligne", company=company_a)

        assert verifier(api_client, equipe, controle["id"], "AAAAAAAAAA", role="autre_controleur").status_code == 404

    def test_on_ne_verifie_plus_dans_un_controle_cloture(self, api_client, equipe, trajet, controle):  # noqa: F811
        cloturer(api_client, equipe, controle["id"])

        assert verifier(api_client, equipe, controle["id"], "AAAAAAAAAA").status_code == 400

    @pytest.mark.parametrize("role", ["guichetier", "qhse", "chef_ligne", "conducteur"])
    def test_seul_le_controleur_verifie(self, api_client, equipe, controle, role):  # noqa: F811
        assert verifier(api_client, equipe, controle["id"], "AAAAAAAAAA", role=role).status_code == 403


@pytest.mark.django_db
class TestRapportEtCloture:
    def test_le_rapport_compare_voyageurs_et_charge_a_ce_qui_a_ete_enregistre(self, api_client, equipe, trajet, controle, company_a):  # noqa: F811
        billets = vendre(trajet, equipe, nombre=10)
        for billet in billets[:6]:
            verifier(api_client, equipe, controle["id"], billet.code)
        for numero, kg in enumerate((30, 20)):
            colis = Colis(
                company=company_a, depart=trajet["depart"], description=f"C{numero}", poids_kg=kg, expediteur_nom="A",
                destinataire_nom="B", destinataire_telephone="0700000003", enregistre_par=equipe["guichetier"], statut=StatutColis.CHARGE,
            )
            colis.definir_code("ABC234")
            colis.save()

        reponse = cloturer(api_client, equipe, controle["id"], passagers_constates=10, charge_constatee_kg="52", commentaire="RAS")

        assert reponse.status_code == 200 and reponse.data["est_ouvert"] is False and reponse.data["infraction_grave"] is False
        rapport = reponse.data["rapport"]
        assert rapport["billets"]["verifies"] == 6 and rapport["billets"]["valides"] == 6 and rapport["billets"]["refuses"] == 0
        assert rapport["voyageurs"]["vendus"] == 10 and rapport["voyageurs"]["constates"] == 10 and rapport["voyageurs"]["ecart"] == 0
        assert float(rapport["charge"]["declaree_kg"]) == 50 and float(rapport["charge"]["ecart_kg"]) == 2
        assert rapport["anomalies"] == [] and rapport["ligne"] == "Adjamé-Bouaké" and rapport["controleur"] == "controleur_ligne_suivi"

    def test_des_voyageurs_sans_billet_sont_signales(self, api_client, equipe, trajet, controle):  # noqa: F811
        vendre(trajet, equipe, nombre=10)

        rapport = cloturer(api_client, equipe, controle["id"], passagers_constates=15).data["rapport"]

        assert rapport["voyageurs"]["ecart"] == 5 and rapport["voyageurs"]["ecart_pourcent"] == 50
        assert any("5 voyageur(s) de plus que de billets vendus" in a for a in rapport["anomalies"])

    def test_un_petit_ecart_reste_sous_le_seuil(self, api_client, equipe, trajet, controle):  # noqa: F811
        vendre(trajet, equipe, nombre=20)

        assert cloturer(api_client, equipe, controle["id"], passagers_constates=21).data["rapport"]["anomalies"] == []

    def test_une_charge_non_declaree_est_signalee(self, api_client, equipe, trajet, controle):  # noqa: F811
        rapport = cloturer(api_client, equipe, controle["id"], charge_constatee_kg="120").data["rapport"]

        assert any("colis non déclarés" in a for a in rapport["anomalies"])

    def test_un_apercu_du_rapport_est_disponible_pendant_le_controle(self, api_client, equipe, trajet, controle):  # noqa: F811
        billets = vendre(trajet, equipe, nombre=3)
        verifier(api_client, equipe, controle["id"], billets[0].code)
        api_client.force_authenticate(user=equipe["controleur_ligne"])

        apercu = api_client.get(f"/api/controles/{controle['id']}/rapport/").data

        assert apercu["billets"]["verifies"] == 1 and apercu["voyageurs"]["vendus"] == 3
        assert ControleLigne.objects.get().est_ouvert is True

    def test_le_rapport_cloture_est_celui_enregistre(self, api_client, equipe, trajet, controle):  # noqa: F811
        cloturer(api_client, equipe, controle["id"], commentaire="Contrôle de routine")
        api_client.force_authenticate(user=equipe["qhse"])

        assert api_client.get(f"/api/controles/{controle['id']}/rapport/").data["ligne"] == "Adjamé-Bouaké"

    def test_on_ne_cloture_qu_une_fois(self, api_client, equipe, trajet, controle):  # noqa: F811
        cloturer(api_client, equipe, controle["id"])

        assert cloturer(api_client, equipe, controle["id"]).status_code == 400

    @pytest.mark.parametrize("corps", [{"passagers_constates": "abc"}, {"passagers_constates": -3}, {"charge_constatee_kg": "-1"}, {"charge_constatee_kg": "lourd"}])
    def test_les_constats_invalides_sont_refuses(self, api_client, equipe, trajet, controle, corps):  # noqa: F811
        assert cloturer(api_client, equipe, controle["id"], **corps).status_code == 400
        assert ControleLigne.objects.get().est_ouvert is True


@pytest.mark.django_db
class TestInfractionGrave:
    def test_une_surcharge_est_une_infraction_grave_qui_alerte_directement_la_direction_et_le_qhse(self, api_client, equipe, trajet, controle):  # noqa: F811
        reponse = cloturer(api_client, equipe, controle["id"], passagers_constates=45)  # capacité : 40

        assert reponse.data["infraction_grave"] is True and "Surcharge" in reponse.data["motif_infraction"]
        for role in ("qhse", "pdg", "directeur_exploitation"):
            visibles = [a for a in alertes_de(api_client, equipe[role]) if a["type"] == TypeAlerte.INFRACTION]
            assert len(visibles) == 1, role
            assert visibles[0]["gravite"] == "critique" and "Infraction grave au contrôle" in visibles[0]["titre"]
            assert "SURCHARGE : 45 voyageurs pour 40 places" in visibles[0]["message"]

    def test_l_alerte_est_independante_de_la_regulation_et_de_la_gare(self, api_client, equipe, trajet, controle):  # noqa: F811
        cloturer(api_client, equipe, controle["id"], passagers_constates=45)

        for role in ("chef_ligne", "chef_gare", "guichetier", "conducteur"):
            assert [a for a in alertes_de(api_client, equipe[role]) if a["type"] == TypeAlerte.INFRACTION] == [], role

    def test_l_infraction_devient_un_incident_grave_visible_du_qhse(self, api_client, equipe, trajet, controle):  # noqa: F811
        cloturer(api_client, equipe, controle["id"], passagers_constates=45)

        incident = Incident.objects.get()
        assert incident.gravite == "grave" and incident.statut == "ouvert" and "Surcharge" in incident.description
        assert incident.chauffeur == equipe["conducteur"] and incident.vehicule == trajet["vehicule"]
        api_client.force_authenticate(user=equipe["qhse"])
        assert len(api_client.get("/api/incidents/graves/").data) == 1

    def test_trois_billets_frauduleux_font_une_infraction_grave(self, api_client, equipe, trajet, controle):  # noqa: F811
        billet = vendre(trajet, equipe)[0]
        verifier(api_client, equipe, controle["id"], billet.code)
        verifier(api_client, equipe, controle["id"], billet.code)  # déjà utilisé
        verifier(api_client, equipe, controle["id"], "AAAAAAAAAA")  # inconnu
        verifier(api_client, equipe, controle["id"], "BBBBBBBBBB")  # inconnu

        reponse = cloturer(api_client, equipe, controle["id"])

        assert reponse.data["infraction_grave"] is True and "3 billets frauduleux" in reponse.data["motif_infraction"]
        rapport = reponse.data["rapport"]
        assert rapport["fraudes"] == 3 and any("déjà utilisé" in a for a in rapport["anomalies"])

    def test_deux_faux_billets_ne_suffisent_pas(self, api_client, equipe, trajet, controle):  # noqa: F811
        verifier(api_client, equipe, controle["id"], "AAAAAAAAAA")
        verifier(api_client, equipe, controle["id"], "BBBBBBBBBB")

        assert cloturer(api_client, equipe, controle["id"]).data["infraction_grave"] is False
        assert not Alerte.objects.filter(type=TypeAlerte.INFRACTION).exists()

    def test_le_controleur_signale_lui_meme_une_infraction_avec_un_motif(self, api_client, equipe, trajet, controle):  # noqa: F811
        reponse = cloturer(
            api_client, equipe, controle["id"], infraction_grave=True, motif_infraction="Chauffeur en état d'ébriété"
        )

        assert reponse.data["infraction_grave"] is True and reponse.data["motif_infraction"] == "Chauffeur en état d'ébriété"
        assert Alerte.objects.filter(type=TypeAlerte.INFRACTION).count() == 1

    def test_le_motif_est_obligatoire_pour_une_infraction_signalee(self, api_client, equipe, trajet, controle):  # noqa: F811
        reponse = cloturer(api_client, equipe, controle["id"], infraction_grave=True)

        assert reponse.status_code == 400 and "motif_infraction" in reponse.data
        assert ControleLigne.objects.get().est_ouvert is True  # rien n'a été clôturé

    def test_un_controle_sans_infraction_ne_previent_personne(self, api_client, equipe, trajet, controle):  # noqa: F811
        cloturer(api_client, equipe, controle["id"], passagers_constates=10)

        assert not Alerte.objects.filter(type=TypeAlerte.INFRACTION).exists() and not Incident.objects.exists()


@pytest.mark.django_db
class TestHistorique:
    def cloturer_un_controle(self, api_client, equipe, trajet, **corps):  # noqa: F811
        controle = ouvrir(api_client, equipe, trajet).data
        return cloturer(api_client, equipe, controle["id"], **corps).data

    def test_l_historique_se_filtre_par_ligne_et_par_chauffeur(self, api_client, equipe, trajet, company_a):  # noqa: F811
        self.cloturer_un_controle(api_client, equipe, trajet)
        from reseau.models import Ligne

        autre_ligne = Ligne.objects.create(nom="Autre", gare_depart=trajet["gare_depart"], gare_arrivee=trajet["gare_arrivee"], company=company_a)
        api_client.force_authenticate(user=equipe["qhse"])

        assert len(api_client.get("/api/controles/").data) == 1
        assert len(api_client.get(f"/api/controles/?ligne={trajet['ligne'].id}").data) == 1
        assert api_client.get(f"/api/controles/?ligne={autre_ligne.id}").data == []
        assert len(api_client.get(f"/api/controles/?chauffeur={equipe['conducteur'].id}").data) == 1
        assert api_client.get(f"/api/controles/?chauffeur={equipe['autre'].id}").data == []

    def test_on_filtre_les_controles_avec_infraction_ou_encore_ouverts(self, api_client, equipe, trajet):  # noqa: F811
        self.cloturer_un_controle(api_client, equipe, trajet, passagers_constates=50)
        ouvrir(api_client, equipe, trajet)
        api_client.force_authenticate(user=equipe["directeur_exploitation"])

        assert len(api_client.get("/api/controles/?infraction=1").data) == 1
        assert len(api_client.get("/api/controles/?ouvert=1").data) == 1

    def test_le_controleur_ne_voit_que_ses_controles(self, api_client, equipe, trajet, user_factory, company_a):  # noqa: F811
        self.cloturer_un_controle(api_client, equipe, trajet)
        equipe["collegue"] = user_factory("collegue_controleur", "controleur_ligne", company=company_a)
        api_client.force_authenticate(user=equipe["collegue"])

        assert api_client.get("/api/controles/").data == []

    @pytest.mark.parametrize("role", ["qhse", "directeur_exploitation", "pdg", "secretaire_general", "chef_ligne", "chef_gare"])
    def test_la_supervision_lit_les_controles(self, api_client, equipe, trajet, role):  # noqa: F811
        self.cloturer_un_controle(api_client, equipe, trajet)
        api_client.force_authenticate(user=equipe[role])

        assert len(api_client.get("/api/controles/").data) == 1

    @pytest.mark.parametrize("role", ["guichetier", "drh", "conducteur", "directeur_technique"])
    def test_les_autres_postes_ne_lisent_pas_les_controles(self, api_client, equipe, trajet, role):  # noqa: F811
        self.cloturer_un_controle(api_client, equipe, trajet)
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/controles/").status_code == 403

    def test_les_controles_d_une_autre_compagnie_sont_invisibles(self, api_client, equipe, trajet, company_b, user_factory):  # noqa: F811
        controle = self.cloturer_un_controle(api_client, equipe, trajet)
        qhse_b = user_factory("qhse_controle_b", "qhse", company=company_b)
        api_client.force_authenticate(user=qhse_b)

        assert api_client.get("/api/controles/").data == []
        assert api_client.get(f"/api/controles/{controle['id']}/").status_code == 404

    def test_le_controle_est_trace(self, api_client, equipe, trajet):  # noqa: F811
        from audit.models import JournalAudit

        self.cloturer_un_controle(api_client, equipe, trajet)

        assert JournalAudit.objects.filter(objet_type="personnel_roulant.controleligne", action="creation").exists()


@pytest.mark.django_db
class TestCodeDuBillet:
    def test_chaque_billet_a_un_code_unique_et_lisible(self, equipe, trajet):  # noqa: F811
        billets = vendre(trajet, equipe, nombre=30)

        codes = {b.code for b in billets}

        assert len(codes) == 30 and all(len(c) == 10 and set(c) <= set("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for c in codes)

    def test_le_code_est_expose_mais_ne_se_choisit_pas(self, api_client, equipe, trajet):  # noqa: F811
        api_client.force_authenticate(user=equipe["guichetier"])
        reponse = api_client.post(
            "/api/tickets/",
            {"depart": trajet["depart"].id, "passager_nom": "Awa", "passager_telephone": "0700000001", "prix": "5000",
             "mode_paiement": "especes", "code": "AAAAAAAAAA", "utilise_le": "2030-01-01T00:00:00Z"},
        )

        assert reponse.status_code == 201
        assert reponse.data["code"] != "AAAAAAAAAA" and len(reponse.data["code"]) == 10 and reponse.data["utilise_le"] is None

    def test_le_code_part_avec_la_confirmation_du_billet(self, api_client, equipe, trajet):  # noqa: F811
        from notifications.models import NotificationLog

        api_client.force_authenticate(user=equipe["guichetier"])
        billet = api_client.post(
            "/api/tickets/",
            {"depart": trajet["depart"].id, "passager_nom": "Awa", "passager_telephone": "0700000001", "prix": "5000", "mode_paiement": "especes"},
        ).data

        messages = NotificationLog.objects.filter(destinataire="+2250700000001").values_list("contenu", flat=True)

        assert messages and all(f"Code du billet : {billet['code']}" in m for m in messages)


@pytest.mark.django_db
class TestScoreDeControle:
    def test_le_controleur_marque_des_points_pour_ses_controles(self, api_client, equipe, trajet):  # noqa: F811
        from gamification.moteur import points_agent

        billets = vendre(trajet, equipe, nombre=3)
        controle = ouvrir(api_client, equipe, trajet).data
        for billet in billets:
            verifier(api_client, equipe, controle["id"], billet.code)
        cloturer(api_client, equipe, controle["id"], passagers_constates=50)  # surcharge : infraction grave

        detail = {ligne["code"]: ligne["points"] for ligne in points_agent(equipe["controleur_ligne"])["detail"]}

        assert detail["controle_cloture"] == 5 and detail["billet_verifie"] == 3 and detail["infraction_signalee"] == 10

    def test_le_controleur_a_ses_missions_et_son_classement(self, api_client, equipe, trajet):  # noqa: F811
        api_client.force_authenticate(user=equipe["controleur_ligne"])

        etat = api_client.get("/api/gamification/moi/").data

        assert [m["code"] for m in etat["missions"]] == ["controler_2", "verifier_20"]
        assert [c["type"] for c in etat["classements"]] == ["gares", "controleurs"]
        assert etat["score_applicable"] is True


@pytest.mark.django_db
class TestValeursHostiles:
    """Un code trop long, un nombre démesuré ou « NaN » sont des erreurs 400 (ou un billet inconnu), jamais une erreur 500."""

    def test_un_code_de_plus_de_32_caracteres_est_un_billet_inconnu(self, api_client, equipe, trajet, controle):  # noqa: F811
        reponse = verifier(api_client, equipe, controle["id"], "A" * 200)

        assert reponse.status_code == 200 and reponse.data["resultat"] == "inconnu"
        assert VerificationTicket.objects.get().code == "A" * 32

    @pytest.mark.parametrize("champ, valeur", [
        ("passagers_constates", 99999999999),
        ("passagers_constates", "1" * 5000),
        ("charge_constatee_kg", "NaN"),
        ("charge_constatee_kg", "Infinity"),
        ("charge_constatee_kg", "1000000"),
        ("charge_constatee_kg", 123456789.5),
    ])
    def test_cloture_avec_un_nombre_refuse(self, api_client, equipe, trajet, controle, champ, valeur):  # noqa: F811
        reponse = cloturer(api_client, equipe, controle["id"], **{champ: valeur})

        assert reponse.status_code == 400 and champ in reponse.data
        assert ControleLigne.objects.get(pk=controle["id"]).est_ouvert

    def test_les_bornes_de_la_colonne_sont_acceptees(self, api_client, equipe, trajet, controle):  # noqa: F811
        reponse = cloturer(api_client, equipe, controle["id"], passagers_constates=0, charge_constatee_kg="999999.99")

        assert reponse.status_code == 200
