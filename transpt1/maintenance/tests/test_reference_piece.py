"""La référence d'une pièce est unique dans une compagnie, pas sur toute la plateforme (faille S6 de l'analyse)."""

import pytest
from django.db import IntegrityError, transaction

from maintenance.models import Piece


def corps(reference="REF-COMMUNE", **champs):
    return {"nom": "Filtre", "reference": reference, "quantite_stock": 5, "seuil_alerte": 1, **champs}


@pytest.mark.django_db
class TestUniciteParCompagnie:
    def test_deux_compagnies_peuvent_avoir_la_meme_reference(
        self, api_client, magasinier_a, company_b, user_factory
    ):
        magasinier_b = user_factory("magasinier_b", "magasinier", company=company_b)

        api_client.force_authenticate(user=magasinier_a)
        premiere = api_client.post("/api/pieces/", corps())
        api_client.force_authenticate(user=magasinier_b)
        seconde = api_client.post("/api/pieces/", corps())

        assert premiere.status_code == 201 and seconde.status_code == 201
        assert Piece.objects.filter(reference="REF-COMMUNE").count() == 2

    def test_un_doublon_dans_la_meme_compagnie_est_refuse(self, api_client, magasinier_a):
        api_client.force_authenticate(user=magasinier_a)
        api_client.post("/api/pieces/", corps())

        reponse = api_client.post("/api/pieces/", corps())

        assert reponse.status_code == 400
        assert "porte déjà cette référence" in str(reponse.data["reference"])

    def test_les_espaces_autour_de_la_reference_ne_contournent_pas_le_controle(self, api_client, magasinier_a):
        api_client.force_authenticate(user=magasinier_a)
        api_client.post("/api/pieces/", corps())

        assert api_client.post("/api/pieces/", corps(reference="  REF-COMMUNE ")).status_code == 400

    def test_le_message_ne_revele_rien_d_une_autre_compagnie(self, api_client, magasinier_a, company_b):
        Piece.objects.create(nom="Filtre", reference="REF-VOISIN", quantite_stock=1, seuil_alerte=0, company=company_b)
        api_client.force_authenticate(user=magasinier_a)

        assert api_client.post("/api/pieces/", corps(reference="REF-VOISIN")).status_code == 201

    def test_modifier_une_piece_sans_changer_sa_reference_reste_possible(self, api_client, magasinier_a, piece_a):
        api_client.force_authenticate(user=magasinier_a)

        reponse = api_client.patch(f"/api/pieces/{piece_a.id}/", {"reference": piece_a.reference, "seuil_alerte": 7})

        assert reponse.status_code == 200 and reponse.data["seuil_alerte"] == 7

    def test_on_ne_peut_pas_prendre_la_reference_d_une_autre_piece(self, api_client, magasinier_a, piece_a, piece_basse_a):
        api_client.force_authenticate(user=magasinier_a)

        reponse = api_client.patch(f"/api/pieces/{piece_a.id}/", {"reference": piece_basse_a.reference})

        assert reponse.status_code == 400

    def test_la_base_refuse_aussi_le_doublon_meme_hors_api(self, company_a):
        Piece.objects.create(nom="A", reference="X", quantite_stock=1, seuil_alerte=0, company=company_a)

        with pytest.raises(IntegrityError), transaction.atomic():
            Piece.objects.create(nom="B", reference="X", quantite_stock=1, seuil_alerte=0, company=company_a)
