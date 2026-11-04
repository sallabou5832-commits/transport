from rest_framework import serializers

from configuration import regles
from configuration.models import ConfigurationAgent, ConfigurationCompagnie, ConfigurationPoste, PreferencePersonnelle
from configuration.regles import DureeSession, NiveauAutomatisation, NiveauGamification
from configuration.services import cadre_de, vocal_impose_pour
from core.models import Role
from core.serializers import nom_complet


def _verifier_niveaux(attrs, company_id):
    """Un poste ne dépasse pas le cadre de la compagnie : on le dit clairement plutôt que de plafonner en silence."""
    automatisation_max, gamification_max = cadre_de(company_id)
    erreurs = {}
    niveau = attrs.get("niveau_automatisation")
    if niveau and regles.rang(niveau, NiveauAutomatisation.ORDRE) > regles.rang(automatisation_max, NiveauAutomatisation.ORDRE):
        erreurs["niveau_automatisation"] = (
            f"Le cadre de la compagnie plafonne l'automatisation à « {automatisation_max} »."
        )
    niveau = attrs.get("niveau_gamification")
    if niveau and regles.rang(niveau, NiveauGamification.ORDRE) > regles.rang(gamification_max, NiveauGamification.ORDRE):
        erreurs["niveau_gamification"] = f"Le cadre de la compagnie plafonne la gamification à « {gamification_max} »."
    if erreurs:
        raise serializers.ValidationError(erreurs)


def _verifier_duree_session(attrs, company_id):
    """Un poste peut voir sa durée de session réduite, jamais allongée au-delà du plafond de la compagnie."""
    duree = attrs.get("duree_session_max")
    cadre = ConfigurationCompagnie.objects.filter(company_id=company_id).first()
    plafond = cadre.duree_session_max if cadre is not None else DureeSession.PLAFOND_PAR_DEFAUT
    if duree and regles.rang(duree, DureeSession.ORDRE) > regles.rang(plafond, DureeSession.ORDRE):
        libelle = dict(DureeSession.CHOIX)[plafond].lower()
        raise serializers.ValidationError({"duree_session_max": f"Le cadre de la compagnie plafonne les sessions à « {libelle} »."})


def _verifier_fonctions(valeur):
    if not isinstance(valeur, list):
        raise serializers.ValidationError("Liste de fonctions attendue.")
    # `str` d'abord : un élément qui n'est pas un texte (un nombre, une liste) n'est pas hachable ou pas une fonction connue.
    fonctions = {str(fonction) for fonction in valeur}
    inconnues = sorted(fonctions - set(regles.FONCTIONS))
    if inconnues:
        raise serializers.ValidationError(f"Fonction(s) inconnue(s) : {', '.join(inconnues)}.")
    return sorted(fonctions)


class CadreCompagnieSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationCompagnie
        fields = ["automatisation_max", "gamification_max", "duree_session_max", "code_court_exige", "modifie_le"]
        read_only_fields = ["modifie_le"]


class ConfigurationPosteSerializer(serializers.ModelSerializer):
    role_libelle = serializers.SerializerMethodField()

    class Meta:
        model = ConfigurationPoste
        fields = [
            "role", "role_libelle", "niveau_automatisation", "niveau_gamification", "fonctions_desactivees",
            "prefere_vocal", "prefere_vocal_impose", "duree_session_max", "modifie_le",
        ]
        read_only_fields = ["role", "modifie_le"]
        # Une valeur vide laisse le défaut du socle (pour la durée de session : le plafond de la compagnie).
        extra_kwargs = {
            "niveau_automatisation": {"required": False, "allow_null": True},
            "niveau_gamification": {"required": False, "allow_null": True},
            "duree_session_max": {"required": False, "allow_null": True},
        }

    def get_role_libelle(self, obj):
        return Role(obj.role).label

    def validate_fonctions_desactivees(self, valeur):
        return _verifier_fonctions(valeur)

    def validate(self, attrs):
        _verifier_niveaux(attrs, self.context["request"].user.company_id)
        _verifier_duree_session(attrs, self.context["request"].user.company_id)
        return attrs


class ConfigurationAgentSerializer(serializers.ModelSerializer):
    agent = serializers.IntegerField(source="agent_id", read_only=True)
    agent_nom = serializers.SerializerMethodField()
    agent_role = serializers.CharField(source="agent.role", read_only=True)

    class Meta:
        model = ConfigurationAgent
        fields = [
            "agent", "agent_nom", "agent_role", "niveau_automatisation", "niveau_gamification",
            "fonctions_desactivees", "prefere_vocal", "prefere_vocal_impose", "aisance_numerique", "modifie_le",
        ]
        read_only_fields = ["modifie_le"]
        extra_kwargs = {
            "niveau_automatisation": {"required": False, "allow_null": True},
            "niveau_gamification": {"required": False, "allow_null": True},
            "prefere_vocal": {"required": False, "allow_null": True},
        }

    def get_agent_nom(self, obj):
        return nom_complet(obj.agent)

    def validate_fonctions_desactivees(self, valeur):
        return _verifier_fonctions(valeur)

    def validate(self, attrs):
        _verifier_niveaux(attrs, self.context["request"].user.company_id)
        return attrs


class PreferencePersonnelleSerializer(serializers.ModelSerializer):
    """Mes préférences (`/configuration/mes-preferences/`). `vocal_impose` : le supérieur a fixé le mode vocal, l'agent ne le
    choisit pas."""

    vocal_impose = serializers.SerializerMethodField()

    class Meta:
        model = PreferencePersonnelle
        fields = ["prefere_vocal", "son_alertes", "notifications_navigateur", "vocal_impose", "modifie_le"]
        read_only_fields = ["modifie_le"]
        extra_kwargs = {"prefere_vocal": {"required": False, "allow_null": True}}

    def get_vocal_impose(self, obj):
        return vocal_impose_pour(self.context["request"].user)

    def validate_prefere_vocal(self, valeur):
        if valeur is not None and vocal_impose_pour(self.context["request"].user):
            raise serializers.ValidationError("Votre supérieur a fixé le mode vocal pour vous : il ne se change pas ici.")
        return valeur
