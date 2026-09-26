"""Suivi GPS : le conducteur envoie sa position (même en lot, après une zone sans réseau), la régulation voit les cars."""

import datetime

import pytest
from django.utils import timezone

from personnel_roulant.models import PositionVehicule
from personnel_roulant.tests.conftest_suivi import equipe, partir_il_y_a, trajet  # noqa: F401


def envoyer(api_client, utilisateur, donnees):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/positions/", donnees, format="json")


POSITION = {"latitude": "5.812345", "longitude": "-4.512345", "vitesse_kmh": 88}


@pytest.mark.django_db
class TestEnvoiDePosition:
    def test_le_conducteur_envoie_sa_position(self, api_client, equipe, trajet):  # noqa: F811
        reponse = envoyer(api_client, equipe["conducteur"], POSITION)

        assert reponse.status_code == 201 and reponse.data == {"enregistrees": 1}
        position = PositionVehicule.objects.get()
        assert position.vehicule == trajet["vehicule"] and position.feuille_de_route == trajet["feuille"]
        assert position.releve_par == equipe["conducteur"] and position.vitesse_kmh == 88
        assert str(position.latitude) == "5.812345"

    def test_un_lot_garde_l_heure_reelle_de_chaque_releve(self, api_client, equipe, trajet):  # noqa: F811
        maintenant = timezone.now()
        lot = [
            {**POSITION, "releve_le": (maintenant - datetime.timedelta(minutes=m)).isoformat()} for m in (30, 20, 10)
        ]

        reponse = envoyer(api_client, equipe["conducteur"], lot)

        assert reponse.status_code == 201 and reponse.data["enregistrees"] == 3
        heures = sorted(PositionVehicule.objects.values_list("releve_le", flat=True))
        assert (maintenant - heures[0]).total_seconds() // 60 == 30

    @pytest.mark.parametrize(
        "corps",
        [
            {"latitude": "95", "longitude": "-4"},
            {"latitude": "5", "longitude": "-200"},
            {"latitude": "5", "longitude": "-4", "vitesse_kmh": 400},
            {"latitude": "abc", "longitude": "-4"},
            {"longitude": "-4"},
        ],
    )
    def test_les_valeurs_invalides_sont_refusees(self, api_client, equipe, trajet, corps):  # noqa: F811
        assert envoyer(api_client, equipe["conducteur"], corps).status_code == 400
        assert not PositionVehicule.objects.exists()

    def test_un_releve_dans_le_futur_ou_trop_ancien_est_refuse(self, api_client, equipe, trajet):  # noqa: F811
        futur = (timezone.now() + datetime.timedelta(hours=1)).isoformat()
        ancien = (timezone.now() - datetime.timedelta(days=3)).isoformat()

        assert envoyer(api_client, equipe["conducteur"], {**POSITION, "releve_le": futur}).status_code == 400
        assert envoyer(api_client, equipe["conducteur"], {**POSITION, "releve_le": ancien}).status_code == 400

    def test_un_lot_dont_un_releve_est_invalide_n_enregistre_rien(self, api_client, equipe, trajet):  # noqa: F811
        assert envoyer(api_client, equipe["conducteur"], [POSITION, {"latitude": "999", "longitude": "0"}]).status_code == 400
        assert not PositionVehicule.objects.exists()

    def test_les_lots_vides_ou_enormes_sont_refuses(self, api_client, equipe, trajet):  # noqa: F811
        assert envoyer(api_client, equipe["conducteur"], []).status_code == 400
        assert envoyer(api_client, equipe["conducteur"], [POSITION] * 501).status_code == 400

    def test_sans_trajet_en_cours_on_n_envoie_pas(self, api_client, equipe, trajet):  # noqa: F811
        trajet["feuille"].heure_depart_reelle = None
        trajet["feuille"].save()

        reponse = envoyer(api_client, equipe["conducteur"], POSITION)

        assert reponse.status_code == 400 and "Aucun trajet en cours" in str(reponse.data)

    def test_apres_l_arrivee_on_n_envoie_plus(self, api_client, equipe, trajet):  # noqa: F811
        trajet["feuille"].heure_arrivee_reelle = timezone.now()
        trajet["feuille"].save()

        assert envoyer(api_client, equipe["conducteur"], POSITION).status_code == 400

    def test_un_conducteur_sans_trajet_ne_peut_pas_utiliser_le_trajet_d_un_autre(self, api_client, equipe, trajet):  # noqa: F811
        assert envoyer(api_client, equipe["autre"], POSITION).status_code == 400

    @pytest.mark.parametrize("role", ["guichetier", "chef_ligne", "qhse", "drh", "pdg"])
    def test_seul_un_conducteur_envoie_une_position(self, api_client, equipe, trajet, role):  # noqa: F811
        assert envoyer(api_client, equipe[role], POSITION).status_code == 403

    def test_refuse_sans_authentification(self, api_client):
        assert api_client.post("/api/positions/", POSITION, format="json").status_code == 401


@pytest.mark.django_db
class TestDernieresPositions:
    def positions(self, api_client, utilisateur):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get("/api/positions/dernieres/")

    def test_la_regulation_voit_la_derniere_position_de_chaque_car(self, api_client, equipe, trajet):  # noqa: F811
        envoyer(api_client, equipe["conducteur"], {**POSITION, "latitude": "5.5"})
        envoyer(api_client, equipe["conducteur"], {**POSITION, "latitude": "6.5", "vitesse_kmh": 70})

        reponse = self.positions(api_client, equipe["chef_ligne"])

        assert reponse.status_code == 200 and len(reponse.data) == 1
        voiture = reponse.data[0]
        assert voiture["immatriculation"] == "CI-9100-AA" and voiture["ligne"] == "Adjamé-Bouaké"
        assert str(voiture["latitude"]) == "6.500000" and voiture["vitesse_kmh"] == 70
        assert voiture["chauffeur_nom"] == "conducteur_suivi" and voiture["en_direct"] is True

    def test_une_position_ancienne_n_est_plus_en_direct_mais_reste_affichee(self, api_client, equipe, trajet):  # noqa: F811
        vieux = (timezone.now() - datetime.timedelta(minutes=40)).isoformat()
        envoyer(api_client, equipe["conducteur"], {**POSITION, "releve_le": vieux})

        voiture = self.positions(api_client, equipe["chef_ligne"]).data[0]

        assert voiture["en_direct"] is False and voiture["age_secondes"] >= 40 * 60 - 5

    def test_un_car_sans_position_n_est_pas_sur_la_carte_et_un_car_arrive_non_plus(self, api_client, equipe, trajet):  # noqa: F811
        assert self.positions(api_client, equipe["chef_ligne"]).data == []
        envoyer(api_client, equipe["conducteur"], POSITION)
        trajet["feuille"].heure_arrivee_reelle = timezone.now()
        trajet["feuille"].save()

        assert self.positions(api_client, equipe["chef_ligne"]).data == []

    def test_le_signal_fatigue_accompagne_la_position(self, api_client, equipe, trajet):  # noqa: F811
        envoyer(api_client, equipe["conducteur"], POSITION)
        partir_il_y_a(trajet, datetime.timedelta(hours=5))

        assert self.positions(api_client, equipe["chef_ligne"]).data[0]["fatigue"] is True

    @pytest.mark.parametrize("role", ["chef_ligne", "chef_gare", "directeur_exploitation", "pdg", "qhse", "directeur_technique", "secretaire_general"])
    def test_ces_postes_voient_les_cars(self, api_client, equipe, trajet, role):  # noqa: F811
        assert self.positions(api_client, equipe[role]).status_code == 200

    @pytest.mark.parametrize("role", ["guichetier", "drh", "conducteur", "controleur_ligne"])
    def test_les_autres_postes_ne_les_voient_pas(self, api_client, equipe, trajet, role):  # noqa: F811
        assert self.positions(api_client, equipe[role]).status_code == 403

    def test_les_cars_d_une_autre_compagnie_sont_invisibles(self, api_client, equipe, trajet, company_b, user_factory):  # noqa: F811
        envoyer(api_client, equipe["conducteur"], POSITION)
        chef_b = user_factory("chef_ligne_suivi_b", "chef_ligne", company=company_b)

        assert self.positions(api_client, chef_b).data == []


@pytest.mark.django_db
class TestGeolocalisationDesIncidents:
    def declarer(self, api_client, equipe, trajet, **champs):  # noqa: F811
        api_client.force_authenticate(user=equipe["conducteur"])
        return api_client.post(
            "/api/incidents/",
            {
                "feuille_de_route": trajet["feuille"].id, "vehicule": trajet["vehicule"].id,
                "chauffeur": equipe["conducteur"].id, "type_incident": "panne", "description": "Moteur qui chauffe",
                "gravite": "moyenne", **champs,
            },
        )

    def test_sans_position_donnee_on_prend_la_derniere_connue_du_car(self, api_client, equipe, trajet):  # noqa: F811
        envoyer(api_client, equipe["conducteur"], {"latitude": "7.123456", "longitude": "-5.654321"})

        incident = self.declarer(api_client, equipe, trajet)

        assert incident.status_code == 201
        assert str(incident.data["latitude"]) == "7.123456" and str(incident.data["longitude"]) == "-5.654321"

    def test_la_position_donnee_par_l_appareil_est_conservee(self, api_client, equipe, trajet):  # noqa: F811
        envoyer(api_client, equipe["conducteur"], {"latitude": "7.1", "longitude": "-5.6"})

        incident = self.declarer(api_client, equipe, trajet, latitude="8.000000", longitude="-4.000000")

        assert str(incident.data["latitude"]) == "8.000000"

    def test_une_position_trop_ancienne_n_est_pas_reprise(self, api_client, equipe, trajet):  # noqa: F811
        vieux = (timezone.now() - datetime.timedelta(minutes=40)).isoformat()
        envoyer(api_client, equipe["conducteur"], {"latitude": "7.1", "longitude": "-5.6", "releve_le": vieux})

        assert self.declarer(api_client, equipe, trajet).data["latitude"] is None

    def test_sans_aucune_position_l_incident_est_quand_meme_enregistre(self, api_client, equipe, trajet):  # noqa: F811
        incident = self.declarer(api_client, equipe, trajet)

        assert incident.status_code == 201 and incident.data["latitude"] is None
