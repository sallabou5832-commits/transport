"""Fermer ou rouvrir une ligne : la demande, la décision, l'application et les alertes qui les accompagnent.

Le PDG « gèle » une ligne et le directeur des opérations valide ouvertures et fermetures temporaires : ils appliquent
directement. Le chef de ligne et le chef de gare, qui voient le terrain, demandent ; le directeur des opérations décide.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from reseau.models import ActionChangementLigne, ChangementLigne, StatutChangementLigne, StatutLigne

DECIDEURS = {Role.DIRECTEUR_EXPLOITATION, Role.PDG}
DEMANDEURS = {Role.CHEF_LIGNE, Role.CHEF_GARE}
MOTIF_MIN = 5


def departs_a_traiter(ligne):
    """Départs planifiés à venir sur la ligne : ce que sa fermeture oblige à réaffecter ou à annuler."""
    from billetterie.models import Depart, DepartStatut

    return Depart.objects.filter(ligne=ligne, statut=DepartStatut.PLANIFIE, date_heure__gte=timezone.now()).count()


def _chefs_de_gare(ligne):
    return {gare.chef for gare in (ligne.gare_depart, ligne.gare_arrivee) if gare.chef_id}


def _date(jour):
    return f"{jour:%d/%m/%Y}"


def enregistrer(ligne, utilisateur, *, action, motif, jusqu_au=None):
    """Enregistre une demande de fermeture ou de réouverture. Faite par la direction des opérations ou le PDG, elle
    s'applique aussitôt ; faite par un chef de ligne ou de gare, elle attend la décision du directeur des opérations."""
    motif = (motif or "").strip()
    if action not in ActionChangementLigne.values:
        raise ValidationError({"action": "Action attendue : fermer ou rouvrir."})
    if len(motif) < MOTIF_MIN:
        raise ValidationError({"motif": f"Indiquez le motif ({MOTIF_MIN} caractères au moins)."})
    if action == ActionChangementLigne.FERMER:
        if ligne.est_fermee:
            raise ValidationError("Cette ligne est déjà fermée.")
        if jusqu_au is not None and jusqu_au < timezone.localdate():
            raise ValidationError({"jusqu_au": "Cette date est déjà passée."})
    else:
        if not ligne.est_fermee:
            raise ValidationError("Cette ligne n'est pas fermée.")
        jusqu_au = None

    direct = utilisateur.role in DECIDEURS
    if not direct and ligne.changements.filter(action=action, statut=StatutChangementLigne.EN_ATTENTE).exists():
        raise ValidationError("Une demande identique est déjà en attente de décision.")

    with transaction.atomic():  # une application refusée ne laisse pas de demande orpheline
        changement = ChangementLigne.objects.create(
            ligne=ligne, company=ligne.company, action=action, motif=motif, jusqu_au=jusqu_au, demandeur=utilisateur
        )
        if direct:
            _appliquer(changement, utilisateur)
    if not direct:
        verbe = "fermeture" if action == ActionChangementLigne.FERMER else "réouverture"
        alerter(
            ligne.company,
            type=TypeAlerte.DEMANDE_LIGNE,
            gravite=GraviteAlerte.ATTENTION,
            titre=f"Demande de {verbe} : {ligne.nom}",
            message=f"{motif}. Demandée par {utilisateur.get_full_name() or utilisateur.username}. À valider ou refuser.",
            roles=[Role.DIRECTEUR_EXPLOITATION],
            objet=changement,
            cree_par=utilisateur,
        )
    return changement


def decider(changement, utilisateur, *, decision, commentaire=""):
    """Le directeur des opérations (ou le PDG) valide ou refuse une demande."""
    if changement.statut != StatutChangementLigne.EN_ATTENTE:
        raise ValidationError("Cette demande a déjà été traitée.")
    commentaire = (commentaire or "").strip()[:255]
    if decision == "valider":
        _appliquer(changement, utilisateur, commentaire)
        return changement
    if decision != "refuser":
        raise ValidationError({"decision": "Décision attendue : valider ou refuser."})
    changement.statut = StatutChangementLigne.REFUSE
    changement.decide_par, changement.decide_le, changement.commentaire_decision = utilisateur, timezone.now(), commentaire
    changement.save()
    _prevenir_demandeur(changement, utilisateur, "refusée")
    return changement


def _appliquer(changement, decideur, commentaire=""):
    maintenant = timezone.now()
    with transaction.atomic():
        ligne = type(changement.ligne).objects.select_for_update().get(pk=changement.ligne_id)
        if changement.action == ActionChangementLigne.FERMER:
            if ligne.est_fermee:
                raise ValidationError("Cette ligne est déjà fermée.")
            ligne.statut, ligne.fermee_jusqu_au, ligne.motif_fermeture = StatutLigne.FERMEE, changement.jusqu_au, changement.motif
        else:
            if not ligne.est_fermee:
                raise ValidationError("Cette ligne n'est pas fermée : la demande n'a plus d'objet.")
            ligne.statut, ligne.fermee_jusqu_au, ligne.motif_fermeture = StatutLigne.OUVERTE, None, ""
        ligne.save(update_fields=["statut", "fermee_jusqu_au", "motif_fermeture"])
        changement.ligne = ligne
        changement.statut = StatutChangementLigne.VALIDE
        changement.decide_par, changement.decide_le, changement.commentaire_decision = decideur, maintenant, commentaire
        changement.save()
        # Les demandes identiques encore en attente n'ont plus lieu d'être : la ligne est dans l'état demandé.
        for autre in ligne.changements.filter(action=changement.action, statut=StatutChangementLigne.EN_ATTENTE):
            autre.statut, autre.decide_par, autre.decide_le = StatutChangementLigne.VALIDE, decideur, maintenant
            autre.commentaire_decision = "Appliquée par une autre décision."
            autre.save()

    _annoncer(changement, ligne, decideur)
    if changement.demandeur_id != decideur.id:
        _prevenir_demandeur(changement, decideur, "acceptée")


def _annoncer(changement, ligne, decideur):
    """La fermeture (ou la réouverture) prévient tous ceux que la ligne concerne : régulation, gares aux deux bouts, direction."""
    if changement.action == ActionChangementLigne.FERMER:
        restants = departs_a_traiter(ligne)
        duree = f"jusqu'au {_date(ligne.fermee_jusqu_au)} inclus" if ligne.fermee_jusqu_au else "jusqu'à réouverture"
        reste = f"{restants} départ(s) planifié(s) à réaffecter ou annuler." if restants else "Aucun départ planifié."
        titre, gravite = f"Ligne fermée : {ligne.nom}", GraviteAlerte.ATTENTION
        message = f"{changement.motif} — {duree}. {reste}"
        roles = [Role.CHEF_LIGNE, Role.DIRECTEUR_EXPLOITATION, Role.PDG]
    else:
        titre, gravite = f"Ligne rouverte : {ligne.nom}", GraviteAlerte.INFO
        message = f"{changement.motif}. Les départs peuvent de nouveau être planifiés et les billets vendus."
        roles = [Role.CHEF_LIGNE, Role.DIRECTEUR_EXPLOITATION]
    alerter(
        ligne.company,
        type=TypeAlerte.LIGNE,
        gravite=gravite,
        titre=titre,
        message=message,
        roles=roles,
        destinataires=_chefs_de_gare(ligne),
        objet=ligne,
        cree_par=decideur,
    )


def _prevenir_demandeur(changement, decideur, issue):
    verbe = "fermeture" if changement.action == ActionChangementLigne.FERMER else "réouverture"
    commentaire = f" {changement.commentaire_decision}" if changement.commentaire_decision else ""
    alerter(
        changement.company,
        type=TypeAlerte.DEMANDE_LIGNE,
        gravite=GraviteAlerte.INFO,
        titre=f"Demande de {verbe} {issue} : {changement.ligne.nom}",
        message=f"Décision de {decideur.get_full_name() or decideur.username}.{commentaire}",
        destinataires=[changement.demandeur],
        objet=changement,
        cree_par=decideur,
    )


def annoncer_reaffectation(vehicule, ancienne, nouvelle, motif, auteur):
    """Un véhicule change de gare d'attache : les chefs des deux gares et la régulation le savent aussitôt."""
    origine = f"Depuis {ancienne.nom}" if ancienne else "Sans gare d'attache jusque-là"
    alerter(
        vehicule.company,
        type=TypeAlerte.REAFFECTATION,
        gravite=GraviteAlerte.INFO,
        titre=f"Véhicule {vehicule.immatriculation} rattaché à {nouvelle.nom}",
        message=f"{origine}. Motif : {motif}.",
        roles=[Role.CHEF_LIGNE],
        destinataires={gare.chef for gare in (ancienne, nouvelle) if gare is not None and gare.chef_id},
        objet=vehicule,
        cree_par=auteur,
    )
