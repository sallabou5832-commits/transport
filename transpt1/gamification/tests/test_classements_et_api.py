"""Classements (inter-gares, inter-chauffeurs...), niveaux de gamification configurés, vue du DRH, commande d'évaluation."""

import datetime
import io

import pytest
from django.core.management import call_command
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from configuration.models import ConfigurationAgent, ConfigurationCompagnie, ConfigurationPoste
from core.models import Role
from gamification.models import MissionAccomplie
from gamification.tests.conftest import etat, trajet, vendre
from reseau.models import Gare, Ligne


def classement(api_client, utilisateur, type_classement="gares", periode="mois"):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get(f"/api/gamification/classement/?type={type_classement}&periode={periode}")


@pytest.mark.django_db
class TestClassementDesGares:
    @pytest.fixture
    def deux_gares(self, monde, agents, company_a):
        """Adjamé : 3 départs à l'heure, cars pleins. Yopougon : 2 départs dont un en retard, cars à moitié vides."""
        gare_yopougon = Gare.objects.create(nom="Yopougon", ville="Abidjan", company=company_a)
        ligne_yopougon = Ligne.objects.create(nom="Yopougon-Bouaké", gare_depart=gare_yopougon, gare_arrivee=monde["gare_b"], company=company_a)
        from personnel_roulant.models import FeuilleDeRoute

        def depart(ligne, retard, places, heures):
            prevue = timezone.now() - datetime.timedelta(hours=heures)
            d = Depart.objects.create(
                ligne=ligne, vehicule=monde["vehicule"], chauffeur=agents["chauffeur_principal"], company=company_a,
                date_heure=prevue, statut=DepartStatut.TERMINE, places_vendues=places,
            )
            FeuilleDeRoute.objects.create(
                depart=d, chauffeur=agents["chauffeur_principal"], company=company_a, heure_depart_prevue=prevue,
                heure_depart_reelle=prevue + datetime.timedelta(minutes=retard), heure_arrivee_reelle=prevue + datetime.timedelta(hours=1),
            )

        for heures in (4, 5, 6):
            depart(monde["ligne"], 0, 20, heures)  # pleins et à l'heure
        depart(ligne_yopougon, 0, 10, 7)
        depart(ligne_yopougon, 45, 10, 8)  # en retard
        return {"yopougon": gare_yopougon}

    def test_la_gare_ponctuelle_et_pleine_est_premiere(self, api_client, agents, monde, deux_gares):
        resultat = classement(api_client, agents["pdg"]).data

        assert resultat["visible"] is True and resultat["libelle"] == "Inter-gares"
        noms = [g["nom"] for g in resultat["classement"]]
        assert noms[:2] == ["Adjamé", "Yopougon"] and resultat["classement"][0]["rang"] == 1
        adjame, yopougon = resultat["classement"][0], resultat["classement"][1]
        # 3 cars pleins + le départ prévu (sans vente) de la fixture : 60 places sur 80. Un départ à venir pèse dans le taux.
        assert adjame["ponctualite_pourcent"] == 100 and adjame["remplissage_pourcent"] == 75
        assert yopougon["ponctualite_pourcent"] == 50 and yopougon["remplissage_pourcent"] == 50
        assert adjame["score"] > yopougon["score"]

    def test_une_gare_sans_activite_ferme_le_classement(self, api_client, agents, monde, deux_gares):
        resultat = classement(api_client, agents["pdg"]).data["classement"]

        assert resultat[-1]["nom"] == "Bouaké" and resultat[-1]["score"] == 0

    def test_les_recettes_comptent_relativement_a_la_meilleure_gare(self, api_client, agents, monde, deux_gares):
        vendre(monde, agents["guichetier"], prix="10000")  # ticket sur le départ d'Adjamé, du jour

        adjame = next(g for g in classement(api_client, agents["pdg"]).data["classement"] if g["nom"] == "Adjamé")

        assert adjame["recettes_relatives_pourcent"] == 100

    def test_ex_aequo_meme_rang(self, api_client, agents, monde):
        resultat = classement(api_client, agents["pdg"]).data["classement"]

        assert [g["rang"] for g in resultat] == [1, 1]  # deux gares sans activité : mêmes scores, même rang


@pytest.mark.django_db
class TestClassementDesAgents:
    def test_les_chauffeurs_sont_classes_par_points_de_la_periode(self, api_client, agents, monde):
        trajet(monde, agents["chauffeur_principal"], checklist=True)
        trajet(monde, agents["chauffeur2"], retard_minutes=60)

        resultat = classement(api_client, agents["chauffeur_principal"], "chauffeurs").data["classement"]

        assert [(c["nom"], c["score"], c["rang"], c["moi"]) for c in resultat] == [
            ("chauffeur_principal_jeu", 18, 1, True),
            ("chauffeur2_jeu", 5 - 3, 2, False),
        ]

    def test_seuls_les_postes_a_gamification_complete_y_figurent(self, api_client, agents, monde, company_a):
        trajet(monde, agents["chauffeur_principal"])
        ConfigurationAgent.objects.create(agent=agents["chauffeur2"], company=company_a, niveau_gamification="aucun")

        noms = [c["nom"] for c in classement(api_client, agents["chauffeur_principal"], "chauffeurs").data["classement"]]

        assert noms == ["chauffeur_principal_jeu"]

    def test_la_periode_borne_le_classement(self, api_client, agents, monde):
        trajet(monde, agents["chauffeur_principal"], il_y_a=datetime.timedelta(days=60))

        assert classement(api_client, agents["chauffeur_principal"], "chauffeurs", "mois").data["classement"][0]["score"] == 0
        assert classement(api_client, agents["chauffeur_principal"], "chauffeurs", "tout").data["classement"][0]["score"] == 15

    def test_le_classement_d_une_autre_compagnie_est_invisible(self, api_client, agents, monde, company_b, user_factory):
        vendre(monde, agents["guichetier"])
        etranger = user_factory("guichetier_b_jeu", Role.GUICHETIER, company=company_b)

        assert classement(api_client, etranger, "guichetiers").data["classement"] == [
            {"id": etranger.id, "nom": "guichetier_b_jeu", "role": "guichetier", "score": 0, "rang": 1, "moi": True}
        ]


@pytest.mark.django_db
class TestQuiVoitQuoi:
    def test_chaque_poste_voit_les_gares_et_son_propre_groupe(self, api_client, agents):
        assert [t["type"] for t in etat(api_client, agents["guichetier"])["classements"]] == ["gares", "guichetiers"]
        assert [t["type"] for t in etat(api_client, agents["chauffeur_principal"])["classements"]] == ["gares", "chauffeurs"]
        assert [t["type"] for t in etat(api_client, agents["mecanicien"])["classements"]] == ["gares", "ateliers"]
        assert [t["type"] for t in etat(api_client, agents["chef_ligne"])["classements"]] == ["gares", "lignes"]

    def test_la_direction_voit_tous_les_classements(self, api_client, agents):
        types = [t["type"] for t in etat(api_client, agents["pdg"])["classements"]]

        assert types == ["gares", "lignes", "chauffeurs", "guichetiers", "bagagistes", "ateliers", "controleurs"]

    def test_un_classement_hors_de_son_perimetre_est_refuse(self, api_client, agents):
        assert classement(api_client, agents["guichetier"], "chauffeurs").status_code == 403

    @pytest.mark.parametrize("parametres", ["type=n_importe_quoi", "periode=hier"])
    def test_les_parametres_invalides_sont_refuses(self, api_client, agents, parametres):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.get(f"/api/gamification/classement/?{parametres}").status_code == 400


@pytest.mark.django_db
class TestNiveauxConfigures:
    def test_en_mode_sobre_pas_de_classement(self, api_client, agents, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, niveau_gamification="sobre")

        reponse = classement(api_client, agents["guichetier"], "guichetiers")

        assert reponse.status_code == 200 and reponse.data["visible"] is False and reponse.data["classement"] == []

    def test_en_mode_aucun_le_jeu_est_invisible_et_rien_n_est_enregistre(self, api_client, agents, monde, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, niveau_gamification="aucun")
        for _ in range(6):
            vendre(monde, agents["guichetier"])

        donnees = etat(api_client, agents["guichetier"])

        assert donnees == {"actif": False, "niveau_gamification": "aucun"}
        assert not MissionAccomplie.objects.exists()

    def test_direction_support_juridique_demarrent_sobres_sans_classement(self, api_client, agents):
        for role in ("drh", "responsable_juridique", "secretaire_general"):
            donnees = etat(api_client, agents[role])
            assert donnees["niveau_gamification"] == "sobre" and donnees["classements"] == [] and donnees["badges"] == [], role
            assert classement(api_client, agents[role]).data["visible"] is False, role

    def test_le_pdg_peut_passer_la_direction_en_mode_complet(self, api_client, agents, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.DRH, niveau_gamification="complet")

        assert etat(api_client, agents["drh"])["niveau_gamification"] == "complet"

    def test_le_cadre_de_la_compagnie_peut_tout_couper(self, api_client, agents, company_a):
        ConfigurationCompagnie.objects.create(company=company_a, gamification_max="aucun")

        assert etat(api_client, agents["guichetier"])["actif"] is False

    def test_le_superadmin_n_a_pas_de_jeu(self, api_client, superadmin_user):
        assert etat(api_client, superadmin_user)["actif"] is False
        assert classement(api_client, superadmin_user).data["visible"] is False

    def test_l_etat_exige_une_authentification(self, api_client):
        assert api_client.get("/api/gamification/moi/").status_code == 401
        assert api_client.get("/api/gamification/classement/").status_code == 401


@pytest.mark.django_db
class TestVueDuDrh:
    def test_le_drh_voit_les_scores_de_tous_les_agents(self, api_client, agents, monde):
        vendre(monde, agents["guichetier"])
        vendre(monde, agents["guichetier"])
        trajet(monde, agents["chauffeur_principal"])
        api_client.force_authenticate(user=agents["drh"])

        lignes = api_client.get("/api/gamification/agents/").data["agents"]

        par_nom = {ligne["nom"]: ligne for ligne in lignes}
        assert par_nom["chauffeur_principal_jeu"]["points"] == 15 and par_nom["guichetier_jeu"]["points"] == 2
        assert par_nom["guichetier_jeu"]["niveau"]["nom"] == "Recrue"
        assert lignes == sorted(lignes, key=lambda l: (-l["points"], l["nom"]))

    def test_les_agents_qui_ont_choisi_aucun_n_y_figurent_pas(self, api_client, agents, company_a):
        ConfigurationAgent.objects.create(agent=agents["guichetier"], company=company_a, niveau_gamification="aucun")
        api_client.force_authenticate(user=agents["drh"])

        assert "guichetier_jeu" not in [l["nom"] for l in api_client.get("/api/gamification/agents/").data["agents"]]

    @pytest.mark.parametrize("role", ["guichetier", "chef_gare", "qhse", "directeur_exploitation", "responsable_juridique"])
    def test_les_autres_postes_n_ont_pas_acces_aux_scores_des_collegues(self, api_client, agents, role):
        api_client.force_authenticate(user=agents[role])

        assert api_client.get("/api/gamification/agents/").status_code == 403

    def test_le_pdg_y_a_acces(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.get("/api/gamification/agents/").status_code == 200

    def test_pas_de_fuite_entre_compagnies(self, api_client, agents, company_b, user_factory):
        user_factory("guichetier_b_jeu", Role.GUICHETIER, company=company_b)
        api_client.force_authenticate(user=agents["drh"])

        assert "guichetier_b_jeu" not in [l["nom"] for l in api_client.get("/api/gamification/agents/").data["agents"]]


@pytest.mark.django_db
class TestCommandeEvaluer:
    def lancer(self):
        sortie = io.StringIO()
        call_command("evaluer_gamification", stdout=sortie)
        return sortie.getvalue()

    def test_la_commande_enregistre_ce_que_les_agents_n_ont_pas_consulte(self, agents, monde):
        for _ in range(5):
            vendre(monde, agents["guichetier"])

        sortie = self.lancer()

        assert MissionAccomplie.objects.filter(agent=agents["guichetier"], code="zero_erreur").exists()
        assert "mission(s)" in sortie and "badge(s)" in sortie

    def test_la_commande_est_rejouable_sans_doublon(self, agents, monde):
        for _ in range(5):
            vendre(monde, agents["guichetier"])
        self.lancer()

        assert "0 mission(s) et 0 badge(s)" in self.lancer()
        assert MissionAccomplie.objects.filter(agent=agents["guichetier"]).count() == 1

    def test_la_commande_ignore_les_postes_sans_gamification(self, agents, monde, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, niveau_gamification="aucun")
        for _ in range(5):
            vendre(monde, agents["guichetier"])

        self.lancer()

        assert not MissionAccomplie.objects.filter(agent=agents["guichetier"]).exists()


@pytest.mark.django_db
class TestScoreApplicable:
    @pytest.mark.parametrize("role,attendu", [
        ("guichetier", True), ("chauffeur_principal", True), ("qhse", True), ("chef_gare", True), ("drh", True),
        ("pdg", False), ("secretaire_general", False), ("directeur_exploitation", False),
    ])
    def test_seuls_les_postes_qui_ont_quelque_chose_a_marquer_ont_un_score(self, api_client, agents, role, attendu):
        assert etat(api_client, agents[role])["score_applicable"] is attendu
