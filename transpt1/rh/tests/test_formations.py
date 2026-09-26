"""Formations obligatoires (cahier des charges : DRH — suivi automatique des formations obligatoires avec alerte de renouvellement OSER,
lié au module QHSE)."""

import datetime

import pytest

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from rh.models import FormationSuivie, ObligationFormation
from rh.services import ajouter_mois
from rh.tests.conftest import jour


def sessionner(api_client, utilisateur, agent, obligation, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(
        "/api/formations-suivies/", {"agent": agent.id, "obligation": obligation.id, "date_obtention": jour(-30).isoformat(), **corps}, format="json"
    )


def suivi(api_client, utilisateur, **params):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get("/api/formations-obligatoires/suivi/", params)


@pytest.mark.django_db
class TestAjouterMois:
    @pytest.mark.parametrize(
        "depart,mois,attendu",
        [
            (datetime.date(2026, 1, 15), 24, datetime.date(2028, 1, 15)),
            (datetime.date(2026, 1, 31), 1, datetime.date(2026, 2, 28)),
            (datetime.date(2024, 1, 31), 1, datetime.date(2024, 2, 29)),
            (datetime.date(2026, 11, 30), 3, datetime.date(2027, 2, 28)),
            (datetime.date(2026, 12, 10), 1, datetime.date(2027, 1, 10)),
            (datetime.date(2026, 5, 31), 12, datetime.date(2027, 5, 31)),
        ],
    )
    def test_le_dernier_jour_du_mois_si_le_mois_est_plus_court(self, depart, mois, attendu):
        assert ajouter_mois(depart, mois) == attendu


@pytest.mark.django_db
class TestCatalogueDesObligations:
    def creer(self, api_client, utilisateur, **corps):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(
            "/api/obligations-formation/",
            {"nom": "Visite médicale", "roles": ["chauffeur_principal"], "validite_mois": 12, "preavis_jours": 30, **corps},
            format="json",
        )

    @pytest.mark.parametrize("poste", ["drh", "qhse"])
    def test_le_drh_et_le_qhse_tiennent_le_catalogue(self, api_client, equipe, poste):
        reponse = self.creer(api_client, equipe[poste])

        assert reponse.status_code == 201 and reponse.data["roles"] == ["chauffeur_principal"]

    @pytest.mark.parametrize("poste", ["pdg", "secretaire_general"])
    def test_la_direction_lit_sans_ecrire(self, api_client, equipe, oser, poste):
        api_client.force_authenticate(user=equipe[poste])

        assert len(api_client.get("/api/obligations-formation/").data) == 1
        assert self.creer(api_client, equipe[poste]).status_code == 403

    @pytest.mark.parametrize("poste", ["guichetier", "chef_ligne", "chauffeur_principal", "responsable_juridique"])
    def test_les_autres_postes_n_y_touchent_pas(self, api_client, equipe, poste):
        api_client.force_authenticate(user=equipe[poste])

        assert api_client.get("/api/obligations-formation/").status_code == 403
        assert self.creer(api_client, equipe[poste]).status_code == 403

    @pytest.mark.parametrize(
        "corps",
        [{"roles": []}, {"roles": ["astronaute"]}, {"roles": ["superadmin"]}, {"roles": "chauffeur_principal"}, {"validite_mois": 0}, {"nom": " "}],
    )
    def test_les_obligations_invalides_sont_refusees(self, api_client, equipe, corps):
        assert self.creer(api_client, equipe["drh"], **corps).status_code == 400

    def test_un_nom_par_compagnie(self, api_client, equipe, oser):
        assert self.creer(api_client, equipe["drh"], nom="sécurité routière oser").status_code == 400

    def test_sans_validite_l_obligation_ne_s_eteint_pas(self, api_client, equipe):
        assert self.creer(api_client, equipe["drh"], nom="Habilitation", validite_mois=None).status_code == 201

    def test_isolation_entre_compagnies(self, api_client, equipe, oser, user_factory, company_b):
        drh_b = user_factory("drh_b_rh", "drh", company=company_b)
        api_client.force_authenticate(user=drh_b)

        assert api_client.get("/api/obligations-formation/").data == []
        assert api_client.get(f"/api/obligations-formation/{oser.id}/").status_code == 404

    def test_une_obligation_sans_session_se_supprime_pas_une_obligation_utilisee(self, api_client, equipe, oser):
        libre = self.creer(api_client, equipe["drh"], nom="Sans session").data["id"]
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser)

        api_client.force_authenticate(user=equipe["drh"])
        assert api_client.delete(f"/api/obligations-formation/{libre}/").status_code == 204
        refus = api_client.delete(f"/api/obligations-formation/{oser.id}/")
        assert refus.status_code == 400 and "historique" in str(refus.data)
        assert ObligationFormation.objects.filter(pk=oser.id).exists()


@pytest.mark.django_db
class TestSessionsSuivies:
    def test_l_expiration_se_calcule_avec_la_validite(self, api_client, equipe, oser):
        reponse = sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention="2026-01-31")

        assert reponse.status_code == 201 and reponse.data["date_expiration"] == "2028-01-31"
        assert FormationSuivie.objects.get().saisi_par == equipe["drh"]

    def test_une_expiration_donnee_fait_foi(self, api_client, equipe, oser):
        reponse = sessionner(api_client, equipe["qhse"], equipe["chauffeur_principal"], oser, date_expiration=jour(100).isoformat())

        assert reponse.status_code == 201 and reponse.data["date_expiration"] == jour(100).isoformat()

    @pytest.mark.parametrize("corps", [{"date_obtention": "demain"}, {"date_expiration": jour(-60).isoformat()}])
    def test_les_dates_incoherentes_sont_refusees(self, api_client, equipe, oser, corps):
        assert sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, **corps).status_code == 400

    def test_pas_de_formation_datee_du_futur(self, api_client, equipe, oser):
        assert sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=jour(3).isoformat()).status_code == 400

    def test_une_session_ne_s_enregistre_pas_deux_fois(self, api_client, equipe, oser):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention="2026-01-10")

        assert sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention="2026-01-10").status_code == 400

    def test_les_rattachements_doivent_etre_de_la_compagnie(self, api_client, equipe, oser, user_factory, company_b):
        etranger = user_factory("chauffeur_b_rh", "chauffeur_principal", company=company_b)
        obligation_b = ObligationFormation.objects.create(company=company_b, nom="Autre", roles=["guichetier"])

        assert sessionner(api_client, equipe["drh"], etranger, oser).status_code == 400
        assert sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], obligation_b).status_code == 400

    @pytest.mark.parametrize("poste", ["pdg", "chef_ligne", "chauffeur_principal", "guichetier"])
    def test_seuls_le_drh_et_le_qhse_enregistrent(self, api_client, equipe, oser, poste):
        assert sessionner(api_client, equipe[poste], equipe["chauffeur_principal"], oser).status_code == 403

    def test_chacun_voit_ses_sessions_et_l_echelon_celles_des_postes_sous_son_autorite(self, api_client, equipe, oser):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser)
        sessionner(api_client, equipe["drh"], equipe["chauffeur_relais"], oser)

        def visibles(poste):
            api_client.force_authenticate(user=equipe[poste])
            return {s["agent"] for s in api_client.get("/api/formations-suivies/").data}

        conducteur, relais = equipe["chauffeur_principal"].id, equipe["chauffeur_relais"].id
        assert visibles("chauffeur_principal") == {conducteur}
        assert visibles("chef_ligne") == {conducteur, relais}  # le chef de ligne règle les chauffeurs
        assert visibles("guichetier") == set()
        assert visibles("drh") == visibles("qhse") == visibles("pdg") == {conducteur, relais}

    def test_le_filtre_par_agent(self, api_client, equipe, oser):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser)
        sessionner(api_client, equipe["drh"], equipe["chauffeur_relais"], oser)

        api_client.force_authenticate(user=equipe["drh"])
        reponse = api_client.get("/api/formations-suivies/", {"agent": equipe["chauffeur_relais"].id})

        assert [s["agent"] for s in reponse.data] == [equipe["chauffeur_relais"].id]


@pytest.mark.django_db
class TestSuiviAutomatique:
    def etats(self, api_client, utilisateur, **params):
        return {l["agent_nom"]: l["etat"] for l in suivi(api_client, utilisateur, **params).data["lignes"]}

    def test_quatre_etats_du_manquant_a_l_a_jour(self, api_client, equipe, oser, user_factory, company_a):
        expire = user_factory("expire_rh", "chauffeur_principal", company=company_a)
        proche = user_factory("proche_rh", "chauffeur_principal", company=company_a)
        # Le conducteur de l'équipe n'a aucune session : « manquante ».
        sessionner(api_client, equipe["drh"], expire, oser, date_obtention=jour(-800).isoformat())  # expire il y a ~70 j
        sessionner(api_client, equipe["drh"], proche, oser, date_obtention=(jour(30) - datetime.timedelta(days=730)).isoformat())  # expire dans ~30 j
        sessionner(api_client, equipe["drh"], equipe["chauffeur_relais"], oser, date_obtention=jour(-30).isoformat())

        etats = self.etats(api_client, equipe["drh"])

        assert etats == {
            "expire_rh": "expiree", "chauffeur_principal_rh": "manquante", "proche_rh": "a_renouveler", "chauffeur_relais_rh": "a_jour"
        }

    def test_les_lignes_sont_classees_par_urgence_et_resumees(self, api_client, equipe, oser, user_factory, company_a):
        expire = user_factory("expire_rh", "chauffeur_principal", company=company_a)
        sessionner(api_client, equipe["drh"], expire, oser, date_obtention=jour(-800).isoformat())
        sessionner(api_client, equipe["drh"], equipe["chauffeur_relais"], oser, date_obtention=jour(-30).isoformat())

        reponse = suivi(api_client, equipe["drh"]).data

        assert [l["etat"] for l in reponse["lignes"]] == ["expiree", "manquante", "a_jour"]
        assert reponse["resume"] == {"expiree": 1, "manquante": 1, "a_renouveler": 0, "a_jour": 1}
        assert reponse["lignes"][0]["jours_restants"] < 0

    def test_renouveler_c_est_enregistrer_une_nouvelle_session(self, api_client, equipe, oser):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=jour(-800).isoformat())
        assert self.etats(api_client, equipe["drh"])["chauffeur_principal_rh"] == "expiree"

        sessionner(api_client, equipe["qhse"], equipe["chauffeur_principal"], oser, date_obtention=jour(-1).isoformat())

        assert self.etats(api_client, equipe["drh"])["chauffeur_principal_rh"] == "a_jour"
        assert FormationSuivie.objects.count() == 2  # l'historique reste

    def test_une_obligation_sans_validite_ne_s_eteint_pas(self, api_client, equipe, company_a):
        habilitation = ObligationFormation.objects.create(company=company_a, nom="Habilitation", roles=["mecanicien"])
        assert self.etats(api_client, equipe["drh"])["mecanicien_rh"] == "manquante"

        sessionner(api_client, equipe["drh"], equipe["mecanicien"], habilitation, date_obtention="2010-01-01")

        assert self.etats(api_client, equipe["drh"])["mecanicien_rh"] == "a_jour"

    def test_seuls_les_postes_concernes_et_les_agents_actifs_apparaissent(self, api_client, equipe, oser):
        equipe["chauffeur_relais"].is_active = False
        equipe["chauffeur_relais"].save()

        assert set(self.etats(api_client, equipe["drh"])) == {"chauffeur_principal_rh"}

    def test_les_filtres_etat_et_agent(self, api_client, equipe, oser):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_relais"], oser, date_obtention=jour(-30).isoformat())

        assert set(self.etats(api_client, equipe["drh"], etat="manquante")) == {"chauffeur_principal_rh"}
        assert set(self.etats(api_client, equipe["drh"], agent=equipe["chauffeur_relais"].id)) == {"chauffeur_relais_rh"}

    def test_chacun_voit_son_propre_suivi_et_l_echelon_celui_de_ses_postes(self, api_client, equipe, oser):
        assert set(self.etats(api_client, equipe["chauffeur_principal"])) == {"chauffeur_principal_rh"}
        assert set(self.etats(api_client, equipe["chef_ligne"])) == {"chauffeur_principal_rh", "chauffeur_relais_rh"}
        assert self.etats(api_client, equipe["guichetier"]) == {}
        for poste in ("drh", "qhse", "pdg", "secretaire_general"):
            assert len(self.etats(api_client, equipe[poste])) == 2

    def test_une_autre_compagnie_ne_voit_rien(self, api_client, equipe, oser, user_factory, company_b):
        drh_b = user_factory("drh_b_suivi", "drh", company=company_b)

        assert suivi(api_client, drh_b).data["lignes"] == []

    def test_sans_authentification(self, api_client):
        assert api_client.get("/api/formations-obligatoires/suivi/").status_code == 401


@pytest.mark.django_db
class TestAlertesDeRenouvellement:
    def alertes(self):
        return list(Alerte.objects.filter(type=TypeAlerte.FORMATION).order_by("id"))

    def test_une_formation_qui_entre_dans_son_preavis_alerte_le_drh_le_qhse_et_l_agent(self, api_client, equipe, oser, company_a):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=(jour(40) - datetime.timedelta(days=730)).isoformat())

        generer(company_a)

        (alerte,) = self.alertes()
        assert alerte.titre == "Sécurité routière OSER à renouveler : chauffeur_principal_rh" and alerte.gravite == "attention"
        assert set(alerte.roles_destinataires) == {"drh", "qhse"}
        assert list(alerte.destinataires.all()) == [equipe["chauffeur_principal"]]
        assert "Échéance dans 40 jour(s)" in alerte.message

    def test_une_formation_expiree_est_critique(self, api_client, equipe, oser, company_a):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=jour(-800).isoformat())

        generer(company_a)

        (alerte,) = self.alertes()
        assert alerte.gravite == "critique" and alerte.titre == "Sécurité routière OSER expirée : chauffeur_principal_rh"
        assert "Échue depuis" in alerte.message

    def test_ni_manquante_ni_a_jour_ne_declenche_d_alerte(self, api_client, equipe, oser, company_a):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_relais"], oser, date_obtention=jour(-30).isoformat())

        generer(company_a)  # le conducteur sans session est « manquant » : c'est au tableau de suivi, pas une alerte de renouvellement

        assert self.alertes() == []

    def test_une_situation_ne_previent_qu_une_fois(self, api_client, equipe, oser, company_a):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=jour(-800).isoformat())

        generer(company_a)
        generer(company_a)

        assert len(self.alertes()) == 1

    def test_l_alerte_repart_apres_un_renouvellement_qui_expire_a_son_tour(self, api_client, equipe, oser, company_a):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=jour(-800).isoformat())
        generer(company_a)
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=(jour(20) - datetime.timedelta(days=730)).isoformat())

        generer(company_a)

        assert [a.gravite for a in self.alertes()] == ["critique", "attention"]

    def test_le_qhse_recoit_l_alerte_dans_sa_cloche(self, api_client, equipe, oser, company_a):
        sessionner(api_client, equipe["drh"], equipe["chauffeur_principal"], oser, date_obtention=jour(-800).isoformat())
        generer(company_a)

        api_client.force_authenticate(user=equipe["qhse"])
        titres = [a["titre"] for a in api_client.get("/api/alertes/").data["alertes"]]
        api_client.force_authenticate(user=equipe["guichetier"])

        assert any("Sécurité routière OSER expirée" in t for t in titres)
        assert not [a for a in api_client.get("/api/alertes/").data["alertes"] if a["type"] == "formation"]
