from django.utils import timezone
from rest_framework import serializers

from core.serializers import nom_complet
from finance.models import BudgetCarburant, ConfigurationFinance, Depense, Facture, Fournisseur, StatutFacture


def _de_la_compagnie(serializer, objet, message):
    if objet is not None and objet.company_id != serializer.context["request"].user.company_id:
        raise serializers.ValidationError(message)
    return objet


class DepenseSerializer(serializers.ModelSerializer):
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    ligne_nom = serializers.CharField(source="ligne.nom", read_only=True, default=None)
    vehicule_immatriculation = serializers.CharField(source="vehicule.immatriculation", read_only=True, default=None)
    gare_nom = serializers.CharField(source="gare.nom", read_only=True, default=None)
    saisi_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Depense
        fields = [
            "id", "date", "categorie", "categorie_libelle", "libelle", "montant", "ligne", "ligne_nom", "vehicule",
            "vehicule_immatriculation", "gare", "gare_nom", "saisi_par", "saisi_par_nom", "cree_le",
        ]
        read_only_fields = ["saisi_par", "cree_le"]

    def get_saisi_par_nom(self, obj):
        return nom_complet(obj.saisi_par)

    def validate_date(self, valeur):
        if valeur > timezone.localdate():
            raise serializers.ValidationError("Une dépense ne peut pas être datée du futur.")
        return valeur

    def validate_libelle(self, valeur):
        valeur = valeur.strip()
        if len(valeur) < 3:
            raise serializers.ValidationError("Décrivez la dépense.")
        return valeur

    def validate_ligne(self, ligne):
        return _de_la_compagnie(self, ligne, "Cette ligne n'appartient pas à votre compagnie.")

    def validate_vehicule(self, vehicule):
        return _de_la_compagnie(self, vehicule, "Ce véhicule n'appartient pas à votre compagnie.")

    def validate_gare(self, gare):
        return _de_la_compagnie(self, gare, "Cette gare n'appartient pas à votre compagnie.")


class BudgetCarburantSerializer(serializers.ModelSerializer):
    ligne_nom = serializers.CharField(source="ligne.nom", read_only=True)

    class Meta:
        model = BudgetCarburant
        fields = ["id", "ligne", "ligne_nom", "mois", "montant"]
        validators = []  # l'unicité (compagnie, ligne, mois) est vérifiée plus bas : la compagnie vient de la requête

    def validate_mois(self, valeur):
        return valeur.replace(day=1)  # un budget est mensuel : n'importe quel jour du mois désigne le mois

    def validate_ligne(self, ligne):
        return _de_la_compagnie(self, ligne, "Cette ligne n'appartient pas à votre compagnie.")

    def validate(self, attrs):
        ligne = attrs.get("ligne", getattr(self.instance, "ligne", None))
        mois = attrs.get("mois", getattr(self.instance, "mois", None))
        doublon = BudgetCarburant.objects.filter(company_id=self.context["request"].user.company_id, ligne=ligne, mois=mois)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Cette ligne a déjà un budget carburant pour ce mois : modifiez-le.")
        return attrs


class FournisseurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fournisseur
        fields = ["id", "nom", "categorie", "telephone"]
        validators = []

    def validate_nom(self, valeur):
        valeur = valeur.strip()
        doublon = Fournisseur.objects.filter(company_id=self.context["request"].user.company_id, nom__iexact=valeur)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Ce fournisseur existe déjà.")
        return valeur


class FactureSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(source="fournisseur.nom", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    jours_restants = serializers.SerializerMethodField()
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = Facture
        fields = [
            "id", "fournisseur", "fournisseur_nom", "type", "type_libelle", "reference", "libelle", "montant", "date_emission",
            "echeance", "statut", "statut_libelle", "payee_le", "mode_paiement", "depense", "jours_restants", "en_retard",
        ]
        # Le statut, la date de paiement et la dépense ne se choisissent pas : payer ou annuler passe par une action.
        read_only_fields = ["statut", "payee_le", "mode_paiement", "depense"]

    def get_jours_restants(self, obj):
        return (obj.echeance - timezone.localdate()).days if obj.statut == StatutFacture.A_PAYER else None

    def get_en_retard(self, obj):
        return obj.statut == StatutFacture.A_PAYER and obj.echeance < timezone.localdate()

    def validate_fournisseur(self, fournisseur):
        return _de_la_compagnie(self, fournisseur, "Ce fournisseur n'appartient pas à votre compagnie.")

    def validate(self, attrs):
        emission = attrs.get("date_emission", getattr(self.instance, "date_emission", None))
        echeance = attrs.get("echeance", getattr(self.instance, "echeance", None))
        if emission and echeance and echeance < emission:
            raise serializers.ValidationError({"echeance": "L'échéance précède la date d'émission."})
        return attrs


class ConfigurationFinanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationFinance
        fields = ["solde_initial"]
