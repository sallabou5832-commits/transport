from rest_framework import serializers

from personnel_roulant.models import Incident


class IncidentTableauBordSerializer(serializers.ModelSerializer):
    vehicule = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = ["id", "type_incident", "description", "gravite", "date", "vehicule"]

    def get_vehicule(self, obj):
        return {"id": obj.vehicule_id, "immatriculation": obj.vehicule.immatriculation}
