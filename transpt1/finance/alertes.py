"""Alertes financières : budget carburant à 80 % puis dépassé, factures à échéance. Elles s'émettent à la saisie d'une dépense et à
chaque passage de `manage.py generer_alertes` ; chaque situation ne prévient qu'une fois (clé d'alerte)."""

import datetime

from django.utils import timezone

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from finance.analyses import suivi_budget_carburant
from finance.models import Facture, StatutFacture

ROLES_FINANCE_ALERTES = [Role.DIRECTEUR_FINANCIER, Role.PDG]


def _fcfa(montant):
    return f"{montant:,.0f}".replace(",", " ") + " FCFA"


def alertes_budget(company, mois):
    """Une alerte par ligne dont le carburant du mois atteint 80 % de son budget, une autre quand il le dépasse."""
    suivi = suivi_budget_carburant(company, mois)
    for ligne in suivi["lignes"]:
        if ligne["etat"] not in ("alerte", "depasse"):
            continue
        depasse = ligne["etat"] == "depasse"
        yield alerter(
            company,
            type=TypeAlerte.BUDGET,
            gravite=GraviteAlerte.CRITIQUE if depasse else GraviteAlerte.ATTENTION,
            titre=f"Budget carburant {'dépassé' if depasse else 'à 80 %'} : {ligne['nom']}",
            message=f"{_fcfa(ligne['realise'])} dépensés sur {_fcfa(ligne['budget'])} en {suivi['mois']:%m/%Y}.",
            roles=ROLES_FINANCE_ALERTES,
            cle=f"budget:{ligne['ligne']}:{suivi['mois']:%Y-%m}:{100 if depasse else 80}",
        )


def budgets_carburant(company, maintenant):
    yield from alertes_budget(company, timezone.localdate(maintenant))


def factures_a_echeance(company, maintenant):
    """Rappels de paiement : à 7 jours, à 1 jour, puis quand l'échéance est dépassée."""
    aujourdhui = timezone.localdate(maintenant)
    horizon = aujourdhui + datetime.timedelta(days=7)
    for facture in Facture.objects.filter(company=company, statut=StatutFacture.A_PAYER, echeance__lte=horizon).select_related("fournisseur"):
        jours = (facture.echeance - aujourdhui).days
        if jours < 0:
            tranche, gravite, quand = "retard", GraviteAlerte.CRITIQUE, f"en retard de {-jours} jour(s)"
        elif jours <= 1:
            tranche, gravite, quand = "1j", GraviteAlerte.CRITIQUE, "à payer demain" if jours == 1 else "à payer aujourd'hui"
        else:
            tranche, gravite, quand = "7j", GraviteAlerte.ATTENTION, f"à payer dans {jours} jour(s)"
        yield alerter(
            company,
            type=TypeAlerte.PAIEMENT,
            gravite=gravite,
            titre=f"Paiement {quand} : {facture.fournisseur.nom}",
            message=f"{facture.libelle} — {_fcfa(facture.montant)}, échéance le {facture.echeance:%d/%m/%Y}.",
            roles=ROLES_FINANCE_ALERTES,
            objet=facture,
            cle=f"facture:{facture.pk}:{tranche}",
        )
