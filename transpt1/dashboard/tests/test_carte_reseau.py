"""Carte du réseau : gares (couleur selon la ponctualité du jour), lignes, cars en route avec leur dernière position."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from personnel_roulant.models import FeuilleDeRoute, PositionVehicule
from personnel_roulant.tests.conftest_suivi import equipe, trajet  # noqa: F401


def carte(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get("/api/dashboard/carte/")


@pytest.mark.django_db
class TestCarteDuReseau:
    def test_les_gares_les_lignes_et_les_cars_sont_la(self, api_client, equipe, trajet):  # noqa: F811
        PositionVehicule.objects.create(
            company=trajet["feuille"].company, vehicule=trajet["vehicule"], feuille_de_route=trajet["feuille"],
            latitude="6.500000", longitude="-4.700000", vitesse_kmh=80,
        )

        donnees = carte(api_client, equipe["pdg"]).data

        assert {g["nom"] for g in donnees["gares"]} == {"Adjamé", "Bouaké"}
        adjame = next(g for g in donnees["gares"] if g["nom"] == "Adjamé")
        assert str(adjame["latitude"]) == "5.360000" and str(adjame["longitude"]) == "-4.008300"
        assert donnees["lignes"] == [
            {"id": trajet["ligne"].id, "nom": "Adjamé-Bouaké", "gare_depart": trajet["gare_depart"].id, "gare_arrivee": trajet["gare_arrivee"].id}
        ]
        assert len(donnees["vehicules"]) == 1 and donnees["vehicules"][0]["immatriculation"] == "CI-9100-AA"
        assert "mis_a_jour" in donnees

    def test_la_couleur_d_une_gare_suit_sa_ponctualite_du_jour(self, api_client, equipe, trajet):  # noqa: F811
        # Le trajet de la fixture est parti pile à l'heure : gare de départ verte, gare d'arrivée sans départ mesurable.
        gares = {g["nom"]: g for g in carte(api_client, equipe["pdg"]).data["gares"]}

        assert gares["Adjamé"]["couleur"] == "vert" and gares["Adjamé"]["ponctualite_pourcent"] == 100
        assert gares["Bouaké"]["couleur"] == "neutre" and gares["Bouaké"]["ponctualite_pourcent"] is None

    def test_un_depart_en_retard_fait_passer_la_gare_au_rouge(self, api_client, equipe, trajet):  # noqa: F811
        for minutes in (45, 50, 55):
            prevue = timezone.now() - datetime.timedelta(hours=2)
            depart = Depart.objects.create(
                ligne=trajet["ligne"], vehicule=trajet["vehicule"], chauffeur=equipe["conducteur"], company=trajet["ligne"].company,
                date_heure=prevue, statut=DepartStatut.EN_COURS,
            )
            FeuilleDeRoute.objects.create(
                depart=depart, chauffeur=equipe["conducteur"], company=depart.company, heure_depart_prevue=prevue,
                heure_depart_reelle=prevue + datetime.timedelta(minutes=minutes),
            )

        adjame = next(g for g in carte(api_client, equipe["pdg"]).data["gares"] if g["nom"] == "Adjamé")

        assert adjame["couleur"] == "rouge" and adjame["ponctualite_pourcent"] < 70

    def test_une_gare_sans_coordonnees_est_listee_sans_position(self, api_client, equipe, trajet):  # noqa: F811
        trajet["gare_arrivee"].latitude = trajet["gare_arrivee"].longitude = None
        trajet["gare_arrivee"].save()

        gares = {g["nom"]: g for g in carte(api_client, equipe["pdg"]).data["gares"]}

        assert gares["Bouaké"]["latitude"] is None

    @pytest.mark.parametrize("role", ["pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne", "qhse", "directeur_technique"])
    def test_ces_postes_voient_la_carte(self, api_client, equipe, trajet, role):  # noqa: F811
        assert carte(api_client, equipe[role]).status_code == 200

    @pytest.mark.parametrize("role", ["guichetier", "drh", "conducteur", "controleur_ligne"])
    def test_les_autres_postes_ne_la_voient_pas(self, api_client, equipe, trajet, role):  # noqa: F811
        assert carte(api_client, equipe[role]).status_code == 403

    def test_la_carte_d_une_compagnie_ne_montre_rien_d_une_autre(self, api_client, equipe, trajet, company_b, user_factory):  # noqa: F811
        pdg_b = user_factory("pdg_carte_b", "pdg", company=company_b)

        donnees = carte(api_client, pdg_b).data

        assert donnees["gares"] == [] and donnees["vehicules"] == [] and donnees["lignes"] == []

    def test_refuse_sans_authentification(self, api_client):
        assert api_client.get("/api/dashboard/carte/").status_code == 401
