from rest_framework import serializers

from core.models import Company
from tutelle.models import FluxTutelle


class FluxTutelleSerializer(serializers.ModelSerializer):
    """Un flux tel que le lit la compagnie (QHSE, responsable juridique) : tout en lecture seule, il ne se modifie
    que par l'action `traiter` (voir `FluxTutelleViewSet.traiter`)."""

    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    direction_libelle = serializers.CharField(source="get_direction_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = FluxTutelle
        fields = [
            "id", "company", "type", "type_libelle", "direction", "direction_libelle",
            "contenu", "statut", "statut_libelle", "date",
        ]
        read_only_fields = fields


class FluxEntrantSerializer(serializers.ModelSerializer):
    """Ce qu'un compte tutelle envoie à une compagnie (`POST /api/tutelle/entrant/`) : `company`, `type` et
    `contenu` sont fournis par l'appelant ; `direction` et `statut` sont déduits (voir `FluxEntrantView`), jamais
    choisis — un compte tutelle ne peut pas se faire passer pour une compagnie qui « envoie » ni marquer un flux
    déjà « traité »."""

    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())

    class Meta:
        model = FluxTutelle
        fields = ["id", "company", "type", "contenu", "direction", "statut", "date"]
        read_only_fields = ["direction", "statut", "date"]

    def validate_contenu(self, valeur):
        if not isinstance(valeur, dict):
            raise serializers.ValidationError("Le contenu doit être un objet JSON.")
        return valeur
