import pytest

from maintenance.models import SortiePiece


@pytest.mark.django_db
class TestSortiePiece:
    def test_sortie_piece_decremente_le_stock(self, api_client, magasinier_a, ordre_a, piece_a):
        api_client.force_authenticate(user=magasinier_a)

        response = api_client.post(
            "/api/sorties-pieces/",
            {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 3},
        )

        assert response.status_code == 201
        piece_a.refresh_from_db()
        assert piece_a.quantite_stock == 7

    def test_refus_si_stock_insuffisant(self, api_client, magasinier_a, ordre_a, piece_a):
        api_client.force_authenticate(user=magasinier_a)

        response = api_client.post(
            "/api/sorties-pieces/",
            {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 999},
        )

        assert response.status_code == 400
        piece_a.refresh_from_db()
        assert piece_a.quantite_stock == 10
        assert not SortiePiece.objects.filter(piece=piece_a).exists()


@pytest.mark.django_db
class TestAlerteSeuilStock:
    def test_endpoint_liste_uniquement_les_pieces_sous_le_seuil(
        self, api_client, magasinier_a, piece_a, piece_basse_a
    ):
        api_client.force_authenticate(user=magasinier_a)

        response = api_client.get("/api/pieces/sous-seuil/")

        assert response.status_code == 200
        ids = [p["id"] for p in response.data]
        assert ids == [piece_basse_a.id]

    def test_piece_apparait_en_alerte_apres_une_sortie(
        self, api_client, magasinier_a, ordre_a, piece_a
    ):
        api_client.force_authenticate(user=magasinier_a)

        api_client.post(
            "/api/sorties-pieces/",
            {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 6},
        )

        response = api_client.get("/api/pieces/sous-seuil/")

        assert response.status_code == 200
        ids = [p["id"] for p in response.data]
        assert piece_a.id in ids
