"""Les tableaux de bord affichent des noms, pas des identifiants : l'API n'a pas d'annuaire d'agents,
les noms utiles sont donc portés en lecture seule par les ressources qui les concernent."""

import pytest


@pytest.mark.django_db
class TestNomsAffiches:
    def test_feuille_incident_et_ordre_exposent_le_nom_de_l_agent(self, api_client, utilisateurs_a, monde_a):
        chauffeur, mecanicien = monde_a["chauffeur"], monde_a["mecanicien"]
        chauffeur.first_name, chauffeur.last_name = "Awa", "Kone"
        chauffeur.save()
        mecanicien.first_name, mecanicien.last_name = "Ibrahim", "Sanogo"
        mecanicien.save()
        api_client.force_authenticate(user=utilisateurs_a["pdg"])

        assert api_client.get("/api/feuilles-de-route/").data[0]["chauffeur_nom"] == "Awa Kone"
        assert api_client.get("/api/incidents/").data[0]["chauffeur_nom"] == "Awa Kone"
        assert api_client.get("/api/ordres-reparation/").data[0]["mecanicien_nom"] == "Ibrahim Sanogo"

    def test_sans_nom_renseigne_on_affiche_l_identifiant(self, api_client, utilisateurs_a, monde_a):
        api_client.force_authenticate(user=utilisateurs_a["pdg"])

        assert api_client.get("/api/feuilles-de-route/").data[0]["chauffeur_nom"] == monde_a["chauffeur"].username
        assert api_client.get("/api/ordres-reparation/").data[0]["mecanicien_nom"] == monde_a["mecanicien"].username

    def test_les_nouveaux_champs_ne_sont_pas_modifiables(self, api_client, utilisateurs_a, monde_a):
        api_client.force_authenticate(user=utilisateurs_a["chef_atelier"])

        reponse = api_client.patch(
            f"/api/ordres-reparation/{monde_a['ordre'].id}/", {"mecanicien_nom": "Pirate", "statut": "en_cours"}
        )

        assert reponse.status_code == 200
        assert reponse.data["mecanicien_nom"] == monde_a["mecanicien"].username
