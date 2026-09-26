from rest_framework import serializers

from core.models import Company, User


def nom_complet(user):
    """Nom à afficher pour un agent : « Prénom Nom », à défaut son identifiant."""
    if user is None:
        return None
    return user.get_full_name() or user.username


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "headquarters_city", "created_at"]


class CompteSerializer(serializers.ModelSerializer):
    """Un agent vu par le PDG qui gère les comptes : qui il est, s'il peut se connecter, et pourquoi il est suspendu."""

    nom = serializers.SerializerMethodField()
    role_libelle = serializers.CharField(source="get_role_display", read_only=True)
    actif = serializers.BooleanField(source="is_active", read_only=True)
    suspendu_par_nom = serializers.SerializerMethodField()
    gare = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "nom", "role", "role_libelle", "actif", "suspendu_le", "suspendu_par_nom",
            "motif_suspension", "gare",
        ]
        read_only_fields = fields

    def get_nom(self, obj):
        return nom_complet(obj)

    def get_suspendu_par_nom(self, obj):
        return nom_complet(obj.suspendu_par) if obj.suspendu_par_id else None

    def get_gare(self, obj):
        affectation = getattr(obj, "affectation_gare", None)
        return affectation.gare.nom if affectation is not None else None


class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "company",
        ]
