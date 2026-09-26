import datetime

from django.utils import timezone
from rest_framework import serializers

from core.serializers import CompanySerializer, nom_complet
from personnel_roulant.models import (
    BlocageSecurite,
    ChecklistDepart,
    ControleLigne,
    FeuilleDeRoute,
    Incident,
    PositionVehicule,
    Relais,
)
from personnel_roulant.permissions import CHAUFFEUR_ROLES
from reseau.models import VehiculeStatut


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
            "latitude",
            "longitude",
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


class BlocageSecuriteSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    vehicule_immatriculation = serializers.CharField(source="vehicule.immatriculation", read_only=True)
    pose_par_nom = serializers.SerializerMethodField()
    est_actif = serializers.BooleanField(read_only=True)

    class Meta:
        model = BlocageSecurite
        fields = [
            "id",
            "vehicule",
            "vehicule_immatriculation",
            "depart",
            "company",
            "motif",
            "pose_par",
            "pose_par_nom",
            "pose_le",
            "leve_par",
            "leve_le",
            "motif_levee",
            "est_actif",
        ]
        read_only_fields = ["company", "pose_par", "pose_le", "leve_par", "leve_le", "motif_levee"]

    def get_pose_par_nom(self, obj):
        return nom_complet(obj.pose_par)

    def validate_vehicule(self, vehicule):
        if vehicule.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        if vehicule.statut == VehiculeStatut.EN_LIGNE:
            raise serializers.ValidationError("Ce véhicule est en route : seul un départ à venir peut être bloqué.")
        if vehicule.statut == VehiculeStatut.BLOQUE_SECURITE:
            raise serializers.ValidationError("Ce véhicule est déjà bloqué pour raison de sécurité.")
        if vehicule.statut == VehiculeStatut.EN_MAINTENANCE:
            raise serializers.ValidationError("Ce véhicule est déjà immobilisé à l'atelier.")
        return vehicule

    def validate_motif(self, motif):
        motif = motif.strip()
        if len(motif) < 5:
            raise serializers.ValidationError("Indiquez le motif du blocage (5 caractères au moins).")
        return motif

    def validate(self, attrs):
        depart = attrs.get("depart")
        if depart is not None:
            if depart.company_id != self.context["request"].user.company_id:
                raise serializers.ValidationError({"depart": "Ce départ n'appartient pas à votre compagnie."})
            if depart.vehicule_id != attrs["vehicule"].pk:
                raise serializers.ValidationError({"depart": "Ce départ n'est pas celui de ce véhicule."})
        return attrs


class PositionSerializer(serializers.ModelSerializer):
    """Un relevé GPS. `releve_le` (facultatif) est l'heure du relevé : un envoi différé après une zone sans réseau garde
    l'heure réelle. Ni dans le futur, ni plus vieux de deux jours (un relevé plus ancien n'a plus d'intérêt)."""

    class Meta:
        model = PositionVehicule
        fields = ["latitude", "longitude", "vitesse_kmh", "releve_le"]
        extra_kwargs = {"releve_le": {"required": False}}

    def validate_latitude(self, valeur):
        if not -90 <= valeur <= 90:
            raise serializers.ValidationError("La latitude est comprise entre -90 et 90.")
        return valeur

    def validate_longitude(self, valeur):
        if not -180 <= valeur <= 180:
            raise serializers.ValidationError("La longitude est comprise entre -180 et 180.")
        return valeur

    def validate_vitesse_kmh(self, valeur):
        if valeur is not None and valeur > 250:
            raise serializers.ValidationError("Vitesse invraisemblable.")
        return valeur

    def validate_releve_le(self, valeur):
        maintenant = timezone.now()
        if valeur > maintenant + datetime.timedelta(minutes=5):
            raise serializers.ValidationError("Ce relevé est dans le futur.")
        if valeur < maintenant - datetime.timedelta(days=2):
            raise serializers.ValidationError("Ce relevé est trop ancien.")
        return valeur


class RelaisSerializer(serializers.ModelSerializer):
    """Un relais et, une fois faite, la checklist de reprise du nouveau conducteur (avec les défauts qu'il a constatés)."""

    ligne = serializers.CharField(source="feuille_de_route.depart.ligne.nom", read_only=True)
    vehicule = serializers.CharField(source="feuille_de_route.depart.vehicule.immatriculation", read_only=True)
    ancien_chauffeur_nom = serializers.SerializerMethodField()
    nouveau_chauffeur_nom = serializers.SerializerMethodField()
    reprise = serializers.SerializerMethodField()

    class Meta:
        model = Relais
        fields = [
            "id", "feuille_de_route", "ligne", "vehicule", "lieu", "effectue_le", "ancien_chauffeur", "ancien_chauffeur_nom",
            "nouveau_chauffeur", "nouveau_chauffeur_nom", "etat_vehicule", "reprise",
        ]
        read_only_fields = fields

    def get_ancien_chauffeur_nom(self, obj):
        return nom_complet(obj.ancien_chauffeur)

    def get_nouveau_chauffeur_nom(self, obj):
        return nom_complet(obj.nouveau_chauffeur)

    def get_reprise(self, obj):
        items = list(obj.checklist_reprise.all())
        return {
            "faite": bool(items),
            "faite_le": items[0].cree_le if items else None,
            "items": [{"item": i.item, "etat": i.etat, "commentaire": i.commentaire} for i in items],
            "defauts": [i.item for i in items if i.etat == "defaut"],
        }


class ControleLigneSerializer(serializers.ModelSerializer):
    """Un contrôle à bord. À la création on ne donne que la feuille de route (le trajet contrôlé) ; le reste vient des
    vérifications de billets et de la clôture."""

    controleur_nom = serializers.SerializerMethodField()
    ligne_nom = serializers.CharField(source="feuille_de_route.depart.ligne.nom", read_only=True)
    ligne = serializers.IntegerField(source="feuille_de_route.depart.ligne_id", read_only=True)
    chauffeur = serializers.IntegerField(source="feuille_de_route.chauffeur_id", read_only=True)
    chauffeur_nom = serializers.SerializerMethodField()
    vehicule = serializers.CharField(source="feuille_de_route.depart.vehicule.immatriculation", read_only=True)
    est_ouvert = serializers.BooleanField(read_only=True)
    nombre_verifications = serializers.SerializerMethodField()

    class Meta:
        model = ControleLigne
        fields = [
            "id", "controleur", "controleur_nom", "feuille_de_route", "ligne", "ligne_nom", "chauffeur", "chauffeur_nom",
            "vehicule", "debut", "cloture_le", "est_ouvert", "nombre_verifications", "passagers_constates",
            "charge_constatee_kg", "commentaire", "infraction_grave", "motif_infraction", "rapport",
        ]
        read_only_fields = [f for f in fields if f != "feuille_de_route"]

    def get_controleur_nom(self, obj):
        return nom_complet(obj.controleur)

    def get_chauffeur_nom(self, obj):
        return nom_complet(obj.feuille_de_route.chauffeur)

    def get_nombre_verifications(self, obj):
        annote = getattr(obj, "_nombre_verifications", None)
        return annote if annote is not None else obj.verifications.count()

    def validate_feuille_de_route(self, feuille):
        if feuille.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("Cette feuille de route n'appartient pas à votre compagnie.")
        if feuille.heure_arrivee_reelle is not None:
            raise serializers.ValidationError("Ce trajet est terminé : on ne contrôle plus que les cars qui roulent ou vont partir.")
        return feuille
