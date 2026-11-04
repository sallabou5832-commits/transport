from django.utils import timezone
from rest_framework import serializers

from billetterie.models import DepartStatut, StatutTicket
from colis.models import Colis, TypeColis
from core.serializers import CompanySerializer, nom_complet
from core.telephones import valider_telephone


def _telephone(valeur, obligatoire):
    if obligatoire and not (valeur or "").strip():
        raise serializers.ValidationError("Ce numéro est obligatoire : c'est par lui que le client est prévenu.")
    return valider_telephone(valeur)


class ColisSerializer(serializers.ModelSerializer):
    """Le code de retrait n'apparaît jamais ici : il part par SMS ou WhatsApp au destinataire, et n'est conservé
    que sous forme d'empreinte."""

    company = CompanySerializer(read_only=True)
    reference = serializers.CharField(read_only=True)
    depart_libelle = serializers.SerializerMethodField()
    gare_depart = serializers.IntegerField(source="depart.ligne.gare_depart_id", read_only=True)
    gare_depart_nom = serializers.CharField(source="depart.ligne.gare_depart.nom", read_only=True)
    depart_statut = serializers.CharField(source="depart.statut", read_only=True)
    gare_arrivee = serializers.IntegerField(source="depart.ligne.gare_arrivee_id", read_only=True)
    gare_arrivee_nom = serializers.CharField(source="depart.ligne.gare_arrivee.nom", read_only=True)
    enregistre_par_nom = serializers.SerializerMethodField()
    code_verrouille = serializers.BooleanField(read_only=True)

    class Meta:
        model = Colis
        extra_kwargs = {
            # Renseignés par le billet du voyageur quand le bagage est lié à un billet (voir `validate`).
            "expediteur_nom": {"required": False},
            "destinataire_nom": {"required": False},
            "destinataire_telephone": {"required": False},
            "mode_paiement": {"required": False},
        }
        fields = [
            "id", "reference", "company", "depart", "depart_libelle", "depart_statut", "gare_depart", "gare_depart_nom", "gare_arrivee",
            "gare_arrivee_nom", "ticket", "type_colis", "description", "poids_kg", "valeur_declaree", "frais",
            "mode_paiement", "expediteur_nom", "expediteur_telephone", "destinataire_nom", "destinataire_telephone",
            "statut", "code_verrouille", "enregistre_par", "enregistre_par_nom", "enregistre_le", "charge_le",
            "arrive_le", "retire_le", "retire_par_nom", "annule_le", "motif_annulation",
        ]
        read_only_fields = [
            "company", "statut", "enregistre_par", "enregistre_le", "charge_le", "arrive_le", "retire_le",
            "retire_par_nom", "annule_le", "motif_annulation",
        ]

    def get_depart_libelle(self, obj):
        return f"{obj.depart.ligne.nom} — {timezone.localtime(obj.depart.date_heure):%d/%m %H:%M}"

    def get_enregistre_par_nom(self, obj):
        return nom_complet(obj.enregistre_par)

    def validate_depart(self, depart):
        if depart.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("Ce départ n'appartient pas à votre compagnie.")
        return depart

    def validate(self, attrs):
        if self.instance is not None:  # lecture seule après enregistrement : les changements passent par les actions
            raise serializers.ValidationError("Un colis enregistré ne se modifie pas : utilisez les actions de suivi.")
        depart, ticket = attrs["depart"], attrs.get("ticket")
        erreurs = {}

        from personnel_roulant.models import FeuilleDeRoute

        parti = depart.statut != DepartStatut.PLANIFIE or FeuilleDeRoute.objects.filter(
            depart=depart, heure_depart_reelle__isnull=False
        ).exists()
        if parti:
            erreurs["depart"] = "Ce départ est déjà parti ou terminé : on n'y enregistre plus de colis."

        if ticket is not None:
            if ticket.company_id != depart.company_id or ticket.depart_id != depart.pk:
                erreurs["ticket"] = "Ce billet n'est pas celui d'un voyageur de ce départ."
            elif ticket.statut == StatutTicket.ANNULE:
                erreurs["ticket"] = "Ce billet est annulé."
            else:  # le bagage d'un voyageur : expéditeur et destinataire sont, par défaut, le voyageur lui-même
                attrs.setdefault("expediteur_nom", ticket.passager_nom)
                attrs.setdefault("expediteur_telephone", ticket.passager_telephone)
                attrs.setdefault("destinataire_nom", ticket.passager_nom)
                attrs.setdefault("destinataire_telephone", ticket.passager_telephone)
                attrs.setdefault("type_colis", TypeColis.BAGAGE)

        for champ in ("expediteur_nom", "destinataire_nom"):
            if not (attrs.get(champ) or "").strip():
                erreurs.setdefault(champ, "Ce champ est obligatoire.")
        try:
            attrs["destinataire_telephone"] = _telephone(attrs.get("destinataire_telephone"), obligatoire=True)
        except serializers.ValidationError as erreur:
            erreurs["destinataire_telephone"] = erreur.detail
        try:
            attrs["expediteur_telephone"] = _telephone(attrs.get("expediteur_telephone"), obligatoire=False)
        except serializers.ValidationError as erreur:
            erreurs["expediteur_telephone"] = erreur.detail

        frais = attrs.get("frais") or 0
        if frais > 0 and not attrs.get("mode_paiement"):
            erreurs["mode_paiement"] = "Indiquez comment les frais sont réglés (espèces ou mobile money)."
        if not frais:
            attrs["mode_paiement"] = ""

        if erreurs:
            raise serializers.ValidationError(erreurs)
        return attrs
