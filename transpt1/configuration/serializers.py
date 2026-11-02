from rest_framework import serializers

from configuration import regles
from configuration.models import ConfigurationAgent, ConfigurationCompagnie, ConfigurationPoste
from configuration.regles import NiveauAutomatisation, NiveauGamification
from configuration.services import cadre_de
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
        fields = ["automatisation_max", "gamification_max", "modifie_le"]
        read_only_fields = ["modifie_le"]


class ConfigurationPosteSerializer(serializers.ModelSerializer):
    role_libelle = serializers.SerializerMethodField()

    class Meta:
        model = ConfigurationPoste
        fields = [
            "role", "role_libelle", "niveau_automatisation", "niveau_gamification", "fonctions_desactivees",
            "prefere_vocal", "modifie_le",
        ]
        read_only_fields = ["role", "modifie_le"]
        # Une valeur vide laisse le défaut du socle.
        extra_kwargs = {
            "niveau_automatisation": {"required": False, "allow_null": True},
            "niveau_gamification": {"required": False, "allow_null": True},
        }

    def get_role_libelle(self, obj):
        return Role(obj.role).label

    def validate_fonctions_desactivees(self, valeur):
        return _verifier_fonctions(valeur)

    def validate(self, attrs):
        _verifier_niveaux(attrs, self.context["request"].user.company_id)
        return attrs


class ConfigurationAgentSerializer(serializers.ModelSerializer):
    agent = serializers.IntegerField(source="agent_id", read_only=True)
    agent_nom = serializers.SerializerMethodField()
    agent_role = serializers.CharField(source="agent.role", read_only=True)

    class Meta:
        model = ConfigurationAgent
        fields = [
            "agent", "agent_nom", "agent_role", "niveau_automatisation", "niveau_gamification",
            "fonctions_desactivees", "prefere_vocal", "aisance_numerique", "modifie_le",
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
