from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.models import Company, Role, User
from core.telephones import valider_telephone
from reseau.models import Gare
from reseau.team import ROLES_EQUIPE_LOCALE


def nom_complet(user):
    """Nom à afficher pour un agent : « Prénom Nom », à défaut son identifiant."""
    if user is None:
        return None
    return user.get_full_name() or user.username


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "headquarters_city", "created_at"]


class FicheCompagnieSerializer(serializers.ModelSerializer):
    """La fiche « Ma compagnie » : identité, coordonnées et mentions légales. Le logo s'envoie à part (`/compagnie/logo/`)."""

    a_un_logo = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id", "name", "sigle", "headquarters_city", "created_at", "adresse", "telephone", "email", "rccm",
            "compte_contribuable", "autorisation_numero", "autorisation_echeance", "a_un_logo",
        ]

    def get_a_un_logo(self, obj):
        return bool(obj.logo)

    def validate_telephone(self, valeur):
        return valider_telephone(valeur)


class LogoCompagnieSerializer(serializers.Serializer):
    """Ce que l'envoi du logo attend (le contrôle du fichier lui-même est fait par la vue, comme pour toute pièce jointe)."""

    fichier = serializers.FileField()


class CompteSerializer(serializers.ModelSerializer):
    """Un agent vu par le PDG ou le DRH qui gère les comptes : qui il est, s'il peut se connecter, et pourquoi il est
    suspendu."""

    nom = serializers.SerializerMethodField()
    role_libelle = serializers.CharField(source="get_role_display", read_only=True)
    actif = serializers.BooleanField(source="is_active", read_only=True)
    suspendu_par_nom = serializers.SerializerMethodField()
    gare = serializers.SerializerMethodField()
    a_un_dossier = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "nom", "first_name", "last_name", "role", "role_libelle", "actif", "suspendu_le",
            "suspendu_par_nom", "motif_suspension", "gare", "telephone", "matricule", "email", "doit_changer_mot_de_passe",
            "last_login", "a_un_dossier",
        ]
        read_only_fields = fields

    def get_a_un_dossier(self, obj):
        return hasattr(obj, "dossier_agent")

    def get_nom(self, obj):
        return nom_complet(obj)

    def get_suspendu_par_nom(self, obj):
        return nom_complet(obj.suspendu_par) if obj.suspendu_par_id else None

    def get_gare(self, obj):
        affectation = getattr(obj, "affectation_gare", None)
        return affectation.gare.nom if affectation is not None else None


# Les postes qu'on donne à un compte depuis l'écran « Personnel et comptes » : ni PDG, ni opérateur de la plateforme (voir
# `core.comptes.ROLES_INTOUCHABLES`).
POSTES_ATTRIBUABLES = [(role.value, role.label) for role in Role if role not in (Role.PDG, Role.SUPERADMIN)]
IDENTIFIANT_VALIDE = r"^[\w.@+-]+$"


class CompteGereSerializer(serializers.ModelSerializer):
    """Créer un compte (`POST /comptes/`) ou modifier sa fiche (`PATCH /comptes/{id}/`). À la création : `gare` (guichetier,
    bagagiste : leur équipe) et `date_embauche` (ouvre le dossier agent), facultatives. L'identifiant ne change plus ensuite."""

    username = serializers.RegexField(
        IDENTIFIANT_VALIDE,
        max_length=150,
        error_messages={"invalid": "Identifiant : lettres, chiffres et . @ + - _ seulement, sans espace."},
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=POSTES_ATTRIBUABLES)
    gare = serializers.PrimaryKeyRelatedField(queryset=Gare.objects.all(), required=False, allow_null=True, write_only=True)
    date_embauche = serializers.DateField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "role", "telephone", "matricule", "email", "gare", "date_embauche"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:  # modification : identifiant figé, gare et dossier se tiennent ailleurs
            self.fields["username"].read_only = True
            del self.fields["gare"], self.fields["date_embauche"]

    @property
    def _user(self):
        return self.context["request"].user

    def validate_username(self, valeur):
        valeur = valeur.strip()
        if User.objects.filter(username__iexact=valeur).exists():
            raise serializers.ValidationError("Cet identifiant est déjà pris : choisissez-en un autre.")
        return valeur

    def validate_telephone(self, valeur):
        return valider_telephone(valeur)

    def validate_matricule(self, valeur):
        valeur = (valeur or "").strip()
        doublon = User.objects.filter(company_id=self._user.company_id, matricule__iexact=valeur)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if valeur and doublon.exists():
            raise serializers.ValidationError(f"Le matricule {valeur} est déjà celui de {nom_complet(doublon.first())}.")
        return valeur

    def validate_gare(self, gare):
        if gare is not None and gare.company_id != self._user.company_id:
            raise serializers.ValidationError("Cette gare n'appartient pas à votre compagnie.")
        return gare

    def validate_role(self, role):
        agent = self.instance
        if agent is None or role == agent.role:
            return role
        if agent.pk == self._user.pk:
            raise serializers.ValidationError("On ne change pas son propre poste.")
        gare_dirigee = getattr(agent, "gare_dirigee", None)
        if gare_dirigee is not None:
            raise serializers.ValidationError(
                f"{nom_complet(agent)} dirige la gare {gare_dirigee.nom} : désignez-lui d'abord un autre chef (Gares et quais)."
            )
        affectation = getattr(agent, "affectation_gare", None)
        if affectation is not None:
            raise serializers.ValidationError(
                f"{nom_complet(agent)} fait partie de l'équipe de la gare {affectation.gare.nom} : retirez-le d'abord de "
                "l'équipe."
            )
        return role

    def validate(self, attrs):
        if attrs.get("gare") is not None and attrs.get("role") not in ROLES_EQUIPE_LOCALE:
            raise serializers.ValidationError(
                {"gare": "La gare ne s'indique ici que pour un guichetier ou un bagagiste ; le chef d'une gare se désigne "
                         "depuis « Gares et quais »."}
            )
        return attrs


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
            "doit_changer_mot_de_passe",
        ]


class ChangementMotDePasseSerializer(serializers.Serializer):
    """Changer son propre mot de passe : l'actuel est vérifié, le nouveau suit les règles de robustesse du serveur."""

    ancien = serializers.CharField(write_only=True, trim_whitespace=False)
    nouveau = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_ancien(self, valeur):
        if not self.context["request"].user.check_password(valeur):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return valeur

    def validate(self, attrs):
        if attrs["nouveau"] == attrs["ancien"]:
            raise serializers.ValidationError({"nouveau": "Choisissez un mot de passe différent de l'actuel."})
        try:
            validate_password(attrs["nouveau"], self.context["request"].user)
        except DjangoValidationError as erreur:
            raise serializers.ValidationError({"nouveau": list(erreur.messages)}) from erreur
        return attrs
