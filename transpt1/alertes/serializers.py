from rest_framework import serializers

from alertes.models import Alerte


class AlerteSerializer(serializers.ModelSerializer):
    # Posée par le queryset du ViewSet : cette alerte a-t-elle déjà été lue par l'utilisateur qui la consulte ?
    lue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Alerte
        fields = ["id", "type", "gravite", "titre", "message", "objet_type", "objet_id", "cree_le", "lue"]
        read_only_fields = fields
