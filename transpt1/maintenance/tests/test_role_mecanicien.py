"""Le poste « Mécaniciens / électriciens auto » du cahier des charges a son propre rôle : il voit tout ce que voit
la compagnie, agit sur ses propres ordres de réparation, enregistre les sorties de pièces qu'il utilise, et rien d'autre."""

import pytest

from core.models import Role
from maintenance.models import OrdreReparation, SortiePiece, StatutOrdreReparation
from reseau.models import VehiculeStatut


@pytest.mark.django_db
class TestMecanicien:
    def test_il_sort_une_piece_pour_son_propre_ordre_et_le_stock_baisse(
        self, api_client, mecanicien_a, ordre_a, piece_a
    ):
        api_client.force_authenticate(user=mecanicien_a)

        reponse = api_client.post(
            "/api/sorties-pieces/", {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 2}
        )

        assert reponse.status_code == 201
        piece_a.refresh_from_db()
        assert piece_a.quantite_stock == 8

    def test_il_ne_sort_pas_de_piece_pour_l_ordre_d_un_collegue(
        self, api_client, mecanicien_a2, ordre_a, piece_a
    ):
        api_client.force_authenticate(user=mecanicien_a2)

        reponse = api_client.post(
            "/api/sorties-pieces/", {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 1}
        )

        assert reponse.status_code == 400
        assert not SortiePiece.objects.exists()
        piece_a.refresh_from_db()
        assert piece_a.quantite_stock == 10

    def test_il_ne_modifie_ni_ne_supprime_une_sortie_deja_enregistree(
        self, api_client, mecanicien_a, ordre_a, piece_a, magasinier_a
    ):
        api_client.force_authenticate(user=magasinier_a)
        sortie = api_client.post(
            "/api/sorties-pieces/", {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 1}
        ).data
        api_client.force_authenticate(user=mecanicien_a)

        assert api_client.patch(f"/api/sorties-pieces/{sortie['id']}/", {"quantite": 5}).status_code == 403
        assert api_client.delete(f"/api/sorties-pieces/{sortie['id']}/").status_code == 403

    def test_il_ne_touche_pas_au_catalogue_des_pieces(self, api_client, mecanicien_a, piece_a):
        api_client.force_authenticate(user=mecanicien_a)

        creation = api_client.post(
            "/api/pieces/", {"nom": "Courroie", "reference": "REF-COURROIE", "quantite_stock": 5, "seuil_alerte": 1}
        )

        assert creation.status_code == 403
        assert api_client.patch(f"/api/pieces/{piece_a.id}/", {"quantite_stock": 999}).status_code == 403

    def test_il_ne_cree_pas_d_ordre_mais_cloture_le_sien_et_libere_le_vehicule(
        self, api_client, mecanicien_a, ordre_a, vehicule_a
    ):
        api_client.force_authenticate(user=mecanicien_a)
        creation = api_client.post(
            "/api/ordres-reparation/",
            {"vehicule": vehicule_a.id, "description": "Pirate", "mecanicien": mecanicien_a.id},
        )
        assert creation.status_code == 403

        vehicule_a.statut = VehiculeStatut.EN_MAINTENANCE
        vehicule_a.save()
        cloture = api_client.patch(
            f"/api/ordres-reparation/{ordre_a.id}/",
            {"statut": StatutOrdreReparation.TERMINE, "temps_passe_minutes": 90},
        )

        assert cloture.status_code == 200
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_il_ne_cloture_pas_l_ordre_d_un_collegue(self, api_client, mecanicien_a2, ordre_a):
        api_client.force_authenticate(user=mecanicien_a2)

        reponse = api_client.patch(f"/api/ordres-reparation/{ordre_a.id}/", {"statut": StatutOrdreReparation.TERMINE})

        assert reponse.status_code == 403


@pytest.mark.django_db
class TestIntervenantDesignable:
    def test_un_ordre_ne_se_confie_qu_a_un_mecanicien_ou_au_chef_d_atelier(
        self, api_client, chef_atelier_a, vehicule_a, user_factory, company_a
    ):
        bagagiste = user_factory("bagagiste_ordre", Role.BAGAGISTE, company=company_a)
        api_client.force_authenticate(user=chef_atelier_a)

        refus = api_client.post(
            "/api/ordres-reparation/",
            {"vehicule": vehicule_a.id, "description": "Vidange", "mecanicien": bagagiste.id},
        )
        accepte = api_client.post(
            "/api/ordres-reparation/",
            {"vehicule": vehicule_a.id, "description": "Vidange", "mecanicien": chef_atelier_a.id},
        )

        assert refus.status_code == 400
        assert "mécanicien" in str(refus.data["mecanicien"]).lower()
        assert accepte.status_code == 201
        assert OrdreReparation.objects.count() == 1
