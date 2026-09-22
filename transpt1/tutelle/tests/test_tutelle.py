"""Échanges avec le Ministère des Transports et les organismes dépendants (OSER, AMUGA, OFT), étape 16 du cahier des
charges : génération automatique des flux (incident grave, échéance d'assurance), isolation entre compagnies, et
accès réservé aux comptes tutelle pour ce qui vient d'eux. Rien ici ne parle à un vrai système du ministère."""

import datetime

import pytest
from django.utils import timezone

from core.models import Role
from personnel_roulant.models import GraviteIncident, Incident, TypeIncident
from reseau.models import Vehicule
from supports.models import Assurance
from tutelle import generation
from tutelle.models import CompteTutelle, DirectionFlux, FluxTutelle, StatutFlux, TypeFlux


@pytest.fixture
def vehicule_a(company_a):
    return Vehicule.objects.create(immatriculation="CI-TUT-001", capacite=40, company=company_a)


@pytest.fixture
def vehicule_b(company_b):
    return Vehicule.objects.create(immatriculation="CI-TUT-002", capacite=40, company=company_b)


@pytest.fixture
def qhse_a(user_factory, company_a):
    return user_factory("qhse_a_tut", Role.QHSE, company=company_a)


@pytest.fixture
def juridique_a(user_factory, company_a):
    return user_factory("juridique_a_tut", Role.RESPONSABLE_JURIDIQUE, company=company_a)


def creer_incident(company, vehicule, chauffeur, gravite=GraviteIncident.GRAVE, **kwargs):
    return Incident.objects.create(
        company=company,
        vehicule=vehicule,
        chauffeur=chauffeur,
        type_incident=TypeIncident.ACCIDENT,
        description="Collision avec un autre véhicule",
        gravite=gravite,
        **kwargs,
    )


def creer_assurance(company, vehicule, jours_avant_echeance):
    return Assurance.objects.create(
        vehicule=vehicule,
        company=company,
        compagnie_assurance="Assurance Générale de Côte d'Ivoire",
        numero_police="POL-2026-001",
        date_echeance=timezone.localdate() + datetime.timedelta(days=jours_avant_echeance),
    )


@pytest.mark.django_db
class TestGenerationAutomatiqueSecurite:
    """Endpoint 2 : un incident grave génère un flux « sécurité » vers la tutelle, tout seul."""

    def test_un_incident_grave_genere_un_flux_securite(self, company_a, vehicule_a, user_factory):
        chauffeur = user_factory("chauffeur_tut_1", Role.CHAUFFEUR_PRINCIPAL, company=company_a)

        incident = creer_incident(company_a, vehicule_a, chauffeur)

        flux = FluxTutelle.objects.get()
        assert flux.company == company_a
        assert flux.type == TypeFlux.SECURITE
        assert flux.direction == DirectionFlux.VERS_TUTELLE
        assert flux.statut == StatutFlux.ENVOYE
        assert flux.contenu["incident_id"] == incident.pk
        assert flux.contenu["vehicule"] == "CI-TUT-001"

    @pytest.mark.parametrize("gravite", [GraviteIncident.FAIBLE, GraviteIncident.MOYENNE])
    def test_un_incident_non_grave_ne_genere_rien(self, company_a, vehicule_a, user_factory, gravite):
        chauffeur = user_factory("chauffeur_tut_2", Role.CHAUFFEUR_PRINCIPAL, company=company_a)

        creer_incident(company_a, vehicule_a, chauffeur, gravite=gravite)

        assert not FluxTutelle.objects.exists()

    def test_requalifie_en_grave_genere_le_flux(self, company_a, vehicule_a, user_factory):
        chauffeur = user_factory("chauffeur_tut_3", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        incident = creer_incident(company_a, vehicule_a, chauffeur, gravite=GraviteIncident.FAIBLE)
        assert not FluxTutelle.objects.exists()

        incident.gravite = GraviteIncident.GRAVE
        incident.save()

        assert FluxTutelle.objects.count() == 1

    def test_un_incident_grave_resauvegarde_ne_duplique_pas_le_flux(self, company_a, vehicule_a, user_factory):
        chauffeur = user_factory("chauffeur_tut_4", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        incident = creer_incident(company_a, vehicule_a, chauffeur)
        assert FluxTutelle.objects.count() == 1

        incident.description = "Précision ajoutée après coup"
        incident.save()

        assert FluxTutelle.objects.count() == 1

    def test_un_echec_de_generation_nempeche_pas_de_declarer_lincident(self, company_a, vehicule_a, user_factory, monkeypatch):
        chauffeur = user_factory("chauffeur_tut_5", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        monkeypatch.setattr(
            "tutelle.signals.generer_flux_securite",
            lambda incident: (_ for _ in ()).throw(RuntimeError("panne du module tutelle")),
        )

        incident = creer_incident(company_a, vehicule_a, chauffeur)

        assert incident.pk is not None
        assert not FluxTutelle.objects.exists()

    def test_le_rattrapage_par_lots_couvre_les_incidents_deja_graves(self, company_a, vehicule_a, user_factory):
        """`generer_flux_securite_incidents_graves` : utile pour un incident créé hors API (script, admin...)."""
        chauffeur = user_factory("chauffeur_tut_6", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        incident = creer_incident(company_a, vehicule_a, chauffeur)
        FluxTutelle.objects.all().delete()  # simule un incident grave jamais transmis

        crees = generation.generer_flux_securite_incidents_graves(company_a)

        assert len(crees) == 1
        assert FluxTutelle.objects.get().contenu["incident_id"] == incident.pk

        # Relancer ne duplique rien.
        assert generation.generer_flux_securite_incidents_graves(company_a) == []
        assert FluxTutelle.objects.count() == 1


@pytest.mark.django_db
class TestGenerationAutomatiqueConformite:
    """Endpoint 3 : une assurance proche de l'échéance génère un flux « conformité » vers la tutelle."""

    @pytest.mark.parametrize("jours", [30, 7, 0, -5])
    def test_une_assurance_proche_ou_expiree_genere_un_flux(self, company_a, vehicule_a, jours):
        assurance = creer_assurance(company_a, vehicule_a, jours)

        crees = generation.generer_flux_conformite_assurances(company_a)

        assert len(crees) == 1
        flux = FluxTutelle.objects.get()
        assert flux.type == TypeFlux.CONFORMITE
        assert flux.direction == DirectionFlux.VERS_TUTELLE
        assert flux.statut == StatutFlux.ENVOYE
        assert flux.contenu["assurance_id"] == assurance.pk

    def test_une_assurance_lointaine_ne_genere_rien(self, company_a, vehicule_a):
        creer_assurance(company_a, vehicule_a, 60)

        crees = generation.generer_flux_conformite_assurances(company_a)

        assert crees == []
        assert not FluxTutelle.objects.exists()

    def test_relancer_la_generation_ne_duplique_rien(self, company_a, vehicule_a):
        creer_assurance(company_a, vehicule_a, 10)

        generation.generer_flux_conformite_assurances(company_a)
        crees = generation.generer_flux_conformite_assurances(company_a)

        assert crees == []
        assert FluxTutelle.objects.count() == 1

    def test_plusieurs_assurances_chacune_son_flux(self, company_a, vehicule_a):
        autre_vehicule = Vehicule.objects.create(immatriculation="CI-TUT-003", capacite=30, company=company_a)
        creer_assurance(company_a, vehicule_a, 15)
        creer_assurance(company_a, autre_vehicule, 5)

        crees = generation.generer_flux_conformite_assurances(company_a)

        assert len(crees) == 2
        assert FluxTutelle.objects.filter(type=TypeFlux.CONFORMITE).count() == 2


@pytest.mark.django_db
class TestEndpointGenerer:
    """`POST /api/tutelle/generer/` : rattrapage à la demande, pour la compagnie de l'appelant seulement."""

    def test_le_qhse_declenche_la_generation(self, api_client, qhse_a, company_a, vehicule_a, user_factory):
        chauffeur = user_factory("chauffeur_tut_7", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        creer_incident(company_a, vehicule_a, chauffeur)
        creer_assurance(company_a, vehicule_a, 10)
        FluxTutelle.objects.all().delete()
        api_client.force_authenticate(user=qhse_a)

        reponse = api_client.post("/api/tutelle/generer/")

        assert reponse.status_code == 201
        assert reponse.data == {"securite": 1, "conformite": 1}

    def test_le_responsable_juridique_declenche_aussi_la_generation(self, api_client, juridique_a, company_a, vehicule_a):
        creer_assurance(company_a, vehicule_a, 5)

        api_client.force_authenticate(user=juridique_a)
        reponse = api_client.post("/api/tutelle/generer/")

        assert reponse.status_code == 201
        assert reponse.data["conformite"] == 1

    @pytest.mark.parametrize("role", ["pdg", "guichetier", "chef_gare", "directeur_technique"])
    def test_les_autres_postes_ne_declenchent_rien(self, api_client, user_factory, company_a, role):
        agent = user_factory(f"{role}_tut_generer", Role(role), company=company_a)
        api_client.force_authenticate(user=agent)

        assert api_client.post("/api/tutelle/generer/").status_code == 403

    def test_sans_authentification_refuse(self, api_client):
        assert api_client.post("/api/tutelle/generer/").status_code == 401


@pytest.mark.django_db
class TestIsolationEntreCompagnies:
    def test_generer_pour_une_compagnie_ne_touche_pas_lautre(self, company_a, company_b, vehicule_a, vehicule_b, user_factory):
        chauffeur_a = user_factory("chauffeur_tut_iso_a", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        creer_incident(company_a, vehicule_a, chauffeur_a)
        creer_assurance(company_b, vehicule_b, 5)

        assert FluxTutelle.objects.filter(company=company_a).count() == 1
        assert FluxTutelle.objects.filter(company=company_b).count() == 0

        generation.generer_flux_conformite_assurances(company_a)
        assert FluxTutelle.objects.filter(company=company_a, type=TypeFlux.CONFORMITE).count() == 0

        generation.generer_flux_conformite_assurances(company_b)
        assert FluxTutelle.objects.filter(company=company_b, type=TypeFlux.CONFORMITE).count() == 1

    def test_un_poste_ne_voit_que_les_flux_de_sa_compagnie(
        self, api_client, qhse_a, company_a, company_b, vehicule_a, vehicule_b, user_factory
    ):
        chauffeur_a = user_factory("chauffeur_tut_iso_b1", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        chauffeur_b = user_factory("chauffeur_tut_iso_b2", Role.CHAUFFEUR_PRINCIPAL, company=company_b)
        creer_incident(company_a, vehicule_a, chauffeur_a)
        creer_incident(company_b, vehicule_b, chauffeur_b)

        api_client.force_authenticate(user=qhse_a)
        reponse = api_client.get("/api/flux-tutelle/")

        assert len(reponse.data) == 1
        assert reponse.data[0]["company"] == company_a.pk

    def test_impossible_de_traiter_le_flux_dune_autre_compagnie(
        self, api_client, qhse_a, company_a, company_b, vehicule_b, user_factory
    ):
        chauffeur_b = user_factory("chauffeur_tut_iso_b3", Role.CHAUFFEUR_PRINCIPAL, company=company_b)
        creer_incident(company_b, vehicule_b, chauffeur_b)
        flux_b = FluxTutelle.objects.get()

        api_client.force_authenticate(user=qhse_a)
        reponse = api_client.post(f"/api/flux-tutelle/{flux_b.pk}/traiter/")

        assert reponse.status_code == 404

    def test_le_flux_entrant_de_la_tutelle_ne_vise_quune_compagnie(self, api_client, company_a, company_b, qhse_a, user_factory):
        _, cle = CompteTutelle.creer("Ministère des Transports")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        api_client.post(
            "/api/tutelle/entrant/",
            {"company": company_a.pk, "type": "conformite", "contenu": {"norme": "Nouvelle norme incendie"}},
            format="json",
        )

        api_client.credentials()
        api_client.force_authenticate(user=qhse_a)
        assert len(api_client.get("/api/flux-tutelle/").data) == 1
        juridique_b = user_factory("juridique_b_tut", Role.RESPONSABLE_JURIDIQUE, company=company_b)
        api_client.force_authenticate(user=juridique_b)
        assert api_client.get("/api/flux-tutelle/").data == []


@pytest.mark.django_db
class TestFluxEntrantDeLaTutelle:
    """Endpoint 4 : la tutelle envoie un flux vers une compagnie, réservé aux comptes tutelle."""

    def test_un_compte_tutelle_envoie_un_flux(self, api_client, company_a):
        _, cle = CompteTutelle.creer("Ministère des Transports")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        reponse = api_client.post(
            "/api/tutelle/entrant/",
            {"company": company_a.pk, "type": "conformite", "contenu": {"norme": "Contrôle technique renforcé"}},
            format="json",
        )

        assert reponse.status_code == 201
        flux = FluxTutelle.objects.get()
        assert flux.company == company_a
        assert flux.direction == DirectionFlux.VERS_COMPAGNIE
        assert flux.statut == StatutFlux.RECU
        assert flux.type == TypeFlux.CONFORMITE
        assert flux.contenu == {"norme": "Contrôle technique renforcé"}

    @pytest.mark.parametrize("type_flux", ["securite", "fluidite", "conformite", "trafic_agrege"])
    def test_les_quatre_types_de_flux_sont_acceptes(self, api_client, company_a, type_flux):
        _, cle = CompteTutelle.creer("OSER")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        reponse = api_client.post(
            "/api/tutelle/entrant/", {"company": company_a.pk, "type": type_flux, "contenu": {}}, format="json"
        )

        assert reponse.status_code == 201

    def test_sans_cle_dapi_refuse(self, api_client, company_a):
        reponse = api_client.post(
            "/api/tutelle/entrant/", {"company": company_a.pk, "type": "conformite", "contenu": {}}, format="json"
        )

        assert reponse.status_code in (401, 403)
        assert not FluxTutelle.objects.exists()

    def test_une_cle_invalide_refuse(self, api_client, company_a):
        api_client.credentials(HTTP_AUTHORIZATION="ApiKey clef-inventee-au-hasard")

        reponse = api_client.post(
            "/api/tutelle/entrant/", {"company": company_a.pk, "type": "conformite", "contenu": {}}, format="json"
        )

        assert reponse.status_code == 401

    def test_un_compte_tutelle_desactive_est_refuse(self, api_client, company_a):
        compte, cle = CompteTutelle.creer("Organisme suspendu")
        compte.actif = False
        compte.save(update_fields=["actif"])
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        reponse = api_client.post(
            "/api/tutelle/entrant/", {"company": company_a.pk, "type": "conformite", "contenu": {}}, format="json"
        )

        assert reponse.status_code == 401

    def test_un_jeton_jwt_de_compte_interne_ne_donne_pas_acces_meme_pour_le_pdg(self, api_client, user_factory, company_a):
        pdg = user_factory("pdg_tut_entrant", Role.PDG, company=company_a)
        api_client.force_authenticate(user=pdg)  # jeton JWT interne, pas de clé d'API tutelle

        reponse = api_client.post(
            "/api/tutelle/entrant/", {"company": company_a.pk, "type": "conformite", "contenu": {}}, format="json"
        )

        assert reponse.status_code == 403

    def test_un_compte_tutelle_na_pas_acces_aux_routes_internes(self, api_client, company_a):
        _, cle = CompteTutelle.creer("Ministère des Transports")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        assert api_client.get("/api/flux-tutelle/").status_code in (401, 403)
        assert api_client.post("/api/tutelle/generer/").status_code in (401, 403)

    @pytest.mark.parametrize("corps", [{}, {"type": "securite"}, {"company": None, "type": "securite", "contenu": {}}])
    def test_un_flux_entrant_incomplet_est_refuse(self, api_client, company_a, corps):
        _, cle = CompteTutelle.creer("Ministère des Transports")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        assert api_client.post("/api/tutelle/entrant/", corps, format="json").status_code == 400

    def test_un_type_de_flux_inconnu_est_refuse(self, api_client, company_a):
        _, cle = CompteTutelle.creer("Ministère des Transports")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        reponse = api_client.post(
            "/api/tutelle/entrant/", {"company": company_a.pk, "type": "meteo", "contenu": {}}, format="json"
        )

        assert reponse.status_code == 400

    def test_le_contenu_doit_etre_un_objet(self, api_client, company_a):
        _, cle = CompteTutelle.creer("Ministère des Transports")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        reponse = api_client.post(
            "/api/tutelle/entrant/", {"company": company_a.pk, "type": "conformite", "contenu": "pas un objet"}, format="json"
        )

        assert reponse.status_code == 400

    def test_direction_et_statut_ne_se_choisissent_pas(self, api_client, company_a):
        """Un compte tutelle ne peut pas se faire passer pour la compagnie qui « envoie », ni créer un flux déjà « traité »."""
        _, cle = CompteTutelle.creer("Ministère des Transports")
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")

        api_client.post(
            "/api/tutelle/entrant/",
            {
                "company": company_a.pk, "type": "conformite", "contenu": {},
                "direction": "vers_tutelle", "statut": "traite",
            },
            format="json",
        )

        flux = FluxTutelle.objects.get()
        assert flux.direction == DirectionFlux.VERS_COMPAGNIE
        assert flux.statut == StatutFlux.RECU


@pytest.mark.django_db
class TestListeEtTraitement:
    """Endpoint 5 : QHSE et responsable juridique listent les flux de leur compagnie et les marquent « traité »."""

    @pytest.mark.parametrize("role_fixture", ["qhse_a", "juridique_a"])
    def test_liste_les_flux_avec_leur_statut(self, api_client, company_a, vehicule_a, user_factory, request, role_fixture):
        agent = request.getfixturevalue(role_fixture)
        chauffeur = user_factory("chauffeur_tut_liste", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        creer_incident(company_a, vehicule_a, chauffeur)
        api_client.force_authenticate(user=agent)

        reponse = api_client.get("/api/flux-tutelle/")

        assert reponse.status_code == 200
        assert len(reponse.data) == 1
        assert reponse.data[0]["statut"] == "envoye"
        assert reponse.data[0]["type"] == "securite"

    def test_filtre_par_statut_type_et_direction(self, api_client, qhse_a, company_a):
        FluxTutelle.objects.create(company=company_a, type=TypeFlux.SECURITE, direction=DirectionFlux.VERS_TUTELLE, statut=StatutFlux.ENVOYE)
        FluxTutelle.objects.create(company=company_a, type=TypeFlux.CONFORMITE, direction=DirectionFlux.VERS_COMPAGNIE, statut=StatutFlux.RECU)
        api_client.force_authenticate(user=qhse_a)

        assert len(api_client.get("/api/flux-tutelle/?type=conformite").data) == 1
        assert len(api_client.get("/api/flux-tutelle/?direction=vers_compagnie").data) == 1
        assert len(api_client.get("/api/flux-tutelle/?statut=envoye").data) == 1
        assert len(api_client.get("/api/flux-tutelle/?statut=traite").data) == 0

    def test_marquer_traite(self, api_client, qhse_a, company_a):
        flux = FluxTutelle.objects.create(
            company=company_a, type=TypeFlux.CONFORMITE, direction=DirectionFlux.VERS_COMPAGNIE, statut=StatutFlux.RECU
        )
        api_client.force_authenticate(user=qhse_a)

        reponse = api_client.post(f"/api/flux-tutelle/{flux.pk}/traiter/")

        assert reponse.status_code == 200
        assert reponse.data["statut"] == "traite"
        flux.refresh_from_db()
        assert flux.statut == StatutFlux.TRAITE

    def test_un_flux_deja_traite_ne_se_retraite_pas(self, api_client, qhse_a, company_a):
        flux = FluxTutelle.objects.create(
            company=company_a, type=TypeFlux.SECURITE, direction=DirectionFlux.VERS_TUTELLE, statut=StatutFlux.TRAITE
        )
        api_client.force_authenticate(user=qhse_a)

        assert api_client.post(f"/api/flux-tutelle/{flux.pk}/traiter/").status_code == 400

    @pytest.mark.parametrize(
        "role", ["pdg", "guichetier", "chef_gare", "directeur_technique", "secretaire_general", "chauffeur_principal"]
    )
    def test_les_autres_postes_ne_voient_pas_les_flux(self, api_client, user_factory, company_a, role):
        agent = user_factory(f"{role}_tut_liste", Role(role), company=company_a)
        api_client.force_authenticate(user=agent)

        assert api_client.get("/api/flux-tutelle/").status_code == 403

    def test_sans_authentification_refuse(self, api_client):
        assert api_client.get("/api/flux-tutelle/").status_code == 401
