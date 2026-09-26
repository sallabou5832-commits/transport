"""Carnet de route numérique du conducteur (cahier des charges : Chauffeur principal — « carnet de route et documents du véhicule
numériques ») : `/api/carnet-de-route/`."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from maintenance.models import PlanEntretien
from personnel_roulant.models import FeuilleDeRoute, GraviteIncident, Incident, TypeIncident
from personnel_roulant.tests.conftest_suivi import equipe, trajet  # noqa: F401
from reseau.models import Vehicule
from supports.models import Assurance

URL = "/api/carnet-de-route/"


def carnet(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get(URL)


def ancien_trajet(trajet, equipe, *, il_y_a_jours, en_retard=False, immatriculation="CI-9200-AA", conducteur="conducteur"):  # noqa: F811
    """Un trajet terminé, mené par `conducteur`, parti (à l'heure ou avec 40 minutes de retard) il y a `il_y_a_jours` jours."""
    prevu = timezone.now() - datetime.timedelta(days=il_y_a_jours)
    vehicule = Vehicule.objects.create(immatriculation=immatriculation, capacite=50, company=trajet["feuille"].company, kilometrage=120000)
    depart = Depart.objects.create(
        ligne=trajet["ligne"], vehicule=vehicule, chauffeur=equipe[conducteur], company=trajet["feuille"].company,
        date_heure=prevu, statut=DepartStatut.TERMINE,
    )
    reel = prevu + datetime.timedelta(minutes=40 if en_retard else 2)
    return FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=equipe[conducteur], company=depart.company, heure_depart_prevue=prevu, heure_depart_reelle=reel,
        heure_arrivee_reelle=reel + datetime.timedelta(hours=5),
    )


@pytest.mark.django_db
class TestLeCarnet:
    def test_le_conducteur_voit_son_trajet_en_cours_et_le_vehicule_associe(self, api_client, equipe, trajet):  # noqa: F811
        donnees = carnet(api_client, equipe["conducteur"]).data

        assert [t["ligne"] for t in donnees["trajets"]] == ["Adjamé-Bouaké"]
        assert donnees["trajets"][0]["en_cours"] is True and donnees["trajets"][0]["vehicule"] == "CI-9100-AA"
        assert donnees["vehicule"]["immatriculation"] == "CI-9100-AA" and donnees["vehicule"]["trajet"] == "en cours"

    def test_les_trajets_sont_du_plus_recent_au_plus_ancien(self, api_client, equipe, trajet):  # noqa: F811
        ancien_trajet(trajet, equipe, il_y_a_jours=5, immatriculation="CI-9201-AA")
        ancien_trajet(trajet, equipe, il_y_a_jours=12, immatriculation="CI-9202-AA")

        vehicules = [t["vehicule"] for t in carnet(api_client, equipe["conducteur"]).data["trajets"]]

        assert vehicules == ["CI-9100-AA", "CI-9201-AA", "CI-9202-AA"]

    def test_chacun_ne_voit_que_ses_propres_trajets(self, api_client, equipe, trajet):  # noqa: F811
        ancien_trajet(trajet, equipe, il_y_a_jours=3, immatriculation="CI-9203-AA", conducteur="autre")

        assert [t["vehicule"] for t in carnet(api_client, equipe["conducteur"]).data["trajets"]] == ["CI-9100-AA"]
        assert [t["vehicule"] for t in carnet(api_client, equipe["autre"]).data["trajets"]] == ["CI-9203-AA"]

    def test_un_nouveau_conducteur_a_un_carnet_vide(self, api_client, equipe):  # noqa: F811
        donnees = carnet(api_client, equipe["relais"]).data

        assert donnees["trajets"] == [] and donnees["vehicule"] is None
        assert donnees["statistiques"] == {"trajets_30_jours": 0, "ponctualite_30_jours_pourcent": None, "incidents_30_jours": 0}

    def test_la_ponctualite_et_les_incidents_des_30_derniers_jours(self, api_client, equipe, trajet):  # noqa: F811
        ok = ancien_trajet(trajet, equipe, il_y_a_jours=4, immatriculation="CI-9204-AA")
        en_retard = ancien_trajet(trajet, equipe, il_y_a_jours=8, en_retard=True, immatriculation="CI-9205-AA")
        ancien_trajet(trajet, equipe, il_y_a_jours=90, en_retard=True, immatriculation="CI-9206-AA")  # trop ancien pour la statistique
        Incident.objects.create(
            feuille_de_route=en_retard, vehicule=en_retard.depart.vehicule, chauffeur=equipe["conducteur"], company=ok.company,
            type_incident=TypeIncident.PANNE, description="Crevaison", gravite=GraviteIncident.FAIBLE,
        )

        donnees = carnet(api_client, equipe["conducteur"]).data

        # Le trajet en cours (parti à l'heure) compte aussi : 2 à l'heure sur 3 mesurables.
        assert donnees["statistiques"]["trajets_30_jours"] == 3
        assert donnees["statistiques"]["ponctualite_30_jours_pourcent"] == 67
        assert donnees["statistiques"]["incidents_30_jours"] == 1
        retard = next(t for t in donnees["trajets"] if t["vehicule"] == "CI-9205-AA")
        assert retard["ponctualite"] == "en_retard" and retard["retard_minutes"] == 40 and retard["incidents"] == 1

    def test_le_vehicule_du_prochain_trajet_quand_rien_n_est_en_cours(self, api_client, equipe, trajet):  # noqa: F811
        FeuilleDeRoute.objects.filter(pk=trajet["feuille"].pk).update(heure_arrivee_reelle=timezone.now())
        prochain = timezone.now() + datetime.timedelta(hours=6)
        vehicule = Vehicule.objects.create(immatriculation="CI-9207-AA", capacite=50, company=trajet["feuille"].company)
        depart = Depart.objects.create(
            ligne=trajet["ligne"], vehicule=vehicule, chauffeur=equipe["conducteur"], company=vehicule.company, date_heure=prochain,
        )
        FeuilleDeRoute.objects.create(depart=depart, chauffeur=equipe["conducteur"], company=vehicule.company, heure_depart_prevue=prochain)

        donnees = carnet(api_client, equipe["conducteur"]).data

        assert donnees["vehicule"]["immatriculation"] == "CI-9207-AA" and donnees["vehicule"]["trajet"] == "prochain"

    def test_a_defaut_le_vehicule_du_dernier_trajet(self, api_client, equipe, trajet):  # noqa: F811
        FeuilleDeRoute.objects.filter(pk=trajet["feuille"].pk).update(heure_arrivee_reelle=timezone.now())

        donnees = carnet(api_client, equipe["conducteur"]).data

        assert donnees["vehicule"]["trajet"] == "dernier"


@pytest.mark.django_db
class TestLesDocumentsDuVehicule:
    def test_assurance_et_obligations_reglementaires(self, api_client, equipe, trajet):  # noqa: F811
        vehicule = trajet["vehicule"]
        Assurance.objects.create(
            vehicule=vehicule, company=vehicule.company, compagnie_assurance="NSIA", numero_police="POL-77",
            date_echeance=timezone.localdate() + datetime.timedelta(days=20),
        )
        PlanEntretien.objects.create(
            vehicule=vehicule, company=vehicule.company, libelle="Contrôle technique", periodicite_jours=365, reglementaire=True,
            derniere_date=timezone.localdate() - datetime.timedelta(days=100),
        )
        PlanEntretien.objects.create(  # un entretien ordinaire : pas un document du véhicule
            vehicule=vehicule, company=vehicule.company, libelle="Vidange", periodicite_jours=30,
        )

        documents = carnet(api_client, equipe["conducteur"]).data["vehicule"]

        assert documents["assurance"]["police"] == "POL-77" and documents["assurance"]["etat"] == "bientot"
        assert documents["assurance"]["jours_restants"] == 20
        assert [(o["libelle"], o["etat"], o["jours_restants"]) for o in documents["obligations"]] == [("Contrôle technique", "a_jour", 265)]

    def test_un_vehicule_sans_assurance_le_dit(self, api_client, equipe, trajet):  # noqa: F811
        documents = carnet(api_client, equipe["conducteur"]).data["vehicule"]

        assert documents["assurance"]["etat"] == "absente" and documents["obligations"] == []

    def test_le_kilometrage_et_la_capacite_figurent_au_carnet(self, api_client, equipe, trajet):  # noqa: F811
        Vehicule.objects.filter(pk=trajet["vehicule"].pk).update(kilometrage=245000)

        documents = carnet(api_client, equipe["conducteur"]).data["vehicule"]

        assert (documents["capacite"], documents["kilometrage"]) == (40, 245000)


@pytest.mark.django_db
class TestQuiPeutLeLire:
    @pytest.mark.parametrize("role", ["conducteur", "relais"])
    def test_les_conducteurs_lisent_le_leur(self, api_client, equipe, role):  # noqa: F811
        assert carnet(api_client, equipe[role]).status_code == 200

    @pytest.mark.parametrize("role", ["chef_ligne", "pdg", "qhse", "guichetier", "controleur_ligne", "drh"])
    def test_les_autres_postes_n_ont_pas_de_carnet(self, api_client, equipe, role):  # noqa: F811
        assert carnet(api_client, equipe[role]).status_code == 403

    def test_sans_authentification_rien(self, api_client):
        assert api_client.get(URL).status_code == 401
