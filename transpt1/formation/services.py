from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from formation.models import ParcoursFormation, ProgressionFormation


def parcours_du_role(user):
    """Le parcours de formation correspondant au rôle de l'utilisateur."""
    parcours = (
        ParcoursFormation.objects.prefetch_related("etapes").filter(role=user.role).first()
    )
    if parcours is None:
        raise NotFound("Aucun parcours de formation n'existe pour votre rôle.")
    return parcours


def progression_de(user, parcours):
    return ProgressionFormation.objects.filter(user=user, parcours=parcours).first()


def demarrer_parcours(user):
    """Démarre (ou reprend, sans rien réinitialiser) le parcours de l'utilisateur."""
    parcours = parcours_du_role(user)
    premiere_etape = parcours.etapes.order_by("ordre").first()
    if premiere_etape is None:
        raise ValidationError("Ce parcours de formation ne contient encore aucune étape.")
    progression, _ = ProgressionFormation.objects.get_or_create(
        user=user, parcours=parcours, defaults={"etape_courante": premiere_etape}
    )
    return parcours, progression


def terminer_etape(user, etape_id):
    """Marque l'étape courante comme terminée et avance à la suivante.

    Seule l'étape courante peut être terminée : on ne saute pas d'étape et on ne
    rejoue pas une étape déjà faite. Ne touche que les tables ``formation_*``.
    """
    parcours = parcours_du_role(user)
    etape = get_object_or_404(parcours.etapes, pk=etape_id)

    with transaction.atomic():
        # Pas de select_related : etape_courante est nullable, donc la jointure serait
        # externe et PostgreSQL refuse FOR UPDATE dessus. On verrouille la ligne seule.
        progression = (
            ProgressionFormation.objects.select_for_update()
            .filter(user=user, parcours=parcours)
            .first()
        )
        if progression is None:
            raise ValidationError("Démarrez d'abord votre parcours de formation.")
        if progression.termine:
            raise ValidationError("Ce parcours de formation est déjà terminé.")

        courante = progression.etape_courante
        if etape.ordre < courante.ordre:
            raise ValidationError("Cette étape est déjà terminée.")
        if etape.ordre > courante.ordre:
            raise ValidationError(f"Terminez d'abord l'étape « {courante.titre} ».")

        suivante = parcours.etapes.filter(ordre__gt=etape.ordre).order_by("ordre").first()
        if suivante is not None:
            progression.etape_courante = suivante
        else:
            progression.etape_courante = None
            progression.termine = True
            progression.date_fin = timezone.now()
        progression.save(update_fields=["etape_courante", "termine", "date_fin"])

    return parcours, progression
