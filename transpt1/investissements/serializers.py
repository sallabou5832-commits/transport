from rest_framework import serializers

from core.serializers import nom_complet
from investissements.models import Investissement


class InvestissementSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    demandeur_nom = serializers.SerializerMethodField()
    demandeur_role = serializers.CharField(source="demandeur.role", read_only=True)
    decide_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Investissement
        fields = [
            "id", "type", "type_libelle", "libelle", "justification", "montant", "quantite", "demandeur", "demandeur_nom",
            "demandeur_role", "statut", "decide_par", "decide_par_nom", "decide_le", "commentaire_decision", "cree_le",
        ]
        # Le statut et la décision ne se changent que par l'action `decider`.
        read_only_fields = ["demandeur", "statut", "decide_par", "decide_le", "commentaire_decision", "cree_le"]

    def get_demandeur_nom(self, obj):
        return nom_complet(obj.demandeur)

    def get_decide_par_nom(self, obj):
        return nom_complet(obj.decide_par) if obj.decide_par_id else None

    def validate_libelle(self, valeur):
        valeur = valeur.strip()
        if len(valeur) < 3:
            raise serializers.ValidationError("Donnez un intitulé à la demande.")
        return valeur

    def validate_quantite(self, valeur):
        if valeur is not None and valeur < 1:
            raise serializers.ValidationError("La quantité doit être d'au moins un.")
        return valeur
