import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.models import Role
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut


@pytest.fixture
def contexte_ventes(db, company_a, user_factory):
    gare_adjame = Gare.objects.create(nom="Gare Adjamé", ville="Abidjan", company=company_a)
    gare_yopougon = Gare.objects.create(nom="Gare Yopougon", ville="Abidjan", company=company_a)
    gare_bouake = Gare.objects.create(nom="Gare Bouaké", ville="Bouaké", company=company_a)

    ligne_depuis_adjame = Ligne.objects.create(
        nom="Adjamé-Bouaké", gare_depart=gare_adjame, gare_arrivee=gare_bouake, company=company_a
    )
    ligne_depuis_yopougon = Ligne.objects.create(
        nom="Yopougon-Bouaké", gare_depart=gare_yopougon, gare_arrivee=gare_bouake, company=company_a
    )

    vehicule = Vehicule.objects.create(
        immatriculation="CI-5000-AA", capacite=50, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )
    chauffeur = user_factory("chauffeur_synthese", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
    guichetier = user_factory("guichetier_synthese", Role.GUICHETIER, company=company_a)

    depart_adjame = Depart.objects.create(
        ligne=ligne_depuis_adjame,
        vehicule=vehicule,
        chauffeur=chauffeur,
        company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=2),
        statut=DepartStatut.PLANIFIE,
    )
    depart_yopougon = Depart.objects.create(
        ligne=ligne_depuis_yopougon,
        vehicule=vehicule,
        chauffeur=chauffeur,
        company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=3),
        statut=DepartStatut.PLANIFIE,
    )

    Ticket.objects.create(
        depart=depart_adjame, company=company_a, passager_nom="P1", passager_telephone="+225",
        prix="5000.00", mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
    )
    Ticket.objects.create(
        depart=depart_adjame, company=company_a, passager_nom="P2", passager_telephone="+225",
        prix="5000.00", mode_paiement=ModePaiement.MOBILE_MONEY, vendu_par=guichetier,
    )
    Ticket.objects.create(
        depart=depart_yopougon, company=company_a, passager_nom="P3", passager_telephone="+225",
        prix="7000.00", mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
    )

    return {"gare_adjame": gare_adjame, "gare_yopougon": gare_yopougon}


@pytest.mark.django_db
class TestSyntheseFinanciere:
    def test_synthese_regroupee_par_gare(self, api_client, directeur_financier_a, contexte_ventes):
        api_client.force_authenticate(user=directeur_financier_a)
        today = timezone.localdate().isoformat()

        response = api_client.get(
            f"/api/synthese-financiere/?date_debut={today}&date_fin={today}"
        )

        assert response.status_code == 200
        gares = {g["gare_id"]: g for g in response.data["gares"]}

        adjame = gares[contexte_ventes["gare_adjame"].id]
        assert adjame["nombre_tickets"] == 2
        assert float(adjame["montant_total"]) == 10000.00

        yopougon = gares[contexte_ventes["gare_yopougon"].id]
        assert yopougon["nombre_tickets"] == 1
        assert float(yopougon["montant_total"]) == 7000.00

    def test_periode_sans_ventes_renvoie_liste_vide(
        self, api_client, directeur_financier_a, contexte_ventes
    ):
        api_client.force_authenticate(user=directeur_financier_a)
        hier = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        avant_hier = (timezone.localdate() - datetime.timedelta(days=2)).isoformat()

        response = api_client.get(
            f"/api/synthese-financiere/?date_debut={avant_hier}&date_fin={hier}"
        )

        assert response.status_code == 200
        assert response.data["gares"] == []

    def test_role_non_finance_ne_peut_pas_consulter_la_synthese(
        self, api_client, drh_a, contexte_ventes
    ):
        api_client.force_authenticate(user=drh_a)
        today = timezone.localdate().isoformat()

        response = api_client.get(
            f"/api/synthese-financiere/?date_debut={today}&date_fin={today}"
        )

        assert response.status_code == 403
