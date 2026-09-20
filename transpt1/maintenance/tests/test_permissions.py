import pytest

from maintenance.models import SortiePiece


@pytest.mark.django_db
class TestRestrictionSortiePiece:
    @pytest.mark.parametrize(
        "role_fixture", ["magasinier_a", "chef_atelier_a", "directeur_technique_a"]
    )
    def test_roles_autorises_peuvent_creer_une_sortie(
        self, api_client, request, role_fixture, ordre_a, piece_a
    ):
        user = request.getfixturevalue(role_fixture)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            "/api/sorties-pieces/",
            {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 1},
        )

        assert response.status_code == 201

    def test_mecanicien_ne_peut_pas_creer_une_sortie(
        self, api_client, mecanicien_a, ordre_a, piece_a
    ):
        api_client.force_authenticate(user=mecanicien_a)

        response = api_client.post(
            "/api/sorties-pieces/",
            {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 1},
        )

        assert response.status_code == 403
        assert not SortiePiece.objects.filter(piece=piece_a).exists()


@pytest.mark.django_db
class TestRestrictionOrdreReparation:
    def test_chef_atelier_peut_modifier_nimporte_quel_ordre(
        self, api_client, chef_atelier_a, ordre_a
    ):
        api_client.force_authenticate(user=chef_atelier_a)

        response = api_client.patch(
            f"/api/ordres-reparation/{ordre_a.id}/", {"temps_passe_minutes": 45}
        )

        assert response.status_code == 200

    def test_mecanicien_assigne_peut_modifier_son_propre_ordre(
        self, api_client, mecanicien_a, ordre_a
    ):
        api_client.force_authenticate(user=mecanicien_a)

        response = api_client.patch(
            f"/api/ordres-reparation/{ordre_a.id}/", {"temps_passe_minutes": 30}
        )

        assert response.status_code == 200

    def test_autre_mecanicien_ne_peut_pas_modifier_lordre(
        self, api_client, mecanicien_a2, ordre_a
    ):
        api_client.force_authenticate(user=mecanicien_a2)

        response = api_client.patch(
            f"/api/ordres-reparation/{ordre_a.id}/", {"temps_passe_minutes": 30}
        )

        assert response.status_code == 403

    def test_magasinier_ne_peut_pas_modifier_lordre(self, api_client, magasinier_a, ordre_a):
        api_client.force_authenticate(user=magasinier_a)

        response = api_client.patch(
            f"/api/ordres-reparation/{ordre_a.id}/", {"temps_passe_minutes": 30}
        )

        assert response.status_code == 403
