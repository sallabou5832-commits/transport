"""La configuration a de vrais effets, contrôlés par le serveur : désactiver une fonction ne se contente pas de cacher un
bouton, et le planning assisté est optionnel."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from configuration.tests.conftest import regler_agent, regler_poste
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut


@pytest.fixture
def reseau(company_a, agents):
    depart_gare = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=agents["chef_gare"])
    arrivee_gare = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=depart_gare, gare_arrivee=arrivee_gare, company=company_a)
    vehicule = Vehicule.objects.create(immatriculation="CI-8000-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company_a)
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=agents["chauffeur_principal"], company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=3), statut=DepartStatut.PLANIFIE,
    )
    FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=agents["chauffeur_principal"], company=company_a, heure_depart_prevue=depart.date_heure
    )
    return {"ligne": ligne, "vehicule": vehicule, "depart": depart}


def vendre(api_client, utilisateur, reseau):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(
        "/api/tickets/",
        {"depart": reseau["depart"].id, "passager_nom": "Awa", "passager_telephone": "0700000001", "prix": "5000", "mode_paiement": "especes"},
    )


@pytest.mark.django_db
class TestFonctionsRetirees:
    def test_un_guichetier_sans_la_vente_ne_vend_plus(self, api_client, agents, reseau):
        regler_poste(api_client, agents["chef_gare"], "guichetier", fonctions_desactivees=["vente_ticket"])

        reponse = vendre(api_client, agents["guichetier"], reseau)

        assert reponse.status_code == 403 and "désactivée pour votre poste" in reponse.data["detail"]
        assert "vendre des tickets" in reponse.data["detail"].lower()

    def test_les_autres_postes_continuent_de_vendre(self, api_client, agents, reseau):
        regler_poste(api_client, agents["chef_gare"], "guichetier", fonctions_desactivees=["vente_ticket"])

        assert vendre(api_client, agents["chef_gare"], reseau).status_code == 201

    def test_remettre_la_fonction_la_restaure(self, api_client, agents, reseau):
        regler_poste(api_client, agents["chef_gare"], "guichetier", fonctions_desactivees=["vente_ticket"])
        regler_poste(api_client, agents["chef_gare"], "guichetier", fonctions_desactivees=[])

        assert vendre(api_client, agents["guichetier"], reseau).status_code == 201

    def test_le_retrait_peut_viser_un_seul_agent(self, api_client, agents, reseau, user_factory, company_a):
        autre = user_factory("guichetier_config_2", "guichetier", company=company_a)
        regler_agent(api_client, agents["chef_gare"], agents["guichetier"], fonctions_desactivees=["vente_ticket"])

        assert vendre(api_client, agents["guichetier"], reseau).status_code == 403
        assert vendre(api_client, autre, reseau).status_code == 201

    def test_le_retrait_du_poste_et_celui_de_l_agent_se_cumulent(self, api_client, agents, reseau):
        regler_poste(api_client, agents["chef_gare"], "guichetier", fonctions_desactivees=["cloture_caisse"])
        regler_agent(api_client, agents["chef_gare"], agents["guichetier"], fonctions_desactivees=["vente_ticket"])
        api_client.force_authenticate(user=agents["guichetier"])

        config = api_client.get("/api/configuration/moi/").data

        assert config["fonctions_desactivees"] == ["cloture_caisse", "vente_ticket"]

    def test_le_bagagiste_sans_l_enregistrement_ne_prend_plus_de_colis(self, api_client, agents, reseau):
        regler_poste(api_client, agents["chef_gare"], "bagagiste", fonctions_desactivees=["enregistrement_colis"])
        api_client.force_authenticate(user=agents["bagagiste"])

        reponse = api_client.post(
            "/api/colis/",
            {"depart": reseau["depart"].id, "description": "Carton", "poids_kg": "5", "expediteur_nom": "A",
             "destinataire_nom": "B", "destinataire_telephone": "0700000003"},
        )

        assert reponse.status_code == 403 and "désactivée" in reponse.data["detail"]

    def test_le_chef_de_ligne_sans_la_planification_ne_planifie_plus(self, api_client, agents, reseau):
        regler_poste(api_client, agents["directeur_exploitation"], "chef_ligne", fonctions_desactivees=["planification_departs"])
        api_client.force_authenticate(user=agents["chef_ligne"])

        reponse = api_client.post(
            "/api/departs/planifier/",
            {"ligne": reseau["ligne"].id, "vehicule": reseau["vehicule"].id, "chauffeur": agents["chauffeur_principal"].id,
             "date_heure": (timezone.now() + datetime.timedelta(days=2)).isoformat()},
        )

        assert reponse.status_code == 403 and "désactivée" in reponse.data["detail"]


@pytest.mark.django_db
class TestPlanningAssiste:
    def remplacants(self, api_client, utilisateur, reseau):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get(f"/api/departs/{reseau['depart'].id}/remplacants-possibles/")

    def test_par_defaut_le_systeme_propose_un_remplacant(self, api_client, agents, reseau):
        assert self.remplacants(api_client, agents["chef_ligne"], reseau).status_code == 200

    def test_en_mode_manuel_le_regulateur_choisit_seul(self, api_client, agents, reseau):
        regler_poste(api_client, agents["directeur_exploitation"], "chef_ligne", niveau_automatisation="manuel")

        reponse = self.remplacants(api_client, agents["chef_ligne"], reseau)

        assert reponse.status_code == 403 and "planning assisté est désactivé" in reponse.data["detail"]

    def test_le_reglage_d_un_chef_de_ligne_ne_prive_pas_les_autres_regulateurs(self, api_client, agents, reseau):
        regler_poste(api_client, agents["directeur_exploitation"], "chef_ligne", niveau_automatisation="manuel")

        assert self.remplacants(api_client, agents["chef_gare"], reseau).status_code == 200

    def test_le_mode_automatique_garde_l_assistance(self, api_client, agents, reseau):
        regler_poste(api_client, agents["directeur_exploitation"], "chef_ligne", niveau_automatisation="automatique")

        assert self.remplacants(api_client, agents["chef_ligne"], reseau).status_code == 200

    def test_un_agent_a_l_aise_peut_etre_plus_automatise_que_son_poste(self, api_client, agents, reseau):
        regler_poste(api_client, agents["directeur_exploitation"], "chef_ligne", niveau_automatisation="manuel")
        regler_agent(api_client, agents["directeur_exploitation"], agents["chef_ligne"], niveau_automatisation="assiste")

        assert self.remplacants(api_client, agents["chef_ligne"], reseau).status_code == 200
