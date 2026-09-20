import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.models import Role
from personnel_roulant.models import GraviteIncident, Incident, StatutIncident, TypeIncident
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut


def _activite(company, user_factory, suffixe, tickets_aujourdhui, tickets_hier, vehicule_bloque):
    chauffeur = user_factory(f"chauffeur_plat_{suffixe}", Role.CHAUFFEUR_PRINCIPAL, company=company)
    guichetier = user_factory(f"guichetier_plat_{suffixe}", Role.GUICHETIER, company=company)
    gare = Gare.objects.create(nom=f"Gare {suffixe}", ville="Abidjan", company=company)
    ligne = Ligne.objects.create(nom=f"Ligne {suffixe}", gare_depart=gare, gare_arrivee=gare, company=company)
    vehicule = Vehicule.objects.create(
        immatriculation=f"CI-P-{suffixe}", capacite=50, company=company,
        statut=VehiculeStatut.BLOQUE_SECURITE if vehicule_bloque else VehiculeStatut.DISPONIBLE,
    )
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company,
        date_heure=timezone.now(), statut=DepartStatut.PLANIFIE,
    )
    for i in range(tickets_aujourdhui):
        Ticket.objects.create(
            depart=depart, company=company, passager_nom=f"P{i}", passager_telephone="+225",
            prix="1000.00", mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
        )
    for i in range(tickets_hier):
        ticket = Ticket.objects.create(
            depart=depart, company=company, passager_nom=f"H{i}", passager_telephone="+225",
            prix="9000.00", mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
        )
        Ticket.objects.filter(pk=ticket.pk).update(date_vente=timezone.now() - datetime.timedelta(days=1))
    Incident.objects.create(
        vehicule=vehicule, chauffeur=chauffeur, company=company, type_incident=TypeIncident.PANNE,
        description="Panne.", gravite=GraviteIncident.MOYENNE, statut=StatutIncident.OUVERT,
    )


@pytest.fixture
def activite(db, company_a, company_b, user_factory):
    _activite(company_a, user_factory, "A", tickets_aujourdhui=3, tickets_hier=2, vehicule_bloque=True)
    _activite(company_b, user_factory, "B", tickets_aujourdhui=5, tickets_hier=0, vehicule_bloque=False)


@pytest.mark.django_db
class TestDashboardPlateforme:
    def test_une_ligne_par_compagnie_avec_ses_propres_chiffres(self, api_client, superadmin_user, activite, company_a, company_b):
        api_client.force_authenticate(user=superadmin_user)

        reponse = api_client.get("/api/dashboard/plateforme/")

        assert reponse.status_code == 200
        compagnies = {c["nom"]: c for c in reponse.data["compagnies"]}
        a, b = compagnies[company_a.name], compagnies[company_b.name]
        assert (a["tickets_du_jour"], float(a["recettes_du_jour"])) == (3, 3000.0)  # pas les tickets d'hier
        assert (b["tickets_du_jour"], float(b["recettes_du_jour"])) == (5, 5000.0)
        assert (a["gares"], a["lignes"], a["vehicules"], a["vehicules_bloques"]) == (1, 1, 1, 1)
        assert (b["vehicules"], b["vehicules_bloques"]) == (1, 0)
        assert (a["incidents_ouverts"], b["incidents_ouverts"]) == (1, 1)
        assert a["agents"] == 2 and b["agents"] == 2  # chauffeur + guichetier, sans le superadmin

    def test_totaux(self, api_client, superadmin_user, activite):
        api_client.force_authenticate(user=superadmin_user)

        totaux = api_client.get("/api/dashboard/plateforme/").data["totaux"]

        assert totaux["compagnies"] == 2
        assert (totaux["tickets_du_jour"], float(totaux["recettes_du_jour"])) == (8, 8000.0)
        assert totaux["vehicules"] == 2 and totaux["agents"] == 4

    def test_une_compagnie_sans_activite_apparait_avec_des_zeros(self, api_client, superadmin_user, company_a):
        api_client.force_authenticate(user=superadmin_user)

        compagnie = api_client.get("/api/dashboard/plateforme/").data["compagnies"][0]

        assert compagnie["nom"] == company_a.name
        assert compagnie["tickets_du_jour"] == 0 and float(compagnie["recettes_du_jour"]) == 0.0

    @pytest.mark.parametrize("role", [r.value for r in Role if r != Role.SUPERADMIN])
    def test_seul_le_superadmin_y_accede(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_plat", Role(role), company=company_a))

        assert api_client.get("/api/dashboard/plateforme/").status_code == 403

    def test_utilisateur_non_authentifie_refuse(self, api_client):
        assert api_client.get("/api/dashboard/plateforme/").status_code == 401
