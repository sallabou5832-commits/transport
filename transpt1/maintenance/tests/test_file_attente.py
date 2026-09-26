"""La file d'attente de l'atelier (cahier des charges : Directeur technique — « file d'attente des réparations classée par urgence,
validée ou réordonnée par le directeur technique », « délai estimé, remonté au régulateur »), la répartition des interventions et
la vue de charge (Chef d'atelier)."""

import datetime

import pytest
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte
from core.models import Role
from maintenance.models import OrdreReparation, StatutOrdreReparation, UrgenceReparation
from reseau.models import Vehicule

FILE = "/api/ordres-reparation/file-attente/"


@pytest.fixture
def ordres(db, company_a, vehicule_a, mecanicien_a):
    """Dans l'ordre d'arrivée : une normale, une haute, une normale, une critique, et un ordre terminé (hors file)."""

    def ouvrir(description, urgence, statut=StatutOrdreReparation.OUVERT, **plus):
        return OrdreReparation.objects.create(
            vehicule=vehicule_a, company=company_a, description=description, mecanicien=mecanicien_a, urgence=urgence,
            statut=statut, **plus,
        )

    return {
        "normale1": ouvrir("Normale 1", UrgenceReparation.NORMALE),
        "haute": ouvrir("Haute", UrgenceReparation.HAUTE, delai_estime_heures=6),
        "normale2": ouvrir("Normale 2", UrgenceReparation.NORMALE, statut=StatutOrdreReparation.EN_COURS),
        "critique": ouvrir("Critique", UrgenceReparation.CRITIQUE, delai_estime_heures=2),
        "termine": ouvrir("Terminé", UrgenceReparation.CRITIQUE, statut=StatutOrdreReparation.TERMINE),
    }


def descriptions(reponse):
    return [ordre["description"] for ordre in reponse.data]


@pytest.mark.django_db
class TestLaFile:
    def test_elle_est_classee_par_urgence_puis_par_anciennete(self, api_client, ordres, directeur_technique_a):
        api_client.force_authenticate(user=directeur_technique_a)

        reponse = api_client.get(FILE)

        assert reponse.status_code == 200
        assert descriptions(reponse) == ["Critique", "Haute", "Normale 1", "Normale 2"]

    def test_un_ordre_termine_n_y_figure_pas(self, api_client, ordres, directeur_technique_a):
        api_client.force_authenticate(user=directeur_technique_a)

        assert "Terminé" not in descriptions(api_client.get(FILE))

    def test_chaque_ordre_porte_son_retour_estime_pour_la_regulation(self, api_client, ordres, user_factory, company_a):
        chef_ligne = user_factory("chef_ligne_file", Role.CHEF_LIGNE, company=company_a)
        api_client.force_authenticate(user=chef_ligne)

        par_description = {o["description"]: o for o in api_client.get(FILE).data}

        haute = ordres["haute"]
        assert par_description["Haute"]["vehicule_immatriculation"] == "CI-3000-AA"
        assert par_description["Haute"]["delai_estime_heures"] == 6
        assert par_description["Haute"]["retour_estime"] is not None
        attendu = haute.date_creation + datetime.timedelta(hours=6)
        assert abs((haute.retour_estime - attendu).total_seconds()) < 1
        assert par_description["Normale 1"]["retour_estime"] is None, "sans estimation, pas de retour annoncé"

    def test_une_autre_compagnie_ne_voit_pas_la_file(self, api_client, ordres, user_factory, company_b):
        etranger = user_factory("guichetier_file_b", Role.GUICHETIER, company=company_b)
        api_client.force_authenticate(user=etranger)

        assert api_client.get(FILE).data == []

    def test_le_superadmin_sans_compagnie_n_a_rien_a_y_voir(self, api_client, ordres, superadmin_user):
        api_client.force_authenticate(user=superadmin_user)

        assert api_client.get(FILE).data == []

    def test_sans_authentification_rien(self, api_client):
        assert api_client.get(FILE).status_code == 401


@pytest.mark.django_db
class TestReordonner:
    def reordonner(self, api_client, utilisateur, liste):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post("/api/ordres-reparation/reordonner/", {"ordres": liste}, format="json")

    @pytest.mark.parametrize("role", ["directeur_technique_a", "chef_atelier_a"])
    def test_le_directeur_technique_et_le_chef_d_atelier_reordonnent(self, api_client, ordres, request, role):
        utilisateur = request.getfixturevalue(role)

        reponse = self.reordonner(api_client, utilisateur, [ordres["normale2"].id, ordres["normale1"].id])

        assert reponse.status_code == 200
        assert descriptions(reponse) == ["Critique", "Haute", "Normale 2", "Normale 1"]
        ordres["normale2"].refresh_from_db()
        assert ordres["normale2"].position == 1

    def test_l_urgence_prime_toujours_sur_la_position(self, api_client, ordres, directeur_technique_a):
        reponse = self.reordonner(api_client, directeur_technique_a, [ordres["normale1"].id, ordres["critique"].id])

        assert descriptions(reponse)[0] == "Critique", "pour passer devant, on élève l'urgence"

    def test_une_position_posee_passe_avant_l_anciennete(self, api_client, ordres, directeur_technique_a):
        self.reordonner(api_client, directeur_technique_a, [ordres["normale2"].id])

        assert descriptions(api_client.get(FILE)) == ["Critique", "Haute", "Normale 2", "Normale 1"]

    @pytest.mark.parametrize("corps", [[], "abc", None, [1.5], [True], ["1"], [99999]])
    def test_une_liste_invalide_est_refusee(self, api_client, ordres, directeur_technique_a, corps):
        assert self.reordonner(api_client, directeur_technique_a, corps).status_code == 400

    def test_un_ordre_n_est_cite_qu_une_fois(self, api_client, ordres, directeur_technique_a):
        reponse = self.reordonner(api_client, directeur_technique_a, [ordres["haute"].id, ordres["haute"].id])

        assert reponse.status_code == 400 and "qu'une fois" in str(reponse.data)

    def test_un_ordre_termine_ne_se_reordonne_pas(self, api_client, ordres, directeur_technique_a):
        reponse = self.reordonner(api_client, directeur_technique_a, [ordres["termine"].id])

        assert reponse.status_code == 400 and "déjà terminé" in str(reponse.data)

    def test_l_ordre_d_une_autre_compagnie_est_introuvable(self, api_client, ordres, user_factory, company_b):
        pdg_technique_b = user_factory("dt_file_b", Role.DIRECTEUR_TECHNIQUE, company=company_b)

        reponse = self.reordonner(api_client, pdg_technique_b, [ordres["haute"].id])

        assert reponse.status_code == 400
        ordres["haute"].refresh_from_db()
        assert ordres["haute"].position == 0

    @pytest.mark.parametrize("role", ["mecanicien_a", "magasinier_a"])
    def test_les_autres_postes_ne_reordonnent_pas(self, api_client, ordres, request, role):
        assert self.reordonner(api_client, request.getfixturevalue(role), [ordres["haute"].id]).status_code == 403


@pytest.mark.django_db
class TestPrioriser:
    def prioriser(self, api_client, utilisateur, ordre, **corps):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(f"/api/ordres-reparation/{ordre.id}/prioriser/", corps, format="json")

    @pytest.mark.parametrize("role", ["directeur_technique_a", "chef_atelier_a"])
    def test_le_technique_fixe_l_urgence_et_le_delai(self, api_client, ordres, request, role):
        reponse = self.prioriser(api_client, request.getfixturevalue(role), ordres["normale1"], urgence="haute", delai_estime_heures=8)

        assert reponse.status_code == 200
        assert reponse.data["urgence"] == "haute" and reponse.data["delai_estime_heures"] == 8
        ordres["normale1"].refresh_from_db()
        assert ordres["normale1"].urgence == UrgenceReparation.HAUTE and ordres["normale1"].delai_estime_heures == 8

    def test_on_peut_ne_changer_que_le_delai(self, api_client, ordres, directeur_technique_a):
        reponse = self.prioriser(api_client, directeur_technique_a, ordres["haute"], delai_estime_heures="12")

        assert reponse.status_code == 200 and reponse.data["urgence"] == "haute" and reponse.data["delai_estime_heures"] == 12

    def test_une_urgence_critique_previent_l_atelier_et_la_regulation(self, api_client, ordres, directeur_technique_a, mecanicien_a):
        self.prioriser(api_client, directeur_technique_a, ordres["normale1"], urgence="critique")

        alerte = Alerte.objects.get(type=TypeAlerte.ORDRE_REPARATION, titre__startswith="Réparation critique")
        assert set(alerte.roles_destinataires) == {Role.CHEF_ATELIER, Role.CHEF_LIGNE}
        assert list(alerte.destinataires.all()) == [mecanicien_a]

    def test_un_ordre_deja_critique_ne_reprevient_pas(self, api_client, ordres, directeur_technique_a):
        self.prioriser(api_client, directeur_technique_a, ordres["critique"], urgence="critique", delai_estime_heures=3)

        assert not Alerte.objects.filter(titre__startswith="Réparation critique").exists()

    @pytest.mark.parametrize("corps", [{}, {"urgence": "urgentissime"}, {"delai_estime_heures": 0}, {"delai_estime_heures": "beaucoup"}])
    def test_les_valeurs_invalides_sont_refusees(self, api_client, ordres, directeur_technique_a, corps):
        assert self.prioriser(api_client, directeur_technique_a, ordres["haute"], **corps).status_code == 400

    def test_un_ordre_termine_ne_se_reclasse_pas(self, api_client, ordres, directeur_technique_a):
        assert self.prioriser(api_client, directeur_technique_a, ordres["termine"], urgence="basse").status_code == 400

    def test_le_mecanicien_ne_se_reclasse_pas_lui_meme(self, api_client, ordres, mecanicien_a):
        assert self.prioriser(api_client, mecanicien_a, ordres["haute"], urgence="basse").status_code == 403

        api_client.force_authenticate(user=mecanicien_a)
        api_client.patch(f"/api/ordres-reparation/{ordres['haute'].id}/", {"urgence": "basse", "delai_estime_heures": 1}, format="json")
        ordres["haute"].refresh_from_db()
        assert ordres["haute"].urgence == UrgenceReparation.HAUTE and ordres["haute"].delai_estime_heures == 6

    def test_a_l_ouverture_de_l_ordre_l_urgence_et_le_delai_se_fixent(self, api_client, chef_atelier_a, vehicule_a, mecanicien_a):
        api_client.force_authenticate(user=chef_atelier_a)

        reponse = api_client.post(
            "/api/ordres-reparation/",
            {"vehicule": vehicule_a.id, "description": "Freins", "mecanicien": mecanicien_a.id, "urgence": "critique", "delai_estime_heures": 4},
            format="json",
        )

        assert reponse.status_code == 201
        assert reponse.data["urgence"] == "critique" and reponse.data["delai_estime_heures"] == 4 and reponse.data["position"] == 0

    def test_la_position_ne_se_choisit_pas_a_l_ouverture(self, api_client, chef_atelier_a, vehicule_a, mecanicien_a):
        api_client.force_authenticate(user=chef_atelier_a)

        reponse = api_client.post(
            "/api/ordres-reparation/",
            {"vehicule": vehicule_a.id, "description": "Freins", "mecanicien": mecanicien_a.id, "position": 1},
            format="json",
        )

        assert reponse.status_code == 201 and reponse.data["position"] == 0

    def test_le_mecanicien_est_prevenu_de_son_nouvel_ordre(self, api_client, chef_atelier_a, vehicule_a, mecanicien_a):
        api_client.force_authenticate(user=chef_atelier_a)
        api_client.post(
            "/api/ordres-reparation/", {"vehicule": vehicule_a.id, "description": "Freins", "mecanicien": mecanicien_a.id}, format="json"
        )

        alerte = Alerte.objects.get(type=TypeAlerte.ORDRE_REPARATION)
        assert list(alerte.destinataires.all()) == [mecanicien_a] and "CI-3000-AA" in alerte.titre


@pytest.mark.django_db
class TestRepartitionEtCharge:
    def reaffecter(self, api_client, utilisateur, ordre, mecanicien):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(f"/api/ordres-reparation/{ordre.id}/reaffecter/", {"mecanicien": mecanicien}, format="json")

    def test_la_charge_compte_les_ordres_et_les_heures_de_chacun(
        self, api_client, ordres, chef_atelier_a, mecanicien_a, mecanicien_a2
    ):
        api_client.force_authenticate(user=chef_atelier_a)

        charge = {c["nom"]: c for c in api_client.get("/api/maintenance/charge-mecaniciens/").data}

        assert charge["mecanicien_a"]["ordres_ouverts"] == 3 and charge["mecanicien_a"]["ordres_en_cours"] == 1
        assert charge["mecanicien_a"]["heures_estimees"] == 8
        assert charge["mecanicien_a2"]["ordres_ouverts"] == 0 and charge["mecanicien_a2"]["heures_estimees"] == 0

    def test_le_moins_charge_est_suggere_et_le_mecanicien_passe_avant_le_chef(
        self, api_client, ordres, chef_atelier_a, mecanicien_a, mecanicien_a2
    ):
        api_client.force_authenticate(user=chef_atelier_a)

        lignes = api_client.get("/api/maintenance/charge-mecaniciens/").data

        assert [c["nom"] for c in lignes] == ["mecanicien_a2", "mecanicien_a", "chef_atelier_a"]
        assert [c["suggere"] for c in lignes] == [True, False, False]

    def test_les_ordres_termines_les_derniers_jours_sont_comptes_a_part(self, api_client, ordres, chef_atelier_a):
        OrdreReparation.objects.filter(pk=ordres["termine"].pk).update(date_cloture=timezone.now())
        api_client.force_authenticate(user=chef_atelier_a)

        charge = {c["nom"]: c for c in api_client.get("/api/maintenance/charge-mecaniciens/").data}

        assert charge["mecanicien_a"]["cloturees_7_jours"] == 1

    @pytest.mark.parametrize("role", ["directeur_technique_a", "chef_atelier_a"])
    def test_le_technique_voit_la_charge(self, api_client, request, role):
        api_client.force_authenticate(user=request.getfixturevalue(role))

        assert api_client.get("/api/maintenance/charge-mecaniciens/").status_code == 200

    @pytest.mark.parametrize("role", ["mecanicien_a", "magasinier_a"])
    def test_les_autres_postes_ne_voient_pas_la_charge(self, api_client, request, role):
        api_client.force_authenticate(user=request.getfixturevalue(role))

        assert api_client.get("/api/maintenance/charge-mecaniciens/").status_code == 403

    @pytest.mark.parametrize("role", ["directeur_technique_a", "chef_atelier_a"])
    def test_le_technique_confie_l_ordre_a_un_autre_mecanicien(self, api_client, ordres, request, role, mecanicien_a, mecanicien_a2):
        reponse = self.reaffecter(api_client, request.getfixturevalue(role), ordres["haute"], mecanicien_a2.id)

        assert reponse.status_code == 200 and reponse.data["mecanicien"] == mecanicien_a2.id
        ordres["haute"].refresh_from_db()
        assert ordres["haute"].mecanicien == mecanicien_a2

    def test_le_nouvel_et_l_ancien_intervenant_sont_prevenus(self, api_client, ordres, chef_atelier_a, mecanicien_a, mecanicien_a2):
        self.reaffecter(api_client, chef_atelier_a, ordres["haute"], mecanicien_a2.id)

        alerte = Alerte.objects.get(titre__startswith="Ordre de réparation confié")
        assert set(alerte.destinataires.all()) == {mecanicien_a, mecanicien_a2}

    def test_on_ne_confie_pas_un_ordre_a_un_non_intervenant_ni_a_un_etranger(
        self, api_client, ordres, chef_atelier_a, magasinier_a, user_factory, company_b
    ):
        etranger = user_factory("mecanicien_b_file", Role.MECANICIEN, company=company_b)

        assert self.reaffecter(api_client, chef_atelier_a, ordres["haute"], magasinier_a.id).status_code == 400
        assert self.reaffecter(api_client, chef_atelier_a, ordres["haute"], etranger.id).status_code == 400
        assert self.reaffecter(api_client, chef_atelier_a, ordres["haute"], "abc").status_code == 400

    def test_confier_a_celui_qui_l_a_deja_est_refuse(self, api_client, ordres, chef_atelier_a, mecanicien_a):
        assert self.reaffecter(api_client, chef_atelier_a, ordres["haute"], mecanicien_a.id).status_code == 400

    def test_un_ordre_termine_ne_se_reaffecte_pas(self, api_client, ordres, chef_atelier_a, mecanicien_a2):
        assert self.reaffecter(api_client, chef_atelier_a, ordres["termine"], mecanicien_a2.id).status_code == 400

    @pytest.mark.parametrize("role", ["mecanicien_a", "magasinier_a"])
    def test_les_autres_postes_ne_repartissent_pas(self, api_client, ordres, request, role, mecanicien_a2):
        assert self.reaffecter(api_client, request.getfixturevalue(role), ordres["haute"], mecanicien_a2.id).status_code == 403

    def test_l_ordre_d_une_autre_compagnie_est_introuvable(self, api_client, ordres, user_factory, company_b):
        dt_b = user_factory("dt_reaff_b", Role.DIRECTEUR_TECHNIQUE, company=company_b)
        mecano_b = user_factory("mecano_reaff_b", Role.MECANICIEN, company=company_b)

        assert self.reaffecter(api_client, dt_b, ordres["haute"], mecano_b.id).status_code == 404
