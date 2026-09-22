"""Génération automatique des flux vers la tutelle :

- un incident grave (`personnel_roulant.Incident`, étape 4) prévient tout de suite (voir `tutelle.signals`) ;
- une assurance proche de son échéance (`supports.Assurance`, étape 6) est rattrapée par la tâche planifiée
  (`tutelle/management/commands/generer_flux_tutelle.py`) ou par `POST /api/tutelle/generer/`.

Idempotent : relancer une génération ne crée jamais de doublon (voir `_deja_genere`, qui s'appuie sur l'identifiant
de la source, porté dans `contenu`) — comme `alertes.generation` le fait avec sa `cle`.
"""

import datetime

from django.utils import timezone

from personnel_roulant.models import GraviteIncident, Incident
from supports.models import Assurance
from tutelle.models import DirectionFlux, FluxTutelle, StatutFlux, TypeFlux

# Même seuil que les rappels de renouvellement d'assurance (`alertes.generation.ECHEANCE_ASSURANCE_JOURS`) : une
# assurance entre dans le champ de la tutelle dès qu'elle entrerait dans celui du responsable juridique.
ECHEANCE_ASSURANCE_JOURS = 30


def _deja_genere(company, type_flux, cle_contenu, valeur):
    return FluxTutelle.objects.filter(company=company, type=type_flux, **{f"contenu__{cle_contenu}": valeur}).exists()


def generer_flux_securite(incident):
    """Le flux « sécurité » d'un incident grave. Rien s'il n'est pas grave, ou si son flux existe déjà (un incident
    modifié alors qu'il est déjà grave — ou requalifié en grave puis remodifié — ne prévient qu'une fois). Renvoie
    le flux créé, ou `None`."""
    if incident.gravite != GraviteIncident.GRAVE:
        return None
    if _deja_genere(incident.company, TypeFlux.SECURITE, "incident_id", incident.pk):
        return None
    return FluxTutelle.objects.create(
        company=incident.company,
        type=TypeFlux.SECURITE,
        direction=DirectionFlux.VERS_TUTELLE,
        statut=StatutFlux.ENVOYE,
        contenu={
            "incident_id": incident.pk,
            "type_incident": incident.type_incident,
            "gravite": incident.gravite,
            "description": incident.description,
            "vehicule": incident.vehicule.immatriculation,
            "date": incident.date.isoformat(),
        },
    )


def generer_flux_securite_incidents_graves(company):
    """Rattrapage : tous les incidents graves de la compagnie sans flux encore généré (voir `generer_flux_securite`).
    En usage normal les incidents graves préviennent déjà tout seuls (`tutelle.signals`) ; sert pour un incident créé
    avant l'existence de ce module, ou en dehors de l'API (script, admin...)."""
    return [
        flux
        for incident in Incident.objects.filter(company=company, gravite=GraviteIncident.GRAVE).select_related("vehicule")
        if (flux := generer_flux_securite(incident)) is not None
    ]


def generer_flux_conformite_assurance(assurance, maintenant=None):
    """Le flux « conformité » d'une assurance proche de son échéance (ou déjà expirée). Rien si l'échéance est
    encore lointaine, ou si son flux existe déjà (une seule alerte à la tutelle par assurance). Renvoie le flux
    créé, ou `None`."""
    maintenant = maintenant or timezone.now()
    aujourdhui = timezone.localdate(maintenant)
    if (assurance.date_echeance - aujourdhui).days > ECHEANCE_ASSURANCE_JOURS:
        return None
    if _deja_genere(assurance.company, TypeFlux.CONFORMITE, "assurance_id", assurance.pk):
        return None
    return FluxTutelle.objects.create(
        company=assurance.company,
        type=TypeFlux.CONFORMITE,
        direction=DirectionFlux.VERS_TUTELLE,
        statut=StatutFlux.ENVOYE,
        contenu={
            "assurance_id": assurance.pk,
            "vehicule": assurance.vehicule.immatriculation,
            "numero_police": assurance.numero_police,
            "compagnie_assurance": assurance.compagnie_assurance,
            "date_echeance": assurance.date_echeance.isoformat(),
        },
    )


def generer_flux_conformite_assurances(company, maintenant=None):
    """Toutes les assurances de la compagnie proches de l'échéance, sans flux encore généré (voir
    `generer_flux_conformite_assurance`) : à planifier régulièrement (voir la commande `generer_flux_tutelle`), une
    échéance n'est l'objet d'aucun évènement de sauvegarde à écouter — contrairement à un incident grave."""
    maintenant = maintenant or timezone.now()
    limite = timezone.localdate(maintenant) + datetime.timedelta(days=ECHEANCE_ASSURANCE_JOURS)
    return [
        flux
        for assurance in Assurance.objects.filter(company=company, date_echeance__lte=limite).select_related("vehicule")
        if (flux := generer_flux_conformite_assurance(assurance, maintenant)) is not None
    ]


def generer_tout(company, maintenant=None):
    """Toutes les générations automatiques d'une compagnie (tâche planifiée, ou rattrapage à la demande) ; renvoie
    `{"securite": [...], "conformite": [...]}`, les flux qui viennent d'être créés."""
    return {
        "securite": generer_flux_securite_incidents_graves(company),
        "conformite": generer_flux_conformite_assurances(company, maintenant),
    }
