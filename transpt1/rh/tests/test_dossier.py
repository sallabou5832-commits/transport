"""Dossier de l'agent (cahier des charges : DRH — dossier centralisé par poste : contrat, formation, évaluations, discipline, accessible
selon le principe de configuration hiérarchique)."""

import datetime

import pytest

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from rh.models import ContratAgent, EvaluationAgent, MesureDisciplinaire
from rh.tests.conftest import jour
from supports.models import DossierAgent


def ouvrir_dossier(agent, notes="Note interne du DRH"):
    return DossierAgent.objects.create(agent=agent, company=agent.company, date_embauche=datetime.date(2022, 1, 1), poste="Poste", notes_rh=notes)


def poster(api_client, utilisateur, chemin, corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(chemin, corps, format="json")


def contrat(api_client, utilisateur, agent, **corps):
    return poster(api_client, utilisateur, "/api/contrats/", {"agent": agent.id, "type": "cdd", "date_debut": "2026-01-01", "date_fin": "2026-12-31", **corps})


def evaluation(api_client, utilisateur, agent, **corps):
    return poster(api_client, utilisateur, "/api/evaluations/", {"agent": agent.id, "date": jour(-1).isoformat(), "note": 4, "commentaire": "Solide", **corps})


def mesure(api_client, utilisateur, agent, **corps):
    return poster(api_client, utilisateur, "/api/mesures-disciplinaires/", {"agent": agent.id, "date": jour(-1).isoformat(), "type": "avertissement", "motif": "Retards répétés", **corps})


@pytest.mark.django_db
class TestContrats:
    def test_le_drh_enregistre_un_contrat(self, api_client, equipe):
        reponse = contrat(api_client, equipe["drh"], equipe["chauffeur_principal"])

        assert reponse.status_code == 201 and reponse.data["type_libelle"] == "CDD"
        assert ContratAgent.objects.get().company == equipe["drh"].company

    @pytest.mark.parametrize("poste", ["pdg", "chef_ligne", "qhse", "chauffeur_principal", "secretaire_general"])
    def test_personne_d_autre_n_ecrit_un_contrat(self, api_client, equipe, poste):
        assert contrat(api_client, equipe[poste], equipe["chauffeur_principal"]).status_code == 403

    def test_la_fin_ne_precede_pas_le_debut(self, api_client, equipe):
        assert contrat(api_client, equipe["drh"], equipe["guichetier"], date_fin="2025-12-31").status_code == 400

    def test_l_agent_doit_etre_de_la_compagnie(self, api_client, equipe, user_factory, company_b):
        assert contrat(api_client, equipe["drh"], user_factory("autre_b_rh", "guichetier", company=company_b)).status_code == 400

    def test_chacun_voit_le_sien_et_l_echelon_ceux_de_ses_postes(self, api_client, equipe):
        contrat(api_client, equipe["drh"], equipe["chauffeur_principal"])
        contrat(api_client, equipe["drh"], equipe["guichetier"])

        def agents(poste):
            api_client.force_authenticate(user=equipe[poste])
            return {c["agent"] for c in api_client.get("/api/contrats/").data}

        assert agents("chauffeur_principal") == {equipe["chauffeur_principal"].id}
        assert agents("chef_ligne") == {equipe["chauffeur_principal"].id}
        assert agents("chef_gare") == {equipe["guichetier"].id}
        assert agents("bagagiste") == set()
        assert agents("drh") == agents("pdg") == {equipe["chauffeur_principal"].id, equipe["guichetier"].id}

    def test_un_contrat_a_terme_alerte_le_drh_une_fois(self, api_client, equipe, company_a):
        contrat(api_client, equipe["drh"], equipe["guichetier"], date_fin=jour(20).isoformat())
        contrat(api_client, equipe["drh"], equipe["bagagiste"], date_fin=jour(80).isoformat())  # trop loin
        contrat(api_client, equipe["drh"], equipe["chef_gare"], type="cdi", date_fin=None)  # un CDI ne se termine pas
        contrat(api_client, equipe["drh"], equipe["controleur_ligne"], date_fin=jour(-5).isoformat(), date_debut="2025-01-01")  # déjà fini

        generer(company_a)
        generer(company_a)

        (alerte,) = Alerte.objects.filter(type=TypeAlerte.CONTRAT)
        assert alerte.titre == "Fin de contrat dans 20 jour(s) : guichetier_rh" and alerte.roles_destinataires == ["drh"]

    def test_isolation_entre_compagnies(self, api_client, equipe, user_factory, company_b):
        contrat(api_client, equipe["drh"], equipe["guichetier"])
        drh_b = user_factory("drh_b_contrat", "drh", company=company_b)

        api_client.force_authenticate(user=drh_b)
        assert api_client.get("/api/contrats/").data == []


@pytest.mark.django_db
class TestEvaluations:
    def test_le_drh_evalue_tout_le_monde(self, api_client, equipe):
        reponse = evaluation(api_client, equipe["drh"], equipe["chef_ligne"])

        assert reponse.status_code == 201 and reponse.data["evaluateur"] == equipe["drh"].id and reponse.data["evaluateur_nom"] == "drh_rh"

    @pytest.mark.parametrize(
        "evaluateur,agent,statut",
        [
            ("chef_gare", "guichetier", 201),
            ("chef_gare", "bagagiste", 201),
            ("chef_gare", "chef_ligne", 403),  # pas sous son autorité
            ("chef_ligne", "chauffeur_principal", 201),
            ("chef_atelier", "mecanicien", 201),
            ("directeur_exploitation", "chef_gare", 201),
            ("directeur_exploitation", "guichetier", 403),  # deux échelons plus bas
            ("pdg", "directeur_technique", 201),
            ("guichetier", "bagagiste", 403),  # aucun poste sous son autorité
            ("chauffeur_principal", "chauffeur_relais", 403),
        ],
    )
    def test_un_echelon_evalue_les_postes_sous_son_autorite(self, api_client, equipe, evaluateur, agent, statut):
        assert evaluation(api_client, equipe[evaluateur], equipe[agent]).status_code == statut

    @pytest.mark.parametrize("note", [0, 6, -1])
    def test_la_note_va_de_un_a_cinq(self, api_client, equipe, note):
        assert evaluation(api_client, equipe["drh"], equipe["guichetier"], note=note).status_code == 400

    def test_pas_d_evaluation_datee_du_futur(self, api_client, equipe):
        assert evaluation(api_client, equipe["drh"], equipe["guichetier"], date=jour(2).isoformat()).status_code == 400

    def test_seul_son_auteur_ou_le_drh_la_modifie(self, api_client, equipe):
        cree = evaluation(api_client, equipe["chef_gare"], equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe["pdg"])
        assert api_client.patch(f"/api/evaluations/{cree}/", {"note": 1}, format="json").status_code == 403
        api_client.force_authenticate(user=equipe["chef_gare"])
        assert api_client.patch(f"/api/evaluations/{cree}/", {"note": 5}, format="json").data["note"] == 5
        api_client.force_authenticate(user=equipe["drh"])
        assert api_client.delete(f"/api/evaluations/{cree}/").status_code == 204

    def test_l_agent_lit_ses_evaluations_sans_pouvoir_en_ecrire(self, api_client, equipe):
        evaluation(api_client, equipe["chef_gare"], equipe["guichetier"])
        evaluation(api_client, equipe["chef_gare"], equipe["bagagiste"])

        api_client.force_authenticate(user=equipe["guichetier"])
        assert [e["agent"] for e in api_client.get("/api/evaluations/").data] == [equipe["guichetier"].id]

    def test_l_echelon_superieur_lit_celles_de_ses_postes(self, api_client, equipe):
        evaluation(api_client, equipe["drh"], equipe["guichetier"])
        evaluation(api_client, equipe["drh"], equipe["chauffeur_principal"])

        api_client.force_authenticate(user=equipe["chef_gare"])
        assert {e["agent"] for e in api_client.get("/api/evaluations/").data} == {equipe["guichetier"].id}

    def test_le_filtre_par_agent(self, api_client, equipe):
        evaluation(api_client, equipe["drh"], equipe["guichetier"])
        evaluation(api_client, equipe["drh"], equipe["bagagiste"])

        api_client.force_authenticate(user=equipe["drh"])
        assert len(api_client.get("/api/evaluations/", {"agent": equipe["bagagiste"].id}).data) == 1
        assert EvaluationAgent.objects.count() == 2


@pytest.mark.django_db
class TestDiscipline:
    def test_le_drh_note_une_mesure(self, api_client, equipe):
        reponse = mesure(api_client, equipe["drh"], equipe["chauffeur_principal"], type="mise_a_pied", duree_jours=3)

        assert reponse.status_code == 201 and reponse.data["type_libelle"] == "Mise à pied" and reponse.data["decidee_par"] == equipe["drh"].id
        assert MesureDisciplinaire.objects.get().duree_jours == 3

    @pytest.mark.parametrize("poste", ["pdg", "chef_ligne", "qhse", "chauffeur_principal"])
    def test_seul_le_drh_sanctionne(self, api_client, equipe, poste):
        assert mesure(api_client, equipe[poste], equipe["chauffeur_principal"]).status_code == 403

    @pytest.mark.parametrize("corps", [{"motif": "  "}, {"motif": "x"}, {"date": "demain"}, {"type": "exil"}])
    def test_les_mesures_invalides_sont_refusees(self, api_client, equipe, corps):
        assert mesure(api_client, equipe["drh"], equipe["chauffeur_principal"], **corps).status_code == 400

    def test_l_agent_et_sa_hierarchie_la_lisent_pas_les_autres(self, api_client, equipe):
        mesure(api_client, equipe["drh"], equipe["chauffeur_principal"])

        def vues(poste):
            api_client.force_authenticate(user=equipe[poste])
            return len(api_client.get("/api/mesures-disciplinaires/").data)

        assert (vues("chauffeur_principal"), vues("chef_ligne"), vues("pdg"), vues("drh")) == (1, 1, 1, 1)
        assert (vues("chauffeur_relais"), vues("guichetier"), vues("chef_gare"), vues("qhse")) == (0, 0, 0, 0)


@pytest.mark.django_db
class TestDossierHierarchique:
    def test_chaque_echelon_lit_le_dossier_des_postes_sous_son_autorite_sans_les_notes_du_drh(self, api_client, equipe):
        dossier = ouvrir_dossier(equipe["chauffeur_principal"])

        api_client.force_authenticate(user=equipe["chef_ligne"])
        liste = api_client.get("/api/dossiers-agents/").data
        detail = api_client.get(f"/api/dossiers-agents/{dossier.id}/").data

        assert [d["id"] for d in liste] == [dossier.id] and "notes_rh" not in liste[0] and "notes_rh" not in detail

    def test_le_drh_et_l_agent_lisent_les_notes(self, api_client, equipe):
        dossier = ouvrir_dossier(equipe["chauffeur_principal"])

        for poste in ("drh", "chauffeur_principal"):
            api_client.force_authenticate(user=equipe[poste])
            assert api_client.get(f"/api/dossiers-agents/{dossier.id}/").data["notes_rh"] == "Note interne du DRH", poste

    def test_un_pair_ou_un_autre_echelon_ne_le_voit_pas(self, api_client, equipe):
        dossier = ouvrir_dossier(equipe["chauffeur_principal"])

        for poste in ("chauffeur_relais", "guichetier", "chef_gare", "qhse", "directeur_financier", "secretaire_general"):
            api_client.force_authenticate(user=equipe[poste])
            assert api_client.get(f"/api/dossiers-agents/{dossier.id}/").status_code == 404, poste

    @pytest.mark.parametrize("poste", ["chef_ligne", "pdg", "chauffeur_principal"])
    def test_seul_le_drh_modifie_un_dossier(self, api_client, equipe, poste):
        dossier = ouvrir_dossier(equipe["chauffeur_principal"])

        api_client.force_authenticate(user=equipe[poste])
        assert api_client.patch(f"/api/dossiers-agents/{dossier.id}/", {"statut": "termine"}, format="json").status_code == 403

    def test_la_fiche_rassemble_contrats_evaluations_discipline_et_formations(self, api_client, equipe, oser):
        dossier = ouvrir_dossier(equipe["chauffeur_principal"])
        contrat(api_client, equipe["drh"], equipe["chauffeur_principal"], notes="Clause confidentielle")
        evaluation(api_client, equipe["chef_ligne"], equipe["chauffeur_principal"])
        mesure(api_client, equipe["drh"], equipe["chauffeur_principal"])

        api_client.force_authenticate(user=equipe["drh"])
        fiche = api_client.get(f"/api/dossiers-agents/{dossier.id}/fiche/").data

        assert fiche["dossier"]["notes_rh"] == "Note interne du DRH"
        assert [c["notes"] for c in fiche["contrats"]] == ["Clause confidentielle"]
        assert [e["note"] for e in fiche["evaluations"]] == [4] and [m["type"] for m in fiche["mesures"]] == ["avertissement"]
        assert [(f["obligation_nom"], f["etat"]) for f in fiche["formations"]] == [("Sécurité routière OSER", "manquante")]

    def test_la_fiche_vue_de_la_hierarchie_sans_les_notes(self, api_client, equipe):
        dossier = ouvrir_dossier(equipe["chauffeur_principal"])
        contrat(api_client, equipe["drh"], equipe["chauffeur_principal"], notes="Clause confidentielle")

        api_client.force_authenticate(user=equipe["chef_ligne"])
        fiche = api_client.get(f"/api/dossiers-agents/{dossier.id}/fiche/").data

        assert "notes_rh" not in fiche["dossier"] and fiche["contrats"] and "notes" not in fiche["contrats"][0]

    def test_la_fiche_d_un_autre_poste_est_introuvable(self, api_client, equipe):
        dossier = ouvrir_dossier(equipe["chauffeur_principal"])

        api_client.force_authenticate(user=equipe["guichetier"])
        assert api_client.get(f"/api/dossiers-agents/{dossier.id}/fiche/").status_code == 404
