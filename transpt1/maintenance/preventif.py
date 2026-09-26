"""Entretien préventif : où en est chaque plan, et l'ordre de réparation ouvert tout seul quand l'échéance approche.

Un plan se déclare en jours et/ou en kilomètres (« vidange tous les 10 000 km ou tous les 6 mois »). L'échéance est la première des
deux atteinte. Le kilométrage du véhicule est relevé par le technique ; sans relevé, seul le délai en jours compte.
"""

import datetime

from django.conf import settings
from django.utils import timezone

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from maintenance.models import OrdreReparation, PlanEntretien, StatutOrdreReparation, UrgenceReparation

ROLES_ATELIER = [Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER]
A_JOUR, BIENTOT, EN_RETARD = "a_jour", "bientot", "en_retard"
RANG_ETAT = {EN_RETARD: 0, BIENTOT: 1, A_JOUR: 2}


def echeance(plan, aujourdhui=None):
    """Où en est ce plan : prochaine date et prochain kilométrage, ce qu'il en reste, et l'état (à jour, bientôt dû, en retard)."""
    aujourdhui = aujourdhui or timezone.localdate()
    vehicule = plan.vehicule
    prochaine_date = prochain_km = jours_restants = km_restants = None
    if plan.periodicite_jours:
        prochaine_date = (plan.derniere_date or aujourdhui) + datetime.timedelta(days=plan.periodicite_jours)
        jours_restants = (prochaine_date - aujourdhui).days
    if plan.periodicite_km:
        base = plan.dernier_km if plan.dernier_km is not None else vehicule.kilometrage
        prochain_km = base + plan.periodicite_km
        km_restants = prochain_km - vehicule.kilometrage

    if (jours_restants is not None and jours_restants < 0) or (km_restants is not None and km_restants < 0):
        etat = EN_RETARD
    elif (jours_restants is not None and jours_restants <= settings.ENTRETIEN_PREAVIS_JOURS) or (
        km_restants is not None and km_restants <= settings.ENTRETIEN_PREAVIS_KM
    ):
        etat = BIENTOT
    else:
        etat = A_JOUR
    return {
        "prochaine_date": prochaine_date,
        "prochain_km": prochain_km,
        "jours_restants": jours_restants,
        "km_restants": km_restants,
        "etat": etat,
    }


def plans_par_echeance(company, aujourdhui=None):
    """Les plans actifs de la compagnie avec leur échéance, les plus en retard d'abord : `[(plan, échéance)]`."""
    plans = PlanEntretien.objects.filter(company=company, actif=True).select_related("vehicule")
    resultat = [(plan, echeance(plan, aujourdhui)) for plan in plans]

    def cle(element):
        _, e = element
        restants = [v for v in (e["jours_restants"], e["km_restants"]) if v is not None]
        return RANG_ETAT[e["etat"]], min(restants) if restants else 0

    return sorted(resultat, key=cle)


def renouveler(plan, *, date=None, km=None):
    """L'entretien vient d'être fait : le plan repart de zéro (date du jour et kilométrage actuel, sauf précision)."""
    plan.derniere_date = date or timezone.localdate()
    plan.dernier_km = km if km is not None else plan.vehicule.kilometrage
    plan.save(update_fields=["derniere_date", "dernier_km"])
    return plan


def renouveler_apres_ordre(ordre):
    """La clôture de l'ordre de réparation d'un entretien préventif renouvelle son plan."""
    renouveler(ordre.plan_entretien, date=timezone.localdate(ordre.date_cloture) if ordre.date_cloture else None)


def ordre_ouvert_pour(plan):
    return plan.ordres.exclude(statut=StatutOrdreReparation.TERMINE).exists()


def creer_ordre_preventif(plan, etat):
    """Ouvre l'ordre de réparation de l'entretien, confié au mécanicien le moins chargé. Sans mécanicien, ou si un ordre est déjà
    ouvert pour ce plan, ne fait rien (l'alerte prévient quand même l'atelier). Renvoie l'ordre créé, ou None."""
    from maintenance.analyses import moins_charge

    if not plan.declenche_ordre or ordre_ouvert_pour(plan):
        return None
    intervenant = moins_charge(plan.company)
    if intervenant is None:
        return None
    return OrdreReparation.objects.create(
        vehicule=plan.vehicule,
        company=plan.company,
        description=f"Entretien préventif : {plan.libelle}",
        mecanicien=intervenant,
        urgence=UrgenceReparation.HAUTE if etat == EN_RETARD else UrgenceReparation.NORMALE,
        delai_estime_heures=plan.duree_estimee_heures,
        plan_entretien=plan,
    )


def _reste(e):
    morceaux = []
    if e["jours_restants"] is not None:
        morceaux.append(f"{e['jours_restants']} jour(s)" if e["jours_restants"] >= 0 else f"{-e['jours_restants']} jour(s) de retard")
    if e["km_restants"] is not None:
        morceaux.append(f"{e['km_restants']} km" if e["km_restants"] >= 0 else f"{-e['km_restants']} km de dépassement")
    return " / ".join(morceaux)


def entretiens_a_echeance(company, maintenant):
    """Alerte l'atelier (directeur technique, chef d'atelier) avant l'échéance de chaque plan, puis quand elle est dépassée, et
    ouvre l'ordre de réparation correspondant. Une échéance ne prévient qu'une fois par état : renouveler le plan (nouvelle
    échéance) relance le cycle."""
    aujourdhui = timezone.localdate(maintenant)
    for plan, e in plans_par_echeance(company, aujourdhui):
        if e["etat"] == A_JOUR:
            continue
        echeance_cle = e["prochaine_date"].isoformat() if e["prochaine_date"] else str(e["prochain_km"]) + "km"
        en_retard = e["etat"] == EN_RETARD
        yield alerter(
            company,
            type=TypeAlerte.ENTRETIEN,
            gravite=GraviteAlerte.CRITIQUE if en_retard else GraviteAlerte.ATTENTION,
            titre=f"{'Entretien en retard' if en_retard else 'Entretien à prévoir'} : {plan.libelle} — {plan.vehicule.immatriculation}",
            message=f"Échéance : {_reste(e)}.",
            roles=ROLES_ATELIER,
            objet=plan,
            cle=f"entretien:{plan.pk}:{echeance_cle}:{e['etat']}",
        )
        ordre = creer_ordre_preventif(plan, e["etat"])
        if ordre is not None:
            yield alerter(
                company,
                type=TypeAlerte.ORDRE_REPARATION,
                gravite=GraviteAlerte.ATTENTION if en_retard else GraviteAlerte.INFO,
                titre=f"Ordre de réparation ouvert : {ordre.description} — {plan.vehicule.immatriculation}",
                message=f"Ordre déclenché par l'entretien préventif ({_reste(e)}). Durée estimée : {plan.duree_estimee_heures} h.",
                destinataires=[ordre.mecanicien],
                roles=[Role.CHEF_ATELIER],
                objet=ordre,
            )
