"""Alerte fatigue et pauses ; relais entre conducteurs (transfert de la feuille de route et de l'état du véhicule) ;
anomalie de cargaison (mode surveillance du convoyeur)."""

import datetime
import re

import pytest
from django.utils import timezone

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from alertes.tests.conftest import alertes_de
from core.models import Role
from personnel_roulant.models import ChecklistDepart, Incident, PausePrise, Relais
from personnel_roulant.tests.conftest_suivi import equipe, partir_il_y_a, trajet  # noqa: F401
from personnel_roulant.tests.test_positions_gps import POSITION, envoyer


def fatigue(api_client, utilisateur, trajet):  # noqa: F811
    api_client.force_authenticate(user=utilisateur)
    return api_client.get(f"/api/feuilles-de-route/{trajet['feuille'].id}/fatigue/")


def pause(api_client, utilisateur, trajet, action):  # noqa: F811
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"/api/feuilles-de-route/{trajet['feuille'].id}/pause/", {"action": action}, format="json")


def relayer(api_client, utilisateur, trajet, relais, lieu="Yamoussoukro"):  # noqa: F811
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(
        f"/api/feuilles-de-route/{trajet['feuille'].id}/relais/", {"relais": relais.id, "lieu": lieu}, format="json"
    )


@pytest.mark.django_db
class TestFatigue:
    def test_le_temps_de_conduite_continue_court_depuis_le_depart(self, api_client, equipe, trajet):  # noqa: F811
        etat = fatigue(api_client, equipe["conducteur"], trajet).data

        assert 59 <= etat["conduite_continue_minutes"] <= 61 and etat["seuil_minutes"] == 270
        assert etat["alerte"] is False and etat["minutes_avant_alerte"] > 200 and etat["en_pause"] is False

    def test_l_alerte_se_declenche_au_seuil_de_quatre_heures_trente(self, api_client, equipe, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=4, minutes=29))
        assert fatigue(api_client, equipe["conducteur"], trajet).data["alerte"] is False

        partir_il_y_a(trajet, datetime.timedelta(hours=4, minutes=31))
        etat = fatigue(api_client, equipe["conducteur"], trajet).data

        assert etat["alerte"] is True and etat["minutes_avant_alerte"] == 0

    def test_le_seuil_se_regle(self, api_client, equipe, trajet, settings):  # noqa: F811
        settings.SUIVI_SEUIL_FATIGUE_MINUTES = 90
        partir_il_y_a(trajet, datetime.timedelta(hours=2))

        assert fatigue(api_client, equipe["conducteur"], trajet).data["alerte"] is True

    def test_l_alerte_propose_des_relais_libres_le_relais_d_abord(self, api_client, equipe, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))

        etat = fatigue(api_client, equipe["conducteur"], trajet).data

        propositions = [r["nom"] for r in etat["relais_suggeres"]]
        assert propositions == ["relais_suivi", "autre_chauffeur_suivi"]  # le chauffeur relais avant le principal

    def test_un_conducteur_deja_en_route_n_est_pas_propose(self, api_client, equipe, trajet):  # noqa: F811
        from billetterie.models import Depart, DepartStatut
        from personnel_roulant.models import FeuilleDeRoute

        partir_il_y_a(trajet, datetime.timedelta(hours=5))
        maintenant = timezone.now() - datetime.timedelta(minutes=30)
        depart = Depart.objects.create(
            ligne=trajet["ligne"], vehicule=trajet["vehicule"], chauffeur=equipe["relais"], company=equipe["relais"].company,
            date_heure=maintenant, statut=DepartStatut.EN_COURS,
        )
        FeuilleDeRoute.objects.create(
            depart=depart, chauffeur=equipe["relais"], company=depart.company, heure_depart_prevue=maintenant, heure_depart_reelle=maintenant
        )

        propositions = [r["nom"] for r in fatigue(api_client, equipe["conducteur"], trajet).data["relais_suggeres"]]

        assert "relais_suivi" not in propositions

    def test_visible_du_conducteur_de_la_regulation_et_du_qhse_seulement(self, api_client, equipe, trajet):  # noqa: F811
        for role in ("conducteur", "chef_ligne", "chef_gare", "directeur_exploitation", "qhse", "pdg"):
            assert fatigue(api_client, equipe[role], trajet).status_code == 200, role
        for role in ("guichetier", "drh", "autre", "controleur_ligne"):
            assert fatigue(api_client, equipe[role], trajet).status_code == 403, role

    def test_un_trajet_termine_n_a_plus_de_fatigue(self, api_client, equipe, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=6))
        trajet["feuille"].heure_arrivee_reelle = timezone.now()
        trajet["feuille"].save()

        etat = fatigue(api_client, equipe["conducteur"], trajet).data

        assert etat["conduite_continue_minutes"] == 0 and etat["alerte"] is False


@pytest.mark.django_db
class TestPauses:
    def test_une_pause_remet_le_compteur_a_zero(self, api_client, equipe, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))
        assert fatigue(api_client, equipe["conducteur"], trajet).data["alerte"] is True

        debut = pause(api_client, equipe["conducteur"], trajet, "debut")
        assert debut.status_code == 200 and debut.data["en_pause"] is True and debut.data["conduite_continue_minutes"] == 0
        fin = pause(api_client, equipe["conducteur"], trajet, "fin")

        assert fin.data["en_pause"] is False and fin.data["conduite_continue_minutes"] <= 1 and fin.data["alerte"] is False

    def test_on_ne_commence_pas_deux_pauses(self, api_client, equipe, trajet):  # noqa: F811
        pause(api_client, equipe["conducteur"], trajet, "debut")

        assert pause(api_client, equipe["conducteur"], trajet, "debut").status_code == 400

    def test_on_ne_termine_pas_une_pause_qui_n_existe_pas(self, api_client, equipe, trajet):  # noqa: F811
        assert pause(api_client, equipe["conducteur"], trajet, "fin").status_code == 400

    def test_l_action_doit_etre_debut_ou_fin(self, api_client, equipe, trajet):  # noqa: F811
        assert pause(api_client, equipe["conducteur"], trajet, "dormir").status_code == 400

    @pytest.mark.parametrize("role", ["chef_ligne", "qhse", "autre", "guichetier"])
    def test_seul_le_conducteur_du_trajet_prend_une_pause(self, api_client, equipe, trajet, role):  # noqa: F811
        assert pause(api_client, equipe[role], trajet, "debut").status_code == 403
        assert not PausePrise.objects.exists()

    def test_une_pause_sur_un_trajet_pas_commence_est_refusee(self, api_client, equipe, trajet):  # noqa: F811
        trajet["feuille"].heure_depart_reelle = None
        trajet["feuille"].save()

        assert pause(api_client, equipe["conducteur"], trajet, "debut").status_code == 400


@pytest.mark.django_db
class TestAlerteFatigueAutomatique:
    def test_le_conducteur_et_la_regulation_sont_prevenus_avec_des_relais_possibles(self, api_client, equipe, trajet, company_a):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))

        generer(company_a)

        for role in ("conducteur", "chef_ligne"):
            visibles = [a for a in alertes_de(api_client, equipe[role]) if a["type"] == TypeAlerte.FATIGUE]
            assert len(visibles) == 1, role
            assert re.search(r"5 h 0\d de conduite continue", visibles[0]["message"]), visibles[0]["message"]
            assert "relais_suivi" in visibles[0]["message"]
        assert [a for a in alertes_de(api_client, equipe["guichetier"]) if a["type"] == TypeAlerte.FATIGUE] == []

    def test_pas_d_alerte_avant_le_seuil(self, company_a, trajet):  # noqa: F811
        assert [a for a in generer(company_a) if a.type == TypeAlerte.FATIGUE] == []

    def test_relancer_ne_previent_pas_deux_fois_au_meme_palier(self, company_a, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))
        generer(company_a)

        assert [a for a in generer(company_a) if a.type == TypeAlerte.FATIGUE] == []
        assert Alerte.objects.filter(type=TypeAlerte.FATIGUE).count() == 1

    def test_un_nouveau_palier_reprevient_et_devient_critique(self, company_a, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))
        generer(company_a)
        partir_il_y_a(trajet, datetime.timedelta(hours=10))

        generer(company_a)

        gravites = list(Alerte.objects.filter(type=TypeAlerte.FATIGUE).order_by("id").values_list("gravite", flat=True))
        assert gravites == ["attention", "critique"]

    def test_une_pause_evite_l_alerte(self, api_client, company_a, trajet, equipe):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))
        pause(api_client, equipe["conducteur"], trajet, "debut")

        assert [a for a in generer(company_a) if a.type == TypeAlerte.FATIGUE] == []

    def test_sans_relais_libre_l_alerte_le_dit(self, company_a, trajet, equipe):  # noqa: F811
        equipe["relais"].delete()
        equipe["autre"].delete()
        partir_il_y_a(trajet, datetime.timedelta(hours=5))

        generer(company_a)

        assert "Aucun conducteur libre" in Alerte.objects.get(type=TypeAlerte.FATIGUE).message


@pytest.mark.django_db
class TestRelais:
    def test_le_conducteur_passe_le_trajet_au_relais(self, api_client, equipe, trajet):  # noqa: F811
        reponse = relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        assert reponse.status_code == 201 and reponse.data["lieu"] == "Yamoussoukro"
        trajet["feuille"].refresh_from_db()
        trajet["depart"].refresh_from_db()
        assert trajet["feuille"].chauffeur == equipe["relais"] and trajet["depart"].chauffeur == equipe["relais"]
        relais = Relais.objects.get()
        assert relais.ancien_chauffeur == equipe["conducteur"] and relais.nouveau_chauffeur == equipe["relais"]
        assert reponse.data["feuille_de_route"]["chauffeur"] == equipe["relais"].id

    def test_l_etat_du_vehicule_est_transmis(self, api_client, equipe, trajet, company_a):  # noqa: F811
        ChecklistDepart.objects.create(feuille_de_route=trajet["feuille"], company=company_a, item="carburant", etat="defaut")
        Incident.objects.create(
            feuille_de_route=trajet["feuille"], vehicule=trajet["vehicule"], chauffeur=equipe["conducteur"], company=company_a,
            type_incident="panne", description="Voyant moteur", gravite="faible",
        )

        etat = relayer(api_client, equipe["conducteur"], trajet, equipe["relais"]).data["etat_vehicule"]

        assert etat["immatriculation"] == "CI-9100-AA" and etat["statut"] == "en_ligne"
        assert etat["defauts_checklist"] == ["carburant"]
        assert [i["description"] for i in etat["incidents_ouverts"]] == ["Voyant moteur"]

    def test_le_lieu_et_l_heure_previennent_le_nouveau_conducteur_la_regulation_et_les_gares(self, api_client, equipe, trajet):  # noqa: F811
        relayer(api_client, equipe["conducteur"], trajet, equipe["relais"], lieu="Toumodi")

        for role in ("relais", "chef_ligne", "chef_gare"):
            visibles = [a for a in alertes_de(api_client, equipe[role]) if a["type"] == TypeAlerte.RELAIS]
            assert len(visibles) == 1, role
            assert "Toumodi" in visibles[0]["message"] and "conducteur_suivi → relais_suivi" in visibles[0]["message"]
        assert [a for a in alertes_de(api_client, equipe["guichetier"]) if a["type"] == TypeAlerte.RELAIS] == []

    def test_le_suivi_gps_continue_sur_le_nouveau_conducteur(self, api_client, equipe, trajet):  # noqa: F811
        envoyer(api_client, equipe["conducteur"], POSITION)
        relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        apres = envoyer(api_client, equipe["relais"], {"latitude": "6.9", "longitude": "-5.2"})
        ancien = envoyer(api_client, equipe["conducteur"], POSITION)

        assert apres.status_code == 201  # le relais envoie sa position sans rien réactiver
        assert ancien.status_code == 400  # l'ancien conducteur n'a plus de trajet en cours
        api_client.force_authenticate(user=equipe["chef_ligne"])
        voiture = api_client.get("/api/positions/dernieres/").data[0]
        assert voiture["chauffeur_nom"] == "relais_suivi" and str(voiture["latitude"]) == "6.900000"

    def test_la_fatigue_repart_de_zero_pour_le_nouveau_conducteur(self, api_client, equipe, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))
        relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        etat = fatigue(api_client, equipe["relais"], trajet).data

        assert etat["conduite_continue_minutes"] <= 1 and etat["alerte"] is False and etat["chauffeur"] == equipe["relais"].id

    def test_une_pause_ouverte_est_close_par_le_relais(self, api_client, equipe, trajet):  # noqa: F811
        pause(api_client, equipe["conducteur"], trajet, "debut")

        relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        assert not PausePrise.objects.filter(fin__isnull=True).exists()

    def test_apres_le_relais_l_ancien_conducteur_n_agit_plus_sur_le_trajet(self, api_client, equipe, trajet):  # noqa: F811
        relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        assert pause(api_client, equipe["conducteur"], trajet, "debut").status_code == 403
        assert fatigue(api_client, equipe["conducteur"], trajet).status_code == 403

    def test_la_regulation_peut_organiser_le_relais(self, api_client, equipe, trajet):  # noqa: F811
        assert relayer(api_client, equipe["chef_ligne"], trajet, equipe["relais"]).status_code == 201

    @pytest.mark.parametrize("role", ["guichetier", "qhse", "directeur_technique", "drh", "autre", "controleur_ligne"])
    def test_les_autres_postes_ne_font_pas_de_relais(self, api_client, equipe, trajet, role):  # noqa: F811
        assert relayer(api_client, equipe[role], trajet, equipe["relais"]).status_code == 403
        assert not Relais.objects.exists()

    def test_le_relais_doit_etre_un_conducteur(self, api_client, equipe, trajet):  # noqa: F811
        assert relayer(api_client, equipe["conducteur"], trajet, equipe["guichetier"]).status_code == 400

    def test_on_ne_se_relaie_pas_soi_meme(self, api_client, equipe, trajet):  # noqa: F811
        assert relayer(api_client, equipe["conducteur"], trajet, equipe["conducteur"]).status_code == 400

    def test_le_lieu_est_obligatoire(self, api_client, equipe, trajet):  # noqa: F811
        assert relayer(api_client, equipe["conducteur"], trajet, equipe["relais"], lieu=" ").status_code == 400

    def test_un_relais_est_designe_par_un_identifiant_valide(self, api_client, equipe, trajet):  # noqa: F811
        api_client.force_authenticate(user=equipe["conducteur"])

        reponse = api_client.post(f"/api/feuilles-de-route/{trajet['feuille'].id}/relais/", {"lieu": "Toumodi"}, format="json")

        assert reponse.status_code == 400

    def test_pas_de_relais_sur_un_trajet_pas_commence_ou_termine(self, api_client, equipe, trajet):  # noqa: F811
        trajet["feuille"].heure_arrivee_reelle = timezone.now()
        trajet["feuille"].save()

        assert relayer(api_client, equipe["chef_ligne"], trajet, equipe["relais"]).status_code == 400

    def test_un_conducteur_deja_en_route_ne_peut_pas_relayer(self, api_client, equipe, trajet):  # noqa: F811
        from billetterie.models import Depart, DepartStatut
        from personnel_roulant.models import FeuilleDeRoute

        maintenant = timezone.now() - datetime.timedelta(minutes=30)
        depart = Depart.objects.create(
            ligne=trajet["ligne"], vehicule=trajet["vehicule"], chauffeur=equipe["relais"], company=equipe["relais"].company,
            date_heure=maintenant, statut=DepartStatut.EN_COURS,
        )
        FeuilleDeRoute.objects.create(
            depart=depart, chauffeur=equipe["relais"], company=depart.company, heure_depart_prevue=maintenant, heure_depart_reelle=maintenant
        )

        reponse = relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        assert reponse.status_code == 400 and "déjà en route" in str(reponse.data)

    def test_on_ne_relaie_pas_vers_un_conducteur_d_une_autre_compagnie(self, api_client, equipe, trajet, company_b, user_factory):  # noqa: F811
        etranger = user_factory("relais_b", Role.CHAUFFEUR_RELAIS, company=company_b)

        assert relayer(api_client, equipe["conducteur"], trajet, etranger).status_code == 400

    def test_le_relais_est_trace(self, api_client, equipe, trajet):  # noqa: F811
        from audit.models import JournalAudit

        relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        assert JournalAudit.objects.filter(objet_type="personnel_roulant.relais", action="creation").exists()


@pytest.mark.django_db
class TestAnomalieDeCargaison:
    def signaler(self, api_client, utilisateur, trajet, description="Soute ouverte en route"):  # noqa: F811
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(
            f"/api/feuilles-de-route/{trajet['feuille'].id}/anomalie-cargaison/", {"description": description}, format="json"
        )

    def test_le_convoyeur_signale_une_anomalie_qui_alerte_la_direction_et_le_qhse(self, api_client, equipe, trajet):  # noqa: F811
        envoyer(api_client, equipe["conducteur"], {"latitude": "7.5", "longitude": "-5.1"})

        reponse = self.signaler(api_client, equipe["conducteur"], trajet)

        assert reponse.status_code == 201 and reponse.data["gravite"] == "grave"
        incident = Incident.objects.get()
        assert incident.type_incident == "cargaison" and str(incident.latitude) == "7.500000"
        for role in ("qhse", "directeur_exploitation", "chef_ligne", "chef_gare"):
            visibles = alertes_de(api_client, equipe[role])
            assert any(a["titre"].startswith("Incident grave : anomalie de cargaison") for a in visibles), role

    def test_le_controleur_peut_aussi_le_faire(self, api_client, equipe, trajet):  # noqa: F811
        assert self.signaler(api_client, equipe["controleur_ligne"], trajet).status_code == 201

    @pytest.mark.parametrize("role", ["guichetier", "qhse", "chef_ligne", "autre"])
    def test_les_autres_postes_ne_le_font_pas(self, api_client, equipe, trajet, role):  # noqa: F811
        assert self.signaler(api_client, equipe[role], trajet).status_code == 403

    def test_la_description_est_obligatoire(self, api_client, equipe, trajet):  # noqa: F811
        assert self.signaler(api_client, equipe["conducteur"], trajet, description="ok").status_code == 400


@pytest.mark.django_db
class TestMonTrajet:
    def moi(self, api_client, utilisateur):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get("/api/suivi/moi/")

    def test_le_conducteur_voit_son_trajet_et_sa_fatigue(self, api_client, equipe, trajet):  # noqa: F811
        donnees = self.moi(api_client, equipe["conducteur"]).data

        assert donnees["en_cours"] is True and donnees["ligne"] == "Adjamé-Bouaké"
        assert donnees["feuille_de_route"] == trajet["feuille"].id and donnees["fatigue"]["alerte"] is False
        assert "relais_suggeres" not in donnees["fatigue"]

    def test_l_alerte_propose_des_relais(self, api_client, equipe, trajet):  # noqa: F811
        partir_il_y_a(trajet, datetime.timedelta(hours=5))

        fatigue_moi = self.moi(api_client, equipe["conducteur"]).data["fatigue"]

        assert fatigue_moi["alerte"] is True and fatigue_moi["relais_suggeres"][0]["nom"] == "relais_suivi"

    @pytest.mark.parametrize("role", ["autre", "guichetier", "chef_ligne", "pdg"])
    def test_qui_ne_conduit_pas_n_a_pas_de_trajet(self, api_client, equipe, trajet, role):  # noqa: F811
        assert self.moi(api_client, equipe[role]).data == {"en_cours": False}

    def test_apres_le_relais_le_trajet_passe_au_nouveau_conducteur(self, api_client, equipe, trajet):  # noqa: F811
        relayer(api_client, equipe["conducteur"], trajet, equipe["relais"])

        assert self.moi(api_client, equipe["conducteur"]).data == {"en_cours": False}
        assert self.moi(api_client, equipe["relais"]).data["en_cours"] is True

    def test_refuse_sans_authentification(self, api_client):
        assert api_client.get("/api/suivi/moi/").status_code == 401
