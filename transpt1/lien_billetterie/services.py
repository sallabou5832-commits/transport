"""Le mode de billetterie d'une compagnie, et l'enregistrement des ventes et des annulations venues de son logiciel.

Une vente reçue devient un vrai billet (`billetterie.Ticket`), avec les mêmes garde-fous que celle du guichet : les places
sont prises sous verrou du départ, celles réservées pour la vente hors ligne restent aux guichets (en billetterie mixte, les
deux ventes se partagent les places sans survente). Elle n'entre dans la caisse d'aucun guichetier (l'argent est dans le
logiciel de la compagnie) et aucun SMS n'est envoyé (le logiciel prévient lui-même son client). Chaque vente est
reconnue par sa référence dans ce logiciel : la recevoir deux fois (lot rejoué, fichier réimporté) ne crée rien de plus.
"""

import datetime
from collections import Counter
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from billetterie import reservations
from billetterie.models import Depart, ModePaiement, StatutTicket, Ticket
from billetterie.ventes import annuler_ticket
from core.entiers import lire_entier
from lien_billetterie.models import ModeBilletterie, ReglageBilletterie
from personnel_roulant.controle import normaliser_code

# Une vente qui serait datée plus tard que maintenant (horloges mal réglées comprises) n'a pas encore eu lieu.
TOLERANCE_HORLOGE = datetime.timedelta(minutes=5)
FORMATS_DATE_HEURE = [
    "iso-8601", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %Hh%M",
]


def mode_billetterie(company_id):
    """Le mode de billetterie de la compagnie ; sans réglage, la billetterie est intégrée."""
    reglage = ReglageBilletterie.objects.filter(company_id=company_id).first() if company_id is not None else None
    return reglage.mode if reglage is not None else ModeBilletterie.INTEGRE


def exiger_vente_au_guichet(user):
    """Refuse (403) la vente au guichet quand la billetterie de la compagnie passe tout entière par son logiciel."""
    if mode_billetterie(user.company_id) == ModeBilletterie.EXTERNE:
        raise PermissionDenied(
            "La billetterie de la compagnie passe par son propre logiciel : la vente au guichet est fermée."
        )


def exiger_lien_ouvert(company_id):
    """Refuse (403) les ventes d'un logiciel externe tant que la compagnie garde la billetterie intégrée."""
    if mode_billetterie(company_id) == ModeBilletterie.INTEGRE:
        raise PermissionDenied(
            "La billetterie de la compagnie est intégrée : elle ne reçoit pas les ventes d'un autre logiciel. "
            "Le PDG ou le directeur des opérations peut passer en billetterie externe ou mixte."
        )


class VenteExterneSerializer(serializers.Serializer):
    """Une vente du logiciel de la compagnie. Le départ se désigne par son identifiant (`depart`, lu dans
    `GET /lien-billetterie/departs/`) ou, pour un logiciel qui ne connaît pas nos identifiants, par sa ligne (nom ou
    identifiant) et sa date et heure de départ, à la minute près."""

    reference = serializers.CharField(max_length=64)
    depart = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    ligne = serializers.CharField(max_length=255, required=False, allow_blank=True)
    date_heure = serializers.DateTimeField(required=False, allow_null=True, input_formats=FORMATS_DATE_HEURE)
    passager_nom = serializers.CharField(max_length=255)
    passager_telephone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    prix = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True
    )
    mode_paiement = serializers.ChoiceField(choices=ModePaiement.choices)
    vendu_le = serializers.DateTimeField(required=False, allow_null=True, input_formats=FORMATS_DATE_HEURE)

    def validate_vendu_le(self, vendu_le):
        if vendu_le is not None and vendu_le > timezone.now() + TOLERANCE_HORLOGE:
            raise serializers.ValidationError("Une vente ne peut pas être datée du futur.")
        return vendu_le

    def validate(self, attrs):
        attrs["depart"] = self._depart(self.context["company"], attrs)
        return attrs

    @staticmethod
    def _depart(company, attrs):
        departs = Depart.objects.filter(company=company).select_related("ligne", "ligne__gare_depart")
        if attrs.get("depart") is not None:
            depart = departs.filter(pk=attrs["depart"]).first()
        elif attrs.get("ligne") and attrs.get("date_heure"):
            ligne = attrs["ligne"].strip()
            ligne_id = lire_entier(ligne)
            departs = departs.filter(ligne_id=ligne_id) if ligne_id is not None else departs.filter(ligne__nom__iexact=ligne)
            minute = attrs["date_heure"].replace(second=0, microsecond=0)
            depart = departs.filter(date_heure__gte=minute, date_heure__lt=minute + datetime.timedelta(minutes=1)).first()
        else:
            raise serializers.ValidationError(
                {"depart": "Indiquez le départ : son identifiant, ou sa ligne et sa date et heure de départ."}
            )
        if depart is None:
            raise serializers.ValidationError({"depart": "Aucun départ de la compagnie ne correspond."})
        return depart


def _resultat(reference, statut, ticket):
    return {"reference": reference, "statut": statut, "ticket": ticket.pk, "code": ticket.code}


def _refus(reference, erreurs):
    return {"reference": reference, "statut": "refusee", "erreurs": erreurs}


def _reference(donnees):
    return str(donnees.get("reference") or "").strip() if isinstance(donnees, dict) else ""


def enregistrer_vente(company, donnees, *, source, logiciel, chef_de_gare_id=None):
    """Enregistre une vente du logiciel de la compagnie et renvoie ce qu'il en est advenu : `creee`, `deja_recue` (même
    référence déjà reçue : rien ne change, même si le départ est complet depuis) ou `refusee` (avec les erreurs).

    `chef_de_gare_id` : l'import d'un chef de gare ne porte que sur les départs de la gare qu'il dirige."""
    reference = _reference(donnees)
    if not isinstance(donnees, dict):
        return _refus(reference, {"vente": "Une vente est un objet : {reference, depart, passager_nom, ...}."})
    existant = Ticket.objects.filter(company=company, reference_externe=reference).first() if reference else None
    if existant is not None:
        return _resultat(reference, "deja_recue", existant)

    serializer = VenteExterneSerializer(data=donnees, context={"company": company})
    if not serializer.is_valid():
        return _refus(reference, serializer.errors)
    vente = serializer.validated_data
    reference = vente["reference"].strip()
    if chef_de_gare_id is not None and vente["depart"].ligne.gare_depart.chef_id != chef_de_gare_id:
        return _refus(reference, {"depart": "Ce départ ne part pas de votre gare."})

    try:
        with transaction.atomic():
            depart = Depart.objects.select_for_update().select_related("vehicule", "ligne").get(pk=vente["depart"].pk)
            reservations.consommer_une_place(depart, None)
            tarif = depart.ligne.tarif
            prix = vente.get("prix") or tarif
            if prix is None:
                raise ValidationError({"prix": "Ce champ est obligatoire : cette ligne n'a pas de tarif."})
            ticket = Ticket.objects.create(
                depart=depart,
                company=company,
                passager_nom=vente["passager_nom"].strip(),
                passager_telephone=vente["passager_telephone"].strip(),
                prix=prix,
                prix_tarif=tarif,
                # Le logiciel de la compagnie a fixé ce prix : l'écart au tarif reste visible, comme une dérogation.
                motif_derogation=f"Prix fixé par {logiciel}"[:255] if tarif is not None and prix != tarif else "",
                mode_paiement=vente["mode_paiement"],
                source=source,
                logiciel=logiciel,
                reference_externe=reference,
                code_externe=normaliser_code(reference)[:32],
            )
            if vente.get("vendu_le") is not None:  # la date de la vente, pas celle de sa réception (recettes du jour)
                Ticket.objects.filter(pk=ticket.pk).update(date_vente=vente["vendu_le"])
            depart.places_vendues += 1
            depart.save(update_fields=["places_vendues"])
    except ValidationError as erreur:
        return _refus(reference, erreur.detail)
    except IntegrityError:
        # La même vente reçue deux fois au même instant : l'autre envoi l'a enregistrée.
        existant = Ticket.objects.filter(company=company, reference_externe=reference).first()
        if existant is None:
            raise
        return _resultat(reference, "deja_recue", existant)
    return _resultat(reference, "creee", ticket)


def annuler_vente(company, donnees, *, logiciel):
    """Annule une vente reçue du logiciel de la compagnie (désignée par sa référence) : `annulee`, `deja_annulee` ou
    `refusee`. La place est libérée et la vente sort des recettes, comme une annulation au guichet."""
    reference = _reference(donnees)
    if not reference:
        return _refus(reference, {"reference": "Indiquez la référence de la vente à annuler."})
    ticket = Ticket.objects.filter(company=company, reference_externe=reference).first()
    if ticket is None:
        return _refus(reference, {"reference": "Aucune vente reçue sous cette référence."})
    if ticket.statut == StatutTicket.ANNULE:
        return _resultat(reference, "deja_annulee", ticket)
    motif = str(donnees.get("motif") or "").strip()
    try:
        ticket = annuler_ticket(ticket.pk, par=None, motif=f"Annulé dans {logiciel}" + (f" : {motif}" if motif else ""))
    except ValidationError:  # annulée entre-temps par un autre envoi
        return _resultat(reference, "deja_annulee", ticket)
    return _resultat(reference, "annulee", ticket)


STATUTS = ("creee", "deja_recue", "annulee", "deja_annulee", "refusee")


def bilan(resultats):
    """Le compte rendu d'un lot : chaque résultat, et combien de chaque sorte."""
    nombres = Counter(resultat["statut"] for resultat in resultats)
    return {"resultats": resultats, **{statut: nombres[statut] for statut in STATUTS}}
