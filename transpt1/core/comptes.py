"""Les comptes du personnel : création, fiche, mot de passe provisoire (PDG et DRH), suspension (PDG).

Créer un compte ou réinitialiser son mot de passe donne un **mot de passe provisoire**, montré une seule fois à celui qui
l'a fait pour qu'il le remette à l'agent ; tant que l'agent ne l'a pas changé, son compte ne fait rien d'autre
(`core.authentification`). Réinitialiser ferme aussi les sessions ouvertes du compte.

Suspendre (`is_active` à faux) est un pouvoir d'intervention direct du PDG (« bloquer un compte guichetier ») : le compte ne
se connecte plus, et ses sessions ouvertes sont coupées à la requête suivante. Rien n'est supprimé : les ventes, les colis et
le journal d'audit de l'agent restent intacts, et la réactivation rend le compte tel qu'il était.
"""

import secrets

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role, User
from core.serializers import nom_complet
from core.textes import lire_texte

MOTIF_MIN = 5
# Ce que le PDG ne suspend pas ici : lui-même, un autre PDG, l'opérateur de la plateforme. Ni le PDG ni le DRH ne créent,
# ne modifient ou ne réinitialisent ces comptes-là ici.
ROLES_INTOUCHABLES = {Role.PDG, Role.SUPERADMIN}
# Sans lettres ni chiffres qui se confondent à la lecture (l, 1, I, O, 0) : le mot de passe se recopie à la main.
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def mot_de_passe_provisoire(agent=None):
    """Douze caractères en trois groupes (« Kx7m-Pq4z-Ta9r »), conformes aux règles de robustesse du serveur."""
    while True:
        mot = "-".join("".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(3))
        try:
            validate_password(mot, agent)
        except DjangoValidationError:
            continue
        return mot


def _prevenir_la_direction(agent, auteur, *, titre, message):
    """Le PDG est prévenu de ce que fait le DRH sur les comptes, et le DRH de ce que fait le PDG."""
    alerter(
        agent.company,
        type=TypeAlerte.COMPTE,
        gravite=GraviteAlerte.INFO,
        titre=titre,
        message=message,
        roles=[Role.PDG] if auteur.role == Role.DRH else [Role.DRH],
        objet=agent,
        cree_par=auteur,
    )


@transaction.atomic
def creer(par, *, gare=None, date_embauche=None, **champs):
    """Crée le compte (mot de passe provisoire à changer à la première connexion), l'affecte à sa gare (guichetier,
    bagagiste) et ouvre son dossier agent si la date d'embauche est donnée. Renvoie (agent, mot de passe provisoire)."""
    from reseau.models import AffectationGare
    from supports.models import DossierAgent

    agent = User(company_id=par.company_id, doit_changer_mot_de_passe=True, **champs)
    provisoire = mot_de_passe_provisoire(agent)
    agent.set_password(provisoire)
    agent.save()
    if gare is not None:
        AffectationGare.objects.create(agent=agent, gare=gare, company_id=par.company_id)
    if date_embauche is not None:
        DossierAgent.objects.create(
            agent=agent, company_id=par.company_id, date_embauche=date_embauche, poste=agent.get_role_display()
        )
    _prevenir_la_direction(
        agent,
        par,
        titre=f"Compte créé : {nom_complet(agent)} ({agent.get_role_display()})",
        message=f"Créé par {nom_complet(par)}, identifiant « {agent.username} ».",
    )
    return agent, provisoire


def changer_de_poste(agent, par, ancien_role):
    """Après un changement de poste : les sessions de l'agent sont fermées (il se reconnecte sur son nouvel espace) et la
    direction est prévenue."""
    agent.version_session += 1
    agent.save(update_fields=["version_session"])
    _prevenir_la_direction(
        agent,
        par,
        titre=f"Changement de poste : {nom_complet(agent)}",
        message=f"{Role(ancien_role).label} → {agent.get_role_display()}, par {nom_complet(par)}.",
    )


def reinitialiser(agent, par):
    """Nouveau mot de passe provisoire, sessions fermées. Renvoie le mot de passe provisoire."""
    if agent.pk == par.pk:
        raise ValidationError("Votre propre mot de passe se change dans « Mes paramètres ».")
    if agent.role in ROLES_INTOUCHABLES:
        raise ValidationError("Le mot de passe d'un PDG ne se réinitialise pas ici.")
    provisoire = mot_de_passe_provisoire(agent)
    agent.set_password(provisoire)
    agent.doit_changer_mot_de_passe = True
    agent.version_session += 1
    agent.save(update_fields=["password", "doit_changer_mot_de_passe", "version_session"])
    return provisoire


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
    motif = lire_texte(motif)
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
    motif = lire_texte(motif)
    if agent.is_active:
        raise ValidationError("Ce compte n'est pas suspendu.")
    agent.is_active = True
    agent.suspendu_le, agent.suspendu_par, agent.motif_suspension = None, None, ""
    agent.save(update_fields=["is_active", "suspendu_le", "suspendu_par", "motif_suspension"])
    _prevenir(
        agent,
        par,
        titre=f"Compte réactivé : {nom_complet(agent)} ({agent.get_role_display()})",
        message=f"Réactivé par {nom_complet(par)}." + (f" {motif}." if motif else ""),
        gravite=GraviteAlerte.INFO,
    )
    return agent
