from rest_framework import serializers

from core.serializers import CompanySerializer, nom_complet
from personnel_roulant.models import ChecklistDepart, FeuilleDeRoute, Incident
from personnel_roulant.permissions import CHAUFFEUR_ROLES


def _check_chauffeur(chauffeur, request):
    if chauffeur.role not in CHAUFFEUR_ROLES:
        raise serializers.ValidationError(
            "Le chauffeur doit avoir le rôle chauffeur_principal ou chauffeur_relais."
        )
    user = request.user
    if chauffeur.company_id != user.company_id:
        raise serializers.ValidationError("Le chauffeur doit appartenir à la même compagnie.")
    if user.role in CHAUFFEUR_ROLES and chauffeur.id != user.id:
        raise serializers.ValidationError(
            "Vous ne pouvez créer ou modifier que vos propres données."
        )
    return chauffeur


class FeuilleDeRouteSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    chauffeur_nom = serializers.SerializerMethodField()

    class Meta:
        model = FeuilleDeRoute
        fields = [
            "id",
            "depart",
            "chauffeur",
            "chauffeur_nom",
            "company",
            "heure_depart_prevue",
            "heure_depart_reelle",
            "heure_arrivee_prevue",
            "heure_arrivee_reelle",
        ]
        read_only_fields = ["company", "heure_depart_reelle", "heure_arrivee_reelle"]

    def get_chauffeur_nom(self, obj):
        return nom_complet(obj.chauffeur)

    def validate_chauffeur(self, chauffeur):
        return _check_chauffeur(chauffeur, self.context["request"])

    def validate_depart(self, depart):
        request = self.context["request"]
        if depart.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce départ n'appartient pas à votre compagnie.")
        return depart


class ChecklistDepartSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    est_item_securite = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChecklistDepart
        fields = ["id", "feuille_de_route", "company", "item", "etat", "commentaire", "est_item_securite"]
        read_only_fields = ["company"]

    def validate_feuille_de_route(self, feuille_de_route):
        request = self.context["request"]
        user = request.user
        if feuille_de_route.company_id != user.company_id:
            raise serializers.ValidationError(
                "Cette feuille de route n'appartient pas à votre compagnie."
            )
        if user.role in CHAUFFEUR_ROLES and feuille_de_route.chauffeur_id != user.id:
            raise serializers.ValidationError(
                "Vous ne pouvez créer ou modifier que les checklists de vos propres feuilles de route."
            )
        return feuille_de_route


class IncidentSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    chauffeur_nom = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "id",
            "feuille_de_route",
            "vehicule",
            "chauffeur",
            "chauffeur_nom",
            "company",
            "type_incident",
            "description",
            "date",
            "gravite",
            "statut",
        ]
        read_only_fields = ["company"]

    def get_chauffeur_nom(self, obj):
        return nom_complet(obj.chauffeur)

    def validate_chauffeur(self, chauffeur):
        return _check_chauffeur(chauffeur, self.context["request"])

    def validate_vehicule(self, vehicule):
        request = self.context["request"]
        if vehicule.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        return vehicule

    def validate_feuille_de_route(self, feuille_de_route):
        if feuille_de_route is None:
            return feuille_de_route
        request = self.context["request"]
        if feuille_de_route.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cette feuille de route n'appartient pas à votre compagnie."
            )
        return feuille_de_route
