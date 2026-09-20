from rest_framework import serializers

from core.serializers import CompanySerializer, nom_complet
from maintenance.models import OrdreReparation, Piece, SortiePiece


class PieceSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    en_alerte = serializers.BooleanField(read_only=True)

    class Meta:
        model = Piece
        fields = ["id", "nom", "reference", "quantite_stock", "seuil_alerte", "company", "en_alerte"]
        read_only_fields = ["company"]


class OrdreReparationSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    mecanicien_nom = serializers.SerializerMethodField()

    class Meta:
        model = OrdreReparation
        fields = [
            "id",
            "vehicule",
            "description",
            "statut",
            "mecanicien",
            "mecanicien_nom",
            "company",
            "date_creation",
            "date_cloture",
            "temps_passe_minutes",
        ]
        read_only_fields = ["company", "date_creation", "date_cloture"]

    def get_mecanicien_nom(self, obj):
        return nom_complet(obj.mecanicien)

    def validate_vehicule(self, vehicule):
        request = self.context["request"]
        if vehicule.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        return vehicule

    def validate_mecanicien(self, mecanicien):
        request = self.context["request"]
        if mecanicien.company_id != request.user.company_id:
            raise serializers.ValidationError("Le mécanicien doit appartenir à la même compagnie.")
        return mecanicien


class SortiePieceSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = SortiePiece
        fields = ["id", "ordre_reparation", "piece", "company", "quantite", "date"]
        read_only_fields = ["company", "date"]

    def validate_ordre_reparation(self, ordre_reparation):
        request = self.context["request"]
        if ordre_reparation.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet ordre de réparation n'appartient pas à votre compagnie."
            )
        return ordre_reparation

    def validate_piece(self, piece):
        request = self.context["request"]
        if piece.company_id != request.user.company_id:
            raise serializers.ValidationError("Cette pièce n'appartient pas à votre compagnie.")
        return piece
