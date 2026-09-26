from django.utils import timezone
from rest_framework import serializers

from core.models import Role
from core.serializers import CompanySerializer, nom_complet
from maintenance import preventif
from maintenance.models import DemandePiece, OrdreReparation, Piece, PlanEntretien, SortiePiece, StatutOrdreReparation

# Qui peut être désigné pour une intervention : le mécanicien, ou le chef d'atelier qui la prend lui-même.
ROLES_INTERVENANTS = {Role.MECANICIEN, Role.CHEF_ATELIER}


class PieceSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    en_alerte = serializers.BooleanField(read_only=True)

    class Meta:
        model = Piece
        fields = ["id", "nom", "reference", "quantite_stock", "seuil_alerte", "company", "en_alerte"]
        read_only_fields = ["company"]
        # L'unicité (compagnie, référence) est vérifiée ci-dessous : la compagnie vient de la requête, pas du corps.
        validators = []

    def validate_reference(self, reference):
        reference = reference.strip()
        doublon = Piece.objects.filter(company_id=self.context["request"].user.company_id, reference=reference)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Une pièce de votre compagnie porte déjà cette référence.")
        return reference


class OrdreReparationSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    mecanicien_nom = serializers.SerializerMethodField()
    vehicule_immatriculation = serializers.CharField(source="vehicule.immatriculation", read_only=True)
    retour_estime = serializers.DateTimeField(read_only=True)

    class Meta:
        model = OrdreReparation
        fields = [
            "id",
            "vehicule",
            "vehicule_immatriculation",
            "description",
            "statut",
            "mecanicien",
            "mecanicien_nom",
            "company",
            "date_creation",
            "date_cloture",
            "temps_passe_minutes",
            "urgence",
            "position",
            "delai_estime_heures",
            "retour_estime",
            "plan_entretien",
        ]
        # La position se pose par `reordonner`, le lien au plan par le préventif : jamais à la main.
        read_only_fields = ["company", "date_creation", "date_cloture", "position", "plan_entretien"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # L'urgence et le délai se fixent à l'ouverture de l'ordre ; ensuite, seuls le directeur technique et le chef d'atelier
        # les changent, par `prioriser` (le mécanicien qui met à jour son ordre n'a pas à se reclasser lui-même).
        if isinstance(self.instance, OrdreReparation):
            self.fields["urgence"].read_only = True
            self.fields["delai_estime_heures"].read_only = True

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
        if mecanicien.role not in ROLES_INTERVENANTS:
            raise serializers.ValidationError("L'intervenant doit être un mécanicien ou le chef d'atelier.")
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
        if request.user.role == Role.MECANICIEN and ordre_reparation.mecanicien_id != request.user.id:
            raise serializers.ValidationError("Vous ne pouvez sortir des pièces que pour vos propres ordres.")
        return ordre_reparation

    def validate_piece(self, piece):
        request = self.context["request"]
        if piece.company_id != request.user.company_id:
            raise serializers.ValidationError("Cette pièce n'appartient pas à votre compagnie.")
        return piece


class PlanEntretienSerializer(serializers.ModelSerializer):
    vehicule_immatriculation = serializers.CharField(source="vehicule.immatriculation", read_only=True)
    echeance = serializers.SerializerMethodField()

    class Meta:
        model = PlanEntretien
        fields = [
            "id", "vehicule", "vehicule_immatriculation", "libelle", "periodicite_jours", "periodicite_km", "derniere_date",
            "dernier_km", "duree_estimee_heures", "declenche_ordre", "actif", "reglementaire", "echeance",
        ]

    def get_echeance(self, obj):
        return preventif.echeance(obj)

    def validate_vehicule(self, vehicule):
        if vehicule.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        return vehicule

    def validate(self, attrs):
        jours = attrs.get("periodicite_jours", getattr(self.instance, "periodicite_jours", None))
        km = attrs.get("periodicite_km", getattr(self.instance, "periodicite_km", None))
        if not jours and not km:
            raise serializers.ValidationError("Indiquez une périodicité : en jours, en kilomètres, ou les deux.")
        return attrs

    def create(self, validated_data):
        # Un plan déclaré sans précision part d'aujourd'hui, au kilométrage actuel du véhicule.
        validated_data.setdefault("derniere_date", timezone.localdate())
        if validated_data.get("dernier_km") is None:
            validated_data["dernier_km"] = validated_data["vehicule"].kilometrage
        return super().create(validated_data)


class DemandePieceSerializer(serializers.ModelSerializer):
    piece_nom = serializers.CharField(source="piece.nom", read_only=True)
    piece_reference = serializers.CharField(source="piece.reference", read_only=True)
    stock_actuel = serializers.IntegerField(source="piece.quantite_stock", read_only=True)
    vehicule_immatriculation = serializers.CharField(source="ordre_reparation.vehicule.immatriculation", read_only=True)
    demandeur_nom = serializers.SerializerMethodField()
    traitee_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = DemandePiece
        fields = [
            "id", "ordre_reparation", "vehicule_immatriculation", "piece", "piece_nom", "piece_reference", "quantite",
            "stock_actuel", "demandeur", "demandeur_nom", "statut", "disponible_a_la_demande", "traitee_par", "traitee_par_nom",
            "traitee_le", "commentaire", "sortie", "cree_le",
        ]
        # Le statut, la disponibilité et le traitement ne se choisissent pas : la demande naît « demandée », le magasinier la traite.
        read_only_fields = [
            "demandeur", "statut", "disponible_a_la_demande", "traitee_par", "traitee_le", "commentaire", "sortie", "cree_le",
        ]

    def get_demandeur_nom(self, obj):
        return nom_complet(obj.demandeur)

    def get_traitee_par_nom(self, obj):
        return nom_complet(obj.traitee_par) if obj.traitee_par_id else None

    def validate_ordre_reparation(self, ordre):
        utilisateur = self.context["request"].user
        if ordre.company_id != utilisateur.company_id:
            raise serializers.ValidationError("Cet ordre de réparation n'appartient pas à votre compagnie.")
        if utilisateur.role == Role.MECANICIEN and ordre.mecanicien_id != utilisateur.id:
            raise serializers.ValidationError("Vous ne demandez des pièces que pour vos propres ordres.")
        if ordre.statut == StatutOrdreReparation.TERMINE:
            raise serializers.ValidationError("Cet ordre est terminé : on ne demande plus de pièce pour lui.")
        return ordre

    def validate_piece(self, piece):
        if piece.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("Cette pièce n'appartient pas à votre compagnie.")
        return piece
