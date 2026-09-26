"""Suspendre ou réactiver le compte d'un agent : pouvoir d'intervention direct du PDG (« bloquer un compte guichetier »).

Un compte suspendu (`is_active` à faux) ne se connecte plus, et ses sessions ouvertes sont coupées à la requête suivante :
l'authentification par jeton refuse un compte inactif. Rien n'est supprimé : les ventes, les colis et le journal d'audit de
l'agent restent intacts, et la réactivation rend le compte tel qu'il était.
"""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from core.serializers import nom_complet

MOTIF_MIN = 5
# Ce que le PDG ne suspend pas ici : lui-même, un autre PDG, l'opérateur de la plateforme.
ROLES_INTOUCHABLES = {Role.PDG, Role.SUPERADMIN}


def _chef_de_la_gare(agent):
    affectation = getattr(agent, "affectation_gare", None)
    return affectation.gare.chef if affectation is not None and affectation.gare.chef_id else None


def _prevenir(agent, auteur, *, titre, message, gravite):
    chef = _chef_de_la_gare(agent)
    alerter(
        agent.company,
        type=TypeAlerte.COMPTE,
        gravite=gravite,
        titre=titre,
        message=message,
        roles=[Role.DRH],
        destinataires=[chef] if chef is not None else [],
        objet=agent,
        cree_par=auteur,
    )


def suspendre(agent, par, motif):
    motif = (motif or "").strip()
    if agent.pk == par.pk:
        raise ValidationError("Vous ne pouvez pas suspendre votre propre compte.")
    if agent.role in ROLES_INTOUCHABLES:
        raise ValidationError("Le compte d'un PDG ne se suspend pas ici.")
    if not agent.is_active:
        raise ValidationError("Ce compte est déjà suspendu.")
    if len(motif) < MOTIF_MIN:
        raise ValidationError({"motif": f"Indiquez le motif ({MOTIF_MIN} caractères au moins)."})
    agent.is_active = False
    agent.suspendu_le, agent.suspendu_par, agent.motif_suspension = timezone.now(), par, motif[:255]
    agent.save(update_fields=["is_active", "suspendu_le", "suspendu_par", "motif_suspension"])
    _prevenir(
        agent,
        par,
        titre=f"Compte suspendu : {nom_complet(agent)} ({agent.get_role_display()})",
        message=f"Suspendu par {nom_complet(par)}. Motif : {motif}.",
        gravite=GraviteAlerte.ATTENTION,
    )
    return agent


def reactiver(agent, par, motif=""):
    if agent.is_active:
        raise ValidationError("Ce compte n'est pas suspendu.")
    agent.is_active = True
    agent.suspendu_le, agent.suspendu_par, agent.motif_suspension = None, None, ""
    agent.save(update_fields=["is_active", "suspendu_le", "suspendu_par", "motif_suspension"])
    motif = (motif or "").strip()
    _prevenir(
        agent,
        par,
        titre=f"Compte réactivé : {nom_complet(agent)} ({agent.get_role_display()})",
        message=f"Réactivé par {nom_complet(par)}." + (f" {motif}." if motif else ""),
        gravite=GraviteAlerte.INFO,
    )
    return agent
