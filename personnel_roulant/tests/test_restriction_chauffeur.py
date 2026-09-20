import pytest

from personnel_roulant.models import EtatChecklist, FeuilleDeRoute, Incident, TypeIncident, GraviteIncident


@pytest.mark.django_db
class TestRestrictionChauffeur:
    def test_chauffeur_peut_creer_sa_propre_feuille_de_route(
        self, api_client, chauffeur_a, depart_a
    ):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.post(
            "/api/feuilles-de-route/",
            {
                "depart": depart_a.id,
                "chauffeur": chauffeur_a.id,
                "heure_depart_prevue": depart_a.date_heure.isoformat(),
            },
        )

        assert response.status_code == 201

    def test_chauffeur_ne_peut_pas_creer_feuille_pour_un_autre(
        self, api_client, chauffeur_a, chauffeur_a2, depart_a
    ):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.post(
            "/api/feuilles-de-route/",
            {
                "depart": depart_a.id,
                "chauffeur": chauffeur_a2.id,
                "heure_depart_prevue": depart_a.date_heure.isoformat(),
            },
        )

        assert response.status_code == 400
        assert not FeuilleDeRoute.objects.filter(depart=depart_a).exists()

    def test_chauffeur_ne_peut_pas_modifier_la_feuille_dun_autre(
        self, api_client, chauffeur_a2, feuille_a
    ):
        api_client.force_authenticate(user=chauffeur_a2)

        response = api_client.patch(
            f"/api/feuilles-de-route/{feuille_a.id}/",
            {"heure_arrivee_prevue": feuille_a.heure_depart_prevue.isoformat()},
        )

        assert response.status_code == 403

    def test_role_superieur_peut_creer_une_feuille_pour_un_chauffeur(
        self, api_client, chef_ligne_a, chauffeur_a, depart_a
    ):
        api_client.force_authenticate(user=chef_ligne_a)

        response = api_client.post(
            "/api/feuilles-de-route/",
            {
                "depart": depart_a.id,
                "chauffeur": chauffeur_a.id,
                "heure_depart_prevue": depart_a.date_heure.isoformat(),
            },
        )

        assert response.status_code == 201

    def test_chauffeur_ne_peut_pas_creer_checklist_pour_la_feuille_dun_autre(
        self, api_client, chauffeur_a2, feuille_a
    ):
        api_client.force_authenticate(user=chauffeur_a2)

        response = api_client.post(
            "/api/checklists/",
            {"feuille_de_route": feuille_a.id, "item": "pneus", "etat": EtatChecklist.OK},
        )

        assert response.status_code == 400

    def test_chauffeur_peut_creer_son_propre_incident(
        self, api_client, chauffeur_a, vehicule_a
    ):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.post(
            "/api/incidents/",
            {
                "vehicule": vehicule_a.id,
                "chauffeur": chauffeur_a.id,
                "type_incident": TypeIncident.PANNE,
                "description": "Fuite d'huile en cours de route.",
                "gravite": GraviteIncident.MOYENNE,
            },
        )

        assert response.status_code == 201

    def test_chauffeur_ne_peut_pas_creer_incident_pour_un_autre_chauffeur(
        self, api_client, chauffeur_a, chauffeur_a2, vehicule_a
    ):
        api_client.force_authenticate(user=chauffeur_a)

        response = api_client.post(
            "/api/incidents/",
            {
                "vehicule": vehicule_a.id,
                "chauffeur": chauffeur_a2.id,
                "type_incident": TypeIncident.PANNE,
                "description": "Fuite d'huile en cours de route.",
                "gravite": GraviteIncident.MOYENNE,
            },
        )

        assert response.status_code == 400
        assert not Incident.objects.filter(chauffeur=chauffeur_a2).exists()

    def test_chauffeur_ne_peut_pas_modifier_incident_dun_autre(
        self, api_client, chauffeur_a, chauffeur_a2, vehicule_a
    ):
        incident = Incident.objects.create(
            vehicule=vehicule_a,
            chauffeur=chauffeur_a,
            company=chauffeur_a.company,
            type_incident=TypeIncident.PANNE,
            description="Pneu crevé.",
            gravite=GraviteIncident.FAIBLE,
        )

        api_client.force_authenticate(user=chauffeur_a2)
        response = api_client.patch(f"/api/incidents/{incident.id}/", {"statut": "traite"})

        assert response.status_code == 403
