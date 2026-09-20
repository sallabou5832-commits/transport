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
