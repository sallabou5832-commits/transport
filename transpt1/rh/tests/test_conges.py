"""Congés (cahier des charges : DRH — plannings et congés avec vue d'impact sur le personnel disponible avant validation)."""

import datetime

import pytest
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte
from billetterie.models import Depart, DepartStatut
from reseau.models import Gare, Ligne, Vehicule
from rh.models import DemandeConge
from rh.tests.conftest import jour


def _iso(valeur):
    return valeur if isinstance(valeur, str) else valeur.isoformat()


def demander(api_client, utilisateur, debut=None, fin=None, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(
        "/api/conges/", {"type": "annuel", "debut": _iso(debut or jour(10)), "fin": _iso(fin or jour(14)), "motif": "Repos", **corps}, format="json"
    )


def approuver(api_client, drh, demande_id, **corps):
    api_client.force_authenticate(user=drh)
    return api_client.post(f"/api/conges/{demande_id}/approuver/", corps, format="json")


def conge_approuve(api_client, equipe, agent, debut=None, fin=None):
    """Une demande de `agent`, déjà approuvée (en forçant : ce n'est pas l'objet du test)."""
    demande = demander(api_client, agent, debut, fin).data["id"]
    assert approuver(api_client, equipe["drh"], demande, forcer=True).status_code == 200
    return demande


def depart_de(company, chauffeur, jour_depart, heure=9):
    gare = Gare.objects.get_or_create(nom="Gare congés", ville="Abidjan", company=company)[0]
    ligne = Ligne.objects.get_or_create(nom="Ligne congés", gare_depart=gare, gare_arrivee=gare, company=company)[0]
    vehicule = Vehicule.objects.create(immatriculation=f"CI-CG-{Vehicule.objects.count()}", capacite=40, company=company)
    quand = timezone.make_aware(datetime.datetime.combine(jour_depart, datetime.time(heure, 0)))
    return Depart.objects.create(ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company, date_heure=quand, statut=DepartStatut.PLANIFIE)


@pytest.mark.django_db
class TestDemander:
    def test_un_agent_demande_pour_lui_meme(self, api_client, equipe):
        reponse = demander(api_client, equipe["guichetier"])

        assert reponse.status_code == 201
        assert (reponse.data["agent"], reponse.data["statut"], reponse.data["jours"]) == (equipe["guichetier"].id, "en_attente", 5)

    def test_un_agent_ne_demande_pas_pour_un_autre(self, api_client, equipe):
        reponse = demander(api_client, equipe["guichetier"], agent=equipe["bagagiste"].id)

        assert reponse.data["agent"] == equipe["guichetier"].id  # le champ est ignoré : la demande est la sienne

    def test_le_drh_saisit_une_demande_pour_un_agent(self, api_client, equipe):
        reponse = demander(api_client, equipe["drh"], agent=equipe["bagagiste"].id)

        assert reponse.status_code == 201 and reponse.data["agent"] == equipe["bagagiste"].id

    @pytest.mark.parametrize("poste", ["guichetier", "chauffeur_principal", "pdg", "qhse", "responsable_juridique", "mecanicien", "drh"])
    def test_tout_poste_de_la_compagnie_peut_demander(self, api_client, equipe, poste):
        assert demander(api_client, equipe[poste]).status_code == 201

    def test_le_superadmin_n_a_pas_de_compagnie(self, api_client, superadmin_user):
        assert demander(api_client, superadmin_user).status_code == 403

    def test_la_fin_ne_precede_pas_le_debut(self, api_client, equipe):
        assert demander(api_client, equipe["guichetier"], jour(10), jour(8)).status_code == 400

    def test_une_demande_de_plus_de_soixante_jours_est_refusee(self, api_client, equipe):
        assert demander(api_client, equipe["guichetier"], jour(10), jour(70)).status_code == 400
        assert demander(api_client, equipe["guichetier"], jour(10), jour(69)).status_code == 201  # 60 jours pile

    def test_un_conge_ne_se_demande_pas_dans_le_passe_sauf_une_maladie(self, api_client, equipe):
        assert demander(api_client, equipe["guichetier"], jour(-3), jour(2)).status_code == 400
        assert demander(api_client, equipe["guichetier"], jour(-3), jour(2), type="maladie").status_code == 201

    def test_deux_demandes_ne_se_chevauchent_pas(self, api_client, equipe):
        demander(api_client, equipe["guichetier"], jour(10), jour(14))

        assert demander(api_client, equipe["guichetier"], jour(14), jour(18)).status_code == 400
        assert demander(api_client, equipe["guichetier"], jour(15), jour(18)).status_code == 201
        assert demander(api_client, equipe["bagagiste"], jour(10), jour(14)).status_code == 201  # un autre agent, sans souci

    def test_une_demande_refusee_ou_annulee_ne_bloque_plus_ces_dates(self, api_client, equipe):
        premiere = demander(api_client, equipe["guichetier"], jour(10), jour(14)).data["id"]
        api_client.force_authenticate(user=equipe["guichetier"])
        api_client.post(f"/api/conges/{premiere}/annuler/")

        assert demander(api_client, equipe["guichetier"], jour(10), jour(14)).status_code == 201

    @pytest.mark.parametrize("corps", [{"type": "vacances"}, {"debut": "demain"}])
    def test_les_champs_invalides_sont_refuses(self, api_client, equipe, corps):
        assert demander(api_client, equipe["guichetier"], **corps).status_code == 400

    def test_le_drh_est_prevenu_de_la_demande(self, api_client, equipe):
        demander(api_client, equipe["guichetier"])

        (alerte,) = Alerte.objects.filter(type=TypeAlerte.CONGE)
        assert alerte.titre == "Demande de congé : guichetier_rh" and alerte.roles_destinataires == ["drh"]

    def test_les_dossiers_de_conge_sont_immuables_par_l_api(self, api_client, equipe):
        cree = demander(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe["drh"])
        assert api_client.patch(f"/api/conges/{cree}/", {"statut": "approuve"}, format="json").status_code == 405
        assert api_client.delete(f"/api/conges/{cree}/").status_code == 405


@pytest.mark.django_db
class TestVisibilite:
    def test_chacun_voit_les_siennes_et_l_echelon_celles_de_ses_postes(self, api_client, equipe):
        demander(api_client, equipe["chauffeur_principal"])
        demander(api_client, equipe["guichetier"])

        def agents(poste):
            api_client.force_authenticate(user=equipe[poste])
            return {d["agent"] for d in api_client.get("/api/conges/").data}

        assert agents("guichetier") == {equipe["guichetier"].id}
        assert agents("chef_gare") == {equipe["guichetier"].id}
        assert agents("chef_ligne") == {equipe["chauffeur_principal"].id}
        assert agents("bagagiste") == set()
        assert agents("drh") == agents("pdg") == {equipe["guichetier"].id, equipe["chauffeur_principal"].id}

    def test_le_filtre_par_statut(self, api_client, equipe):
        demande = demander(api_client, equipe["guichetier"]).data["id"]
        demander(api_client, equipe["bagagiste"])
        approuver(api_client, equipe["drh"], demande, forcer=True)

        assert len(api_client.get("/api/conges/", {"statut": "approuve"}).data) == 1
        assert len(api_client.get("/api/conges/", {"statut": "en_attente"}).data) == 1

    def test_isolation_entre_compagnies(self, api_client, equipe, user_factory, company_b):
        demande = demander(api_client, equipe["guichetier"]).data["id"]
        drh_b = user_factory("drh_b_conge", "drh", company=company_b)

        api_client.force_authenticate(user=drh_b)
        assert api_client.get("/api/conges/").data == []
        assert api_client.get(f"/api/conges/{demande}/impact/").status_code == 404
        assert api_client.post(f"/api/conges/{demande}/approuver/", {}, format="json").status_code == 404


@pytest.mark.django_db
class TestImpact:
    def impact(self, api_client, utilisateur, demande_id):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get(f"/api/conges/{demande_id}/impact/")

    def test_un_poste_bien_pourvu_ne_risque_rien(self, api_client, equipe, user_factory, company_a):
        for i in range(3):
            user_factory(f"guichetier_extra_{i}", "guichetier", company=company_a)
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        donnees = self.impact(api_client, equipe["drh"], demande).data

        assert donnees["effectif"] == 4 and donnees["niveau"] == "ok" and len(donnees["jours"]) == 5
        assert {j["disponibles_apres"] for j in donnees["jours"]} == {3}
        assert donnees["collegues_en_conge"] == [] and donnees["departs_a_reaffecter"] == []

    def test_les_collegues_deja_en_conge_rendent_l_equipe_tendue(self, api_client, equipe, user_factory, company_a):
        autres = [user_factory(f"guichetier_extra_{i}", "guichetier", company=company_a) for i in range(2)]
        conge_approuve(api_client, equipe, autres[0], jour(11), jour(12))  # 3 guichetiers, un déjà absent deux jours
        demande = demander(api_client, equipe["guichetier"], jour(10), jour(13)).data["id"]

        donnees = self.impact(api_client, equipe["drh"], demande).data

        # effectif 3 : jour 10 -> 2 restent (ok), jours 11-12 -> 1 reste sur 3 (moins de la moitié : tendu), jour 13 -> 2 (ok)
        assert [j["niveau"] for j in donnees["jours"]] == ["ok", "tendu", "tendu", "ok"]
        assert donnees["niveau"] == "tendu" and donnees["jours_tendus"] == 2
        assert [c["agent_nom"] for c in donnees["collegues_en_conge"]] == ["guichetier_extra_0"]

    def test_plus_personne_c_est_critique(self, api_client, equipe, user_factory, company_a):
        autre = user_factory("guichetier_autre", "guichetier", company=company_a)  # deux guichetiers en tout
        conge_approuve(api_client, equipe, autre, jour(10), jour(14))
        demande = demander(api_client, equipe["guichetier"], jour(12), jour(13)).data["id"]

        donnees = self.impact(api_client, equipe["drh"], demande).data

        assert donnees["niveau"] == "critique" and donnees["jours_critiques"] == 2
        assert {j["disponibles_apres"] for j in donnees["jours"]} == {0}

    def test_pour_un_conducteur_on_compare_aux_departs_du_jour(self, api_client, equipe, company_a):
        # Deux conducteurs en tout (principal + relais) : si le principal part, il en reste un.
        depart_de(company_a, equipe["chauffeur_relais"], jour(10))
        depart_de(company_a, equipe["chauffeur_relais"], jour(11))
        depart_de(company_a, equipe["chauffeur_relais"], jour(11), heure=15)
        demande = demander(api_client, equipe["chauffeur_principal"], jour(10), jour(12)).data["id"]

        donnees = self.impact(api_client, equipe["drh"], demande).data

        assert [(j["besoin"], j["disponibles_apres"], j["niveau"]) for j in donnees["jours"]] == [(1, 1, "tendu"), (2, 1, "critique"), (0, 1, "ok")]
        assert donnees["niveau"] == "critique"

    def test_les_departs_deja_confies_au_demandeur_sont_signales(self, api_client, equipe, company_a):
        depart = depart_de(company_a, equipe["chauffeur_principal"], jour(11))
        depart_de(company_a, equipe["chauffeur_principal"], jour(30))  # hors des dates du congé
        demande = demander(api_client, equipe["chauffeur_principal"], jour(10), jour(12)).data["id"]

        donnees = self.impact(api_client, equipe["drh"], demande).data

        assert [d["id"] for d in donnees["departs_a_reaffecter"]] == [depart.id]

    def test_un_depart_termine_ne_compte_pas(self, api_client, equipe, company_a):
        depart = depart_de(company_a, equipe["chauffeur_principal"], jour(11))
        Depart.objects.filter(pk=depart.pk).update(statut=DepartStatut.TERMINE)
        demande = demander(api_client, equipe["chauffeur_principal"], jour(10), jour(12)).data["id"]

        donnees = self.impact(api_client, equipe["drh"], demande).data

        assert donnees["departs_a_reaffecter"] == [] and {j["besoin"] for j in donnees["jours"]} == {0}

    def test_la_demande_elle_meme_n_est_pas_comptee_comme_un_collegue_absent(self, api_client, equipe, user_factory, company_a):
        user_factory("guichetier_extra", "guichetier", company=company_a)
        demande = conge_approuve(api_client, equipe, equipe["guichetier"], jour(10), jour(12))

        donnees = self.impact(api_client, equipe["drh"], demande).data

        assert donnees["collegues_en_conge"] == [] and donnees["niveau"] == "ok"

    def test_le_drh_et_le_pdg_seuls_voient_l_impact(self, api_client, equipe):
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        assert self.impact(api_client, equipe["drh"], demande).status_code == 200
        assert self.impact(api_client, equipe["pdg"], demande).status_code == 200
        for poste in ("chef_gare", "guichetier", "chef_ligne", "qhse"):
            assert self.impact(api_client, equipe[poste], demande).status_code == 403, poste


@pytest.mark.django_db
class TestDecision:
    def test_le_drh_approuve_et_l_agent_est_prevenu(self, api_client, equipe, user_factory, company_a):
        for i in range(3):
            user_factory(f"guichetier_extra_{i}", "guichetier", company=company_a)
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        reponse = approuver(api_client, equipe["drh"], demande, motif="Bon repos")

        assert reponse.status_code == 200 and reponse.data["statut"] == "approuve" and reponse.data["decide_par_nom"] == "drh_rh"
        alerte = Alerte.objects.filter(type=TypeAlerte.CONGE, titre__startswith="Congé approuvé").get()
        assert list(alerte.destinataires.all()) == [equipe["guichetier"]] and alerte.message == "Bon repos"

    def test_un_impact_critique_demande_confirmation(self, api_client, equipe, user_factory, company_a):
        autre = user_factory("guichetier_autre", "guichetier", company=company_a)
        conge_approuve(api_client, equipe, autre, jour(10), jour(14))
        demande = demander(api_client, equipe["guichetier"], jour(12), jour(13)).data["id"]

        refus = approuver(api_client, equipe["drh"], demande)
        assert refus.status_code == 409 and "Impact critique" in refus.data["detail"]
        assert DemandeConge.objects.get(pk=demande).statut == "en_attente"

        confirme = approuver(api_client, equipe["drh"], demande, forcer=True)
        assert confirme.status_code == 200 and confirme.data["statut"] == "approuve"

    def test_des_departs_a_reaffecter_demandent_confirmation_et_alertent_l_exploitation(self, api_client, equipe, company_a, user_factory):
        user_factory("chauffeur_extra_1", "chauffeur_principal", company=company_a)
        user_factory("chauffeur_extra_2", "chauffeur_principal", company=company_a)
        depart_de(company_a, equipe["chauffeur_principal"], jour(11))
        demande = demander(api_client, equipe["chauffeur_principal"], jour(10), jour(12)).data["id"]

        refus = approuver(api_client, equipe["drh"], demande)
        assert refus.status_code == 409 and "réaffectés" in refus.data["detail"]

        assert approuver(api_client, equipe["drh"], demande, forcer=True).status_code == 200
        alerte = Alerte.objects.get(titre="Départs à réaffecter : chauffeur_principal_rh en congé")
        assert set(alerte.roles_destinataires) == {"directeur_exploitation", "chef_ligne"} and alerte.gravite == "attention"

    def test_le_drh_refuse_en_donnant_un_motif(self, api_client, equipe):
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe["drh"])
        assert api_client.post(f"/api/conges/{demande}/refuser/", {}, format="json").status_code == 400
        reponse = api_client.post(f"/api/conges/{demande}/refuser/", {"motif": "Période de pointe"}, format="json")

        assert reponse.status_code == 200 and reponse.data["statut"] == "refuse" and reponse.data["motif_decision"] == "Période de pointe"
        assert Alerte.objects.filter(type=TypeAlerte.CONGE, titre__startswith="Congé refusé").get().destinataires.get() == equipe["guichetier"]

    def test_une_decision_ne_se_prend_qu_une_fois(self, api_client, equipe):
        demande = demander(api_client, equipe["guichetier"]).data["id"]
        approuver(api_client, equipe["drh"], demande, forcer=True)

        assert approuver(api_client, equipe["drh"], demande, forcer=True).status_code == 400
        api_client.force_authenticate(user=equipe["drh"])
        assert api_client.post(f"/api/conges/{demande}/refuser/", {"motif": "Trop tard"}, format="json").status_code == 400

    @pytest.mark.parametrize("poste", ["pdg", "chef_gare", "qhse", "guichetier"])
    def test_seul_le_drh_decide(self, api_client, equipe, poste):
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe[poste])
        assert api_client.post(f"/api/conges/{demande}/approuver/", {"forcer": True}, format="json").status_code in (403, 404)
        assert api_client.post(f"/api/conges/{demande}/refuser/", {"motif": "Non"}, format="json").status_code in (403, 404)
        assert DemandeConge.objects.get(pk=demande).statut == "en_attente"


@pytest.mark.django_db
class TestAnnulation:
    def annuler(self, api_client, utilisateur, demande):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(f"/api/conges/{demande}/annuler/")

    def test_l_agent_retire_sa_demande(self, api_client, equipe):
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        assert self.annuler(api_client, equipe["guichetier"], demande).data["statut"] == "annule"

    def test_l_agent_annule_un_conge_approuve_a_venir(self, api_client, equipe):
        demande = conge_approuve(api_client, equipe, equipe["guichetier"])

        assert self.annuler(api_client, equipe["guichetier"], demande).data["statut"] == "annule"

    def test_le_drh_peut_annuler_pour_l_agent(self, api_client, equipe):
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        assert self.annuler(api_client, equipe["drh"], demande).status_code == 200

    def test_un_autre_agent_ne_peut_pas(self, api_client, equipe):
        demande = demander(api_client, equipe["guichetier"]).data["id"]

        assert self.annuler(api_client, equipe["bagagiste"], demande).status_code == 404  # il ne la voit même pas
        assert self.annuler(api_client, equipe["chef_gare"], demande).status_code == 403  # il la voit (son équipe) mais n'en décide pas

    def test_un_conge_termine_ou_deja_refuse_ne_s_annule_plus(self, api_client, equipe):
        passe = demander(api_client, equipe["guichetier"], jour(-5), jour(-2), type="maladie").data["id"]
        refusee = demander(api_client, equipe["bagagiste"]).data["id"]
        api_client.force_authenticate(user=equipe["drh"])
        api_client.post(f"/api/conges/{refusee}/refuser/", {"motif": "Non"}, format="json")

        assert self.annuler(api_client, equipe["guichetier"], passe).status_code == 400
        assert self.annuler(api_client, equipe["bagagiste"], refusee).status_code == 400


@pytest.mark.django_db
class TestPlanification:
    """Un congé approuvé rend le conducteur indisponible pour les départs."""

    def planifier(self, api_client, chef, ligne, vehicule, chauffeur, quand):
        api_client.force_authenticate(user=chef)
        return api_client.post(
            "/api/departs/planifier/",
            {"ligne": ligne.id, "vehicule": vehicule.id, "chauffeur": chauffeur.id, "date_heure": quand.isoformat()},
            format="json",
        )

    def quand(self, decalage, heure=9):
        return timezone.make_aware(datetime.datetime.combine(jour(decalage), datetime.time(heure, 0)))

    def test_un_conducteur_en_conge_ne_se_planifie_pas(self, api_client, equipe, ligne_a, company_a):
        conge_approuve(api_client, equipe, equipe["chauffeur_principal"], jour(10), jour(12))
        bus = Vehicule.objects.create(immatriculation="CI-PLAN-CG1", capacite=40, company=company_a)

        reponse = self.planifier(api_client, equipe["chef_ligne"], ligne_a, bus, equipe["chauffeur_principal"], self.quand(11))

        assert reponse.status_code == 400 and "en congé" in str(reponse.data["chauffeur"])

    def test_la_veille_et_le_lendemain_du_conge_il_se_planifie(self, api_client, equipe, ligne_a, company_a):
        conge_approuve(api_client, equipe, equipe["chauffeur_principal"], jour(10), jour(12))
        bus = Vehicule.objects.create(immatriculation="CI-PLAN-CG2", capacite=40, company=company_a)
        bus2 = Vehicule.objects.create(immatriculation="CI-PLAN-CG3", capacite=40, company=company_a)

        assert self.planifier(api_client, equipe["chef_ligne"], ligne_a, bus, equipe["chauffeur_principal"], self.quand(9)).status_code == 201
        assert self.planifier(api_client, equipe["chef_ligne"], ligne_a, bus2, equipe["chauffeur_principal"], self.quand(13)).status_code == 201

    def test_une_demande_en_attente_ou_refusee_ne_bloque_rien(self, api_client, equipe, ligne_a, company_a):
        demander(api_client, equipe["chauffeur_principal"], jour(10), jour(12))
        bus = Vehicule.objects.create(immatriculation="CI-PLAN-CG4", capacite=40, company=company_a)

        assert self.planifier(api_client, equipe["chef_ligne"], ligne_a, bus, equipe["chauffeur_principal"], self.quand(11)).status_code == 201

    def test_les_remplacants_proposes_excluent_les_conducteurs_en_conge(self, api_client, equipe, ligne_a, company_a):
        depart = depart_de(company_a, equipe["chauffeur_principal"], jour(11))
        conge_approuve(api_client, equipe, equipe["chauffeur_relais"], jour(10), jour(12))

        api_client.force_authenticate(user=equipe["chef_ligne"])
        remplacants = api_client.get(f"/api/departs/{depart.id}/remplacants-possibles/").data

        assert remplacants["chauffeurs"] == []  # le seul autre conducteur est en congé

    def test_un_conducteur_libre_est_propose_hors_de_ses_dates_de_conge(self, api_client, equipe, company_a):
        depart = depart_de(company_a, equipe["chauffeur_principal"], jour(20))
        conge_approuve(api_client, equipe, equipe["chauffeur_relais"], jour(10), jour(12))

        api_client.force_authenticate(user=equipe["chef_ligne"])
        remplacants = api_client.get(f"/api/departs/{depart.id}/remplacants-possibles/").data

        assert [c["id"] for c in remplacants["chauffeurs"]] == [equipe["chauffeur_relais"].id]
