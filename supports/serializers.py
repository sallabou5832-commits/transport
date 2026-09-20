from rest_framework import serializers

from core.serializers import CompanySerializer
from supports.models import Assurance, DossierAgent, Sinistre


class DossierAgentSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = DossierAgent
        fields = ["id", "agent", "company", "date_embauche", "poste", "statut", "notes_rh"]
        read_only_fields = ["company"]

    def validate_agent(self, agent):
        request = self.context["request"]
        if agent.company_id != request.user.company_id:
            raise serializers.ValidationError("Cet agent n'appartient pas à votre compagnie.")
        return agent


class AssuranceSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Assurance
        fields = [
            "id",
            "vehicule",
            "company",
            "compagnie_assurance",
            "numero_police",
            "date_echeance",
        ]
        read_only_fields = ["company"]

    def validate_vehicule(self, vehicule):
        request = self.context["request"]
        if vehicule.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        return vehicule


class SinistreSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Sinistre
        fields = ["id", "vehicule", "incident", "company", "description", "statut", "date"]
        read_only_fields = ["company"]

    def validate_vehicule(self, vehicule):
        if vehicule is None:
            return vehicule
        request = self.context["request"]
        if vehicule.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        return vehicule

    def validate_incident(self, incident):
        if incident is None:
            return incident
        request = self.context["request"]
        if incident.company_id != request.user.company_id:
            raise serializers.ValidationError("Cet incident n'appartient pas à votre compagnie.")
        return incident
