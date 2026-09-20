"""Isolation des données de formation.

Règle absolue : rien de ce qui est fait en formation ne doit créer, modifier ou
supprimer une donnée des vrais modules métier, ni y apparaître. Ces tests le
vérifient sous trois angles : les tables métier (contenu), les requêtes SQL
d'écriture (comportement), et la structure du code (relations et imports).
"""

import ast
import datetime
import json
import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.models import Role
from formation.models import EtapeFormation, ParcoursFormation, ProgressionFormation
from maintenance.models import Piece
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut

APPS_METIER = ["reseau", "billetterie", "personnel_roulant", "maintenance", "supports", "notifications"]
MODULES_METIER = APPS_METIER + ["dashboard"]

ENDPOINTS_METIER = [
    "/api/gares/",
    "/api/lignes/",
    "/api/vehicules/",
    "/api/departs/",
    "/api/tickets/",
    "/api/feuilles-de-route/",
    "/api/checklists/",
    "/api/incidents/",
    "/api/pieces/",
    "/api/ordres-reparation/",
    "/api/sorties-pieces/",
]

DEMARRER = "/api/formation/mon-parcours/demarrer/"


def terminer_url(etape_id):
    return f"/api/formation/mon-parcours/etapes/{etape_id}/terminer/"


def suivre_tous_les_parcours(api_client, utilisateurs):
    """Fait réaliser à chaque utilisateur son parcours de formation, de bout en bout."""
    for user in utilisateurs:
        api_client.force_authenticate(user=user)
        assert api_client.post(DEMARRER).status_code == 200
        parcours = ParcoursFormation.objects.get(role=user.role)
        for etape_id in parcours.etapes.order_by("ordre").values_list("id", flat=True):
            assert api_client.post(terminer_url(etape_id)).status_code == 200
    assert ProgressionFormation.objects.filter(termine=True).count() == len(utilisateurs)


def contenu_des_tables_metier():
    """Photographie complète (toutes les lignes) de chaque table des modules métier."""
    contenu = {}
    for label in APPS_METIER:
        for modele in apps.get_app_config(label).get_models():
            contenu[modele._meta.label] = list(modele.objects.order_by("pk").values())
    return contenu


@pytest.fixture
def stagiaires(guichetier_a, chauffeur_a, magasinier_a):
    return [guichetier_a, chauffeur_a, magasinier_a]


@pytest.fixture
def donnees_metier_reelles(db, company_a, chauffeur_a, guichetier_a):
    gare_depart = Gare.objects.create(nom="Gare réelle Adjamé", ville="Abidjan", company=company_a)
    gare_arrivee = Gare.objects.create(nom="Gare réelle Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(
        nom="Ligne réelle", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company_a
    )
    vehicule = Vehicule.objects.create(
        immatriculation="CI-7777-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )
    depart = Depart.objects.create(
        ligne=ligne,
        vehicule=vehicule,
        chauffeur=chauffeur_a,
        company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=2),
        statut=DepartStatut.PLANIFIE,
        places_vendues=1,
    )
    Ticket.objects.create(
        depart=depart,
        company=company_a,
        passager_nom="Passager réel",
        passager_telephone="+2250700000000",
        prix=Decimal("5000.00"),
        mode_paiement=ModePaiement.ESPECES,
        vendu_par=guichetier_a,
    )
    Piece.objects.create(
        nom="Filtre réel", reference="REEL-001", quantite_stock=10, seuil_alerte=4, company=company_a
    )


@pytest.mark.django_db
class TestAucuneDonneeMetierEcrite:
    def test_les_tables_metier_restent_vides(self, api_client, parcours_de_base, stagiaires):
        suivre_tous_les_parcours(api_client, stagiaires)

        contenu = contenu_des_tables_metier()
        assert contenu  # au moins un modèle métier inspecté
        assert all(lignes == [] for lignes in contenu.values()), {
            table: lignes for table, lignes in contenu.items() if lignes
        }

    def test_les_donnees_reelles_existantes_ne_sont_ni_modifiees_ni_completees(
        self, api_client, parcours_de_base, stagiaires, donnees_metier_reelles
    ):
        avant = contenu_des_tables_metier()
        assert any(lignes for lignes in avant.values())  # le test n'est pas vide

        suivre_tous_les_parcours(api_client, stagiaires)

        assert contenu_des_tables_metier() == avant

    def test_les_requetes_d_ecriture_ne_visent_que_les_tables_de_formation(
        self, api_client, parcours_de_base, stagiaires, donnees_metier_reelles
    ):
        with CaptureQueriesContext(connection) as requetes:
            suivre_tous_les_parcours(api_client, stagiaires)

        ecritures = set()
        lectures = set()
        for requete in requetes.captured_queries:
            sql = requete["sql"]
            ecriture = re.match(r'\s*(?:INSERT INTO|UPDATE|DELETE FROM)\s+"(\w+)"', sql, re.IGNORECASE)
            if ecriture:
                ecritures.add(ecriture.group(1))
            lectures.update(re.findall(r'(?:FROM|JOIN)\s+"(\w+)"', sql, re.IGNORECASE))

        assert ecritures, "aucune écriture capturée : le test serait vide"
        assert all(table.startswith("formation_") for table in ecritures), ecritures
        # Lecture : uniquement la formation elle-même et le compte de l'utilisateur.
        assert all(table.startswith(("formation_", "core_")) for table in lectures), lectures

    def test_aucune_notification_client_n_est_envoyee(
        self, api_client, parcours_de_base, stagiaires, settings
    ):
        # Même en mode « envoi réel », un exercice de vente ne doit pas contacter le client.
        settings.NOTIFICATIONS_SIMULATION_MODE = False

        with patch("twilio.rest.Client") as twilio, patch("requests.post") as http:
            suivre_tous_les_parcours(api_client, stagiaires)

        twilio.assert_not_called()
        http.assert_not_called()
        assert contenu_des_tables_metier()["notifications.NotificationLog"] == []


@pytest.mark.django_db
class TestLesModulesMetierNeMontrentJamaisLaFormation:
    def test_les_api_metier_sont_inchangees_et_sans_donnee_fictive(
        self, api_client, parcours_de_base, stagiaires, donnees_metier_reelles, pdg_a
    ):
        def lire_les_api_metier():
            api_client.force_authenticate(user=pdg_a)
            reponses = {}
            for url in ENDPOINTS_METIER:
                reponse = api_client.get(url)
                assert reponse.status_code == 200, url
                reponses[url] = json.loads(json.dumps(reponse.data, default=str))
            return reponses

        avant = lire_les_api_metier()
        assert avant["/api/tickets/"] and avant["/api/pieces/"]  # les vraies données sont visibles

        suivre_tous_les_parcours(api_client, stagiaires)
        apres = lire_les_api_metier()

        assert apres == avant
        texte = json.dumps(apres)
        assert "(formation)" not in texte and "SIM-" not in texte and "Formation" not in texte


class TestIsolationStructurelle:
    def test_les_modeles_de_formation_ne_referencent_que_la_formation_et_les_utilisateurs(self):
        modeles_formation = list(apps.get_app_config("formation").get_models())
        autorises = {m._meta.label_lower for m in modeles_formation} | {"core.user"}
        for modele in modeles_formation:
            for champ in modele._meta.get_fields():
                if champ.is_relation and champ.related_model is not None:
                    assert champ.related_model._meta.label_lower in autorises, (
                        f"{modele._meta.label}.{champ.name} -> {champ.related_model._meta.label}"
                    )

    def test_aucun_modele_metier_ne_reference_la_formation(self):
        for label in MODULES_METIER + ["core"]:
            if not apps.is_installed(label):
                continue
            for modele in apps.get_app_config(label).get_models():
                for champ in modele._meta.get_fields():
                    if champ.is_relation and champ.related_model is not None:
                        if champ.related_model._meta.app_label == "formation" and not champ.auto_created:
                            pytest.fail(f"{modele._meta.label}.{champ.name} référence la formation")

    @staticmethod
    def _modules_importes(chemin):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    yield alias.name.split(".")[0]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                yield noeud.module.split(".")[0]

    def test_le_code_de_formation_n_importe_aucun_module_metier(self):
        racine = Path(settings.BASE_DIR) / "formation"
        fichiers = [f for f in racine.rglob("*.py") if "tests" not in f.parts]
        assert fichiers
        for fichier in fichiers:
            importes = set(self._modules_importes(fichier))
            assert not importes & set(MODULES_METIER), (fichier, importes & set(MODULES_METIER))

    def test_le_code_metier_n_importe_pas_la_formation(self):
        for module in MODULES_METIER:
            racine = Path(settings.BASE_DIR) / module
            for fichier in racine.rglob("*.py"):
                if "tests" in fichier.parts or "migrations" in fichier.parts:
                    continue
                assert "formation" not in set(self._modules_importes(fichier)), fichier

    def test_les_etapes_sont_toutes_simulees(self, db):
        from formation.parcours_de_base import charger_parcours_de_base

        charger_parcours_de_base()

        assert not EtapeFormation.objects.exclude(type_action="simulee").exists()
        assert not ParcoursFormation.objects.filter(role=Role.SUPERADMIN).exists()
