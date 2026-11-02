from django.utils import timezone
from rest_framework import serializers

from core.models import Role
from core.serializers import nom_complet
from rh import services
from rh.models import (
    Candidature,
    ContratAgent,
    DemandeConge,
    Doleance,
    EvaluationAgent,
    FicheDePoste,
    FormationSuivie,
    GraviteDoleance,
    MesureDisciplinaire,
    ObligationFormation,
    OffreRecrutement,
    StatutOffre,
    SuiviDoleance,
    TypeConge,
)

ROLES_VALIDES = {role.value for role in Role if role != Role.SUPERADMIN}


def _de_la_compagnie(serializer, objet, message):
    if objet is not None and objet.company_id != serializer.context["request"].user.company_id:
        raise serializers.ValidationError(message)
    return objet


def _agent_de_la_compagnie(serializer, agent):
    return _de_la_compagnie(serializer, agent, "Cet agent n'appartient pas à votre compagnie.")


class ObligationFormationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObligationFormation
        fields = ["id", "nom", "description", "roles", "validite_mois", "preavis_jours"]
        validators = []

    def validate_nom(self, valeur):
        valeur = valeur.strip()
        doublon = ObligationFormation.objects.filter(company_id=self.context["request"].user.company_id, nom__iexact=valeur)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Cette obligation existe déjà.")
        return valeur

    def validate_roles(self, valeur):
        if not isinstance(valeur, list) or not valeur:
            raise serializers.ValidationError("Indiquez au moins un poste concerné.")
        # `str` d'abord : un élément qui n'est pas un texte (un nombre, une liste) n'est pas hachable ou pas un poste connu.
        postes = {str(poste) for poste in valeur}
        inconnus = sorted(postes - ROLES_VALIDES)
        if inconnus:
            raise serializers.ValidationError(f"Postes inconnus : {', '.join(inconnus)}.")
        return sorted(postes)


class FormationSuivieSerializer(serializers.ModelSerializer):
    agent_nom = serializers.SerializerMethodField()
    obligation_nom = serializers.CharField(source="obligation.nom", read_only=True)

    class Meta:
        model = FormationSuivie
        fields = [
            "id", "agent", "agent_nom", "obligation", "obligation_nom", "date_obtention", "date_expiration", "organisme", "reference",
        ]
        validators = []

    def get_agent_nom(self, obj):
        return nom_complet(obj.agent)

    def validate_agent(self, agent):
        return _agent_de_la_compagnie(self, agent)

    def validate_obligation(self, obligation):
        return _de_la_compagnie(self, obligation, "Cette obligation n'appartient pas à votre compagnie.")

    def validate_date_obtention(self, valeur):
        if valeur > timezone.localdate():
            raise serializers.ValidationError("Une formation ne peut pas être datée du futur.")
        return valeur

    def validate(self, attrs):
        obtention = attrs.get("date_obtention", getattr(self.instance, "date_obtention", None))
        expiration = attrs.get("date_expiration", getattr(self.instance, "date_expiration", None))
        obligation = attrs.get("obligation", getattr(self.instance, "obligation", None))
        if expiration is None and obtention and obligation is not None and obligation.validite_mois:
            attrs["date_expiration"] = services.ajouter_mois(obtention, obligation.validite_mois)  # la durée de validité fait foi
        elif expiration is not None and obtention and expiration <= obtention:
            raise serializers.ValidationError({"date_expiration": "L'expiration doit suivre la date d'obtention."})
        agent = attrs.get("agent", getattr(self.instance, "agent", None))
        doublon = FormationSuivie.objects.filter(agent=agent, obligation=obligation, date_obtention=obtention)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Cette session est déjà enregistrée pour cet agent.")
        return attrs


class ContratAgentSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = ContratAgent
        fields = ["id", "agent", "type", "type_libelle", "date_debut", "date_fin", "reference", "notes"]

    def validate_agent(self, agent):
        return _agent_de_la_compagnie(self, agent)

    def validate(self, attrs):
        debut = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        fin = attrs.get("date_fin", getattr(self.instance, "date_fin", None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"date_fin": "La fin précède le début du contrat."})
        return attrs


class EvaluationAgentSerializer(serializers.ModelSerializer):
    evaluateur_nom = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationAgent
        fields = ["id", "agent", "date", "note", "commentaire", "evaluateur", "evaluateur_nom"]
        read_only_fields = ["evaluateur"]

    def get_evaluateur_nom(self, obj):
        return nom_complet(obj.evaluateur)

    def validate_agent(self, agent):
        return _agent_de_la_compagnie(self, agent)

    def validate_date(self, valeur):
        if valeur > timezone.localdate():
            raise serializers.ValidationError("Une évaluation ne peut pas être datée du futur.")
        return valeur


class MesureDisciplinaireSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = MesureDisciplinaire
        fields = ["id", "agent", "date", "type", "type_libelle", "motif", "duree_jours", "decidee_par"]
        read_only_fields = ["decidee_par"]

    def validate_agent(self, agent):
        return _agent_de_la_compagnie(self, agent)

    def validate_date(self, valeur):
        if valeur > timezone.localdate():
            raise serializers.ValidationError("Une mesure ne peut pas être datée du futur.")
        return valeur

    def validate_motif(self, valeur):
        if len(valeur.strip()) < 5:
            raise serializers.ValidationError("Indiquez le motif de la mesure.")
        return valeur.strip()


class DemandeCongeSerializer(serializers.ModelSerializer):
    agent_nom = serializers.SerializerMethodField()
    agent_role = serializers.CharField(source="agent.role", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    decide_par_nom = serializers.SerializerMethodField()
    jours = serializers.SerializerMethodField()

    class Meta:
        model = DemandeConge
        fields = [
            "id", "agent", "agent_nom", "agent_role", "type", "type_libelle", "debut", "fin", "jours", "motif", "statut",
            "statut_libelle", "decide_par_nom", "decide_le", "motif_decision", "cree_le",
        ]
        read_only_fields = ["statut", "decide_le", "motif_decision", "cree_le"]
        extra_kwargs = {"agent": {"required": False}}

    def get_agent_nom(self, obj):
        return nom_complet(obj.agent)

    def get_decide_par_nom(self, obj):
        return nom_complet(obj.decide_par)

    def get_jours(self, obj):
        return (obj.fin - obj.debut).days + 1

    def validate_agent(self, agent):
        return _agent_de_la_compagnie(self, agent)

    def validate(self, attrs):
        debut, fin = attrs["debut"], attrs["fin"]
        if fin < debut:
            raise serializers.ValidationError({"fin": "La fin précède le début du congé."})
        if (fin - debut).days + 1 > services.DUREE_MAX_CONGE_JOURS:
            raise serializers.ValidationError(f"Une demande ne peut pas dépasser {services.DUREE_MAX_CONGE_JOURS} jours : faites-en deux.")
        # Un arrêt maladie se déclare après coup ; tout autre congé se demande avant.
        if debut < timezone.localdate() and attrs.get("type", TypeConge.ANNUEL) != TypeConge.MALADIE:
            raise serializers.ValidationError({"debut": "Ce congé commence dans le passé : seule une maladie se déclare après coup."})
        return attrs


class FicheDePosteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FicheDePoste
        fields = ["role", "intitule", "missions", "profil", "conditions"]
        read_only_fields = ["role"]


class OffreRecrutementSerializer(serializers.ModelSerializer):
    role_libelle = serializers.CharField(source="get_role_display", read_only=True)
    gare_nom = serializers.CharField(source="gare.nom", read_only=True, default=None)
    candidatures_total = serializers.SerializerMethodField()
    retenues = serializers.SerializerMethodField()

    class Meta:
        model = OffreRecrutement
        fields = [
            "id", "role", "role_libelle", "intitule", "description", "nombre_postes", "gare", "gare_nom", "date_limite", "statut",
            "candidatures_total", "retenues", "cree_le",
        ]
        read_only_fields = ["cree_le"]
        extra_kwargs = {"intitule": {"required": False}, "description": {"required": False}}

    def get_candidatures_total(self, obj):
        return obj.candidatures.count()

    def get_retenues(self, obj):
        return obj.candidatures.filter(statut="retenue").count()

    def validate_gare(self, gare):
        return _de_la_compagnie(self, gare, "Cette gare n'appartient pas à votre compagnie.")

    def validate_role(self, role):
        if role not in ROLES_VALIDES:
            raise serializers.ValidationError("Ce poste n'existe pas dans l'organigramme.")
        return role

    def validate_date_limite(self, valeur):
        if valeur is not None and valeur < timezone.localdate() and self.instance is None:
            raise serializers.ValidationError("La date limite est déjà passée.")
        return valeur


class CandidatureSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    offre_intitule = serializers.CharField(source="offre.intitule", read_only=True)

    class Meta:
        model = Candidature
        fields = ["id", "offre", "offre_intitule", "nom", "telephone", "email", "source", "statut", "statut_libelle", "notes", "cree_le"]
        read_only_fields = ["cree_le"]

    def validate_offre(self, offre):
        offre = _de_la_compagnie(self, offre, "Cette offre n'appartient pas à votre compagnie.")
        if offre.statut != StatutOffre.OUVERTE and self.instance is None:
            raise serializers.ValidationError("Cette offre n'est plus ouverte.")
        return offre


class SuiviDoleanceSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = SuiviDoleance
        fields = ["id", "texte", "visible_du_deposant", "auteur_nom", "cree_le"]
        read_only_fields = ["cree_le"]

    def get_auteur_nom(self, obj):
        return nom_complet(obj.auteur)


class DoleanceSerializer(serializers.ModelSerializer):
    """Ce que voit le DRH (tout) et le déposant (sa doléance, avec les étapes qu'on a choisi de lui montrer)."""

    auteur_nom = serializers.SerializerMethodField()
    auteur_role = serializers.CharField(source="auteur.role", read_only=True, default=None)
    origine_libelle = serializers.CharField(source="get_origine_display", read_only=True)
    gravite_libelle = serializers.CharField(source="get_gravite_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    suivis = serializers.SerializerMethodField()
    litige = serializers.SerializerMethodField()

    class Meta:
        model = Doleance
        fields = [
            "id", "origine", "origine_libelle", "auteur", "auteur_nom", "auteur_role", "syndicat", "objet", "description", "gravite",
            "gravite_libelle", "statut", "statut_libelle", "litige", "litige_signale_le", "suivis", "cree_le",
        ]
        read_only_fields = ["auteur", "litige_signale_le", "cree_le"]
        extra_kwargs = {"origine": {"required": False}, "gravite": {"required": False}, "statut": {"required": False}}

    def _drh(self):
        return self.context["request"].user.role == Role.DRH

    def get_auteur_nom(self, obj):
        return nom_complet(obj.auteur) if obj.auteur_id else None

    def get_litige(self, obj):
        return services.est_litige(obj)

    def get_suivis(self, obj):
        suivis = obj.suivis.all()
        if not self._drh():
            suivis = [s for s in suivis if s.visible_du_deposant]
        return SuiviDoleanceSerializer(suivis, many=True, context=self.context).data

    def validate_gravite(self, valeur):
        # Un agent qualifie sa doléance jusqu'à « grave » ; « critique » est une décision du DRH.
        if not self._drh() and valeur == GraviteDoleance.CRITIQUE:
            raise serializers.ValidationError("Seul le DRH qualifie une doléance de critique.")
        return valeur

    def validate(self, attrs):
        if not self._drh():
            # Un agent ne dépose que la sienne, sans toucher à son traitement.
            for interdit in ("origine", "statut", "syndicat"):
                if interdit in attrs:
                    raise serializers.ValidationError({interdit: "Réservé au DRH."})
        elif attrs.get("origine") == "syndicat" and not (attrs.get("syndicat") or getattr(self.instance, "syndicat", "")).strip():
            raise serializers.ValidationError({"syndicat": "Indiquez le syndicat ou les délégués qui déposent cette doléance."})
        return attrs

    def validate_objet(self, valeur):
        if len(valeur.strip()) < 3:
            raise serializers.ValidationError("Donnez un objet à la doléance.")
        return valeur.strip()

    def validate_description(self, valeur):
        if len(valeur.strip()) < 10:
            raise serializers.ValidationError("Décrivez la situation en quelques mots au moins.")
        return valeur.strip()


class LitigeSerializer(serializers.ModelSerializer):
    """Le litige social vu du juridique : l'objet, la gravité et le poste de l'auteur, pas son identité."""

    auteur_role = serializers.CharField(source="auteur.role", read_only=True, default=None)
    gravite_libelle = serializers.CharField(source="get_gravite_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    origine_libelle = serializers.CharField(source="get_origine_display", read_only=True)

    class Meta:
        model = Doleance
        fields = [
            "id", "origine", "origine_libelle", "auteur_role", "syndicat", "objet", "description", "gravite", "gravite_libelle",
            "statut", "statut_libelle", "litige_signale_le", "cree_le",
        ]

