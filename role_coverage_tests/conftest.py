import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.models import Role
from maintenance.models import OrdreReparation, Piece, StatutOrdreReparation
from personnel_roulant.models import (
    FeuilleDeRoute,
    GraviteIncident,
    Incident,
    StatutIncident,
    TypeIncident,
)
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut
from supports.models import Assurance, DossierAgent, Sinistre


def _construire_monde(company, user_factory, suffixe):
    chauffeur = user_factory(f"chauffeur_monde_{suffixe}", Role.CHAUFFEUR_PRINCIPAL, company=company)
    guichetier = user_factory(f"guichetier_monde_{suffixe}", Role.GUICHETIER, company=company)
    mecanicien = user_factory(f"mecanicien_monde_{suffixe}", Role.CHAUFFEUR_RELAIS, company=company)
    agent = user_factory(f"agent_monde_{suffixe}", Role.CONTROLEUR_LIGNE, company=company)

    gare_depart = Gare.objects.create(nom=f"Gare Depart {suffixe}", ville="Abidjan", company=company)
    gare_arrivee = Gare.objects.create(nom=f"Gare Arrivee {suffixe}", ville="Bouaké", company=company)
    ligne = Ligne.objects.create(
        nom=f"Ligne {suffixe}", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company
    )
    vehicule = Vehicule.objects.create(
        immatriculation=f"CI-9{suffixe}00-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company
    )
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company,
        date_heure=timezone.now() + datetime.timedelta(hours=2), statut=DepartStatut.PLANIFIE,
    )
    ticket = Ticket.objects.create(
        depart=depart, company=company, passager_nom="Passager", passager_telephone="+225",
        prix="5000.00", mode_paiement=ModePaiement.ESPECES, vendu_par=guichetier,
    )
    feuille = FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=chauffeur, company=company, heure_depart_prevue=depart.date_heure,
    )
    incident = Incident.objects.create(
        vehicule=vehicule, chauffeur=chauffeur, company=company, type_incident=TypeIncident.RETARD,
        description="Retard mineur.", gravite=GraviteIncident.FAIBLE, statut=StatutIncident.OUVERT,
    )
    piece = Piece.objects.create(
        nom=f"Pièce {suffixe}", reference=f"REF-MONDE-{suffixe}", quantite_stock=10, seuil_alerte=2, company=company
    )
    ordre = OrdreReparation.objects.create(
        vehicule=vehicule, company=company, description="Entretien courant.",
        statut=StatutOrdreReparation.OUVERT, mecanicien=mecanicien,
    )
    assurance = Assurance.objects.create(
        vehicule=vehicule, company=company, compagnie_assurance="NSIA", numero_police=f"POL-{suffixe}",
        date_echeance=timezone.localdate() + datetime.timedelta(days=200),
    )
    sinistre = Sinistre.objects.create(
        vehicule=vehicule, company=company, description="Petit accrochage.",
    )
    dossier = DossierAgent.objects.create(
        agent=agent, company=company, date_embauche=datetime.date(2022, 1, 1), poste="Contrôleur",
    )

    return {
        "gare_depart": gare_depart,
        "gare_arrivee": gare_arrivee,
        "ligne": ligne,
        "vehicule": vehicule,
        "depart": depart,
        "ticket": ticket,
        "feuille": feuille,
        "incident": incident,
        "piece": piece,
        "ordre": ordre,
        "assurance": assurance,
        "sinistre": sinistre,
        "dossier": dossier,
        "agent": agent,
        "chauffeur": chauffeur,
        "guichetier": guichetier,
        "mecanicien": mecanicien,
    }


@pytest.fixture
def monde_a(db, company_a, user_factory):
    return _construire_monde(company_a, user_factory, "A")


@pytest.fixture
def monde_b(db, company_b, user_factory):
    return _construire_monde(company_b, user_factory, "B")


ROLES_A_TESTER = [
    "pdg",
    "secretaire_general",
    "qhse",
    "directeur_exploitation",
    "chef_gare",
    "chef_ligne",
    "guichetier",
    "bagagiste",
    "chauffeur_principal",
    "chauffeur_relais",
    "controleur_ligne",
    "directeur_technique",
    "magasinier",
    "chef_atelier",
    "drh",
    "directeur_financier",
    "responsable_juridique",
]


@pytest.fixture
def utilisateurs_a(user_factory, company_a, monde_a):
    users = {
        role: user_factory(f"{role}_couverture_a", getattr(Role, role.upper()), company=company_a)
        for role in ROLES_A_TESTER
    }
    monde_a["gare_depart"].chef = users["chef_gare"]
    monde_a["gare_depart"].save()
    return users
