"""Le scénario du pilote (SCENARIO_PILOTE.md) joué de bout en bout par l'API, un rôle après l'autre.

Chaque étape utilise le compte du rôle concerné : si une permission ou une règle métier casse le parcours
réel (un guichetier qui vend, un chauffeur qui part, l'atelier qui répare, le PDG qui consulte), ce test
échoue avant le pilote.
"""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from maintenance.models import OrdreReparation, StatutOrdreReparation
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut

ITEMS_CHECKLIST = ["pneus", "freins", "carburant", "eclairage", "direction", "ceintures"]
ROLES = ["guichetier", "chauffeur_principal", "qhse", "chef_atelier", "pdg", "directeur_exploitation"]


@pytest.fixture
def maintenant(monkeypatch):
    fixe = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(timezone, "now", lambda: fixe)
    return fixe


@pytest.fixture
def monde(db, company_a, user_factory, maintenant):
    acteurs = {role: user_factory(f"{role}_pilote", Role(role), company=company_a) for role in ROLES}
    gare_depart = Gare.objects.create(nom="Gare Adjamé", ville="Abidjan", company=company_a)
    gare_arrivee = Gare.objects.create(nom="Gare Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(nom="Abidjan-Bouaké", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company_a)
    vehicule = Vehicule.objects.create(immatriculation="CI-1001-AB", capacite=70, company=company_a)
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=acteurs["chauffeur_principal"], company=company_a,
        date_heure=maintenant + datetime.timedelta(hours=1), statut=DepartStatut.PLANIFIE,
    )
    feuille = FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=acteurs["chauffeur_principal"], company=company_a, heure_depart_prevue=depart.date_heure
    )
    return {**acteurs, "vehicule": vehicule, "depart": depart, "feuille": feuille}


def _vente(client, depart):
    return client.post(
        "/api/tickets/",
        {
            "depart": depart.id, "passager_nom": "Awa Pilote", "passager_telephone": "+2250700000001",
            "prix": "7500", "mode_paiement": "mobile_money",
        },
    )


def _checklist(client, feuille, defauts=()):
    for item in ITEMS_CHECKLIST:
        reponse = client.post(
            "/api/checklists/",
            {"feuille_de_route": feuille.id, "item": item, "etat": "defaut" if item in defauts else "ok"},
        )
        assert reponse.status_code in (200, 201), reponse.data


def _agir(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client


@pytest.mark.django_db
class TestScenarioNominal:
    def test_du_ticket_a_la_consultation_du_pdg(self, api_client, monde):
        # 1. Le guichetier vend un ticket.
        client = _agir(api_client, monde["guichetier"])
        assert _vente(client, monde["depart"]).status_code == 201
        monde["depart"].refresh_from_db()
        assert monde["depart"].places_vendues == 1

        # 2. Le chauffeur remplit sa checklist et part : le départ est en cours, le car en ligne.
        client = _agir(api_client, monde["chauffeur_principal"])
        _checklist(client, monde["feuille"])
        assert client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/").status_code == 200
        monde["depart"].refresh_from_db()
        monde["vehicule"].refresh_from_db()
        assert monde["depart"].statut == DepartStatut.EN_COURS
        assert monde["vehicule"].statut == VehiculeStatut.EN_LIGNE

        # 3. Il déclare un incident grave en route ; le QHSE et l'exploitation le voient.
        incident = client.post(
            "/api/incidents/",
            {
                "feuille_de_route": monde["feuille"].id, "vehicule": monde["vehicule"].id,
                "chauffeur": monde["chauffeur_principal"].id, "type_incident": "panne", "gravite": "grave",
                "description": "Panne moteur à 40 km de Bouaké.",
            },
        )
        assert incident.status_code == 201
        client = _agir(api_client, monde["qhse"])
        assert [i["id"] for i in client.get("/api/dashboard/qhse/").data] == [incident.data["id"]]
        client = _agir(api_client, monde["directeur_exploitation"])
        exploitation = client.get("/api/dashboard/exploitation/").data
        assert exploitation["incidents_ouverts_par_gravite"]["grave"] == 1
        assert exploitation["incidents_graves_ouverts"][0]["chauffeur_nom"] == monde["chauffeur_principal"].username

        # 4. L'atelier ouvre l'ordre de réparation, le démarre puis le clôture.
        client = _agir(api_client, monde["chef_atelier"])
        ordre = client.post(
            "/api/ordres-reparation/",
            {"vehicule": monde["vehicule"].id, "description": "Remplacement de la pompe à eau.", "mecanicien": monde["chef_atelier"].id},
        )
        assert ordre.status_code == 201
        url = f"/api/ordres-reparation/{ordre.data['id']}/"
        assert client.patch(url, {"statut": "en_cours"}).status_code == 200
        assert client.patch(url, {"statut": "termine", "temps_passe_minutes": 90}).status_code == 200
        cloture = OrdreReparation.objects.get(pk=ordre.data["id"])
        assert cloture.statut == StatutOrdreReparation.TERMINE and cloture.date_cloture is not None
        monde["vehicule"].refresh_from_db()
        assert monde["vehicule"].statut == VehiculeStatut.DISPONIBLE  # libéré pour le régulateur

        # 5. Le PDG consulte son tableau de bord : recette du jour et incident grave ouvert.
        client = _agir(api_client, monde["pdg"])
        direction = client.get("/api/dashboard/direction/").data
        assert float(direction["recettes_du_jour"]) == 7500.0
        assert direction["incidents_ouverts_par_gravite_7_jours"]["grave"] == 1

        # 6. Le QHSE clôt l'incident : il disparaît de la direction.
        client = _agir(api_client, monde["qhse"])
        assert client.patch(f"/api/incidents/{incident.data['id']}/", {"statut": "traite"}).status_code == 200
        client = _agir(api_client, monde["pdg"])
        assert client.get("/api/dashboard/direction/").data["incidents_ouverts_par_gravite_7_jours"]["grave"] == 0

        # 7. Le car arrive : le départ est terminé et n'accepte plus de vente.
        client = _agir(api_client, monde["chauffeur_principal"])
        assert client.post(f"/api/feuilles-de-route/{monde['feuille'].id}/arriver/").status_code == 200
        monde["depart"].refresh_from_db()
        assert monde["depart"].statut == DepartStatut.TERMINE
        client = _agir(api_client, monde["guichetier"])
        assert _vente(client, monde["depart"]).status_code == 400


@pytest.mark.django_db
class TestVarianteDefautDeSecurite:
    def test_du_blocage_a_la_reprise(self, api_client, monde):
        url_demarrer = f"/api/feuilles-de-route/{monde['feuille'].id}/demarrer/"

        # Défaut sur les freins : le véhicule est bloqué et le départ refusé.
        chauffeur = _agir(api_client, monde["chauffeur_principal"])
        _checklist(chauffeur, monde["feuille"], defauts={"freins"})
        monde["vehicule"].refresh_from_db()
        assert monde["vehicule"].statut == VehiculeStatut.BLOQUE_SECURITE
        assert chauffeur.post(url_demarrer).status_code == 400

        # L'exploitation voit le véhicule indisponible.
        exploitation = _agir(api_client, monde["directeur_exploitation"]).get("/api/dashboard/exploitation/").data
        assert [(v["immatriculation"], v["statut"]) for v in exploitation["vehicules_indisponibles"]] == [
            ("CI-1001-AB", "bloque_securite")
        ]

        # L'atelier ouvre l'ordre : le véhicule bloqué passe en maintenance ; puis il clôture.
        atelier = _agir(api_client, monde["chef_atelier"])
        ordre = atelier.post(
            "/api/ordres-reparation/",
            {"vehicule": monde["vehicule"].id, "description": "Remplacement des plaquettes.", "mecanicien": monde["chef_atelier"].id},
        )
        assert ordre.status_code == 201
        monde["vehicule"].refresh_from_db()
        assert monde["vehicule"].statut == VehiculeStatut.EN_MAINTENANCE
        atelier.patch(f"/api/ordres-reparation/{ordre.data['id']}/", {"statut": "termine", "temps_passe_minutes": 45})
        monde["vehicule"].refresh_from_db()
        assert monde["vehicule"].statut == VehiculeStatut.DISPONIBLE

        # Le défaut est toujours inscrit sur la feuille : le chauffeur doit le ressaisir « OK » pour repartir.
        chauffeur = _agir(api_client, monde["chauffeur_principal"])
        assert chauffeur.post(url_demarrer).status_code == 400
        _checklist(chauffeur, monde["feuille"])
        assert chauffeur.post(url_demarrer).status_code == 200
        monde["depart"].refresh_from_db()
        assert monde["depart"].statut == DepartStatut.EN_COURS
