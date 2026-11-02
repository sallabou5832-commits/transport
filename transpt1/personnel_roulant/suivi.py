"""Suivi d'un trajet en cours : position, temps de conduite continue (fatigue), relais entre conducteurs."""

import datetime
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from core.serializers import nom_complet
from personnel_roulant.models import (
    ITEMS_REPRISE,
    ITEMS_SECURITE,
    ChecklistReprise,
    EtatChecklist,
    FeuilleDeRoute,
    Incident,
    PausePrise,
    PositionVehicule,
    Relais,
    StatutIncident,
)

journal = logging.getLogger(__name__)

CHAUFFEURS = {Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS}
# Une position plus vieille que cela n'est plus « en direct » (le car est peut-être sans réseau) : on l'affiche quand même, datée.
PEREMPTION_POSITION = datetime.timedelta(minutes=15)


def seuil_fatigue_minutes():
    # 4 h 30 de conduite continue ; jamais moins d'une minute (un seuil nul ferait diviser par zéro la génération des alertes)
    return max(1, getattr(settings, "SUIVI_SEUIL_FATIGUE_MINUTES", 270))


def trajets_en_cours(company_id=None):
    trajets = FeuilleDeRoute.objects.filter(heure_depart_reelle__isnull=False, heure_arrivee_reelle__isnull=True)
    return trajets.filter(company_id=company_id) if company_id is not None else trajets


def trajet_en_cours_de(chauffeur):
    """Le trajet que ce conducteur mène en ce moment (départ réel donné, arrivée pas encore), ou None."""
    return (
        trajets_en_cours(chauffeur.company_id)
        .filter(chauffeur=chauffeur)
        .select_related("depart__vehicule", "depart__ligne")
        .order_by("-heure_depart_reelle")
        .first()
    )


# --- Fatigue -------------------------------------------------------------------------------------------------------------


def debut_conduite_continue(feuille):
    """Depuis quand le conducteur actuel conduit sans s'arrêter : le départ, le dernier relais ou la fin de la dernière pause."""
    reperes = [feuille.heure_depart_reelle]
    dernier_relais = feuille.relais.order_by("-effectue_le").first()
    if dernier_relais is not None:
        reperes.append(dernier_relais.effectue_le)
    derniere_pause = feuille.pauses.filter(fin__isnull=False).order_by("-fin").first()
    if derniere_pause is not None:
        reperes.append(derniere_pause.fin)
    return max(reperes)


def etat_fatigue(feuille, maintenant=None):
    maintenant = maintenant or timezone.now()
    seuil = seuil_fatigue_minutes()
    en_pause = feuille.pauses.filter(fin__isnull=True).exists()
    if feuille.heure_depart_reelle is None or feuille.heure_arrivee_reelle is not None:
        continue_minutes = 0
    elif en_pause:
        continue_minutes = 0
    else:
        continue_minutes = max(0, int((maintenant - debut_conduite_continue(feuille)).total_seconds() // 60))
    return {
        "feuille_de_route": feuille.pk,
        "chauffeur": feuille.chauffeur_id,
        "conduite_continue_minutes": continue_minutes,
        "seuil_minutes": seuil,
        "minutes_avant_alerte": max(0, seuil - continue_minutes),
        "en_pause": en_pause,
        "alerte": continue_minutes >= seuil,
    }


def relais_suggeres(feuille, maintenant=None):
    """Conducteurs libres qui pourraient relayer (le relais d'abord) : la suggestion de l'alerte fatigue."""
    from billetterie import planning

    maintenant = maintenant or timezone.now()
    libres = planning.chauffeurs_disponibles(feuille.company_id, maintenant).exclude(pk=feuille.chauffeur_id)
    en_route = set(trajets_en_cours(feuille.company_id).values_list("chauffeur_id", flat=True))
    candidats = sorted((c for c in libres if c.pk not in en_route), key=lambda c: (c.role != Role.CHAUFFEUR_RELAIS, c.username))
    return [{"id": c.pk, "nom": nom_complet(c), "role": c.role} for c in candidats[:5]]


def commencer_pause(feuille, chauffeur):
    if feuille.pauses.filter(fin__isnull=True).exists():
        raise ValidationError("Une pause est déjà en cours.")
    return PausePrise.objects.create(feuille_de_route=feuille, company=feuille.company, chauffeur=chauffeur)


def terminer_pause(feuille):
    pause = feuille.pauses.filter(fin__isnull=True).first()
    if pause is None:
        raise ValidationError("Aucune pause n'est en cours.")
    pause.fin = timezone.now()
    pause.save(update_fields=["fin"])
    return pause


# --- Relais --------------------------------------------------------------------------------------------------------------


def etat_du_vehicule(feuille):
    """L'état transmis au conducteur qui reprend : statut du car, défauts de checklist, incidents ouverts."""
    vehicule = feuille.depart.vehicule
    return {
        "immatriculation": vehicule.immatriculation,
        "statut": vehicule.statut,
        "defauts_checklist": list(
            feuille.checklist_items.filter(etat=EtatChecklist.DEFAUT).values_list("item", flat=True)
        ),
        "incidents_ouverts": list(
            Incident.objects.filter(vehicule=vehicule, statut=StatutIncident.OUVERT).values("id", "type_incident", "description")
        ),
    }


def effectuer_relais(feuille, nouveau_chauffeur, lieu, par):
    """Transfère le trajet en cours à `nouveau_chauffeur` : la feuille de route change de main avec l'état du véhicule, et
    le nouveau conducteur, la régulation et les gares sont prévenus du lieu et de l'heure."""
    if feuille.heure_depart_reelle is None or feuille.heure_arrivee_reelle is not None:
        raise ValidationError("Ce trajet n'est pas en cours : il n'y a pas de relais à faire.")
    if nouveau_chauffeur.role not in CHAUFFEURS or nouveau_chauffeur.company_id != feuille.company_id:
        raise ValidationError({"relais": "Le relais doit être un chauffeur de la compagnie."})
    if nouveau_chauffeur.pk == feuille.chauffeur_id:
        raise ValidationError({"relais": "Ce conducteur mène déjà ce trajet."})
    if trajets_en_cours(feuille.company_id).filter(chauffeur=nouveau_chauffeur).exists():
        raise ValidationError({"relais": "Ce conducteur est déjà en route sur un autre trajet."})
    lieu = (lieu or "").strip()
    if len(lieu) < 2:
        raise ValidationError({"lieu": "Indiquez le lieu du relais."})

    ancien = feuille.chauffeur
    depart = feuille.depart
    with transaction.atomic():
        etat = etat_du_vehicule(feuille)
        relais = Relais.objects.create(
            feuille_de_route=feuille, company=feuille.company, ancien_chauffeur=ancien, nouveau_chauffeur=nouveau_chauffeur,
            lieu=lieu[:255], effectue_par=par, etat_vehicule=etat,
        )
        feuille.chauffeur = nouveau_chauffeur
        feuille.save(update_fields=["chauffeur"])
        depart.chauffeur = nouveau_chauffeur  # une seule vérité sur qui conduit : le départ suit la feuille
        depart.save(update_fields=["chauffeur"])
        feuille.pauses.filter(fin__isnull=True).update(fin=relais.effectue_le)
    _prevenir_du_relais(relais, feuille, depart)
    return relais


def _prevenir_du_relais(relais, feuille, depart):
    heure = f"{timezone.localtime(relais.effectue_le):%H:%M}"
    gare_arrivee = depart.ligne.gare_arrivee
    defauts = relais.etat_vehicule.get("defauts_checklist") or []
    etat = f" Défaut(s) signalé(s) : {', '.join(defauts)}." if defauts else " Aucun défaut signalé sur la checklist."
    message = (
        f"Relais à {relais.lieu} à {heure} : {nom_complet(relais.ancien_chauffeur)} → {nom_complet(relais.nouveau_chauffeur)} "
        f"sur {depart.ligne.nom} ({relais.etat_vehicule.get('immatriculation')}).{etat}"
    )
    alerter(
        feuille.company,
        type=TypeAlerte.RELAIS,
        gravite=GraviteAlerte.INFO,
        titre=f"Relais sur {depart.ligne.nom} à {relais.lieu}",
        message=message,
        roles=[Role.CHEF_LIGNE],
        destinataires=[relais.nouveau_chauffeur, depart.ligne.gare_depart.chef, gare_arrivee.chef],
        objet=relais,
        cree_par=relais.effectue_par,
    )


# --- Checklist de reprise ------------------------------------------------------------------------------------------------


def reprise_a_faire(conducteur):
    """Le relais dont ce conducteur doit encore constater l'état du car (le dernier, trajet en cours, sans checklist), sinon None."""
    return (
        Relais.objects.filter(
            nouveau_chauffeur=conducteur, feuille_de_route__heure_arrivee_reelle__isnull=True, checklist_reprise__isnull=True
        )
        .select_related("feuille_de_route__depart__ligne__gare_depart__chef", "feuille_de_route__depart__vehicule")
        .order_by("-effectue_le")
        .first()
    )


def enregistrer_reprise(relais, items):
    """Enregistre la checklist de reprise du nouveau conducteur : les six items (`ITEMS_REPRISE`), chacun « ok » ou « defaut ». Refusée si le
    trajet est terminé, si la checklist est déjà faite, ou si un item manque ou est inconnu. Un défaut prévient la régulation et l'atelier ;
    un défaut de sécurité, aussi le QHSE et la direction des opérations (alerte critique)."""
    feuille = relais.feuille_de_route
    if feuille.heure_arrivee_reelle is not None:
        raise ValidationError("Ce trajet est terminé : il n'y a plus de reprise à constater.")
    if relais.checklist_reprise.exists():
        raise ValidationError("La checklist de reprise de ce relais est déjà faite.")
    if not isinstance(items, list) or not items:
        raise ValidationError({"items": "Renseignez l'état de chaque item du car."})
    etats = {}
    for element in items:
        item = str((element or {}).get("item", "")).strip().lower()
        etat = (element or {}).get("etat")
        if item not in ITEMS_REPRISE:
            raise ValidationError({"items": f"Item inconnu : « {item} ». Items attendus : {', '.join(ITEMS_REPRISE)}."})
        if etat not in EtatChecklist.values:
            raise ValidationError({"items": f"État invalide pour « {item} » : ok ou defaut."})
        if item in etats:
            raise ValidationError({"items": f"L'item « {item} » est renseigné deux fois."})
        etats[item] = (etat, str((element or {}).get("commentaire", "")).strip()[:500])
    manquants = [item for item in ITEMS_REPRISE if item not in etats]
    if manquants:
        raise ValidationError({"items": f"Il manque : {', '.join(manquants)}."})

    with transaction.atomic():
        for item in ITEMS_REPRISE:
            etat, commentaire = etats[item]
            ChecklistReprise.objects.create(relais=relais, company=relais.company, item=item, etat=etat, commentaire=commentaire)
    defauts = [item for item in ITEMS_REPRISE if etats[item][0] == EtatChecklist.DEFAUT]
    if defauts:
        _alerter_des_defauts_de_reprise(relais, defauts, etats)
    return relais


def _alerter_des_defauts_de_reprise(relais, defauts, etats):
    depart = relais.feuille_de_route.depart
    securite = [d for d in defauts if d in ITEMS_SECURITE]
    roles = [Role.CHEF_LIGNE, Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER]
    if securite:
        roles += [Role.QHSE, Role.DIRECTEUR_EXPLOITATION]
    details = " ; ".join(f"{d}" + (f" ({etats[d][1]})" if etats[d][1] else "") for d in defauts)
    alerter(
        relais.company,
        type=TypeAlerte.RELAIS,
        gravite=GraviteAlerte.CRITIQUE if securite else GraviteAlerte.ATTENTION,
        titre=f"Défaut à la reprise du trajet : {', '.join(defauts)} — {depart.vehicule.immatriculation}",
        message=(
            f"{nom_complet(relais.nouveau_chauffeur)} a repris {depart.ligne.nom} à {relais.lieu} et constate : {details}."
            + (" Défaut de sécurité : le car roule." if securite else "")
        ),
        roles=roles,
        destinataires=[depart.ligne.gare_depart.chef, depart.ligne.gare_arrivee.chef],
        objet=relais,
        cree_par=relais.nouveau_chauffeur,
    )


# --- Positions -----------------------------------------------------------------------------------------------------------


def _ligne_carte(trajet, position, maintenant):
    """Une position mise en forme pour la carte : même forme pour `GET /api/dashboard/carte/` (premier
    chargement) et pour ce que pousse `diffuser_position` (voir `dashboard/consumers.py`), pour que le
    site n'ait qu'une seule façon de les lire (`frontend/src/lib/carte.js`). Toujours JSON-sûr (un
    `Decimal` ou un `datetime` brut ferait échouer le message poussé : la couche de canaux le sérialise
    elle-même, contrairement à la réponse HTTP que DRF sait convertir seule) — latitude/longitude en texte
    à précision fixe (comme le fait déjà l'encodeur JSON de DRF pour un `Decimal`, jamais un nombre à
    virgule flottante qui perdrait des zéros significatifs), date en texte ISO.
    """
    age = maintenant - position.releve_le
    return {
        "vehicule": trajet.depart.vehicule_id,
        "immatriculation": trajet.depart.vehicule.immatriculation,
        "feuille_de_route": trajet.pk,
        "ligne": trajet.depart.ligne.nom,
        "chauffeur_nom": nom_complet(trajet.chauffeur),
        "latitude": str(position.latitude),
        "longitude": str(position.longitude),
        "vitesse_kmh": position.vitesse_kmh,
        "releve_le": position.releve_le.isoformat(),
        "age_secondes": max(0, int(age.total_seconds())),
        "en_direct": age <= PEREMPTION_POSITION,
        "fatigue": etat_fatigue(trajet, maintenant)["alerte"],
    }


def dernieres_positions(company_id, maintenant=None):
    """La dernière position connue de chaque car en route de la compagnie, avec ce qu'il faut pour l'afficher."""
    maintenant = maintenant or timezone.now()
    trajets = {t.pk: t for t in trajets_en_cours(company_id).select_related("depart__vehicule", "depart__ligne", "chauffeur")}
    derniers = (
        PositionVehicule.objects.filter(feuille_de_route_id__in=list(trajets))
        .order_by("feuille_de_route_id", "-releve_le", "-id")
        .distinct("feuille_de_route_id")
    )
    return [_ligne_carte(trajets[position.feuille_de_route_id], position, maintenant) for position in derniers]


def diffuser_position(trajet, position):
    """Pousse la position la plus récente d'un envoi aux navigateurs qui regardent la carte de la
    compagnie (voir `dashboard/consumers.py`, `PositionViewSet.create`). Silencieux si la couche de
    canaux n'est pas configurée (elle l'est toujours par défaut, voir `settings.CHANNEL_LAYERS`) : un
    relevé GPS n'a jamais besoin d'attendre ou de faire échouer sa propre requête pour cette raison."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    couche = get_channel_layer()
    if couche is None:
        return
    try:
        async_to_sync(couche.group_send)(
            f"carte_{trajet.company_id}", {"type": "position", "position": _ligne_carte(trajet, position, timezone.now())}
        )
    except Exception:  # noqa: BLE001 — Redis injoignable : les positions sont déjà enregistrées, un renvoi du lot les doublerait
        journal.warning("Diffusion de la position impossible (couche de canaux indisponible).", exc_info=True)


def derniere_position_recente(vehicule_id, maintenant=None, delai=PEREMPTION_POSITION):
    maintenant = maintenant or timezone.now()
    return PositionVehicule.objects.filter(vehicule_id=vehicule_id, releve_le__gte=maintenant - delai).order_by("-releve_le").first()


TAILLE_LOT_PURGE_POSITIONS = 5000


def purger_positions(retention_jours=None, maintenant=None, taille_lot=TAILLE_LOT_PURGE_POSITIONS):
    """Supprime les relevés GPS plus vieux que `retention_jours` (réglage `POSITIONS_RETENTION_JOURS` si omis), par lots de
    `taille_lot` pour ne jamais verrouiller la table longtemps sur une grosse purge de rattrapage. Idempotent : relancer
    sans nouveau relevé à supprimer renvoie 0. Voir `manage.py purger_positions_gps`."""
    if retention_jours is None:
        retention_jours = getattr(settings, "POSITIONS_RETENTION_JOURS", 30)
    seuil = (maintenant or timezone.now()) - datetime.timedelta(days=retention_jours)
    total = 0
    while True:
        lot = list(PositionVehicule.objects.filter(releve_le__lt=seuil).values_list("pk", flat=True)[:taille_lot])
        if not lot:
            break
        PositionVehicule.objects.filter(pk__in=lot).delete()
        total += len(lot)
    return total
