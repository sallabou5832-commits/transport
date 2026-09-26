"""Chaque action d'un pôle qui en concerne un autre prévient ce pôle automatiquement (cahier des charges :
« notification automatique du pôle concerné quand une action le nécessite »)."""

import pytest

from alertes.models import Alerte, TypeAlerte
from alertes.tests.conftest import alertes_de
from reseau.models import VehiculeStatut


def titres(api_client, utilisateur):
    return [alerte["titre"] for alerte in alertes_de(api_client, utilisateur)]


@pytest.mark.django_db
class TestDefautDeChecklist:
    def poser_defaut(self, api_client, agents, reseau_a, item="freins"):
        api_client.force_authenticate(user=agents["chauffeur_principal"])
        return api_client.post(
            "/api/checklists/",
            {"feuille_de_route": reseau_a["feuille"].id, "item": item, "etat": "defaut", "commentaire": "Pédale molle"},
        )

    def test_le_defaut_de_securite_previent_qhse_atelier_regulation_et_gare(self, api_client, agents, reseau_a):
        assert self.poser_defaut(api_client, agents, reseau_a).status_code == 201

        for role in ("qhse", "chef_atelier", "directeur_technique", "chef_ligne", "chef_gare"):
            visibles = alertes_de(api_client, agents[role])
            assert len(visibles) == 1, role
            assert "freins" in visibles[0]["titre"] and "CI-4000-AA" in visibles[0]["titre"]
            assert visibles[0]["gravite"] == "critique"
            assert visibles[0]["type"] == TypeAlerte.DEFAUT_CHECKLIST

    def test_les_autres_postes_ne_sont_pas_derangés(self, api_client, agents, reseau_a):
        self.poser_defaut(api_client, agents, reseau_a)

        for role in ("guichetier", "drh", "magasinier", "mecanicien", "pdg"):
            assert alertes_de(api_client, agents[role]) == [], role

    def test_un_defaut_sans_gravite_pour_la_securite_ne_prévient_personne(self, api_client, agents, reseau_a):
        self.poser_defaut(api_client, agents, reseau_a, item="carburant")

        assert Alerte.objects.count() == 0

    def test_le_chef_de_gare_d_une_autre_gare_n_est_pas_prevenu(
        self, api_client, agents, reseau_a, user_factory, company_a
    ):
        autre_chef = user_factory("chef_gare_autre", "chef_gare", company=company_a)
        self.poser_defaut(api_client, agents, reseau_a)

        assert alertes_de(api_client, autre_chef) == []

    def test_le_blocage_reste_signale_une_seule_fois(self, api_client, agents, reseau_a):
        self.poser_defaut(api_client, agents, reseau_a)
        self.poser_defaut(api_client, agents, reseau_a, item="pneus")  # le véhicule est déjà bloqué

        assert Alerte.objects.count() == 1


@pytest.mark.django_db
class TestIncident:
    def declarer(self, api_client, agents, reseau_a, **champs):
        api_client.force_authenticate(user=agents["chauffeur_principal"])
        donnees = {
            "feuille_de_route": reseau_a["feuille"].id, "vehicule": reseau_a["vehicule"].id,
            "chauffeur": agents["chauffeur_principal"].id, "type_incident": "panne",
            "description": "Le moteur chauffe.", "gravite": "moyenne", **champs,
        }
        return api_client.post("/api/incidents/", donnees)

    def test_une_panne_previent_la_regulation_et_le_technique(self, api_client, agents, reseau_a):
        assert self.declarer(api_client, agents, reseau_a).status_code == 201

        for role in ("chef_ligne", "directeur_technique", "chef_atelier"):
            assert len(alertes_de(api_client, agents[role])) == 1, role
        for role in ("qhse", "directeur_exploitation", "chef_gare"):
            assert alertes_de(api_client, agents[role]) == [], role

    def test_un_incident_grave_remonte_a_la_direction_au_qhse_et_a_la_gare(self, api_client, agents, reseau_a):
        self.declarer(api_client, agents, reseau_a, gravite="grave", type_incident="accident")

        for role in ("chef_ligne", "directeur_technique", "directeur_exploitation", "qhse", "chef_gare"):
            visibles = alertes_de(api_client, agents[role])
            assert len(visibles) == 1, role
            assert visibles[0]["titre"].startswith("Incident grave")
            assert visibles[0]["gravite"] == "critique"

    def test_un_simple_retard_ne_previent_que_la_regulation(self, api_client, agents, reseau_a):
        self.declarer(api_client, agents, reseau_a, type_incident="retard", gravite="faible")

        assert len(alertes_de(api_client, agents["chef_ligne"])) == 1
        assert alertes_de(api_client, agents["directeur_technique"]) == []

    def test_requalifier_un_incident_en_grave_declenche_l_alerte_grave(self, api_client, agents, reseau_a):
        incident = self.declarer(api_client, agents, reseau_a, type_incident="retard", gravite="faible").data
        assert alertes_de(api_client, agents["qhse"]) == []

        api_client.force_authenticate(user=agents["chauffeur_principal"])
        api_client.patch(f"/api/incidents/{incident['id']}/", {"gravite": "grave"})

        assert len(alertes_de(api_client, agents["qhse"])) == 1

    def test_modifier_un_incident_deja_grave_ne_reprevient_pas(self, api_client, agents, reseau_a):
        incident = self.declarer(api_client, agents, reseau_a, gravite="grave").data
        api_client.patch(f"/api/incidents/{incident['id']}/", {"description": "Précision."})

        assert len(alertes_de(api_client, agents["qhse"])) == 1


@pytest.mark.django_db
class TestStock:
    def sortir(self, api_client, agents, ordre, piece, quantite):
        api_client.force_authenticate(user=agents["magasinier"])
        return api_client.post(
            "/api/sorties-pieces/", {"ordre_reparation": ordre.id, "piece": piece.id, "quantite": quantite}
        )

    def test_passer_sous_le_seuil_previent_magasinier_et_technique(self, api_client, agents, ordre, piece):
        assert self.sortir(api_client, agents, ordre, piece, 2).status_code == 201  # 6 -> 4, seuil 5

        for role in ("magasinier", "directeur_technique"):
            visibles = alertes_de(api_client, agents[role])
            assert len(visibles) == 1
            assert visibles[0]["titre"] == "Stock bas : Filtre"
            assert visibles[0]["gravite"] == "attention"

    def test_une_rupture_est_critique(self, api_client, agents, ordre, piece):
        self.sortir(api_client, agents, ordre, piece, 6)

        assert alertes_de(api_client, agents["magasinier"])[0]["titre"] == "Rupture : Filtre"
        assert alertes_de(api_client, agents["magasinier"])[0]["gravite"] == "critique"

    def test_une_sortie_qui_reste_au_dessus_du_seuil_ne_previent_pas(self, api_client, agents, ordre, piece):
        piece.quantite_stock = 20
        piece.save()

        self.sortir(api_client, agents, ordre, piece, 2)

        assert Alerte.objects.count() == 0

    def test_une_piece_deja_sous_le_seuil_ne_re_alerte_pas_a_chaque_sortie(self, api_client, agents, ordre, piece):
        self.sortir(api_client, agents, ordre, piece, 2)
        self.sortir(api_client, agents, ordre, piece, 1)

        assert Alerte.objects.count() == 1


@pytest.mark.django_db
class TestVehiculeLibere:
    def test_la_cloture_de_l_ordre_previent_le_regulateur_et_la_gare(self, api_client, agents, reseau_a, ordre):
        reseau_a["vehicule"].statut = VehiculeStatut.EN_MAINTENANCE
        reseau_a["vehicule"].save()
        api_client.force_authenticate(user=agents["mecanicien"])

        reponse = api_client.patch(
            f"/api/ordres-reparation/{ordre.id}/", {"statut": "termine", "temps_passe_minutes": 60}
        )

        assert reponse.status_code == 200
        for role in ("chef_ligne", "chef_gare"):
            visibles = alertes_de(api_client, agents[role])
            assert [a["titre"] for a in visibles] == ["Véhicule disponible : CI-4000-AA"], role


@pytest.mark.django_db
class TestPenurie:
    def test_aucun_remplacant_previent_le_directeur_des_operations_et_le_chef_de_gare(
        self, api_client, agents, reseau_a
    ):
        # Un seul véhicule et un seul chauffeur dans la compagnie : impossible de remplacer.
        api_client.force_authenticate(user=agents["chef_ligne"])
        reponse = api_client.get(f"/api/departs/{reseau_a['depart'].id}/remplacants-possibles/")

        assert reponse.status_code == 200
        assert reponse.data["vehicules"] == [] and reponse.data["chauffeurs"] == []
        for role in ("directeur_exploitation", "chef_gare"):
            assert sorted(titres(api_client, agents[role])) == [
                "Pénurie de chauffeur : Adjamé-Bouaké",
                "Pénurie de véhicule : Adjamé-Bouaké",
            ], role

    def test_chercher_deux_fois_ne_previent_pas_deux_fois(self, api_client, agents, reseau_a):
        api_client.force_authenticate(user=agents["chef_ligne"])
        for _ in range(3):
            api_client.get(f"/api/departs/{reseau_a['depart'].id}/remplacants-possibles/")

        assert Alerte.objects.filter(type=TypeAlerte.PENURIE).count() == 2

    def test_un_remplacant_disponible_ne_declenche_rien(self, api_client, agents, reseau_a, company_a, user_factory):
        from reseau.models import Vehicule

        Vehicule.objects.create(immatriculation="CI-4001-AA", capacite=30, company=company_a)
        user_factory("chauffeur_dispo", "chauffeur_principal", company=company_a)
        api_client.force_authenticate(user=agents["chef_ligne"])

        api_client.get(f"/api/departs/{reseau_a['depart'].id}/remplacants-possibles/")

        assert Alerte.objects.count() == 0
