from rest_framework import serializers

from core.models import Role
from core.serializers import CompanySerializer
from billetterie.models import Depart, DepartStatut, Ticket

CHAUFFEUR_ROLES = {Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS}


class DepartSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    places_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Depart
        fields = [
            "id",
            "ligne",
            "vehicule",
            "chauffeur",
            "company",
            "date_heure",
            "statut",
            "places_vendues",
            "places_restantes",
        ]
        read_only_fields = ["company", "places_vendues"]

    def validate_chauffeur(self, chauffeur):
        if chauffeur.role not in CHAUFFEUR_ROLES:
            raise serializers.ValidationError(
                "Le chauffeur doit avoir le rôle chauffeur_principal ou chauffeur_relais."
            )
        return chauffeur

    def validate(self, attrs):
        request = self.context["request"]
        target_company_id = request.user.company_id

        ligne = attrs.get("ligne") or getattr(self.instance, "ligne", None)
        vehicule = attrs.get("vehicule") or getattr(self.instance, "vehicule", None)
        chauffeur = attrs.get("chauffeur") or getattr(self.instance, "chauffeur", None)

        for field_name, related in (
            ("ligne", ligne),
            ("vehicule", vehicule),
            ("chauffeur", chauffeur),
        ):
            if related is not None and related.company_id != target_company_id:
                raise serializers.ValidationError(
                    {field_name: "N'appartient pas à votre compagnie."}
                )
        return attrs


class TicketSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    vendu_par = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "depart",
            "company",
            "passager_nom",
            "passager_telephone",
            "prix",
            "mode_paiement",
            "vendu_par",
            "date_vente",
        ]
        read_only_fields = ["company", "vendu_par", "date_vente"]

    def validate_depart(self, depart):
        request = self.context["request"]
        if depart.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce départ n'appartient pas à votre compagnie.")
        if depart.statut == DepartStatut.TERMINE:
            raise serializers.ValidationError("Ce départ est terminé, vente impossible.")
        return depart
