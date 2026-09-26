from rest_framework import serializers

from core.models import Role
from core.serializers import CompanySerializer, nom_complet
from communication.poles import POLES
from core.fichiers import nom_affichable, verifier_fichier
from supports.models import Assurance, DossierAgent, ModeleJuridique, PieceSinistre, Sinistre


class DossierAgentSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    # Identité de l'agent : mêmes destinataires que le dossier (le DRH, ou l'agent lui-même).
    agent_nom = serializers.SerializerMethodField()
    agent_role = serializers.CharField(source="agent.role", read_only=True)

    class Meta:
        model = DossierAgent
        fields = [
            "id",
            "agent",
            "agent_nom",
            "agent_role",
            "company",
            "date_embauche",
            "poste",
            "statut",
            "notes_rh",
        ]
        read_only_fields = ["company"]

    def get_agent_nom(self, obj):
        return nom_complet(obj.agent)

    def to_representation(self, instance):
        donnees = super().to_representation(instance)
        request = self.context.get("request")
        # Les notes internes du DRH ne sont lues que par lui et par l'agent concerné, pas par sa hiérarchie.
        if request is not None and request.user.role not in (Role.DRH, Role.SUPERADMIN) and instance.agent_id != request.user.id:
            donnees.pop("notes_rh", None)
        return donnees

    def validate_agent(self, agent):
        request = self.context["request"]
        if agent.company_id != request.user.company_id:
            raise serializers.ValidationError("Cet agent n'appartient pas à votre compagnie.")
        return agent


class AssuranceSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Assurance
        fields = [
            "id",
            "vehicule",
            "company",
            "compagnie_assurance",
            "numero_police",
            "date_echeance",
        ]
        read_only_fields = ["company"]

    def validate_vehicule(self, vehicule):
        request = self.context["request"]
        if vehicule.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        return vehicule


class SinistreSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    pieces_total = serializers.SerializerMethodField()
    incident_resume = serializers.SerializerMethodField()
    vehicule_immatriculation = serializers.CharField(source="vehicule.immatriculation", read_only=True, default=None)

    class Meta:
        model = Sinistre
        fields = [
            "id", "vehicule", "vehicule_immatriculation", "incident", "incident_resume", "company", "description", "statut", "date",
            "reference_assureur", "montant_estime", "montant_indemnise", "clos_le", "pieces_total",
        ]
        read_only_fields = ["company", "clos_le"]
        extra_kwargs = {"description": {"required": False, "allow_blank": True}}

    def get_pieces_total(self, obj):
        return obj.pieces.count()

    def get_incident_resume(self, obj):
        if obj.incident_id is None:
            return None
        incident = obj.incident
        return {"id": incident.id, "type": incident.get_type_incident_display(), "gravite": incident.gravite, "date": incident.date}

    def validate(self, attrs):
        # Un sinistre rattaché à un incident reprend son véhicule et sa description : le juridique n'a rien à ressaisir.
        incident = attrs.get("incident")
        if incident is not None and self.instance is None:
            attrs.setdefault("vehicule", incident.vehicule)
            if not str(attrs.get("description", "")).strip():
                attrs["description"] = f"{incident.get_type_incident_display()} — {incident.description}"
        if self.instance is None and not str(attrs.get("description", "")).strip():
            raise serializers.ValidationError({"description": "Décrivez le sinistre (ou rattachez-le à un incident)."})
        return attrs

    def validate_vehicule(self, vehicule):
        if vehicule is None:
            return vehicule
        request = self.context["request"]
        if vehicule.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre compagnie.")
        return vehicule

    def validate_incident(self, incident):
        if incident is None:
            return incident
        request = self.context["request"]
        if incident.company_id != request.user.company_id:
            raise serializers.ValidationError("Cet incident n'appartient pas à votre compagnie.")
        deja = Sinistre.objects.filter(incident=incident)
        if self.instance is not None:
            deja = deja.exclude(pk=self.instance.pk)
        if deja.exists():
            raise serializers.ValidationError("Cet incident a déjà un dossier de sinistre.")
        return incident


class PieceSinistreSerializer(serializers.ModelSerializer):
    ajoute_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = PieceSinistre
        fields = ["id", "sinistre", "fichier", "nom_fichier", "libelle", "taille", "ajoute_par_nom", "cree_le"]
        read_only_fields = ["nom_fichier", "taille", "cree_le"]
        extra_kwargs = {"fichier": {"write_only": True}}

    def get_ajoute_par_nom(self, obj):
        return nom_complet(obj.ajoute_par)

    def validate_sinistre(self, sinistre):
        if sinistre.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("Ce sinistre n'appartient pas à votre compagnie.")
        return sinistre

    def validate_fichier(self, fichier):
        verifier_fichier(fichier)
        return fichier

    def create(self, validated_data):
        fichier = validated_data["fichier"]
        validated_data["nom_fichier"] = nom_affichable(fichier.name)
        validated_data["taille"] = fichier.size
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Une pièce garde son fichier et son dossier : pour en changer, on la retire et on en joint une autre.
        validated_data.pop("fichier", None)
        validated_data.pop("sinistre", None)
        return super().update(instance, validated_data)


class ModeleJuridiqueSerializer(serializers.ModelSerializer):
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    poles_libelles = serializers.SerializerMethodField()
    a_un_fichier = serializers.SerializerMethodField()
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = ModeleJuridique
        fields = [
            "id", "titre", "categorie", "categorie_libelle", "description", "contenu", "poles", "poles_libelles", "version",
            "a_un_fichier", "nom_fichier", "taille", "auteur_nom", "modifie_le",
        ]
        read_only_fields = ["nom_fichier", "taille", "modifie_le"]
        validators = []

    def get_poles_libelles(self, obj):
        return [POLES[p][0] for p in obj.poles if p in POLES] or ["Tous les pôles"]

    def get_a_un_fichier(self, obj):
        return bool(obj.fichier)

    def get_auteur_nom(self, obj):
        return nom_complet(obj.auteur)

    def validate_titre(self, valeur):
        valeur = valeur.strip()
        doublon = ModeleJuridique.objects.filter(company_id=self.context["request"].user.company_id, titre__iexact=valeur)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Un modèle porte déjà ce titre.")
        return valeur

    def validate_poles(self, valeur):
        if not isinstance(valeur, list):
            raise serializers.ValidationError("Une liste de pôles est attendue (vide : tous les pôles).")
        inconnus = sorted(set(valeur) - set(POLES))
        if inconnus:
            raise serializers.ValidationError(f"Pôles inconnus : {', '.join(map(str, inconnus))}.")
        return sorted(set(valeur))

    def validate(self, attrs):
        contenu = attrs.get("contenu", getattr(self.instance, "contenu", ""))
        if self.instance is None and not str(contenu).strip():
            raise serializers.ValidationError({"contenu": "Rédigez le modèle (le fichier peut s'y ajouter ensuite)."})
        return attrs
