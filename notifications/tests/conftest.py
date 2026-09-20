import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut


@pytest.fixture
def guichetier_a(user_factory, company_a):
    return user_factory("guichetier_notif_a", Role.GUICHETIER, company=company_a)


@pytest.fixture
def chauffeur_a(user_factory, company_a):
    return user_factory("chauffeur_notif_a", Role.CHAUFFEUR_PRINCIPAL, company=company_a)


@pytest.fixture
def depart_a(db, company_a, chauffeur_a):
    gare_depart = Gare.objects.create(nom="Gare Adjamé", ville="Abidjan", company=company_a)
    gare_arrivee = Gare.objects.create(nom="Gare Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(
        nom="Adjamé-Bouaké", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company_a
    )
    vehicule = Vehicule.objects.create(
        immatriculation="CI-6000-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )
    return Depart.objects.create(
        ligne=ligne,
        vehicule=vehicule,
        chauffeur=chauffeur_a,
        company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=2),
        statut=DepartStatut.PLANIFIE,
    )
