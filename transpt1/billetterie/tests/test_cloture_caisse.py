import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement
from core.models import Role
from reseau.models import AffectationGare


def _vendre(api_client, depart, passager, prix, mode):
    return api_client.post(
        "/api/tickets/",
        {
            "depart": depart.id,
            "passager_nom": passager,
            "passager_telephone": "+2250700000000",
            "prix": prix,
            "mode_paiement": mode,
        },
    )


@pytest.mark.django_db
class TestClotureCaisse:
    def test_calcul_cloture_caisse(self, api_client, guichetier_a, depart_a):
        api_client.force_authenticate(user=guichetier_a)

        assert _vendre(api_client, depart_a, "Passager 1", "5000.00", ModePaiement.ESPECES).status_code == 201
        assert _vendre(api_client, depart_a, "Passager 2", "5000.00", ModePaiement.ESPECES).status_code == 201
        assert _vendre(api_client, depart_a, "Passager 3", "7000.00", ModePaiement.MOBILE_MONEY).status_code == 201

        today = timezone.localdate().isoformat()
        response = api_client.get(
            f"/api/tickets/cloture-caisse/?date_debut={today}&date_fin={today}"
        )

        assert response.status_code == 200
        data = response.data
        assert data["guichetier"] == guichetier_a.id
        assert data["nombre_tickets"] == 3
        assert float(data["montant_total"]) == 17000.00
        assert data["especes"]["nombre"] == 2
        assert float(data["especes"]["montant"]) == 10000.00
        assert data["mobile_money"]["nombre"] == 1
        assert float(data["mobile_money"]["montant"]) == 7000.00

    def test_cloture_ne_compte_pas_les_ventes_dun_autre_guichetier(
        self, api_client, guichetier_a, guichetier_a2, depart_a, ligne_a, vehicule_a, chauffeur_a, company_a
    ):
        depart_b = Depart.objects.create(
            ligne=ligne_a,
            vehicule=vehicule_a,
            chauffeur=chauffeur_a,
            company=company_a,
            date_heure=timezone.now() + datetime.timedelta(hours=4),
            statut=DepartStatut.PLANIFIE,
        )

        api_client.force_authenticate(user=guichetier_a)
        assert _vendre(api_client, depart_a, "Passager A", "5000.00", ModePaiement.ESPECES).status_code == 201

        api_client.force_authenticate(user=guichetier_a2)
        assert _vendre(api_client, depart_b, "Passager B", "9000.00", ModePaiement.MOBILE_MONEY).status_code == 201

        today = timezone.localdate().isoformat()
        api_client.force_authenticate(user=guichetier_a)
        response = api_client.get(
            f"/api/tickets/cloture-caisse/?date_debut={today}&date_fin={today}"
        )

        assert response.status_code == 200
        assert response.data["nombre_tickets"] == 1
        assert float(response.data["montant_total"]) == 5000.00

    def test_superieur_peut_consulter_cloture_dun_guichetier(
        self, api_client, guichetier_a, chef_gare_billetterie_a, depart_a, gare_depart_a, company_a
    ):
        gare_depart_a.chef = chef_gare_billetterie_a
        gare_depart_a.save()
        AffectationGare.objects.create(agent=guichetier_a, gare=gare_depart_a, company=company_a)
        api_client.force_authenticate(user=guichetier_a)
        assert _vendre(api_client, depart_a, "Passager 1", "5000.00", ModePaiement.ESPECES).status_code == 201

        today = timezone.localdate().isoformat()
        api_client.force_authenticate(user=chef_gare_billetterie_a)
        response = api_client.get(
            f"/api/tickets/cloture-caisse/?guichetier={guichetier_a.id}&date_debut={today}&date_fin={today}"
        )

        assert response.status_code == 200
        assert response.data["nombre_tickets"] == 1

    def test_le_chef_de_gare_ne_consulte_que_la_caisse_des_guichetiers_de_sa_gare(
        self, api_client, guichetier_a, chef_gare_billetterie_a, user_factory, company_a
    ):
        today = timezone.localdate().isoformat()
        url = f"/api/tickets/cloture-caisse/?guichetier={guichetier_a.id}&date_debut={today}&date_fin={today}"

        # Un guichetier sans gare, ou d'une gare qu'il ne dirige pas : refusé ; la direction des opérations voit tout.
        api_client.force_authenticate(user=chef_gare_billetterie_a)
        assert api_client.get(url).status_code == 403
        api_client.force_authenticate(user=user_factory("dirops_consulte", Role.DIRECTEUR_EXPLOITATION, company=company_a))
        assert api_client.get(url).status_code == 200

    def test_guichetier_ne_peut_pas_consulter_la_cloture_dun_autre(
        self, api_client, guichetier_a, guichetier_a2, depart_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        assert _vendre(api_client, depart_a, "Passager 1", "5000.00", ModePaiement.ESPECES).status_code == 201

        today = timezone.localdate().isoformat()
        api_client.force_authenticate(user=guichetier_a2)
        response = api_client.get(
            f"/api/tickets/cloture-caisse/?guichetier={guichetier_a.id}&date_debut={today}&date_fin={today}"
        )

        assert response.status_code == 403
