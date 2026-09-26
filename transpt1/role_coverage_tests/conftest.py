import datetime

import pytest
from django.utils import timezone

from alertes.models import TypeAlerte
from alertes.services import alerter
from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from colis.models import Colis
from communication.models import DocumentArchive, EvenementAgenda
from core.models import Role
from django.core.files.base import ContentFile
from finance.models import BudgetCarburant, Depense, Facture, Fournisseur
from investissements.models import Investissement
from maintenance.models import DemandePiece, OrdreReparation, Piece, PlanEntretien, StatutOrdreReparation
from personnel_roulant.models import (
    BlocageSecurite,
    ControleLigne,
    FeuilleDeRoute,
    GraviteIncident,
    Incident,
    StatutIncident,
    TypeIncident,
)
from reseau.models import AffectationGare, ChangementLigne, Gare, Ligne, Vehicule, VehiculeStatut
from rh.models import (
    Candidature,
    ContratAgent,
    DemandeConge,
    Doleance,
    EvaluationAgent,
    MesureDisciplinaire,
    ObligationFormation,
    OffreRecrutement,
)
from personnel_roulant.models import Relais
from supports.models import Assurance, DossierAgent, ModeleJuridique, PieceSinistre, Sinistre

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


@pytest.fixture(autouse=True)
def pieces_jointes_jetables(settings, tmp_path):
    """Les pièces jointes du monde d'exemple vont dans un dossier jetable, pas dans le vrai dossier de la compagnie."""
    settings.MEDIA_ROOT = str(tmp_path)


def _construire_monde(company, user_factory, suffixe):
    chauffeur = user_factory(f"chauffeur_monde_{suffixe}", Role.CHAUFFEUR_PRINCIPAL, company=company)
    guichetier = user_factory(f"guichetier_monde_{suffixe}", Role.GUICHETIER, company=company)
    mecanicien = user_factory(f"mecanicien_monde_{suffixe}", Role.MECANICIEN, company=company)
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

    colis = Colis(
        company=company, depart=depart, description="Carton de démonstration", poids_kg=10, frais=1000,
        mode_paiement="especes", expediteur_nom="Expéditeur", destinataire_nom="Destinataire",
        destinataire_telephone="0700000000", enregistre_par=guichetier,
    )
    colis.definir_code("ABC234")
    colis.save()
    controle = ControleLigne.objects.create(company=company, controleur=agent, feuille_de_route=feuille)
    alerte = alerter(company, type=TypeAlerte.AUTRE, titre=f"Alerte {suffixe}", roles=["pdg", "qhse", "chef_ligne"])
    blocage = BlocageSecurite.objects.create(
        vehicule=vehicule, company=company, motif="Contrôle de routine", pose_par=agent,
        leve_le=timezone.now(), leve_par=agent,
    )

    archive = DocumentArchive.objects.create(company=company, auteur=agent, titre="Bail", date_document=datetime.date(2026, 1, 5))
    evenement = EvenementAgenda.objects.create(company=company, auteur=agent, titre="Comité", debut=timezone.now())
    affectation = AffectationGare.objects.create(agent=guichetier, gare=gare_depart, company=company)
    plan_entretien = PlanEntretien.objects.create(
        vehicule=vehicule, company=company, libelle="Vidange", periodicite_jours=180, derniere_date=timezone.localdate()
    )
    demande_piece = DemandePiece.objects.create(
        ordre_reparation=ordre, piece=piece, company=company, quantite=1, demandeur=mecanicien, disponible_a_la_demande=True
    )
    changement_ligne = ChangementLigne.objects.create(
        ligne=ligne, company=company, action="fermer", motif="Route coupée", demandeur=agent
    )
    investissement = Investissement.objects.create(
        company=company, type="achat_vehicule", libelle="Deux cars", montant="100000000", demandeur=agent
    )
    aujourdhui = timezone.localdate()
    depense = Depense.objects.create(
        company=company, date=aujourdhui, categorie="carburant", libelle="Plein", montant="50000", ligne=ligne, saisi_par=agent
    )
    budget_carburant = BudgetCarburant.objects.create(company=company, ligne=ligne, mois=aujourdhui.replace(day=1), montant="400000")
    fournisseur = Fournisseur.objects.create(company=company, nom=f"Garage {suffixe}")
    facture = Facture.objects.create(
        company=company, fournisseur=fournisseur, libelle="Pièces", montant="120000", date_emission=aujourdhui,
        echeance=aujourdhui + datetime.timedelta(days=15), saisi_par=agent,
    )

    conge = DemandeConge.objects.create(
        company=company, agent=guichetier, debut=aujourdhui + datetime.timedelta(days=10), fin=aujourdhui + datetime.timedelta(days=14)
    )
    obligation_formation = ObligationFormation.objects.create(company=company, nom=f"Sécurité routière {suffixe}", roles=["chauffeur_principal"])
    contrat = ContratAgent.objects.create(company=company, agent=agent, type="cdi", date_debut=datetime.date(2022, 1, 1))
    evaluation = EvaluationAgent.objects.create(company=company, agent=agent, date=aujourdhui, note=4, evaluateur=agent)
    mesure = MesureDisciplinaire.objects.create(company=company, agent=agent, date=aujourdhui, motif="Retards répétés", decidee_par=agent)
    offre = OffreRecrutement.objects.create(company=company, role="guichetier", intitule="Guichetier", cree_par=agent)
    candidature = Candidature.objects.create(company=company, offre=offre, nom="Candidat", telephone="0700000000")
    doleance = Doleance.objects.create(company=company, auteur=guichetier, objet="Heures impayées", description="Trois semaines de retard.")
    piece_sinistre = PieceSinistre.objects.create(
        company=company, sinistre=sinistre, fichier=ContentFile(PDF, name="constat.pdf"), nom_fichier="constat.pdf", taille=len(PDF), ajoute_par=agent
    )
    modele = ModeleJuridique.objects.create(
        company=company, titre=f"Attestation {suffixe}", contenu="Je soussigné…", auteur=agent, fichier=ContentFile(PDF, name="modele.pdf"),
        nom_fichier="modele.pdf", taille=len(PDF),
    )

    relais = Relais.objects.create(
        feuille_de_route=feuille, company=company, ancien_chauffeur=chauffeur, nouveau_chauffeur=chauffeur, lieu="Toumodi"
    )

    return {
        "relais": relais,
        "conge": conge,
        "obligation_formation": obligation_formation,
        "contrat": contrat,
        "evaluation": evaluation,
        "mesure": mesure,
        "offre": offre,
        "candidature": candidature,
        "doleance": doleance,
        "piece_sinistre": piece_sinistre,
        "modele": modele,
        "depense": depense,
        "budget_carburant": budget_carburant,
        "fournisseur": fournisseur,
        "facture": facture,
        "alerte": alerte,
        "blocage": blocage,
        "changement_ligne": changement_ligne,
        "archive": archive,
        "evenement": evenement,
        "affectation": affectation,
        "plan_entretien": plan_entretien,
        "demande_piece": demande_piece,
        "investissement": investissement,
        "compte": guichetier,
        "colis": colis,
        "controle": controle,
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
    "mecanicien",
    "drh",
    "directeur_financier",
    "responsable_juridique",
]


@pytest.fixture
def utilisateurs_a(user_factory, company_a, monde_a):
    users = {
        role: user_factory(f"{role}_couverture_a", getattr(Role, role.upper()), company=company_a)
        for role in ROLES_A_TESTER
        if role != "mecanicien"
    }
    # Le mécanicien ne modifie que les ordres qui lui sont confiés : on prend celui de l'ordre d'exemple.
    users["mecanicien"] = monde_a["mecanicien"]
    monde_a["gare_depart"].chef = users["chef_gare"]
    monde_a["gare_depart"].save()
    return users


@pytest.fixture
def tous_les_roles(utilisateurs_a, superadmin_user):
    """Un utilisateur par rôle (les 17 rôles métier de la compagnie A, plus le superadmin)."""
    return {**utilisateurs_a, "superadmin": superadmin_user}
