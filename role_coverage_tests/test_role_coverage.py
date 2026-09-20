"""Audit de couverture des permissions.

Pour chaque rôle du cahier des charges (voir PERMISSIONS.md à la racine du projet),
ce module vérifie au minimum : consultation, création, modification, et tentative
d'accès à une autre compagnie — sur un endpoint représentatif de ce que ce rôle est
censé pouvoir faire (ou ne pas faire).
"""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from personnel_roulant.models import FeuilleDeRoute, GraviteIncident, Incident, StatutIncident, TypeIncident


def _creer_feuille_personnelle(company, ligne, vehicule, chauffeur, suffixe):
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company,
        date_heure=timezone.now() + datetime.timedelta(hours=5), statut=DepartStatut.PLANIFIE,
    )
    feuille = FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=chauffeur, company=company, heure_depart_prevue=depart.date_heure,
    )
    incident = Incident.objects.create(
        vehicule=vehicule, chauffeur=chauffeur, company=company, type_incident=TypeIncident.RETARD,
        description=f"Incident {suffixe}.", gravite=GraviteIncident.FAIBLE, statut=StatutIncident.OUVERT,
    )
    return depart, feuille, incident


@pytest.mark.django_db
class TestCouvertureParRole:
    def test_pdg(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["pdg"])

        assert api_client.get("/api/lignes/").status_code == 200

        creation = api_client.post(
            "/api/lignes/",
            {
                "nom": "Ligne PDG",
                "gare_depart": monde_a["gare_depart"].id,
                "gare_arrivee": monde_a["gare_arrivee"].id,
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(f"/api/lignes/{monde_a['ligne'].id}/", {"nom": "Ligne modifiée"})
        assert modification.status_code == 200

        assert api_client.get(f"/api/lignes/{monde_b['ligne'].id}/").status_code == 404

    def test_secretaire_general(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["secretaire_general"])

        assert api_client.get("/api/gares/").status_code == 200

        creation = api_client.post("/api/gares/", {"nom": "Gare SG", "ville": "Abidjan"})
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/gares/{monde_a['gare_depart'].id}/", {"ville": "Yamoussoukro"}
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/gares/{monde_b['gare_depart'].id}/").status_code == 404

    def test_qhse(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["qhse"])

        assert api_client.get("/api/tickets/").status_code == 200

        creation = api_client.post(
            "/api/tickets/",
            {
                "depart": monde_a["depart"].id,
                "passager_nom": "Passager QHSE",
                "passager_telephone": "+225",
                "prix": "1000.00",
                "mode_paiement": "especes",
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/tickets/{monde_a['ticket'].id}/", {"passager_nom": "Nom corrigé"}
        )
        assert modification.status_code == 200

        acces_autre_compagnie = api_client.post(
            "/api/tickets/",
            {
                "depart": monde_b["depart"].id,
                "passager_nom": "Intrusion",
                "passager_telephone": "+225",
                "prix": "1000.00",
                "mode_paiement": "especes",
            },
        )
        assert acces_autre_compagnie.status_code == 400

    def test_directeur_exploitation(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["directeur_exploitation"])

        assert api_client.get("/api/vehicules/").status_code == 200

        creation = api_client.post(
            "/api/vehicules/", {"immatriculation": "CI-DE-0001", "capacite": 40, "statut": "disponible"}
        )
        assert creation.status_code == 201

        modification = api_client.patch(f"/api/vehicules/{monde_a['vehicule'].id}/", {"capacite": 45})
        assert modification.status_code == 200

        assert api_client.get(f"/api/vehicules/{monde_b['vehicule'].id}/").status_code == 404

    def test_chef_gare(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["chef_gare"])

        assert api_client.get(f"/api/gares/{monde_a['gare_depart'].id}/").status_code == 200

        creation = api_client.post("/api/gares/", {"nom": "Gare Chef", "ville": "Abidjan"})
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/gares/{monde_a['gare_depart'].id}/", {"ville": "San-Pédro"}
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/gares/{monde_b['gare_depart'].id}/").status_code == 404

    def test_chef_ligne(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["chef_ligne"])

        assert api_client.get("/api/lignes/").status_code == 200

        creation = api_client.post(
            "/api/lignes/",
            {
                "nom": "Ligne CL",
                "gare_depart": monde_a["gare_depart"].id,
                "gare_arrivee": monde_a["gare_arrivee"].id,
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(f"/api/lignes/{monde_a['ligne'].id}/", {"nom": "Ligne CL modifiée"})
        assert modification.status_code == 200

        assert api_client.get(f"/api/lignes/{monde_b['ligne'].id}/").status_code == 404

    def test_guichetier(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["guichetier"])

        assert api_client.get("/api/tickets/").status_code == 200

        creation = api_client.post(
            "/api/tickets/",
            {
                "depart": monde_a["depart"].id,
                "passager_nom": "Passager Guichet",
                "passager_telephone": "+225",
                "prix": "2000.00",
                "mode_paiement": "mobile_money",
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/tickets/{monde_a['ticket'].id}/", {"passager_nom": "Nom corrigé"}
        )
        assert modification.status_code == 200

        acces_autre_compagnie = api_client.post(
            "/api/tickets/",
            {
                "depart": monde_b["depart"].id,
                "passager_nom": "Intrusion",
                "passager_telephone": "+225",
                "prix": "2000.00",
                "mode_paiement": "especes",
            },
        )
        assert acces_autre_compagnie.status_code == 400

    def test_bagagiste(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["bagagiste"])

        assert api_client.get("/api/tickets/").status_code == 200

        creation = api_client.post(
            "/api/tickets/",
            {
                "depart": monde_a["depart"].id,
                "passager_nom": "Intrus",
                "passager_telephone": "+225",
                "prix": "1000.00",
                "mode_paiement": "especes",
            },
        )
        assert creation.status_code == 403

        modification = api_client.patch(
            f"/api/tickets/{monde_a['ticket'].id}/", {"passager_nom": "Intrus"}
        )
        assert modification.status_code == 403

        assert api_client.get(f"/api/tickets/{monde_b['ticket'].id}/").status_code == 404

    def test_chauffeur_principal(self, api_client, utilisateurs_a, monde_a, monde_b, company_a):
        chauffeur = utilisateurs_a["chauffeur_principal"]
        _, feuille, _ = _creer_feuille_personnelle(
            company_a, monde_a["ligne"], monde_a["vehicule"], chauffeur, "CP"
        )
        api_client.force_authenticate(user=chauffeur)

        assert api_client.get(f"/api/feuilles-de-route/{feuille.id}/").status_code == 200

        creation = api_client.post(
            "/api/incidents/",
            {
                "vehicule": monde_a["vehicule"].id,
                "chauffeur": chauffeur.id,
                "type_incident": "panne",
                "description": "Panne signalée par le chauffeur.",
                "gravite": "moyenne",
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/feuilles-de-route/{feuille.id}/",
            {"heure_arrivee_prevue": feuille.heure_depart_prevue.isoformat()},
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/feuilles-de-route/{monde_b['feuille'].id}/").status_code == 404

    def test_chauffeur_relais(self, api_client, utilisateurs_a, monde_a, monde_b, company_a):
        chauffeur = utilisateurs_a["chauffeur_relais"]
        _, feuille, _ = _creer_feuille_personnelle(
            company_a, monde_a["ligne"], monde_a["vehicule"], chauffeur, "CR"
        )
        api_client.force_authenticate(user=chauffeur)

        assert api_client.get(f"/api/feuilles-de-route/{feuille.id}/").status_code == 200

        creation = api_client.post(
            "/api/incidents/",
            {
                "vehicule": monde_a["vehicule"].id,
                "chauffeur": chauffeur.id,
                "type_incident": "retard",
                "description": "Retard signalé par le chauffeur relais.",
                "gravite": "faible",
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/feuilles-de-route/{feuille.id}/",
            {"heure_arrivee_prevue": feuille.heure_depart_prevue.isoformat()},
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/feuilles-de-route/{monde_b['feuille'].id}/").status_code == 404

    def test_controleur_ligne(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["controleur_ligne"])

        assert api_client.get("/api/incidents/").status_code == 200

        creation = api_client.post(
            "/api/incidents/",
            {
                "vehicule": monde_a["vehicule"].id,
                "chauffeur": monde_a["chauffeur"].id,
                "type_incident": "autre",
                "description": "Anomalie constatée lors du contrôle.",
                "gravite": "moyenne",
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/incidents/{monde_a['incident'].id}/", {"statut": "traite"}
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/incidents/{monde_b['incident'].id}/").status_code == 404

    def test_directeur_technique(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["directeur_technique"])

        assert api_client.get("/api/vehicules/").status_code == 200

        creation = api_client.post(
            "/api/ordres-reparation/",
            {
                "vehicule": monde_a["vehicule"].id,
                "description": "Révision technique.",
                "mecanicien": monde_a["mecanicien"].id,
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(f"/api/vehicules/{monde_a['vehicule'].id}/", {"capacite": 50})
        assert modification.status_code == 200

        assert api_client.get(f"/api/vehicules/{monde_b['vehicule'].id}/").status_code == 404

    def test_magasinier(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["magasinier"])

        assert api_client.get("/api/pieces/").status_code == 200

        creation = api_client.post(
            "/api/sorties-pieces/",
            {"ordre_reparation": monde_a["ordre"].id, "piece": monde_a["piece"].id, "quantite": 1},
        )
        assert creation.status_code == 201

        modification = api_client.patch(f"/api/pieces/{monde_a['piece'].id}/", {"seuil_alerte": 3})
        assert modification.status_code == 200

        assert api_client.get(f"/api/pieces/{monde_b['piece'].id}/").status_code == 404

    def test_chef_atelier(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["chef_atelier"])

        assert api_client.get("/api/ordres-reparation/").status_code == 200

        creation = api_client.post(
            "/api/ordres-reparation/",
            {
                "vehicule": monde_a["vehicule"].id,
                "description": "Diagnostic moteur.",
                "mecanicien": monde_a["mecanicien"].id,
            },
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/ordres-reparation/{monde_a['ordre'].id}/", {"temps_passe_minutes": 90}
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/ordres-reparation/{monde_b['ordre'].id}/").status_code == 404

    def test_drh(self, api_client, utilisateurs_a, monde_a, monde_b, user_factory, company_a):
        from core.models import Role

        api_client.force_authenticate(user=utilisateurs_a["drh"])

        assert api_client.get("/api/dossiers-agents/").status_code == 200

        nouvel_agent = user_factory("agent_sans_dossier_drh", Role.BAGAGISTE, company=company_a)
        creation = api_client.post(
            "/api/dossiers-agents/",
            {"agent": nouvel_agent.id, "date_embauche": "2024-01-01", "poste": "Bagagiste"},
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/dossiers-agents/{monde_a['dossier'].id}/", {"notes_rh": "Suivi RH à jour."}
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/dossiers-agents/{monde_b['dossier'].id}/").status_code == 404

    def test_directeur_financier(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["directeur_financier"])
        today = timezone.localdate().isoformat()

        consultation = api_client.get(
            f"/api/synthese-financiere/?date_debut={today}&date_fin={today}"
        )
        assert consultation.status_code == 200
        montants = {g["gare_id"]: float(g["montant_total"]) for g in consultation.data["gares"]}
        assert montants.get(monde_a["gare_depart"].id) == 5000.00
        assert monde_b["gare_depart"].id not in montants

        creation_refusee = api_client.post(
            "/api/tickets/",
            {
                "depart": monde_a["depart"].id,
                "passager_nom": "Intrus finance",
                "passager_telephone": "+225",
                "prix": "1000.00",
                "mode_paiement": "especes",
            },
        )
        assert creation_refusee.status_code == 403

        modification_refusee = api_client.patch(f"/api/gares/{monde_a['gare_depart'].id}/", {"ville": "X"})
        assert modification_refusee.status_code == 403

    def test_responsable_juridique(self, api_client, utilisateurs_a, monde_a, monde_b):
        api_client.force_authenticate(user=utilisateurs_a["responsable_juridique"])

        assert api_client.get("/api/assurances/").status_code == 200

        creation = api_client.post(
            "/api/sinistres/",
            {"vehicule": monde_a["vehicule"].id, "description": "Bris de glace."},
        )
        assert creation.status_code == 201

        modification = api_client.patch(
            f"/api/assurances/{monde_a['assurance'].id}/", {"numero_police": "POL-MODIFIEE"}
        )
        assert modification.status_code == 200

        assert api_client.get(f"/api/assurances/{monde_b['assurance'].id}/").status_code == 404
