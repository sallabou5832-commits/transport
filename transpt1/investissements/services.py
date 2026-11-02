"""Demander, puis décider un investissement, et prévenir ceux que la demande ou la décision concerne."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from core.serializers import nom_complet
from core.textes import lire_texte
from investissements.models import StatutInvestissement


def _montant(investissement):
    return f"{investissement.montant:,.0f}".replace(",", " ") + " FCFA"


def annoncer_demande(investissement, demandeur):
    """Le PDG est prévenu d'une demande à décider."""
    quantite = f" ({investissement.quantite} véhicule(s))" if investissement.quantite else ""
    alerter(
        investissement.company,
        type=TypeAlerte.INVESTISSEMENT,
        gravite=GraviteAlerte.ATTENTION,
        titre=f"Investissement à valider : {investissement.libelle}",
        message=f"{investissement.get_type_display()}{quantite} — {_montant(investissement)}. Demandé par {nom_complet(demandeur)}.",
        roles=[Role.PDG],
        objet=investissement,
        cree_par=demandeur,
    )


def decider(investissement, pdg, *, decision, commentaire=""):
    if investissement.statut != StatutInvestissement.EN_ATTENTE:
        raise ValidationError("Cette demande a déjà été traitée.")
    commentaire = lire_texte(commentaire, 255)
    if decision not in ("valider", "refuser"):
        raise ValidationError({"decision": "Décision attendue : valider ou refuser."})
    if decision == "refuser" and len(commentaire) < 3:
        raise ValidationError({"commentaire": "Indiquez la raison du refus."})
    valide = decision == "valider"
    investissement.statut = StatutInvestissement.VALIDE if valide else StatutInvestissement.REFUSE
    investissement.decide_par, investissement.decide_le = pdg, timezone.now()
    investissement.commentaire_decision = commentaire
    investissement.save()
    alerter(
        investissement.company,
        type=TypeAlerte.INVESTISSEMENT,
        gravite=GraviteAlerte.INFO,
        titre=f"Investissement {'validé' if valide else 'refusé'} : {investissement.libelle}",
        message=(
            f"Décision de {nom_complet(pdg)}." + (f" {commentaire}." if commentaire else "")
            + (f" {_montant(investissement)} à budgéter." if valide else "")
        ),
        # Le demandeur est prévenu ; la finance l'est aussi quand un montant est engagé, pour le budgéter.
        destinataires=[investissement.demandeur],
        roles=[Role.DIRECTEUR_FINANCIER] if valide else [],
        objet=investissement,
        cree_par=pdg,
    )
    return investissement
