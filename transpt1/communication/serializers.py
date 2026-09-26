from rest_framework import serializers

from communication.models import DocumentArchive, EvenementAgenda, MessageDirect, NoteService
from communication.poles import POLES, TOUS_LES_POSTES
from core.models import Role
from core.serializers import nom_complet


class NoteServiceSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()
    # À l'écriture, on désigne les destinataires par pôles, par postes, ou « tous » : le serveur en déduit la liste des postes.
    poles = serializers.ListField(child=serializers.ChoiceField(choices=list(POLES)), write_only=True, required=False)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=Role.choices), write_only=True, required=False)
    tous = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = NoteService
        fields = [
            "id", "titre", "contenu", "urgente", "auteur", "auteur_nom", "roles_destinataires", "cree_le", "poles", "roles", "tous",
        ]
        read_only_fields = ["auteur", "roles_destinataires", "cree_le"]

    def get_auteur_nom(self, obj):
        return nom_complet(obj.auteur)

    def validate_titre(self, valeur):
        valeur = valeur.strip()
        if len(valeur) < 3:
            raise serializers.ValidationError("Donnez un titre à la note.")
        return valeur

    def validate_contenu(self, valeur):
        valeur = valeur.strip()
        if len(valeur) < 5:
            raise serializers.ValidationError("La note est vide.")
        return valeur

    def validate(self, attrs):
        roles = set(attrs.pop("roles", []))
        for pole in attrs.pop("poles", []):
            roles |= set(POLES[pole][1])
        if attrs.pop("tous", False):
            roles = set(TOUS_LES_POSTES)
        roles.discard(Role.SUPERADMIN)
        if not roles:
            raise serializers.ValidationError({"poles": "Choisissez au moins un pôle, un poste, ou « tous »."})
        attrs["roles_destinataires"] = sorted(roles)
        return attrs


class MessageDirectSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()
    gare_nom = serializers.CharField(source="gare.nom", read_only=True)
    nombre_destinataires = serializers.SerializerMethodField()
    portee_libelle = serializers.CharField(source="get_portee_display", read_only=True)

    class Meta:
        model = MessageDirect
        fields = ["id", "portee", "portee_libelle", "texte", "gare", "gare_nom", "auteur", "auteur_nom", "nombre_destinataires", "cree_le"]
        read_only_fields = ["gare", "auteur", "cree_le"]

    def get_auteur_nom(self, obj):
        return nom_complet(obj.auteur)

    def get_nombre_destinataires(self, obj):
        return obj.destinataires.count()

    def validate_texte(self, valeur):
        valeur = valeur.strip()
        if len(valeur) < 3:
            raise serializers.ValidationError("Le message est vide.")
        return valeur


class EvenementAgendaSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()
    participants = serializers.ListField(child=serializers.ChoiceField(choices=Role.choices), required=False)

    class Meta:
        model = EvenementAgenda
        fields = ["id", "titre", "debut", "fin", "lieu", "description", "participants", "auteur", "auteur_nom", "cree_le"]
        read_only_fields = ["auteur", "cree_le"]

    def get_auteur_nom(self, obj):
        return nom_complet(obj.auteur)

    def validate(self, attrs):
        debut = attrs.get("debut", getattr(self.instance, "debut", None))
        fin = attrs.get("fin", getattr(self.instance, "fin", None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"fin": "La fin précède le début."})
        return attrs


class DocumentArchiveSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)

    class Meta:
        model = DocumentArchive
        fields = [
            "id", "titre", "categorie", "categorie_libelle", "reference", "date_document", "emplacement", "description", "mots_cles",
            "archive", "archive_le", "auteur", "auteur_nom", "cree_le",
        ]
        # L'archivage se décide par les actions `archiver` / `desarchiver` (avec leur date), pas en modifiant la fiche.
        read_only_fields = ["archive", "archive_le", "auteur", "cree_le"]
        validators = []

    def get_auteur_nom(self, obj):
        return nom_complet(obj.auteur)

    def validate_reference(self, valeur):
        valeur = valeur.strip()
        if valeur:
            doublon = DocumentArchive.objects.filter(company_id=self.context["request"].user.company_id, reference=valeur)
            if self.instance is not None:
                doublon = doublon.exclude(pk=self.instance.pk)
            if doublon.exists():
                raise serializers.ValidationError("Un document de votre compagnie porte déjà cette référence.")
        return valeur

    def validate_titre(self, valeur):
        valeur = valeur.strip()
        if len(valeur) < 3:
            raise serializers.ValidationError("Donnez un titre au document.")
        return valeur
