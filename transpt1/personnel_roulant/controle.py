"""Contrôle à bord : vérifier un billet, comparer voyageurs et charge à ce qui a été enregistré, générer le rapport."""

import json
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from billetterie.models import DepartStatut, StatutTicket, Ticket
from colis.models import Colis, StatutColis
from core.models import Role
from core.serializers import nom_complet
from personnel_roulant.models import (
    GraviteIncident,
    Incident,
    ResultatVerification,
    StatutIncident,
    TypeIncident,
    VerificationTicket,
)

# Écarts au-delà desquels le rapport le signale (voyageurs et charge constatés contre enregistrés).
ECART_VOYAGEURS_POURCENT = 10
ECART_CHARGE_POURCENT = 15
# Trois billets refusés pour fraude (déjà utilisé, inconnu) sur un même contrôle : c'est une infraction grave.
FRAUDES_POUR_INFRACTION = 3
ROLES_ALERTE_INFRACTION = [Role.QHSE, Role.PDG, Role.DIRECTEUR_EXPLOITATION]

MESSAGES = {
    ResultatVerification.VALIDE: "Billet valide : le voyageur peut voyager.",
    ResultatVerification.DEJA_UTILISE: "Billet DÉJÀ UTILISÉ.",
    ResultatVerification.ANNULE: "Billet ANNULÉ : il n'est plus valable.",
    ResultatVerification.INCONNU: "Billet INCONNU : ce code ne correspond à aucun billet de la compagnie.",
    ResultatVerification.AUTRE_DEPART: "Ce billet est valable pour un AUTRE départ.",
    ResultatVerification.DEPART_TERMINE: "Le départ de ce billet est terminé.",
}
FRAUDES = {ResultatVerification.DEJA_UTILISE, ResultatVerification.INCONNU}


def normaliser_code(code):
    return str(code or "").strip().upper().replace("-", "").replace(" ", "")


def verifier_ticket(controle, code):
    """Vérifie un billet pour ce contrôle. Un billet valide est marqué utilisé (il ne servira qu'une fois) ; un billet déjà
    utilisé, annulé, inconnu ou d'un autre départ est refusé et compté. Renvoie `(vérification, ticket)`."""
    code = normaliser_code(code)
    if not code:
        raise ValidationError({"code": "Saisissez ou scannez le code du billet."})
    if not controle.est_ouvert:
        raise ValidationError("Ce contrôle est clôturé.")
    depart_controle = controle.feuille_de_route.depart

    with transaction.atomic():
        ticket = (
            # `of=("self",)` : on ne verrouille que le billet (PostgreSQL refuse FOR UPDATE sur le côté nullable d'une jointure).
            Ticket.objects.select_for_update(of=("self",))
            .select_related("depart", "utilise_par")
            .filter(company=controle.company, code=code)
            .first()
        )
        if ticket is None:
            resultat = ResultatVerification.INCONNU
        elif ticket.statut == StatutTicket.ANNULE:
            resultat = ResultatVerification.ANNULE
        elif ticket.utilise_le is not None:
            resultat = ResultatVerification.DEJA_UTILISE
        elif ticket.depart_id != depart_controle.pk:
            resultat = ResultatVerification.AUTRE_DEPART
        elif ticket.depart.statut == DepartStatut.TERMINE:
            resultat = ResultatVerification.DEPART_TERMINE
        else:
            resultat = ResultatVerification.VALIDE
            ticket.utilise_le, ticket.utilise_par = timezone.now(), controle.controleur
            ticket.save(update_fields=["utilise_le", "utilise_par"])
        verification = VerificationTicket.objects.create(controle=controle, code=code, resultat=resultat, ticket=ticket)
    return verification, ticket


def _pourcent(ecart, reference):
    return round(100 * abs(ecart) / reference) if reference else None


def generer_rapport(controle):
    """Le rapport du contrôle : billets vérifiés, voyageurs et charge comparés à ce qui a été enregistré au départ par le
    guichetier et le bagagiste, anomalies relevées. Ne modifie rien."""
    depart = controle.feuille_de_route.depart
    verifications = list(controle.verifications.all())
    par_resultat = {}
    for verification in verifications:
        par_resultat[verification.resultat] = par_resultat.get(verification.resultat, 0) + 1
    refuses = sum(nombre for resultat, nombre in par_resultat.items() if resultat != ResultatVerification.VALIDE)

    vendus = Ticket.objects.filter(depart=depart, statut=StatutTicket.VALIDE).count()
    capacite = depart.vehicule.capacite
    declaree = sum(
        (c.poids_kg for c in Colis.objects.filter(depart=depart, statut__in=[StatutColis.CHARGE, StatutColis.ARRIVE])), Decimal("0")
    )
    anomalies = []

    passagers = {"vendus": vendus, "capacite": capacite, "constates": controle.passagers_constates}
    if controle.passagers_constates is not None:
        ecart = controle.passagers_constates - vendus
        passagers.update({"ecart": ecart, "ecart_pourcent": _pourcent(ecart, vendus)})
        if controle.passagers_constates > capacite:
            anomalies.append(f"SURCHARGE : {controle.passagers_constates} voyageurs pour {capacite} places.")
        if ecart > 0 and (not vendus or _pourcent(ecart, vendus) > ECART_VOYAGEURS_POURCENT):
            anomalies.append(f"{ecart} voyageur(s) de plus que de billets vendus ({vendus}) : voyageurs sans billet ?")
        elif ecart < 0 and _pourcent(ecart, vendus) > ECART_VOYAGEURS_POURCENT:
            anomalies.append(f"{-ecart} voyageur(s) de moins que de billets vendus ({vendus}).")

    charge = {"declaree_kg": declaree, "constatee_kg": controle.charge_constatee_kg}
    if controle.charge_constatee_kg is not None:
        ecart_kg = controle.charge_constatee_kg - declaree
        charge.update({"ecart_kg": ecart_kg, "ecart_pourcent": _pourcent(ecart_kg, declaree)})
        if ecart_kg > 0 and (not declaree or _pourcent(ecart_kg, declaree) > ECART_CHARGE_POURCENT):
            anomalies.append(f"Charge constatée supérieure de {ecart_kg:.0f} kg à la charge enregistrée ({declaree:.0f} kg) : colis non déclarés ?")

    fraudes = sum(par_resultat.get(r, 0) for r in FRAUDES)
    if par_resultat.get(ResultatVerification.DEJA_UTILISE):
        anomalies.append(f"{par_resultat[ResultatVerification.DEJA_UTILISE]} billet(s) déjà utilisé(s).")
    if par_resultat.get(ResultatVerification.INCONNU):
        anomalies.append(f"{par_resultat[ResultatVerification.INCONNU]} billet(s) inconnu(s) (faux billets ?).")

    return {
        "ligne": depart.ligne.nom,
        "date_depart": depart.date_heure,
        "chauffeur": nom_complet(controle.feuille_de_route.chauffeur),
        "vehicule": depart.vehicule.immatriculation,
        "controleur": nom_complet(controle.controleur),
        "billets": {"verifies": len(verifications), "valides": par_resultat.get(ResultatVerification.VALIDE, 0), "refuses": refuses, "par_resultat": par_resultat},
        "voyageurs": passagers,
        "charge": charge,
        "anomalies": anomalies,
        "fraudes": fraudes,
        "surcharge": controle.passagers_constates is not None and controle.passagers_constates > capacite,
    }


def cloturer(controle, *, passagers_constates=None, charge_constatee_kg=None, commentaire="", infraction_grave=False, motif=""):
    """Clôture le contrôle : enregistre les constats, génère le rapport et, en cas d'infraction grave, alerte directement la
    direction et le QHSE (sans passer par la régulation ni la gare)."""
    if not controle.est_ouvert:
        raise ValidationError("Ce contrôle est déjà clôturé.")
    if infraction_grave and not motif:
        raise ValidationError({"motif_infraction": "Indiquez le motif de l'infraction grave."})
    controle.passagers_constates = passagers_constates
    controle.charge_constatee_kg = charge_constatee_kg
    controle.commentaire = commentaire
    rapport = generer_rapport(controle)

    # Une infraction est grave si le contrôleur le dit, ou d'elle-même : surcharge, ou billets frauduleux à répétition.
    motifs = [motif] if infraction_grave and motif else []
    if rapport["surcharge"]:
        motifs.append("Surcharge du véhicule")
    if rapport["fraudes"] >= FRAUDES_POUR_INFRACTION:
        motifs.append(f"{rapport['fraudes']} billets frauduleux (déjà utilisés ou inconnus)")
    grave = infraction_grave or bool(motifs)

    controle.infraction_grave = grave
    controle.motif_infraction = " ; ".join(motifs)[:255]
    rapport["infraction_grave"] = grave
    rapport["motif_infraction"] = controle.motif_infraction
    # Le rapport est enregistré tel qu'il sera relu : décimales et dates sérialisées une fois pour toutes.
    controle.rapport = json.loads(json.dumps(rapport, cls=DjangoJSONEncoder))
    controle.cloture_le = timezone.now()
    with transaction.atomic():
        controle.save()
        if grave:
            feuille = controle.feuille_de_route
            Incident.objects.create(
                feuille_de_route=feuille, vehicule=feuille.depart.vehicule, chauffeur=feuille.chauffeur, company=controle.company,
                type_incident=TypeIncident.AUTRE, gravite=GraviteIncident.GRAVE, statut=StatutIncident.OUVERT,
                description=f"Infraction constatée au contrôle sur {feuille.depart.ligne.nom} : {controle.motif_infraction}.",
            )
    if grave:
        alerter(
            controle.company,
            type=TypeAlerte.INFRACTION,
            gravite=GraviteAlerte.CRITIQUE,
            titre=f"Infraction grave au contrôle : {rapport['ligne']} ({rapport['vehicule']})",
            message=f"Constatée par {rapport['controleur']} : {controle.motif_infraction}. " + " ".join(rapport["anomalies"]),
            roles=ROLES_ALERTE_INFRACTION,
            objet=controle,
            cree_par=controle.controleur,
        )
    return controle
