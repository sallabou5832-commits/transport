import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.models import Role
from maintenance.models import Piece
from personnel_roulant.models import GraviteIncident, Incident, StatutIncident, TypeIncident
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut
from supports.models import Assurance


@pytest.fixture
def pdg_a(user_factory, company_a):
    return user_factory("pdg_a", Role.PDG, company=company_a)


@pytest.fixture
def secretaire_general_a(user_factory, company_a):
    return user_factory("secretaire_general_a", Role.SECRETAIRE_GENERAL, company=company_a)


@pytest.fixture
def qhse_a(user_factory, company_a):
    return user_factory("qhse_a", Role.QHSE, company=company_a)


@pytest.fixture
def pdg_b(user_factory, company_b):
    return user_factory("pdg_b", Role.PDG, company=company_b)


def _construire_scenario(company, user_factory, suffixe):
    chauffeur = user_factory(f"chauffeur_dash_{suffixe}", Role.CHAUFFEUR_PRINCIPAL, company=company)
    guichetier = user_factory(f"guichetier_dash_{suffixe}", Role.GUICHETIER, company=company)

    vehicules = {
        "disponible": Vehicule.objects.create(
            immatriculation=f"CI-D{suffixe}", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company
        ),
        "en_ligne": Vehicule.objects.create(
            immatriculation=f"CI-L{suffixe}", capacite=30, statut=VehiculeStatut.EN_LIGNE, company=company
        ),
        "en_maintenance": Vehicule.objects.create(
            immatriculation=f"CI-M{suffixe}", capacite=30, statut=VehiculeStatut.EN_MAINTENANCE, company=company
        ),
        "bloque_securite": Vehicule.objects.create(
            immatriculation=f"CI-B{suffixe}", capacite=30, statut=VehiculeStatut.BLOQUE_SECURITE, company=company
        ),
    }

    now = timezone.now()
    incidents = {
        "grave_recent": Incident.objects.create(
            vehicule=vehicules["bloque_securite"], chauffeur=chauffeur, company=company,
            type_incident=TypeIncident.ACCIDENT, description="Collision.", gravite=GraviteIncident.GRAVE,
            statut=StatutIncident.OUVERT, date=now - datetime.timedelta(days=1),
        ),
        "moyenne_recent": Incident.objects.create(
            vehicule=vehicules["en_maintenance"], chauffeur=chauffeur, company=company,
            type_incident=TypeIncident.PANNE, description="Panne moteur.", gravite=GraviteIncident.MOYENNE,
            statut=StatutIncident.OUVERT, date=now - datetime.timedelta(days=2),
        ),
        "faible_recent": Incident.objects.create(
            vehicule=vehicules["disponible"], chauffeur=chauffeur, company=company,
            type_incident=TypeIncident.RETARD, description="Retard.", gravite=GraviteIncident.FAIBLE,
            statut=StatutIncident.OUVERT, date=now - datetime.timedelta(days=3),
        ),
        "grave_ancien": Incident.objects.create(
            vehicule=vehicules["disponible"], chauffeur=chauffeur, company=company,
            type_incident=TypeIncident.ACCIDENT, description="Ancien accident.", gravite=GraviteIncident.GRAVE,
            statut=StatutIncident.OUVERT, date=now - datetime.timedelta(days=10),
        ),
        "grave_traite": Incident.objects.create(
            vehicule=vehicules["disponible"], chauffeur=chauffeur, company=company,
            type_incident=TypeIncident.ACCIDENT, description="Accident résolu.", gravite=GraviteIncident.GRAVE,
            statut=StatutIncident.TRAITE, date=now - datetime.timedelta(days=1),
        ),
    }

    gare_depart = Gare.objects.create(nom=f"Gare {suffixe}", ville="Abidjan", company=company)
    gare_arrivee = Gare.objects.create(nom=f"Gare Arrivée {suffixe}", ville="Bouaké", company=company)
    ligne = Ligne.objects.create(
        nom=f"Ligne {suffixe}", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company
    )
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicules["disponible"], chauffeur=chauffeur, company=company,
        date_heure=timezone.now() + datetime.timedelta(hours=2), statut=DepartStatut.PLANIFIE,
    )
    Ticket.objects.create(
        depart=depart, company=company, passager_nom="P1", passager_telephone="+225",
        prix="5000.00", mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
    )
    Ticket.objects.create(
        depart=depart, company=company, passager_nom="P2", passager_telephone="+225",
        prix="3000.00", mode_paiement=ModePaiement.MOBILE_MONEY, vendu_par=guichetier,
    )
    ticket_hier = Ticket.objects.create(
        depart=depart, company=company, passager_nom="P3", passager_telephone="+225",
        prix="9999.00", mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
    )
    Ticket.objects.filter(pk=ticket_hier.pk).update(
        date_vente=timezone.now() - datetime.timedelta(days=1)
    )

    piece_sous_seuil = Piece.objects.create(
        nom="Filtre à huile", reference=f"REF-{suffixe}-1", quantite_stock=2, seuil_alerte=5, company=company
    )
    Piece.objects.create(
        nom="Ampoule", reference=f"REF-{suffixe}-2", quantite_stock=20, seuil_alerte=5, company=company
    )

    assurance_proche = Assurance.objects.create(
        vehicule=vehicules["disponible"], company=company, compagnie_assurance="NSIA",
        numero_police=f"POL-{suffixe}-1", date_echeance=timezone.localdate() + datetime.timedelta(days=15),
    )
    Assurance.objects.create(
        vehicule=vehicules["disponible"], company=company, compagnie_assurance="NSIA",
        numero_police=f"POL-{suffixe}-2", date_echeance=timezone.localdate() + datetime.timedelta(days=60),
    )

    return {
        "vehicules": vehicules,
        "incidents": incidents,
        "piece_sous_seuil": piece_sous_seuil,
        "assurance_proche": assurance_proche,
    }


@pytest.fixture
def scenario_a(db, company_a, user_factory):
    return _construire_scenario(company_a, user_factory, "A")


@pytest.fixture
def scenario_b_decoy(db, company_b, user_factory):
    return _construire_scenario(company_b, user_factory, "B")
