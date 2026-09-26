"""Alertes générées automatiquement : seuils critiques pour le PDG, départs à risque de retard, échéances d'assurance.

À lancer régulièrement (toutes les 5 à 10 minutes) par `manage.py generer_alertes` : voir DEPLOIEMENT.md. Chaque
situation porte une clé, si bien que relancer la commande ne prévient pas dix fois du même problème.
"""

import datetime
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter, chef_de_gare_du_depart
from billetterie.models import Depart, DepartStatut, StatutTicket, Ticket
from core.models import Role
from finance.alertes import budgets_carburant, factures_a_echeance
from maintenance import preventif
from maintenance.analyses import besoin_renouvellement
from dashboard.ponctualite import SEUIL_PONCTUALITE_ORANGE, TOLERANCE_RETARD, pourcentage, statut_ponctualite
from personnel_roulant import suivi
from personnel_roulant.models import EtatChecklist, FeuilleDeRoute, Incident, TypeIncident
from reseau.models import VehiculeStatut
from rh.alertes import contrats_a_terme, formations_a_renouveler, litiges_a_signaler
from supports.models import Assurance

# Un départ est « à risque » dans l'heure qui précède son heure prévue ; sans checklist 30 minutes avant, c'est
# déjà un signe (le chauffeur n'est pas prêt).
HORIZON_RISQUE = datetime.timedelta(minutes=60)
DELAI_CHECKLIST = datetime.timedelta(minutes=30)
ECHEANCE_ASSURANCE_JOURS = 30
ECHEANCE_ASSURANCE_URGENTE_JOURS = 7

# Seuils critiques remontés au PDG (sur les 7 derniers jours, contre les 7 précédents quand c'est une évolution).
MIN_DEPARTS_PONCTUALITE = 5
MIN_PANNES = 3
RATIO_PANNES_EN_HAUSSE = 1.5
RATIO_RECETTE_EN_BAISSE = Decimal("0.7")


def generer(company, maintenant=None):
    """Toutes les alertes automatiques d'une compagnie ; renvoie celles qui viennent d'être créées."""
    maintenant = maintenant or timezone.now()
    creees = []
    for regle in (
        assurances_proches, departs_a_risque, seuils_critiques, conducteurs_fatigues, entretiens, renouvellements, budgets_carburant,
        factures_a_echeance, formations_a_renouveler, contrats_a_terme, litiges_a_signaler,
    ):
        creees += [alerte for alerte in regle(company, maintenant) if alerte is not None]
    return creees


def assurances_proches(company, maintenant):
    """Rappels de renouvellement : à 30 jours, à 7 jours, puis une fois l'assurance expirée."""
    aujourdhui = timezone.localdate(maintenant)
    limite = aujourdhui + datetime.timedelta(days=ECHEANCE_ASSURANCE_JOURS)
    for assurance in Assurance.objects.filter(company=company, date_echeance__lte=limite).select_related("vehicule"):
        jours = (assurance.date_echeance - aujourdhui).days
        if jours < 0:
            tranche, gravite, verbe = "expiree", GraviteAlerte.CRITIQUE, f"expirée depuis {-jours} jour(s)"
        elif jours <= ECHEANCE_ASSURANCE_URGENTE_JOURS:
            tranche, gravite, verbe = "7j", GraviteAlerte.CRITIQUE, f"expire dans {jours} jour(s)"
        else:
            tranche, gravite, verbe = "30j", GraviteAlerte.ATTENTION, f"expire dans {jours} jour(s)"
        yield alerter(
            company,
            type=TypeAlerte.ECHEANCE,
            gravite=gravite,
            titre=f"Assurance {'expirée' if jours < 0 else 'à renouveler'} : {assurance.vehicule.immatriculation}",
            message=f"Police {assurance.numero_police} ({assurance.compagnie_assurance}) {verbe} "
            f"(échéance : {assurance.date_echeance:%d/%m/%Y}).",
            roles=[Role.RESPONSABLE_JURIDIQUE, Role.DIRECTEUR_TECHNIQUE],
            objet=assurance,
            cle=f"assurance:{assurance.pk}:{assurance.date_echeance.isoformat()}:{tranche}",
        )


def departs_a_risque(company, maintenant):
    """Alerte prédictive : un départ qui ne partira pas à l'heure, signalé avant qu'il ne devienne un incident."""
    for risque in risques_de_retard(company, maintenant):
        depart = risque["depart"]
        heure = timezone.localtime(depart.date_heure)
        yield alerter(
            company,
            type=TypeAlerte.RETARD_PREVU,
            gravite=GraviteAlerte.CRITIQUE if risque["deja_en_retard"] else GraviteAlerte.ATTENTION,
            titre=f"{'Départ en retard' if risque['deja_en_retard'] else 'Risque de retard'} : "
            f"{depart.ligne.nom} {heure:%H:%M}",
            message=f"{risque['motif']} (véhicule {depart.vehicule.immatriculation}, "
            f"chauffeur {depart.chauffeur.get_full_name() or depart.chauffeur.username}).",
            roles=[Role.CHEF_LIGNE],
            destinataires=[chef_de_gare_du_depart(depart)],
            objet=depart,
            cle=f"retard:{depart.pk}:{risque['code']}",
        )


def risques_de_retard(company, maintenant):
    """Les départs planifiés qui n'ont pas démarré et ne partiront vraisemblablement pas à l'heure, chacun avec
    la première raison rencontrée : `code` (stable, sert de clé), `motif` (lisible), `deja_en_retard`."""
    departs = (
        Depart.objects.filter(
            company=company,
            statut=DepartStatut.PLANIFIE,
            date_heure__lte=maintenant + HORIZON_RISQUE,
            date_heure__gte=maintenant - datetime.timedelta(hours=3),
        )
        .select_related("ligne__gare_depart__chef", "vehicule", "chauffeur")
        .prefetch_related("feuille_de_route__checklist_items")
    )
    for depart in departs:
        feuille = getattr(depart, "feuille_de_route", None)
        if feuille is None or feuille.heure_depart_reelle is not None:
            continue
        items = list(feuille.checklist_items.all())
        retard = maintenant - depart.date_heure
        if depart.vehicule.statut in (VehiculeStatut.BLOQUE_SECURITE, VehiculeStatut.EN_MAINTENANCE):
            code, motif = "vehicule", f"Le véhicule est immobilisé ({depart.vehicule.get_statut_display().lower()})"
        elif any(item.etat == EtatChecklist.DEFAUT for item in items):
            code, motif = "defaut", "Un défaut est signalé sur la checklist avant départ"
        elif retard > TOLERANCE_RETARD:
            code, motif = "retard", f"Le départ n'a pas eu lieu : {int(retard.total_seconds() // 60)} minute(s) de retard"
        elif not items and depart.date_heure - maintenant <= DELAI_CHECKLIST:
            code, motif = "checklist", "La checklist avant départ n'est pas faite"
        else:
            continue
        yield {"depart": depart, "code": code, "motif": motif, "deja_en_retard": retard > TOLERANCE_RETARD}


def seuils_critiques(company, maintenant):
    """Retards récurrents, pannes en hausse, recette en baisse : ce que le PDG doit savoir sans avoir à le chercher."""
    annee, semaine, _ = timezone.localtime(maintenant).isocalendar()
    periode = f"{annee}-S{semaine:02d}"
    sept_jours = datetime.timedelta(days=7)

    # Retards récurrents
    feuilles = FeuilleDeRoute.objects.filter(
        company=company, heure_depart_prevue__gte=maintenant - sept_jours, heure_depart_prevue__lte=maintenant
    )
    statuts = [statut_ponctualite(feuille, maintenant) for feuille in feuilles]
    a_l_heure, en_retard = statuts.count("a_l_heure"), statuts.count("en_retard")
    ponctualite = pourcentage(a_l_heure, a_l_heure + en_retard)
    if a_l_heure + en_retard >= MIN_DEPARTS_PONCTUALITE and ponctualite < SEUIL_PONCTUALITE_ORANGE:
        yield alerter(
            company,
            type=TypeAlerte.SEUIL_CRITIQUE,
            gravite=GraviteAlerte.CRITIQUE,
            titre=f"Retards récurrents : ponctualité de {ponctualite} % sur 7 jours",
            message=f"{en_retard} départ(s) en retard sur {a_l_heure + en_retard} mesurés (seuil : {SEUIL_PONCTUALITE_ORANGE} %).",
            roles=[Role.PDG, Role.DIRECTEUR_EXPLOITATION],
            cle=f"seuil:ponctualite:{periode}",
        )

    # Pannes en hausse
    pannes = Incident.objects.filter(company=company, type_incident=TypeIncident.PANNE)
    recentes = pannes.filter(date__gte=maintenant - sept_jours, date__lte=maintenant).count()
    precedentes = pannes.filter(date__gte=maintenant - 2 * sept_jours, date__lt=maintenant - sept_jours).count()
    if recentes >= MIN_PANNES and recentes > precedentes * RATIO_PANNES_EN_HAUSSE:
        yield alerter(
            company,
            type=TypeAlerte.SEUIL_CRITIQUE,
            gravite=GraviteAlerte.ATTENTION,
            titre=f"Pannes en hausse : {recentes} en 7 jours",
            message=f"Contre {precedentes} la semaine précédente.",
            roles=[Role.PDG, Role.DIRECTEUR_TECHNIQUE],
            cle=f"seuil:pannes:{periode}",
        )

    # Recette en baisse (les 7 jours pleins qui précèdent aujourd'hui, contre les 7 d'avant)
    debut_jour = timezone.localtime(maintenant).replace(hour=0, minute=0, second=0, microsecond=0)
    ventes = Ticket.objects.filter(company=company, statut=StatutTicket.VALIDE)

    def recette(debut, fin):
        return ventes.filter(date_vente__gte=debut, date_vente__lt=fin).aggregate(total=Sum("prix"))["total"] or Decimal("0")

    derniere, precedente = recette(debut_jour - sept_jours, debut_jour), recette(debut_jour - 2 * sept_jours, debut_jour - sept_jours)
    if precedente > 0 and derniere < precedente * RATIO_RECETTE_EN_BAISSE:
        baisse = round(100 * (1 - derniere / precedente))
        yield alerter(
            company,
            type=TypeAlerte.SEUIL_CRITIQUE,
            gravite=GraviteAlerte.CRITIQUE,
            titre=f"Recette en baisse de {baisse} % sur 7 jours",
            message=f"{int(derniere):,} FCFA contre {int(precedente):,} FCFA la semaine précédente.".replace(",", " "),
            roles=[Role.PDG, Role.DIRECTEUR_FINANCIER],
            cle=f"seuil:recette:{periode}",
        )


def conducteurs_fatigues(company, maintenant):
    """Alerte fatigue : un conducteur au volant depuis plus que le seuil de conduite continue. Le conducteur et la régulation
    sont prévenus, avec des relais possibles ; l'alerte se répète à chaque nouveau palier (deux fois le seuil...)."""
    for trajet in suivi.trajets_en_cours(company.pk).select_related("chauffeur", "depart__ligne"):
        etat = suivi.etat_fatigue(trajet, maintenant)
        if not etat["alerte"]:
            continue
        palier = etat["conduite_continue_minutes"] // etat["seuil_minutes"]
        heures, minutes = divmod(etat["conduite_continue_minutes"], 60)
        propositions = ", ".join(r["nom"] for r in suivi.relais_suggeres(trajet, maintenant)[:3])
        yield alerter(
            company,
            type=TypeAlerte.FATIGUE,
            gravite=GraviteAlerte.ATTENTION if palier == 1 else GraviteAlerte.CRITIQUE,
            titre=f"Fatigue : {trajet.chauffeur.get_full_name() or trajet.chauffeur.username} conduit depuis {heures} h {minutes:02d}",
            message=(
                f"Sur {trajet.depart.ligne.nom}, {heures} h {minutes:02d} de conduite continue (seuil : {etat['seuil_minutes']} min). "
                f"Faites une pause ou organisez un relais."
                + (f" Relais possibles : {propositions}." if propositions else " Aucun conducteur libre pour un relais.")
            ),
            roles=[Role.CHEF_LIGNE],
            destinataires=[trajet.chauffeur],
            objet=trajet,
            cle=f"fatigue:{trajet.pk}:{trajet.chauffeur_id}:{palier}",
        )


def entretiens(company, maintenant):
    """Entretiens préventifs à échéance (alerte de l'atelier, ordre de réparation ouvert tout seul) : voir `maintenance.preventif`."""
    yield from preventif.entretiens_a_echeance(company, maintenant)


def renouvellements(company, maintenant):
    """Un véhicule qui atteint au moins deux seuils d'usure (kilométrage, réparations, immobilisation) est signalé à la Direction
    Générale et au technique, une fois par trimestre tant qu'il n'est pas renouvelé."""
    trimestre = f"{maintenant.year}T{(maintenant.month - 1) // 3 + 1}"
    for vehicule in besoin_renouvellement(company, maintenant)["vehicules"]:
        if vehicule["recommandation"] != "a_renouveler":
            continue
        yield alerter(
            company,
            type=TypeAlerte.RENOUVELLEMENT,
            gravite=GraviteAlerte.ATTENTION,
            titre=f"Renouvellement à envisager : {vehicule['immatriculation']}",
            message=" ; ".join(vehicule["raisons"]) + ".",
            roles=[Role.PDG, Role.DIRECTEUR_TECHNIQUE],
            cle=f"renouvellement:{vehicule['id']}:{trimestre}",
        )
