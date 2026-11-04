from django.utils import timezone
from rest_framework import serializers

from core.models import Role, User
from core.serializers import CompanySerializer, nom_complet
from core.telephones import valider_telephone
from reseau.models import ANNEE_CIRCULATION_MIN, AffectationGare, ChangementLigne, Gare, Ligne, Quai, Vehicule
from reseau.team import ROLES_AFFECTATION_TOUTES_GARES, ROLES_EQUIPE_LOCALE


class GareSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    chef_nom = serializers.SerializerMethodField()

    class Meta:
        model = Gare
        fields = [
            "id", "nom", "ville", "company", "chef", "chef_nom", "latitude", "longitude", "adresse", "telephone",
            "heure_ouverture", "heure_fermeture",
        ]
        read_only_fields = ["company"]
        # Un chef ne dirige qu'une gare : vérifié dans `validate_chef`, avec un message qui dit laquelle.
        extra_kwargs = {"chef": {"validators": []}}

    def get_chef_nom(self, obj):
        return nom_complet(obj.chef) if obj.chef_id else None

    def validate_chef(self, chef):
        if chef is None:
            return chef
        request = self.context["request"]
        target_company_id = request.user.company_id
        if chef.role != Role.CHEF_GARE:
            raise serializers.ValidationError("Le chef d'une gare doit avoir le rôle chef_gare.")
        if chef.company_id != target_company_id:
            raise serializers.ValidationError("Le chef doit appartenir à la même compagnie.")
        autre = Gare.objects.filter(chef=chef).exclude(pk=getattr(self.instance, "pk", None)).first()
        if autre is not None:
            raise serializers.ValidationError(f"{nom_complet(chef)} dirige déjà la gare {autre.nom}.")
        return chef

    def validate_telephone(self, valeur):
        return valider_telephone(valeur)


class QuaiSerializer(serializers.ModelSerializer):
    gare_nom = serializers.CharField(source="gare.nom", read_only=True)

    class Meta:
        model = Quai
        fields = ["id", "gare", "gare_nom", "nom", "actif"]
        validators = []  # l'unicité du nom dans la gare est vérifiée plus bas, avec un message clair

    def validate_gare(self, gare):
        user = self.context["request"].user
        if gare.company_id != user.company_id:
            raise serializers.ValidationError("Cette gare n'appartient pas à votre compagnie.")
        if user.role == Role.CHEF_GARE and gare.chef_id != user.id:
            raise serializers.ValidationError("Vous ne gérez que les quais de la gare que vous dirigez.")
        if self.instance is not None and gare.pk != self.instance.gare_id:
            raise serializers.ValidationError("Un quai ne change pas de gare : créez-le dans l'autre gare.")
        return gare

    def validate(self, attrs):
        gare = attrs.get("gare") or getattr(self.instance, "gare", None)
        nom = attrs.get("nom", getattr(self.instance, "nom", ""))
        doublons = Quai.objects.filter(gare=gare, nom__iexact=nom)
        if self.instance is not None:
            doublons = doublons.exclude(pk=self.instance.pk)
        if gare is not None and doublons.exists():
            raise serializers.ValidationError({"nom": "Cette gare a déjà un quai de ce nom."})
        return attrs


class LigneSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    # La fermeture ne se modifie pas ici : elle passe par une demande décidée (`/lignes/{id}/changement/`).
    est_fermee = serializers.BooleanField(read_only=True)
    gare_depart_nom = serializers.CharField(source="gare_depart.nom", read_only=True)
    gare_arrivee_nom = serializers.CharField(source="gare_arrivee.nom", read_only=True)

    class Meta:
        model = Ligne
        fields = [
            "id", "nom", "gare_depart", "gare_depart_nom", "gare_arrivee", "gare_arrivee_nom", "tarif", "distance_km",
            "duree_prevue_minutes", "company", "statut", "est_fermee", "fermee_jusqu_au", "motif_fermeture",
        ]
        read_only_fields = ["company", "statut", "fermee_jusqu_au", "motif_fermeture"]

    def validate(self, attrs):
        gare_depart = attrs.get("gare_depart") or getattr(self.instance, "gare_depart", None)
        gare_arrivee = attrs.get("gare_arrivee") or getattr(self.instance, "gare_arrivee", None)

        if gare_depart and gare_arrivee and gare_depart.id == gare_arrivee.id:
            raise serializers.ValidationError(
                "La gare de départ et la gare d'arrivée doivent être différentes."
            )

        request = self.context["request"]
        target_company_id = request.user.company_id
        for field_name, gare in (("gare_depart", gare_depart), ("gare_arrivee", gare_arrivee)):
            if gare is not None and gare.company_id != target_company_id:
                raise serializers.ValidationError(
                    {field_name: "Cette gare n'appartient pas à votre compagnie."}
                )
        return attrs


class VehiculeSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    gare_nom = serializers.CharField(source="gare.nom", read_only=True, default=None)

    class Meta:
        model = Vehicule
        # La gare d'attache ne se change que par l'arbitrage `reaffecter-gare` (qui prévient les deux gares).
        fields = [
            "id", "immatriculation", "capacite", "statut", "company", "gare", "gare_nom", "kilometrage", "marque", "modele",
            "annee_mise_en_circulation", "classe", "numero_carte_grise", "carte_transport_numero", "carte_transport_echeance",
        ]
        read_only_fields = ["company", "gare"]

    def validate_annee_mise_en_circulation(self, annee):
        if annee is not None and not ANNEE_CIRCULATION_MIN <= annee <= timezone.localdate().year + 1:
            raise serializers.ValidationError(
                f"Année entre {ANNEE_CIRCULATION_MIN} et {timezone.localdate().year + 1} attendue."
            )
        return annee

    def validate_immatriculation(self, valeur):
        # `company` est en lecture seule : DRF ne génère donc pas le contrôle d'unicité par compagnie (la contrainte de base
        # le ferait échouer en erreur 500). On ne regarde que la compagnie du demandeur, jamais les autres.
        company_id = self.instance.company_id if self.instance is not None else self.context["request"].user.company_id
        doublons = Vehicule.objects.filter(company_id=company_id, immatriculation=valeur)
        if self.instance is not None:
            doublons = doublons.exclude(pk=self.instance.pk)
        if doublons.exists():
            raise serializers.ValidationError("Un véhicule de votre compagnie porte déjà cette immatriculation.")
        return valeur


class AffectationGareSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    # Déclaré à la main : le champ généré par DRF porterait son propre contrôle d'unicité, au message moins utile.
    agent = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    agent_nom = serializers.SerializerMethodField()
    agent_role = serializers.CharField(source="agent.role", read_only=True)
    gare_nom = serializers.CharField(source="gare.nom", read_only=True)

    class Meta:
        model = AffectationGare
        fields = ["id", "agent", "agent_nom", "agent_role", "gare", "gare_nom", "company"]
        read_only_fields = ["company"]
        validators = []  # l'unicité de l'agent est vérifiée plus bas, avec un message qui dit où il est déjà affecté

    def get_agent_nom(self, obj):
        return nom_complet(obj.agent)

    def validate_agent(self, agent):
        user = self.context["request"].user
        if agent.company_id != user.company_id:
            raise serializers.ValidationError("Cet agent n'appartient pas à votre compagnie.")
        if agent.role not in ROLES_EQUIPE_LOCALE:
            raise serializers.ValidationError("Seuls les guichetiers et les bagagistes composent l'équipe d'une gare.")
        existante = AffectationGare.objects.filter(agent=agent).select_related("gare").first()
        if existante is not None and (self.instance is None or existante.pk != self.instance.pk):
            raise serializers.ValidationError(f"Cet agent est déjà affecté à la gare {existante.gare.nom}.")
        return agent

    def validate_gare(self, gare):
        user = self.context["request"].user
        if gare.company_id != user.company_id:
            raise serializers.ValidationError("Cette gare n'appartient pas à votre compagnie.")
        if user.role not in ROLES_AFFECTATION_TOUTES_GARES and gare.chef_id != user.id:
            raise serializers.ValidationError("Vous ne composez que l'équipe de la gare que vous dirigez.")
        return gare


class ChangementLigneSerializer(serializers.ModelSerializer):
    ligne_nom = serializers.CharField(source="ligne.nom", read_only=True)
    demandeur_nom = serializers.SerializerMethodField()
    decide_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = ChangementLigne
        fields = [
            "id", "ligne", "ligne_nom", "action", "motif", "jusqu_au", "demandeur", "demandeur_nom", "statut", "decide_par",
            "decide_par_nom", "decide_le", "commentaire_decision", "cree_le",
        ]
        read_only_fields = fields

    def get_demandeur_nom(self, obj):
        return nom_complet(obj.demandeur)

    def get_decide_par_nom(self, obj):
        return nom_complet(obj.decide_par) if obj.decide_par_id else None
