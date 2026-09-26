"""Validation des investissements (cahier des charges : PDG « validation des investissements (achat de cars, ouverture de
ligne) ») : le technique, l'exploitation et la finance demandent ; le PDG seul décide."""

import pytest

from alertes.models import Alerte, TypeAlerte
from audit.models import JournalAudit
from core.models import Role
from investissements.models import Investissement, StatutInvestissement

DEMANDEURS = ["directeur_technique", "directeur_exploitation", "directeur_financier"]


@pytest.fixture
def equipe(user_factory, company_a):
    return {
        "pdg": user_factory("pdg_invest", Role.PDG, company=company_a),
        "sg": user_factory("sg_invest", Role.SECRETAIRE_GENERAL, company=company_a),
        "directeur_technique": user_factory("dt_invest", Role.DIRECTEUR_TECHNIQUE, company=company_a, first_name="Issa", last_name="Diaby"),
        "directeur_exploitation": user_factory("dirops_invest", Role.DIRECTEUR_EXPLOITATION, company=company_a),
        "directeur_financier": user_factory("df_invest", Role.DIRECTEUR_FINANCIER, company=company_a),
        "drh": user_factory("drh_invest", Role.DRH, company=company_a),
        "guichetier": user_factory("guichetier_invest", Role.GUICHETIER, company=company_a),
        "qhse": user_factory("qhse_invest", Role.QHSE, company=company_a),
    }


def demander(api_client, utilisateur, **corps):
    api_client.force_authenticate(user=utilisateur)
    base = {"type": "achat_vehicule", "libelle": "Cinq cars Yutong", "montant": "250000000", "quantite": 5, "justification": "Flotte vieillissante"}
    return api_client.post("/api/investissements/", {**base, **corps}, format="json")


def decider(api_client, utilisateur, demande, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"/api/investissements/{demande}/decider/", corps, format="json")


@pytest.mark.django_db
class TestDemande:
    @pytest.mark.parametrize("role", DEMANDEURS)
    def test_le_technique_l_exploitation_et_la_finance_deposent_une_demande(self, api_client, equipe, role):
        reponse = demander(api_client, equipe[role])

        assert reponse.status_code == 201
        assert reponse.data["statut"] == StatutInvestissement.EN_ATTENTE
        assert reponse.data["demandeur"] == equipe[role].id and reponse.data["type_libelle"] == "Achat de véhicules"
        investissement = Investissement.objects.get()
        assert investissement.company == equipe[role].company and investissement.demandeur == equipe[role]

    def test_le_pdg_est_prevenu_d_une_demande_a_decider(self, api_client, equipe):
        demander(api_client, equipe["directeur_technique"])

        alerte = Alerte.objects.get(type=TypeAlerte.INVESTISSEMENT)
        assert alerte.roles_destinataires == [Role.PDG]
        assert "Cinq cars Yutong" in alerte.titre
        assert "250 000 000 FCFA" in alerte.message and "5 véhicule(s)" in alerte.message and "Issa Diaby" in alerte.message

    def test_le_demandeur_ne_choisit_ni_le_statut_ni_la_decision(self, api_client, equipe):
        reponse = demander(
            api_client, equipe["directeur_technique"], statut="valide", decide_par=equipe["pdg"].id, commentaire_decision="Déjà validé",
            demandeur=equipe["pdg"].id,
        )

        assert reponse.status_code == 201
        investissement = Investissement.objects.get()
        assert investissement.statut == StatutInvestissement.EN_ATTENTE and investissement.decide_par is None
        assert investissement.commentaire_decision == "" and investissement.demandeur == equipe["directeur_technique"]

    @pytest.mark.parametrize("corps", [{"montant": "0"}, {"montant": "-5"}, {"montant": ""}, {"libelle": " "}, {"quantite": 0}, {"type": "cadeau"}])
    def test_les_demandes_invalides_sont_refusees(self, api_client, equipe, corps):
        assert demander(api_client, equipe["directeur_technique"], **corps).status_code == 400
        assert not Investissement.objects.exists()

    @pytest.mark.parametrize("role", ["pdg", "sg", "drh", "guichetier", "qhse"])
    def test_les_autres_postes_ne_deposent_pas(self, api_client, equipe, role):
        assert demander(api_client, equipe[role]).status_code == 403
        assert not Investissement.objects.exists()

    def test_sans_authentification_rien_n_est_possible(self, api_client):
        assert api_client.get("/api/investissements/").status_code == 401
        assert api_client.post("/api/investissements/", {}).status_code == 401


@pytest.mark.django_db
class TestDecision:
    def test_le_pdg_valide_et_previent_le_demandeur_et_la_finance(self, api_client, equipe):
        demande = demander(api_client, equipe["directeur_technique"]).data["id"]

        reponse = decider(api_client, equipe["pdg"], demande, decision="valider", commentaire="Budget voté")

        assert reponse.status_code == 200
        assert reponse.data["statut"] == StatutInvestissement.VALIDE and reponse.data["decide_par_nom"] == "pdg_invest"
        assert reponse.data["commentaire_decision"] == "Budget voté" and reponse.data["decide_le"] is not None
        alerte = Alerte.objects.get(titre__startswith="Investissement validé")
        assert list(alerte.destinataires.all()) == [equipe["directeur_technique"]]
        assert alerte.roles_destinataires == [Role.DIRECTEUR_FINANCIER]
        assert "250 000 000 FCFA à budgéter" in alerte.message

    def test_le_refus_demande_sa_raison_et_ne_previent_que_le_demandeur(self, api_client, equipe):
        demande = demander(api_client, equipe["directeur_exploitation"], type="ouverture_ligne", libelle="Ligne Abidjan-Man").data["id"]

        assert decider(api_client, equipe["pdg"], demande, decision="refuser").status_code == 400
        reponse = decider(api_client, equipe["pdg"], demande, decision="refuser", commentaire="Étude de marché à refaire")

        assert reponse.status_code == 200 and reponse.data["statut"] == StatutInvestissement.REFUSE
        alerte = Alerte.objects.get(titre__startswith="Investissement refusé")
        assert list(alerte.destinataires.all()) == [equipe["directeur_exploitation"]]
        assert alerte.roles_destinataires == [] and "à budgéter" not in alerte.message

    def test_une_demande_ne_se_decide_qu_une_fois(self, api_client, equipe):
        demande = demander(api_client, equipe["directeur_technique"]).data["id"]
        decider(api_client, equipe["pdg"], demande, decision="valider")

        reponse = decider(api_client, equipe["pdg"], demande, decision="refuser", commentaire="Trop tard")

        assert reponse.status_code == 400 and "déjà été traitée" in str(reponse.data)
        assert Investissement.objects.get().statut == StatutInvestissement.VALIDE

    @pytest.mark.parametrize("decision", ["peut-être", "", None])
    def test_la_decision_doit_etre_valider_ou_refuser(self, api_client, equipe, decision):
        demande = demander(api_client, equipe["directeur_technique"]).data["id"]

        assert decider(api_client, equipe["pdg"], demande, decision=decision).status_code == 400

    @pytest.mark.parametrize("role", ["sg", "directeur_technique", "directeur_exploitation", "directeur_financier", "drh", "guichetier"])
    def test_seul_le_pdg_decide(self, api_client, equipe, role):
        demande = demander(api_client, equipe["directeur_technique"]).data["id"]

        assert decider(api_client, equipe[role], demande, decision="valider").status_code == 403
        assert Investissement.objects.get().statut == StatutInvestissement.EN_ATTENTE

    def test_la_decision_est_tracee_au_journal(self, api_client, equipe):
        demande = demander(api_client, equipe["directeur_technique"]).data["id"]
        decider(api_client, equipe["pdg"], demande, decision="valider")

        entree = JournalAudit.objects.filter(objet_type="investissements.investissement", objet_id=str(demande)).latest("id")
        assert entree.acteur == equipe["pdg"] and entree.changements["statut"] == ["en_attente", "valide"]

    def test_le_statut_ne_se_change_pas_par_une_modification(self, api_client, equipe):
        demande = demander(api_client, equipe["directeur_technique"]).data["id"]

        api_client.force_authenticate(user=equipe["directeur_technique"])
        assert api_client.patch(f"/api/investissements/{demande}/", {"statut": "valide"}, format="json").status_code == 405
        assert api_client.delete(f"/api/investissements/{demande}/").status_code == 405


@pytest.mark.django_db
class TestQuiVoitQuoi:
    def test_la_supervision_voit_toutes_les_demandes(self, api_client, equipe):
        demander(api_client, equipe["directeur_technique"], libelle="Cars")
        demander(api_client, equipe["directeur_exploitation"], libelle="Ligne", type="ouverture_ligne")

        for role in ("pdg", "sg", "directeur_financier"):
            api_client.force_authenticate(user=equipe[role])
            assert {d["libelle"] for d in api_client.get("/api/investissements/").data} == {"Cars", "Ligne"}, role

    def test_un_demandeur_ne_voit_que_les_siennes(self, api_client, equipe):
        demander(api_client, equipe["directeur_technique"], libelle="Cars")
        demander(api_client, equipe["directeur_exploitation"], libelle="Ligne", type="ouverture_ligne")

        api_client.force_authenticate(user=equipe["directeur_technique"])
        assert [d["libelle"] for d in api_client.get("/api/investissements/").data] == ["Cars"]

    def test_le_demandeur_ne_lit_pas_la_demande_d_un_autre(self, api_client, equipe):
        demande = demander(api_client, equipe["directeur_exploitation"], libelle="Ligne", type="ouverture_ligne").data["id"]

        api_client.force_authenticate(user=equipe["directeur_technique"])
        assert api_client.get(f"/api/investissements/{demande}/").status_code == 404

    def test_les_filtres_par_statut_et_par_type(self, api_client, equipe):
        premiere = demander(api_client, equipe["directeur_technique"], libelle="Cars").data["id"]
        demander(api_client, equipe["directeur_exploitation"], libelle="Ligne", type="ouverture_ligne")
        decider(api_client, equipe["pdg"], premiere, decision="valider")

        assert [d["libelle"] for d in api_client.get("/api/investissements/?statut=en_attente").data] == ["Ligne"]
        assert [d["libelle"] for d in api_client.get("/api/investissements/?statut=valide").data] == ["Cars"]
        assert [d["libelle"] for d in api_client.get("/api/investissements/?type=ouverture_ligne").data] == ["Ligne"]
        assert len(api_client.get("/api/investissements/?statut=nimporte").data) == 2

    @pytest.mark.parametrize("role", ["drh", "guichetier", "qhse"])
    def test_les_autres_postes_ne_voient_rien(self, api_client, equipe, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/investissements/").status_code == 403

    def test_le_cloisonnement_entre_compagnies_tient(self, api_client, equipe, user_factory, company_b):
        demande = demander(api_client, equipe["directeur_technique"]).data["id"]
        pdg_b = user_factory("pdg_b_invest", Role.PDG, company=company_b)

        api_client.force_authenticate(user=pdg_b)
        assert api_client.get("/api/investissements/").data == []
        assert api_client.get(f"/api/investissements/{demande}/").status_code == 404
        assert decider(api_client, pdg_b, demande, decision="valider").status_code == 404
        assert Investissement.objects.get().statut == StatutInvestissement.EN_ATTENTE
