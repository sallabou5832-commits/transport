from rest_framework import serializers

from core.models import Role
from core.serializers import CompanySerializer
from reseau.models import Gare, Ligne, Vehicule


class GareSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Gare
        fields = ["id", "nom", "ville", "company", "chef"]
        read_only_fields = ["company"]

    def validate_chef(self, chef):
        if chef is None:
            return chef
        request = self.context["request"]
        target_company_id = request.user.company_id
        if chef.role != Role.CHEF_GARE:
            raise serializers.ValidationError("Le chef d'une gare doit avoir le rôle chef_gare.")
        if chef.company_id != target_company_id:
            raise serializers.ValidationError("Le chef doit appartenir à la même compagnie.")
        return chef


class LigneSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Ligne
        fields = ["id", "nom", "gare_depart", "gare_arrivee", "company"]
        read_only_fields = ["company"]

    def validate(self, attrs):
        gare_depart = attrs.get("gare_depart") or getattr(self.instance, "gare_depart", None)
        gare_arrivee = attrs.get("gare_arrivee") or getattr(self.instance, "gare_arrivee", None)

        if gare_depart and gare_arrivee and gare_depart.id == gare_arrivee.id:
            raise serializers.ValidationError(
                "La gare de départ et la gare d'arrivée doivent être différentes."
            )

        request = self.context["request"]
        target_company_id = request.user.company_id
        for field_name, gare in (("gare_depart", gare_depart), ("gare_arrivee", gare_arrivee)):
            if gare is not None and gare.company_id != target_company_id:
                raise serializers.ValidationError(
                    {field_name: "Cette gare n'appartient pas à votre compagnie."}
                )
        return attrs


class VehiculeSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Vehicule
        fields = ["id", "immatriculation", "capacite", "statut", "company"]
        read_only_fields = ["company"]
