"""Règles métier des colis hors HTTP : prévenir le client, annoncer la restitution, répartir le poids en soute."""

import logging
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from colis.models import Colis, StatutColis
from core.models import Role
from notifications.models import CanalNotification
from notifications.providers import normaliser_numero
from notifications.services import envoyer_sms, envoyer_whatsapp
from reseau.models import AffectationGare

logger = logging.getLogger(__name__)

# Répartition du poids en soute : trois zones, de l'avant vers l'arrière du car.
ZONES_SOUTE = ("avant", "milieu", "arrière")


def charge_max_soute_kg():
    return Decimal(str(getattr(settings, "COLIS_SOUTE_CHARGE_MAX_KG", 2000)))


# --- Prévenir le client -------------------------------------------------------------------------------------------


def _messages(colis, evenement, code):
    """[(numéro, texte)] pour l'expéditeur et le destinataire à cette étape. Un même numéro ne reçoit qu'un message."""
    ref, gare = colis.reference, colis.gare_arrivee.nom
    depart = colis.depart
    date = f"{timezone.localtime(depart.date_heure):%d/%m à %H:%M}"
    exp, dest = colis.expediteur_telephone, colis.destinataire_telephone

    if evenement == "enregistre":
        pour_dest = (
            f"Colis {ref} de {colis.expediteur_nom} enregistré pour vous ({colis.description}). "
            f"Code de retrait : {code}. À présenter à la gare de {gare}, après l'arrivée du car."
        )
        pour_exp = (
            f"Colis {ref} enregistré ({colis.description}) pour {colis.destinataire_nom}, "
            f"départ {depart.ligne.nom} le {date}. Frais : {colis.frais:.0f} FCFA. Vous serez prévenu à chaque étape."
        )
    elif evenement == "charge":
        pour_dest = pour_exp = f"Colis {ref} chargé dans le car {depart.ligne.nom} du {date} : il est en route."
    elif evenement == "arrive":
        pour_dest = (
            f"Votre colis {ref} est arrivé à la gare de {gare}. Retrait sur présentation de votre code de retrait."
        )
        pour_exp = f"Colis {ref} arrivé à la gare de {gare}. {colis.destinataire_nom} en est prévenu."
    elif evenement == "retire":
        pour_dest = f"Colis {ref} remis à {colis.retire_par_nom or colis.destinataire_nom}. Merci de votre confiance."
        pour_exp = f"Colis {ref} retiré par {colis.retire_par_nom or colis.destinataire_nom} à la gare de {gare}."
    elif evenement == "annule":
        pour_dest = pour_exp = f"Colis {ref} annulé ({colis.motif_annulation}). Les frais vous seront rendus."
    elif evenement == "nouveau_code":
        pour_dest = f"Colis {ref} : votre nouveau code de retrait est {code}. L'ancien ne fonctionne plus."
        pour_exp = None
    else:
        raise ValueError(f"Étape de colis inconnue : {evenement}")

    messages = {}
    if exp and pour_exp:
        messages[normaliser_numero(exp)] = pour_exp
    messages[normaliser_numero(dest)] = pour_dest  # le destinataire l'emporte si c'est le même numéro (il a le code)
    return list(messages.items())


def notifier(colis, evenement, *, code=None):
    """Prévient l'expéditeur et le destinataire par SMS et/ou WhatsApp (`NOTIFICATIONS_CANAUX_COLIS`), sans jamais
    faire échouer l'opération de colis : un échec est tracé dans le journal des notifications."""
    try:
        for numero, texte in _messages(colis, evenement, code):
            for canal in settings.NOTIFICATIONS_CANAUX_COLIS:
                if canal == CanalNotification.SMS:
                    envoyer_sms(numero, texte, company=colis.company, colis=colis)
                elif canal == CanalNotification.WHATSAPP:
                    envoyer_whatsapp(numero, texte, company=colis.company, colis=colis)
                else:
                    logger.warning("Canal de notification de colis inconnu ignoré : %r", canal)
    except Exception:  # noqa: BLE001 — jamais d'échec de l'opération métier à cause d'un message
        logger.exception("Impossible de prévenir le client du colis %s", colis.pk)


# --- Restitution : prévenir les gares -----------------------------------------------------------------------------


def _equipe_bagagistes(gare):
    """Les bagagistes affectés à cette gare et son chef ; à défaut d'affectation, tous les bagagistes de la compagnie
    (mieux vaut prévenir trop de monde qu'un colis qui attend sans que personne le sache)."""
    bagagistes = [a.agent for a in AffectationGare.objects.filter(gare=gare, agent__role=Role.BAGAGISTE).select_related("agent")]
    roles = [] if bagagistes else [Role.BAGAGISTE]
    return roles, [*bagagistes, gare.chef]


def annoncer_restitution(depart):
    """Au départ du car : la gare d'arrivée sait combien de colis elle doit restituer, et la gare de départ, s'il
    reste des colis enregistrés que personne n'a chargés."""
    charges = depart.colis.filter(statut=StatutColis.CHARGE)
    nombre = charges.count()
    if nombre:
        poids = charges.aggregate(poids=Sum("poids_kg"))["poids"] or Decimal("0")
        gare = depart.ligne.gare_arrivee
        roles, destinataires = _equipe_bagagistes(gare)
        alerter(
            depart.company,
            type=TypeAlerte.COLIS,
            gravite=GraviteAlerte.INFO,
            titre=f"{nombre} colis à restituer : {depart.ligne.nom}",
            message=(
                f"Le car {depart.vehicule.immatriculation} est parti de {depart.ligne.gare_depart.nom} avec {nombre} "
                f"colis ({poids:.0f} kg) à restituer à la gare de {gare.nom}."
            ),
            roles=roles,
            destinataires=destinataires,
            objet=depart,
            cle=f"colis:restitution:{depart.pk}",
        )
    oublies = depart.colis.filter(statut=StatutColis.ENREGISTRE).count()
    if oublies:
        gare = depart.ligne.gare_depart
        roles, destinataires = _equipe_bagagistes(gare)
        alerter(
            depart.company,
            type=TypeAlerte.COLIS,
            gravite=GraviteAlerte.ATTENTION,
            titre=f"{oublies} colis enregistré(s) non chargé(s) : {depart.ligne.nom}",
            message="Le car est parti sans ces colis : à reprogrammer sur le prochain départ ou à annuler.",
            roles=roles,
            destinataires=destinataires,
            objet=depart,
            cle=f"colis:non-charges:{depart.pk}",
        )


def marquer_arrives(depart):
    """À l'arrivée du car : les colis chargés sont arrivés ; les clients en sont prévenus, la gare d'arrivée aussi."""
    arrives = list(depart.colis.filter(statut=StatutColis.CHARGE).select_related("depart__ligne__gare_arrivee"))
    if not arrives:
        return 0
    maintenant = timezone.now()
    for colis in arrives:
        colis.statut = StatutColis.ARRIVE
        colis.arrive_le = maintenant
        colis.save(update_fields=["statut", "arrive_le"])
        notifier(colis, "arrive")
    gare = depart.ligne.gare_arrivee
    roles, destinataires = _equipe_bagagistes(gare)
    alerter(
        depart.company,
        type=TypeAlerte.COLIS,
        gravite=GraviteAlerte.ATTENTION,
        titre=f"{len(arrives)} colis arrivé(s) à retirer : {gare.nom}",
        message="Les destinataires ont été prévenus par SMS : ils se présentent avec leur code de retrait.",
        roles=roles,
        destinataires=destinataires,
        objet=depart,
        cle=f"colis:arrives:{depart.pk}",
    )
    return len(arrives)


# --- Aide au chargement -------------------------------------------------------------------------------------------


def plan_chargement(depart):
    """Répartition du poids en soute : les colis les plus lourds d'abord, chacun dans la zone la moins chargée, pour
    équilibrer le car. Ne compte que les colis qui voyagent (ni annulés, ni déjà remis)."""
    a_placer = list(
        depart.colis.filter(statut__in=[StatutColis.ENREGISTRE, StatutColis.CHARGE]).order_by("-poids_kg", "id")
    )
    zones = {nom: {"nom": nom, "poids_kg": Decimal("0"), "colis": []} for nom in ZONES_SOUTE}
    ordre = []
    for colis in a_placer:
        zone = min(zones.values(), key=lambda z: (z["poids_kg"], ZONES_SOUTE.index(z["nom"])))
        zone["poids_kg"] += colis.poids_kg
        zone["colis"].append({"id": colis.id, "reference": colis.reference, "description": colis.description,
                              "poids_kg": colis.poids_kg, "statut": colis.statut})
        ordre.append({"colis": colis.id, "reference": colis.reference, "zone": zone["nom"], "poids_kg": colis.poids_kg})
    total = sum((z["poids_kg"] for z in zones.values()), Decimal("0"))
    poids = [z["poids_kg"] for z in zones.values()]
    return {
        "depart": depart.id,
        "zones": list(zones.values()),
        "ordre_chargement": ordre,
        "poids_total_kg": total,
        "ecart_max_kg": max(poids) - min(poids) if poids else Decimal("0"),
        "charge_max_kg": charge_max_soute_kg(),
        "depasse": total > charge_max_soute_kg(),
    }
