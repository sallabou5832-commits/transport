"""Checklist de reprise au relais (cahier des charges : chauffeur relais — checklist de reprise) : le conducteur qui reprend le trajet
constate l'état du car qu'on lui remet, item par item ; un défaut prévient la régulation, l'atelier et, s'il touche la sécurité, le QHSE."""

import datetime

import pytest
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte
from personnel_roulant.models import ITEMS_REPRISE, ChecklistReprise, Relais
from personnel_roulant.tests.conftest_suivi import equipe, trajet  # noqa: F401
from personnel_roulant.tests.test_fatigue_et_relais import relayer

TOUT_OK = [{"item": item, "etat": "ok"} for item in ITEMS_REPRISE]


def avec_defauts(**defauts):
    """La checklist complète, dont les items nommés sont en défaut (`freins="Plaquettes usées"`)."""
    return [
        {"item": item, "etat": "defaut", "commentaire": defauts[item]} if item in defauts else {"item": item, "etat": "ok"}
        for item in ITEMS_REPRISE
    ]


def reprendre(api_client, utilisateur, relais_id, items):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"/api/relais/{relais_id}/reprise/", {"items": items}, format="json")


@pytest.fixture
def relais_fait(api_client, equipe, trajet):  # noqa: F811
    """Le conducteur cède le trajet au chauffeur relais : c'est à celui-ci de constater l'état du car."""
    reponse = relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])
    assert reponse.status_code == 201
    return Relais.objects.get(pk=reponse.data["id"])


@pytest.mark.django_db
class TestReprise:
    def test_le_nouveau_conducteur_a_une_reprise_a_faire(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        api_client.force_authenticate(user=equipe["relais"])

        reponse = api_client.get("/api/suivi/moi/")

        a_faire = reponse.data["reprise_a_faire"]
        assert reponse.data["en_cours"] is True and a_faire["relais"] == relais_fait.id and a_faire["lieu"] == "Yamoussoukro"
        assert a_faire["items"] == list(ITEMS_REPRISE) and a_faire["etat_transmis"]["immatriculation"] == "CI-9100-AA"

    def test_pas_de_reprise_a_faire_avant_le_relais(self, api_client, equipe, trajet):  # noqa: F811
        api_client.force_authenticate(user=equipe["conducteur"])

        assert api_client.get("/api/suivi/moi/").data["reprise_a_faire"] is None

    def test_la_checklist_complete_enregistre_les_six_items(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reponse = reprendre(api_client, equipe["relais"], relais_fait.id, TOUT_OK)

        assert reponse.status_code == 201
        assert reponse.data["reprise"]["faite"] is True and reponse.data["reprise"]["defauts"] == []
        assert [i["item"] for i in reponse.data["reprise"]["items"]] == list(ITEMS_REPRISE)
        assert ChecklistReprise.objects.filter(relais=relais_fait).count() == 6
        assert ChecklistReprise.objects.first().company_id == relais_fait.company_id

    def test_une_fois_faite_elle_n_est_plus_a_faire(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reprendre(api_client, equipe["relais"], relais_fait.id, TOUT_OK)

        assert api_client.get("/api/suivi/moi/").data["reprise_a_faire"] is None

    def test_tout_ok_ne_declenche_aucune_alerte_de_defaut(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reprendre(api_client, equipe["relais"], relais_fait.id, TOUT_OK)

        assert not Alerte.objects.filter(titre__startswith="Défaut à la reprise").exists()

    def test_on_ne_la_fait_qu_une_fois(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reprendre(api_client, equipe["relais"], relais_fait.id, TOUT_OK)

        reponse = reprendre(api_client, equipe["relais"], relais_fait.id, TOUT_OK)

        assert reponse.status_code == 400 and "déjà faite" in str(reponse.data)
        assert ChecklistReprise.objects.count() == 6

    def test_un_trajet_termine_n_a_plus_de_reprise(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        trajet["feuille"].heure_arrivee_reelle = timezone.now()
        trajet["feuille"].save()

        assert reprendre(api_client, equipe["relais"], relais_fait.id, TOUT_OK).status_code == 400


@pytest.mark.django_db
class TestDefautsConstates:
    def test_un_defaut_de_confort_previent_la_regulation_et_l_atelier_sans_alarmer_le_qhse(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reponse = reprendre(api_client, equipe["relais"], relais_fait.id, avec_defauts(carburant="Réservoir au quart"))

        assert reponse.status_code == 201 and reponse.data["reprise"]["defauts"] == ["carburant"]
        alerte = Alerte.objects.get(titre__startswith="Défaut à la reprise")
        assert alerte.type == TypeAlerte.RELAIS and alerte.gravite == "attention"
        assert set(alerte.roles_destinataires) == {"chef_ligne", "directeur_technique", "chef_atelier"}
        assert "Réservoir au quart" in alerte.message and "carburant" in alerte.titre

    def test_un_defaut_de_securite_est_critique_et_previent_le_qhse_et_l_exploitation(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reprendre(api_client, equipe["relais"], relais_fait.id, avec_defauts(freins="Plaquettes usées", carburant="Bas"))

        alerte = Alerte.objects.get(titre__startswith="Défaut à la reprise")
        assert alerte.gravite == "critique" and "freins" in alerte.titre and "carburant" in alerte.titre
        assert {"qhse", "directeur_exploitation", "chef_ligne", "directeur_technique", "chef_atelier"} <= set(alerte.roles_destinataires)
        assert equipe["chef_gare"] in alerte.destinataires.all()  # le chef de la gare de départ est prévenu
        assert "le car roule" in alerte.message

    def test_le_qhse_voit_l_alerte_dans_sa_cloche_pas_le_guichetier(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reprendre(api_client, equipe["relais"], relais_fait.id, avec_defauts(freins="Bruit anormal"))

        for poste, vu in (("qhse", True), ("directeur_technique", True), ("guichetier", False)):
            api_client.force_authenticate(user=equipe[poste])
            titres = [a["titre"] for a in api_client.get("/api/alertes/").data["alertes"]]
            assert any(t.startswith("Défaut à la reprise") for t in titres) is vu, poste

    def test_un_defaut_ne_bloque_pas_le_car_en_route(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reprendre(api_client, equipe["relais"], relais_fait.id, avec_defauts(freins="Bruit anormal"))

        trajet["vehicule"].refresh_from_db()
        assert trajet["vehicule"].statut == "en_ligne"  # le car est déjà sur la route : on prévient, on ne le « bloque » pas


@pytest.mark.django_db
class TestValidation:
    @pytest.mark.parametrize(
        "items",
        [
            None,
            [],
            "pneus",
            TOUT_OK[:-1],  # un item manque
            TOUT_OK + [{"item": "pneus", "etat": "ok"}],  # un item en double
            [{"item": "klaxon", "etat": "ok"}, *TOUT_OK[1:]],  # un item inconnu
            [{"item": "pneus", "etat": "cassé"}, *TOUT_OK[1:]],  # un état invalide
            [{"etat": "ok"}, *TOUT_OK[1:]],  # un item sans nom
        ],
    )
    def test_une_checklist_incomplete_ou_incoherente_est_refusee_sans_rien_enregistrer(self, api_client, equipe, trajet, relais_fait, items):  # noqa: F811
        reponse = reprendre(api_client, equipe["relais"], relais_fait.id, items)

        assert reponse.status_code == 400 and not ChecklistReprise.objects.exists()

    def test_les_noms_d_items_sont_tolerants_sur_la_casse(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        items = [{"item": item.upper(), "etat": "ok"} for item in ITEMS_REPRISE]

        assert reprendre(api_client, equipe["relais"], relais_fait.id, items).status_code == 201


@pytest.mark.django_db
class TestQuiPeutQuoi:
    def test_seul_le_nouveau_conducteur_constate(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        assert reprendre(api_client, equipe["conducteur"], relais_fait.id, TOUT_OK).status_code == 403  # l'ancien : il voit, ne constate pas
        assert reprendre(api_client, equipe["chef_ligne"], relais_fait.id, TOUT_OK).status_code == 403  # la régulation aussi
        assert reprendre(api_client, equipe["autre"], relais_fait.id, TOUT_OK).status_code == 404  # un autre conducteur ne voit même pas ce relais
        assert not ChecklistReprise.objects.exists()

    def test_les_conducteurs_voient_leurs_relais_la_regulation_tous(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        def ids(poste):
            api_client.force_authenticate(user=equipe[poste])
            return [r["id"] for r in api_client.get("/api/relais/").data]

        assert ids("conducteur") == ids("relais") == [relais_fait.id]
        assert ids("autre") == []
        for poste in ("chef_ligne", "chef_gare", "directeur_exploitation", "pdg", "secretaire_general", "qhse", "directeur_technique"):
            assert ids(poste) == [relais_fait.id], poste
        for poste in ("guichetier", "drh", "controleur_ligne"):
            assert ids(poste) == [], poste

    def test_la_regulation_lit_la_checklist_de_reprise(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        reprendre(api_client, equipe["relais"], relais_fait.id, avec_defauts(pneus="Usure à droite"))

        api_client.force_authenticate(user=equipe["chef_ligne"])
        relais = api_client.get(f"/api/relais/{relais_fait.id}/").data

        assert relais["ligne"] == "Adjamé-Bouaké" and relais["vehicule"] == "CI-9100-AA"
        assert relais["nouveau_chauffeur_nom"] == "relais_suivi" and relais["reprise"]["defauts"] == ["pneus"]
        assert relais["reprise"]["items"][0]["commentaire"] == "Usure à droite"

    def test_le_filtre_par_feuille_de_route(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        api_client.force_authenticate(user=equipe["chef_ligne"])

        assert len(api_client.get("/api/relais/", {"feuille": trajet["feuille"].id}).data) == 1
        assert api_client.get("/api/relais/", {"feuille": trajet["feuille"].id + 1000}).data == []

    def test_les_relais_ne_se_creent_ni_ne_se_modifient_par_cette_route(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        api_client.force_authenticate(user=equipe["chef_ligne"])

        assert api_client.post("/api/relais/", {}, format="json").status_code == 405
        assert api_client.delete(f"/api/relais/{relais_fait.id}/").status_code == 405

    def test_isolation_entre_compagnies(self, api_client, equipe, trajet, relais_fait, user_factory, company_b):  # noqa: F811
        etranger = user_factory("chef_ligne_b_reprise", "chef_ligne", company=company_b)

        api_client.force_authenticate(user=etranger)
        assert api_client.get("/api/relais/").data == []
        assert api_client.get(f"/api/relais/{relais_fait.id}/").status_code == 404
        assert reprendre(api_client, etranger, relais_fait.id, TOUT_OK).status_code == 404

    def test_sans_authentification(self, api_client):
        assert api_client.get("/api/relais/").status_code == 401

    def test_le_journal_d_audit_garde_la_trace_de_la_reprise(self, api_client, equipe, trajet, relais_fait):  # noqa: F811
        from audit.models import JournalAudit

        reprendre(api_client, equipe["relais"], relais_fait.id, avec_defauts(freins="Bruit anormal"))

        entrees = JournalAudit.objects.filter(objet_type__iendswith="checklistreprise")
        assert entrees.count() == 6 and {e.acteur_id for e in entrees} == {equipe["relais"].id}


@pytest.mark.django_db
class TestPlusieursRelais:
    def test_la_reprise_a_faire_est_celle_du_dernier_relais(self, api_client, equipe, trajet, relais_fait, user_factory, company_a):  # noqa: F811
        troisieme = user_factory("troisieme_suivi", "chauffeur_principal", company=company_a)
        reprendre(api_client, equipe["relais"], relais_fait.id, TOUT_OK)

        reponse = relayer(api_client, equipe["relais"], trajet, troisieme, lieu="Toumodi")
        assert reponse.status_code == 201

        api_client.force_authenticate(user=troisieme)
        a_faire = api_client.get("/api/suivi/moi/").data["reprise_a_faire"]
        assert a_faire["relais"] == reponse.data["id"] and a_faire["lieu"] == "Toumodi"
        # L'ancien relais garde sa checklist : chaque relais a la sienne.
        assert Relais.objects.count() == 2 and ChecklistReprise.objects.filter(relais=relais_fait).count() == 6
