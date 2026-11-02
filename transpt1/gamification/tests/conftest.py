import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.models import Role
from dashboard.ponctualite import bornes_du_jour
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut

ROLES = [
    "pdg", "drh", "qhse", "directeur_exploitation", "directeur_technique", "chef_gare", "chef_ligne", "guichetier",
    "bagagiste", "chauffeur_principal", "chef_atelier", "mecanicien", "magasinier", "responsable_juridique",
    "secretaire_general",
]


@pytest.fixture
def agents(user_factory, company_a):
    utilisateurs = {role: user_factory(f"{role}_jeu", getattr(Role, role.upper()), company=company_a) for role in ROLES}
    utilisateurs["chauffeur2"] = user_factory("chauffeur2_jeu", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
    utilisateurs["guichetier2"] = user_factory("guichetier2_jeu", Role.GUICHETIER, company=company_a)
    return utilisateurs


@pytest.fixture
def monde(company_a, agents):
    gare_a = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=agents["chef_gare"])
    gare_b = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=gare_a, gare_arrivee=gare_b, company=company_a)
    vehicule = Vehicule.objects.create(immatriculation="CI-6100-AA", capacite=20, statut=VehiculeStatut.DISPONIBLE, company=company_a)
    # Un départ « à venir » mais toujours dans la journée : les classements s'arrêtent à la fin du jour courant, et
    # « maintenant + 5 h » sortirait de la période (donc du calcul) dès 19 h.
    maintenant = timezone.now()
    date_heure = min(maintenant + datetime.timedelta(hours=5), bornes_du_jour(maintenant)[1] - datetime.timedelta(minutes=1))
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=agents["chauffeur_principal"], company=company_a,
        date_heure=date_heure, statut=DepartStatut.PLANIFIE,
    )
    return {"gare_a": gare_a, "gare_b": gare_b, "ligne": ligne, "vehicule": vehicule, "depart": depart}


def vendre(monde, guichetier, prix="5000", statut="valide", company=None):
    ticket = Ticket.objects.create(
        depart=monde["depart"], company=guichetier.company, passager_nom="P", passager_telephone="+225",
        prix=Decimal(prix), mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
    )
    if statut != "valide":
        Ticket.objects.filter(pk=ticket.pk).update(statut=statut)
    return ticket


def trajet(monde, chauffeur, retard_minutes=0, il_y_a=datetime.timedelta(0), checklist=False, gare=None):
    """Un trajet terminé, parti avec `retard_minutes` de retard, il y a `il_y_a`."""
    maintenant = timezone.now()
    prevue = maintenant - il_y_a - datetime.timedelta(hours=3)
    if not il_y_a:
        # Un trajet « du jour » reste dans la journée même juste après minuit (sinon il compterait pour la veille).
        prevue = max(prevue, bornes_du_jour(maintenant)[0] + datetime.timedelta(minutes=1))
    depart = Depart.objects.create(
        ligne=monde["ligne"], vehicule=monde["vehicule"], chauffeur=chauffeur, company=chauffeur.company,
        date_heure=prevue, statut=DepartStatut.TERMINE, places_vendues=10,
    )
    feuille = FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=chauffeur, company=chauffeur.company, heure_depart_prevue=prevue,
        heure_depart_reelle=prevue + datetime.timedelta(minutes=retard_minutes),
        heure_arrivee_reelle=prevue + datetime.timedelta(hours=2),
    )
    if checklist:
        from personnel_roulant.models import ChecklistDepart

        ChecklistDepart.objects.create(feuille_de_route=feuille, company=chauffeur.company, item="pneus", etat="ok")
    return feuille


def etat(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get("/api/gamification/moi/").data
