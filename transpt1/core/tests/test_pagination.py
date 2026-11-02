"""Pagination facultative (`core/pagination.py`) : sans `?limit=` rien ne change, avec `?limit=` on obtient une page."""

import pytest

from core.models import Role
from reseau.models import Vehicule

URL = "/api/vehicules/"


@pytest.fixture
def parc(company_a, user_factory):
    for numero in range(5):
        Vehicule.objects.create(immatriculation=f"CI-70{numero}-AA", capacite=30, company=company_a)
    return user_factory("directeur_pagination", Role.DIRECTEUR_EXPLOITATION, company=company_a)


@pytest.mark.django_db
class TestPaginationFacultative:
    def test_sans_limit_la_liste_est_entiere_et_brute(self, api_client, parc):
        api_client.force_authenticate(user=parc)

        reponse = api_client.get(URL)

        assert reponse.status_code == 200
        assert isinstance(reponse.data, list) and len(reponse.data) == 5

    def test_avec_limit_on_obtient_une_page(self, api_client, parc):
        api_client.force_authenticate(user=parc)

        reponse = api_client.get(URL, {"limit": 2})

        assert reponse.status_code == 200
        assert reponse.data["count"] == 5 and len(reponse.data["results"]) == 2
        assert reponse.data["next"] is not None and reponse.data["previous"] is None

    def test_les_pages_se_suivent_sans_trou_ni_doublon(self, api_client, parc):
        api_client.force_authenticate(user=parc)
        toutes = [v["immatriculation"] for v in api_client.get(URL).data]

        vues = []
        for decalage in (0, 2, 4):
            vues += [v["immatriculation"] for v in api_client.get(URL, {"limit": 2, "offset": decalage}).data["results"]]

        assert vues == toutes

    def test_une_page_ne_sort_pas_de_la_compagnie(self, api_client, parc, company_b):
        Vehicule.objects.create(immatriculation="CI-999-BB", capacite=30, company=company_b)
        api_client.force_authenticate(user=parc)

        reponse = api_client.get(URL, {"limit": 100})

        assert reponse.data["count"] == 5
        assert "CI-999-BB" not in {v["immatriculation"] for v in reponse.data["results"]}

    @pytest.mark.parametrize("limite", ["abc", "0", "-5", ""])
    def test_une_limite_invalide_ne_pagine_pas_et_ne_plante_pas(self, api_client, parc, limite):
        api_client.force_authenticate(user=parc)

        reponse = api_client.get(URL, {"limit": limite})

        assert reponse.status_code == 200 and isinstance(reponse.data, list)

    def test_une_limite_excessive_est_plafonnee(self, api_client, company_a, parc, settings):
        Vehicule.objects.bulk_create(
            [Vehicule(immatriculation=f"CI-BULK-{n}", capacite=10, company=company_a) for n in range(510)]
        )
        api_client.force_authenticate(user=parc)

        reponse = api_client.get(URL, {"limit": 100000})

        assert reponse.data["count"] == 515 and len(reponse.data["results"]) == 500
