from rest_framework import serializers

from core.serializers import nom_complet
from lien_billetterie.models import CleLienBilletterie, ImportVentes


class CleLienSerializer(serializers.ModelSerializer):
    creee_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = CleLienBilletterie
        fields = [
            "id", "logiciel", "debut_cle", "active", "creee_par", "creee_par_nom", "creee_le", "revoquee_le",
            "derniere_utilisation",
        ]
        read_only_fields = [champ for champ in fields if champ != "logiciel"]

    def get_creee_par_nom(self, obj):
        return nom_complet(obj.creee_par) if obj.creee_par else None

    def validate_logiciel(self, logiciel):
        logiciel = logiciel.strip()
        if len(logiciel) < 2:
            raise serializers.ValidationError("Indiquez le nom du logiciel de billetterie relié.")
        return logiciel


class ImportVentesSerializer(serializers.ModelSerializer):
    depose_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = ImportVentes
        fields = [
            "id", "logiciel", "fichier", "depose_par", "depose_par_nom", "depose_le", "lignes", "creees", "deja_recues",
            "refusees",
        ]
        read_only_fields = fields

    def get_depose_par_nom(self, obj):
        return nom_complet(obj.depose_par)


class ImportVentesDetailSerializer(ImportVentesSerializer):
    """Le compte rendu complet, ligne par ligne : seulement pour un import, pas dans la liste."""

    class Meta(ImportVentesSerializer.Meta):
        fields = [*ImportVentesSerializer.Meta.fields, "rapport"]
        read_only_fields = fields
