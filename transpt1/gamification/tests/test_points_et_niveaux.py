"""Points, niveaux : le score se recalcule à partir de ce que l'agent a réellement fait."""

import datetime

import pytest
from django.utils import timezone

from colis.models import Colis, StatutColis
from gamification.moteur import niveau_pour, points_agent
from gamification.tests.conftest import etat, trajet, vendre
from maintenance.models import OrdreReparation, StatutOrdreReparation


class TestNiveaux:
    @pytest.mark.parametrize(
        "points,numero,nom",
        [(0, 1, "Recrue"), (49, 1, "Recrue"), (50, 2, "Apprenti"), (149, 2, "Apprenti"), (150, 3, "Confirmé"),
         (3599, 9, "Légende"), (3600, 10, "Icône"), (4599, 10, "Icône"), (4600, 11, "Icône"), (10000, 16, "Icône"),
         (-40, 1, "Recrue")],
    )
    def test_le_niveau_suit_les_seuils(self, points, numero, nom):
        niveau = niveau_pour(points)

        assert (niveau["numero"], niveau["nom"]) == (numero, nom)

    def test_la_progression_vers_le_niveau_suivant(self):
        niveau = niveau_pour(100)  # entre 50 et 150

        assert niveau["points_du_niveau"] == 50 and niveau["points_niveau_suivant"] == 150
        assert niveau["progression_pourcent"] == 50

    def test_apres_le_dernier_seuil_un_niveau_de_plus_tous_les_mille_points(self):
        assert niveau_pour(4600)["points_du_niveau"] == 4600 and niveau_pour(4600)["points_niveau_suivant"] == 5600


@pytest.mark.django_db
class TestPointsParPoste:
    def test_guichetier_un_point_par_ticket_et_moins_cinq_par_erreur(self, agents, monde):
        for _ in range(3):
            vendre(monde, agents["guichetier"])
        vendre(monde, agents["guichetier"], statut="annule")

        points = points_agent(agents["guichetier"])

        assert points["total"] == 3 - 5
        assert {ligne["code"]: ligne["nombre"] for ligne in points["detail"]} == {"ticket_vendu": 3, "ticket_annule": 1}

    def test_une_annulation_retire_des_points_toute_seule(self, agents, monde):
        ticket = vendre(monde, agents["guichetier"])
        avant = points_agent(agents["guichetier"])["total"]

        type(ticket).objects.filter(pk=ticket.pk).update(statut="annule")

        assert avant == 1 and points_agent(agents["guichetier"])["total"] == -5

    def test_le_score_affiche_ne_descend_jamais_sous_zero(self, api_client, agents, monde):
        vendre(monde, agents["guichetier"], statut="annule")

        assert etat(api_client, agents["guichetier"])["points"] == 0

    def test_chauffeur_trajet_a_l_heure_sans_incident_avec_checklist(self, agents, monde):
        trajet(monde, agents["chauffeur_principal"], retard_minutes=5, checklist=True)

        assert points_agent(agents["chauffeur_principal"])["total"] == 10 + 5 + 3

    def test_chauffeur_un_retard_coute_des_points_et_un_incident_prive_du_bonus_sans_incident(self, agents, monde):
        from personnel_roulant.models import Incident

        feuille = trajet(monde, agents["chauffeur_principal"], retard_minutes=30)
        Incident.objects.create(
            feuille_de_route=feuille, vehicule=monde["vehicule"], chauffeur=agents["chauffeur_principal"],
            company=agents["chauffeur_principal"].company, type_incident="panne", description="Panne", gravite="faible",
        )

        assert points_agent(agents["chauffeur_principal"])["total"] == -3  # en retard, et pas « sans incident »

    def test_dix_minutes_de_retard_restent_dans_la_tolerance(self, agents, monde):
        trajet(monde, agents["chauffeur_principal"], retard_minutes=10)

        assert points_agent(agents["chauffeur_principal"])["total"] == 10 + 5

    def test_un_trajet_pas_termine_ne_compte_pas(self, agents, monde):
        feuille = trajet(monde, agents["chauffeur_principal"])
        feuille.heure_arrivee_reelle = None
        feuille.save()

        assert points_agent(agents["chauffeur_principal"])["total"] == 0

    def test_mecanicien_dix_points_par_intervention_cloturee(self, agents, monde, company_a):
        for numero in range(2):
            OrdreReparation.objects.create(
                vehicule=monde["vehicule"], company=company_a, description=f"Révision {numero}", mecanicien=agents["mecanicien"],
                statut=StatutOrdreReparation.TERMINE,
            )
        OrdreReparation.objects.create(
            vehicule=monde["vehicule"], company=company_a, description="En cours", mecanicien=agents["mecanicien"],
            statut=StatutOrdreReparation.EN_COURS,
        )

        assert points_agent(agents["mecanicien"])["total"] == 20

    def test_bagagiste_colis_enregistre_charge_remis_et_annule(self, agents, monde, company_a):
        def colis(**champs):
            c = Colis(
                company=company_a, depart=monde["depart"], description="Carton", poids_kg=5, expediteur_nom="A",
                destinataire_nom="B", destinataire_telephone="0700000003", enregistre_par=agents["bagagiste"], **champs,
            )
            c.definir_code("ABC234")
            c.save()
            return c

        colis()  # enregistré : +2
        colis(statut=StatutColis.CHARGE, charge_par=agents["bagagiste"], charge_le=timezone.now())  # +2 +1
        colis(statut=StatutColis.RETIRE, retire_par=agents["bagagiste"], retire_le=timezone.now())  # +2 +3
        colis(statut=StatutColis.ANNULE, annule_le=timezone.now())  # +2 -5

        assert points_agent(agents["bagagiste"])["total"] == 2 + (2 + 1) + (2 + 3) + (2 - 5)

    def test_qhse_incident_traite_et_depart_bloque(self, api_client, agents, monde, company_a):
        from personnel_roulant.models import Incident

        incident = Incident.objects.create(
            vehicule=monde["vehicule"], chauffeur=agents["chauffeur_principal"], company=company_a,
            type_incident="retard", description="Retard", gravite="faible",
        )
        api_client.force_authenticate(user=agents["qhse"])
        api_client.patch(f"/api/incidents/{incident.id}/", {"statut": "traite"})
        api_client.post("/api/blocages-securite/", {"vehicule": monde["vehicule"].id, "motif": "Fissure du châssis"})

        assert points_agent(agents["qhse"])["total"] == 5 + 3

    def test_chef_de_ligne_depart_planifie_et_reaffectation(self, api_client, agents, monde, company_a, user_factory):
        api_client.force_authenticate(user=agents["chef_ligne"])
        planifie = api_client.post(
            "/api/departs/planifier/",
            {"ligne": monde["ligne"].id, "vehicule": monde["vehicule"].id, "chauffeur": agents["chauffeur2"].id,
             "date_heure": (timezone.now() + datetime.timedelta(days=2)).isoformat()},
        )
        assert planifie.status_code == 201
        api_client.patch(f"/api/departs/{planifie.data['id']}/", {"chauffeur": agents["chauffeur_principal"].id})

        assert points_agent(agents["chef_ligne"])["total"] == 2 + 3

    def test_chef_de_gare_departs_de_sa_gare_a_l_heure_et_en_retard(self, agents, monde):
        trajet(monde, agents["chauffeur_principal"], retard_minutes=0)
        trajet(monde, agents["chauffeur2"], retard_minutes=0)
        trajet(monde, agents["chauffeur_principal"], retard_minutes=45)

        assert points_agent(agents["chef_gare"])["total"] == 2 + 2 - 1

    def test_drh_dossiers_et_juridique_sinistres_clos(self, api_client, agents, monde, company_a):
        import datetime as dt

        api_client.force_authenticate(user=agents["drh"])
        api_client.post(
            "/api/dossiers-agents/",
            {"agent": agents["guichetier"].id, "date_embauche": dt.date(2022, 1, 1).isoformat(), "poste": "Guichetier"},
        )
        api_client.force_authenticate(user=agents["responsable_juridique"])
        sinistre = api_client.post("/api/sinistres/", {"vehicule": monde["vehicule"].id, "description": "Accrochage"}).data
        api_client.patch(f"/api/sinistres/{sinistre['id']}/", {"statut": "clos"})

        assert points_agent(agents["drh"])["total"] == 2
        assert points_agent(agents["responsable_juridique"])["total"] == 5

    def test_les_postes_sans_regle_n_ont_aucun_point(self, agents):
        assert points_agent(agents["pdg"])["total"] == 0 and points_agent(agents["secretaire_general"])["total"] == 0


@pytest.mark.django_db
class TestPeriode:
    def test_les_points_se_calculent_sur_une_periode(self, agents, monde):
        trajet(monde, agents["chauffeur_principal"], il_y_a=datetime.timedelta(days=40))
        trajet(monde, agents["chauffeur_principal"], il_y_a=datetime.timedelta(days=1))
        maintenant = timezone.now()

        recent = points_agent(agents["chauffeur_principal"], maintenant - datetime.timedelta(days=7), maintenant)
        tout = points_agent(agents["chauffeur_principal"])

        assert recent["total"] == 15 and tout["total"] == 30
