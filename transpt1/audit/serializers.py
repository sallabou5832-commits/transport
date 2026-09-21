from rest_framework import serializers

from audit.models import JournalAudit


class JournalAuditSerializer(serializers.ModelSerializer):
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = JournalAudit
        fields = [
            "id",
            "date",
            "acteur",
            "acteur_nom",
            "acteur_role",
            "action",
            "action_libelle",
            "objet_type",
            "objet_id",
            "objet_repr",
            "changements",
            "adresse_ip",
        ]
        read_only_fields = fields
