from rest_framework import serializers

from formation.models import EtapeFormation, ParcoursFormation, ProgressionFormation

STATUT_TERMINEE = "terminee"
STATUT_EN_COURS = "en_cours"
STATUT_A_VENIR = "a_venir"


def statut_etape(etape, progression):
    if progression is None:
        return STATUT_A_VENIR
    if progression.termine:
        return STATUT_TERMINEE
    courante = progression.etape_courante
    if etape.ordre < courante.ordre:
        return STATUT_TERMINEE
    return STATUT_EN_COURS if etape.pk == courante.pk else STATUT_A_VENIR


class EtapeFormationSerializer(serializers.ModelSerializer):
    statut = serializers.SerializerMethodField()

    class Meta:
        model = EtapeFormation
        fields = [
            "id",
            "ordre",
            "titre",
            "instructions",
            "type_action",
            "scenario",
            "donnees_simulees",
            "statut",
        ]

    def get_statut(self, etape):
        return statut_etape(etape, self.context.get("progression"))


class ProgressionFormationSerializer(serializers.ModelSerializer):
    etape_courante = serializers.PrimaryKeyRelatedField(read_only=True)
    etapes_total = serializers.SerializerMethodField()
    etapes_terminees = serializers.SerializerMethodField()

    class Meta:
        model = ProgressionFormation
        fields = [
            "etape_courante",
            "termine",
            "date_debut",
            "date_fin",
            "etapes_terminees",
            "etapes_total",
        ]

    def get_etapes_total(self, progression):
        return len(progression.parcours.etapes.all())

    def get_etapes_terminees(self, progression):
        etapes = progression.parcours.etapes.all()
        if progression.termine:
            return len(etapes)
        return sum(1 for etape in etapes if etape.ordre < progression.etape_courante.ordre)


class ParcoursFormationSerializer(serializers.ModelSerializer):
    etapes = serializers.SerializerMethodField()
    progression = serializers.SerializerMethodField()

    class Meta:
        model = ParcoursFormation
        fields = ["id", "role", "titre", "description", "etapes", "progression"]

    def get_etapes(self, parcours):
        etapes = sorted(parcours.etapes.all(), key=lambda etape: etape.ordre)
        return EtapeFormationSerializer(etapes, many=True, context=self.context).data

    def get_progression(self, parcours):
        progression = self.context.get("progression")
        if progression is None:
            return None
        return ProgressionFormationSerializer(progression, context=self.context).data
