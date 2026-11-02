"""Qui lit les trajets : les rôles dont le travail y touche, pas toute la compagnie. Un chauffeur ne voit que ses propres feuilles
de route, checklists et incidents (jamais ceux d'un collègue) ; un guichetier, un magasinier ou un agent RH n'y accèdent pas."""

import pytest

from core.models import Role
from personnel_roulant.models import ChecklistDepart, EtatChecklist, FeuilleDeRoute, GraviteIncident, Incident, TypeIncident

ROUTES = ["/api/feuilles-de-route/", "/api/checklists/", "/api/incidents/"]


@pytest.fixture
def trajets(company_a, depart_a, depart_a2, feuille_a, feuille_a2, chauffeur_a, chauffeur_a2, vehicule_a):
    """Une feuille, une checklist et un incident pour chaque chauffeur (a : le premier, a2 : son collègue)."""
    resultat = {}
    for cle, chauffeur, feuille in (("a", chauffeur_a, feuille_a), ("a2", chauffeur_a2, feuille_a2)):
        resultat[cle] = {
            "feuille": feuille,
            "checklist": ChecklistDepart.objects.create(
                feuille_de_route=feuille, company=company_a, item="pneus", etat=EtatChecklist.OK
            ),
            "incident": Incident.objects.create(
                vehicule=vehicule_a, chauffeur=chauffeur, company=company_a, type_incident=TypeIncident.PANNE,
                description=f"Panne de {chauffeur.username}", gravite=GraviteIncident.FAIBLE, feuille_de_route=feuille,
            ),
        }
    return resultat


def _ids(reponse):
    assert reponse.status_code == 200, reponse.data
    return {element["id"] for element in reponse.data}


def _attendus(trajets, qui):
    return {
        "/api/feuilles-de-route/": {t["feuille"].id for t in (trajets[k] for k in qui)},
        "/api/checklists/": {t["checklist"].id for t in (trajets[k] for k in qui)},
        "/api/incidents/": {t["incident"].id for t in (trajets[k] for k in qui)},
    }


@pytest.mark.django_db
class TestUnChauffeurNeVoitQueLesSiens:
    @pytest.mark.parametrize("route", ROUTES)
    def test_la_liste_ne_contient_que_ses_propres_donnees(self, api_client, chauffeur_a, trajets, route):
        api_client.force_authenticate(user=chauffeur_a)

        assert _ids(api_client.get(route)) == _attendus(trajets, ["a"])[route]

    @pytest.mark.parametrize(("route", "cle"), [("/api/feuilles-de-route/", "feuille"), ("/api/checklists/", "checklist"), ("/api/incidents/", "incident")])
    def test_le_detail_d_un_collegue_est_introuvable(self, api_client, chauffeur_a, trajets, route, cle):
        api_client.force_authenticate(user=chauffeur_a)

        assert api_client.get(f"{route}{trajets['a2'][cle].id}/").status_code == 404
        assert api_client.get(f"{route}{trajets['a'][cle].id}/").status_code == 200

    def test_demander_le_chauffeur_d_un_collegue_ne_revele_rien(self, api_client, chauffeur_a, chauffeur_a2, trajets):
        api_client.force_authenticate(user=chauffeur_a)

        assert _ids(api_client.get("/api/feuilles-de-route/", {"chauffeur": chauffeur_a2.id})) == set()

    def test_un_chauffeur_relais_est_traite_comme_un_chauffeur(self, api_client, user_factory, company_a, trajets):
        relais = user_factory("relais_lecture", Role.CHAUFFEUR_RELAIS, company=company_a)
        api_client.force_authenticate(user=relais)

        assert _ids(api_client.get("/api/feuilles-de-route/")) == set()

    def test_la_feuille_reprise_par_un_relais_devient_la_sienne(self, api_client, user_factory, company_a, trajets):
        relais = user_factory("relais_reprise", Role.CHAUFFEUR_RELAIS, company=company_a)
        FeuilleDeRoute.objects.filter(pk=trajets["a"]["feuille"].pk).update(chauffeur=relais)
        api_client.force_authenticate(user=relais)

        assert _ids(api_client.get("/api/feuilles-de-route/")) == {trajets["a"]["feuille"].id}


@pytest.mark.django_db
class TestLesRolesDeGestionVoientToutLaCompagnie:
    @pytest.mark.parametrize("role", [Role.CHEF_LIGNE, Role.CHEF_GARE, Role.DIRECTEUR_EXPLOITATION, Role.CONTROLEUR_LIGNE, Role.QHSE, Role.PDG, Role.SECRETAIRE_GENERAL])
    @pytest.mark.parametrize("route", ROUTES)
    def test_voient_les_donnees_de_tous_les_chauffeurs(self, api_client, user_factory, company_a, trajets, role, route):
        api_client.force_authenticate(user=user_factory(f"{role}_lecture", role, company=company_a))

        assert _ids(api_client.get(route)) == _attendus(trajets, ["a", "a2"])[route]

    @pytest.mark.parametrize("route", ROUTES)
    def test_jamais_les_donnees_d_une_autre_compagnie(self, api_client, user_factory, company_b, trajets, route):
        api_client.force_authenticate(user=user_factory("directeur_b_lecture", Role.DIRECTEUR_EXPLOITATION, company=company_b))

        assert _ids(api_client.get(route)) == set()


@pytest.mark.django_db
class TestLesAutresRolesNeLisentPas:
    @pytest.mark.parametrize(
        "role",
        [Role.GUICHETIER, Role.BAGAGISTE, Role.MAGASINIER, Role.DRH, Role.DIRECTEUR_FINANCIER, Role.MECANICIEN, Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE],
    )
    @pytest.mark.parametrize("route", ROUTES)
    def test_refus(self, api_client, user_factory, company_a, trajets, role, route):
        api_client.force_authenticate(user=user_factory(f"{role}_refuse", role, company=company_a))

        assert api_client.get(route).status_code == 403

    def test_le_juridique_lit_les_incidents_mais_pas_les_trajets(self, api_client, user_factory, company_a, trajets):
        api_client.force_authenticate(user=user_factory("juridique_lecture", Role.RESPONSABLE_JURIDIQUE, company=company_a))

        assert _ids(api_client.get("/api/incidents/")) == _attendus(trajets, ["a", "a2"])["/api/incidents/"]
        assert api_client.get("/api/feuilles-de-route/").status_code == 403
        assert api_client.get("/api/checklists/").status_code == 403

    @pytest.mark.parametrize("route", ROUTES)
    def test_sans_authentification_401(self, api_client, route):
        assert api_client.get(route).status_code == 401
