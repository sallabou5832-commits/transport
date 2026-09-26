"""Le QHSE bloque le départ d'un véhicule en défaut de sécurité, avec notification immédiate au chef de gare et
au chef d'atelier concernés (cahier des charges, poste Responsable QHSE)."""

import pytest

from alertes.tests.conftest import alertes_de
from personnel_roulant.models import BlocageSecurite
from reseau.models import VehiculeStatut


@pytest.fixture
def bloquer(api_client, agents, reseau_a):
    def _bloquer(role="qhse", **champs):
        api_client.force_authenticate(user=agents[role])
        return api_client.post(
            "/api/blocages-securite/",
            {"vehicule": reseau_a["vehicule"].id, "motif": "Fissure du châssis constatée", **champs},
        )

    return _bloquer


@pytest.mark.django_db
class TestPoserUnBlocage:
    def test_le_qhse_bloque_le_vehicule(self, bloquer, reseau_a):
        reponse = bloquer()

        assert reponse.status_code == 201
        assert reponse.data["est_actif"] is True
        assert reponse.data["vehicule_immatriculation"] == "CI-4000-AA"
        reseau_a["vehicule"].refresh_from_db()
        assert reseau_a["vehicule"].statut == VehiculeStatut.BLOQUE_SECURITE

    def test_le_chef_de_gare_et_le_chef_d_atelier_sont_prevenus_aussitot(self, bloquer, api_client, agents):
        bloquer()

        for role in ("chef_gare", "chef_atelier", "directeur_technique", "chef_ligne"):
            visibles = alertes_de(api_client, agents[role])
            assert len(visibles) == 1, role
            assert visibles[0]["titre"] == "Départ bloqué par le QHSE : CI-4000-AA"
            assert "Fissure du châssis" in visibles[0]["message"]
        assert alertes_de(api_client, agents["guichetier"]) == []

    def test_le_chauffeur_ne_peut_plus_demarrer(self, bloquer, api_client, agents, reseau_a):
        bloquer()
        api_client.force_authenticate(user=agents["chauffeur_principal"])

        reponse = api_client.post(f"/api/feuilles-de-route/{reseau_a['feuille'].id}/demarrer/")

        assert reponse.status_code == 400
        assert "bloqué" in str(reponse.data)

    @pytest.mark.parametrize(
        "role", ["pdg", "directeur_exploitation", "chef_gare", "chef_ligne", "chef_atelier", "directeur_technique",
                 "chauffeur_principal", "guichetier"]
    )
    def test_seul_le_qhse_bloque(self, bloquer, role, reseau_a):
        assert bloquer(role).status_code == 403
        reseau_a["vehicule"].refresh_from_db()
        assert reseau_a["vehicule"].statut == VehiculeStatut.DISPONIBLE

    def test_le_motif_est_obligatoire(self, bloquer):
        assert bloquer(motif="  ").status_code == 400
        assert bloquer(motif="mal").status_code == 400

    @pytest.mark.parametrize("statut", [VehiculeStatut.EN_LIGNE, VehiculeStatut.EN_MAINTENANCE, VehiculeStatut.BLOQUE_SECURITE])
    def test_un_vehicule_deja_immobilise_ou_en_route_ne_se_bloque_pas(self, bloquer, reseau_a, statut):
        reseau_a["vehicule"].statut = statut
        reseau_a["vehicule"].save()

        assert bloquer().status_code == 400
        assert not BlocageSecurite.objects.exists()

    def test_on_ne_bloque_pas_le_vehicule_d_une_autre_compagnie(self, api_client, agents, company_b):
        from reseau.models import Vehicule

        etranger = Vehicule.objects.create(immatriculation="CI-9999-ZZ", capacite=10, company=company_b)
        api_client.force_authenticate(user=agents["qhse"])

        reponse = api_client.post("/api/blocages-securite/", {"vehicule": etranger.id, "motif": "Pneus lisses"})

        assert reponse.status_code == 400
        etranger.refresh_from_db()
        assert etranger.statut == VehiculeStatut.DISPONIBLE

    def test_le_depart_cite_doit_etre_celui_du_vehicule(self, bloquer, reseau_a, company_a, agents):
        from reseau.models import Vehicule
        from billetterie.models import Depart

        autre = Vehicule.objects.create(immatriculation="CI-4002-AA", capacite=20, company=company_a)
        depart_autre = Depart.objects.create(
            ligne=reseau_a["ligne"], vehicule=autre, chauffeur=agents["chauffeur_principal"], company=company_a,
            date_heure=reseau_a["depart"].date_heure,
        )

        assert bloquer(depart=depart_autre.id).status_code == 400
        assert bloquer(depart=reseau_a["depart"].id).status_code == 201

    def test_ni_modification_ni_suppression(self, bloquer, api_client):
        blocage = bloquer().data

        assert api_client.patch(f"/api/blocages-securite/{blocage['id']}/", {"motif": "Autre"}).status_code == 405
        assert api_client.delete(f"/api/blocages-securite/{blocage['id']}/").status_code == 405

    def test_tout_le_monde_peut_lire_les_blocages_de_sa_compagnie(self, bloquer, api_client, agents):
        bloquer()
        api_client.force_authenticate(user=agents["guichetier"])

        assert len(api_client.get("/api/blocages-securite/").data) == 1

    def test_le_blocage_est_trace_dans_le_journal_d_audit(self, bloquer):
        from audit.models import JournalAudit

        bloquer()

        assert JournalAudit.objects.filter(objet_type="personnel_roulant.blocagesecurite", action="creation").exists()


@pytest.mark.django_db
class TestLeverUnBlocage:
    def test_le_qhse_leve_et_le_vehicule_redevient_disponible(self, bloquer, api_client, agents, reseau_a):
        blocage = bloquer().data

        reponse = api_client.post(f"/api/blocages-securite/{blocage['id']}/lever/", {"motif": "Châssis réparé et contrôlé"})

        assert reponse.status_code == 200
        assert reponse.data["est_actif"] is False and reponse.data["motif_levee"] == "Châssis réparé et contrôlé"
        reseau_a["vehicule"].refresh_from_db()
        assert reseau_a["vehicule"].statut == VehiculeStatut.DISPONIBLE

    def test_la_levee_prévient_l_atelier_et_la_gare(self, bloquer, api_client, agents):
        blocage = bloquer().data
        api_client.post(f"/api/blocages-securite/{blocage['id']}/lever/", {"motif": "Réparé et contrôlé"})

        titres = [a["titre"] for a in alertes_de(api_client, agents["chef_gare"])]
        assert "Blocage levé : CI-4000-AA" in titres

    def test_le_motif_de_levee_est_obligatoire(self, bloquer, api_client):
        blocage = bloquer().data

        assert api_client.post(f"/api/blocages-securite/{blocage['id']}/lever/", {}).status_code == 400

    def test_on_ne_leve_pas_deux_fois(self, bloquer, api_client):
        blocage = bloquer().data
        api_client.post(f"/api/blocages-securite/{blocage['id']}/lever/", {"motif": "Réparé et contrôlé"})

        assert api_client.post(f"/api/blocages-securite/{blocage['id']}/lever/", {"motif": "Encore"}).status_code == 400

    def test_seul_le_qhse_leve(self, bloquer, api_client, agents):
        blocage = bloquer().data
        api_client.force_authenticate(user=agents["chef_atelier"])

        assert api_client.post(f"/api/blocages-securite/{blocage['id']}/lever/", {"motif": "Je le libère"}).status_code == 403

    def test_un_vehicule_passe_a_l_atelier_entre_temps_reste_immobilise(self, bloquer, api_client, reseau_a):
        blocage = bloquer().data
        reseau_a["vehicule"].statut = VehiculeStatut.EN_MAINTENANCE
        reseau_a["vehicule"].save()

        api_client.post(f"/api/blocages-securite/{blocage['id']}/lever/", {"motif": "Contrôle terminé"})

        reseau_a["vehicule"].refresh_from_db()
        assert reseau_a["vehicule"].statut == VehiculeStatut.EN_MAINTENANCE

    def test_on_peut_rebloquer_apres_la_levee(self, bloquer, api_client):
        premier = bloquer().data
        api_client.post(f"/api/blocages-securite/{premier['id']}/lever/", {"motif": "Réparé et contrôlé"})

        assert bloquer(motif="Nouvelle fissure").status_code == 201
