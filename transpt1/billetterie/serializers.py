from django.db import transaction
from rest_framework import serializers

from core.models import Role
from core.serializers import CompanySerializer, nom_complet
from billetterie.models import Depart, DepartStatut, Ticket

CHAUFFEUR_ROLES = {Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS}


class DepartSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    # Nom du chauffeur, pour les tableaux de bord : l'API n'expose aucun annuaire d'agents.
    chauffeur_nom = serializers.SerializerMethodField()
    places_restantes = serializers.IntegerField(read_only=True)
    # Places mises de côté pour des ventes hors ligne, et places vendables par un guichetier
    # qui n'a pas réservé (= restantes - réservées).
    places_reservees = serializers.IntegerField(read_only=True)
    places_disponibles = serializers.IntegerField(read_only=True)

    class Meta:
        model = Depart
        fields = [
            "id",
            "ligne",
            "vehicule",
            "chauffeur",
            "chauffeur_nom",
            "company",
            "date_heure",
            "statut",
            "places_vendues",
            "places_restantes",
            "places_reservees",
            "places_disponibles",
        ]
        read_only_fields = ["company", "places_vendues"]

    def get_chauffeur_nom(self, obj):
        return nom_complet(obj.chauffeur)

    def update(self, instance, validated_data):
        """Un changement de chauffeur suit sur la feuille de route pas encore démarrée : c'est
        elle que le chauffeur consulte. Une feuille déjà transférée à un relais est laissée."""
        ancien_chauffeur_id = instance.chauffeur_id
        with transaction.atomic():
            depart = super().update(instance, validated_data)
            if depart.chauffeur_id != ancien_chauffeur_id:
                from personnel_roulant.models import FeuilleDeRoute

                FeuilleDeRoute.objects.filter(
                    depart=depart, chauffeur_id=ancien_chauffeur_id, heure_depart_reelle__isnull=True
                ).update(chauffeur=depart.chauffeur)
        return depart

    def validate_chauffeur(self, chauffeur):
        if chauffeur.role not in CHAUFFEUR_ROLES:
            raise serializers.ValidationError(
                "Le chauffeur doit avoir le rôle chauffeur_principal ou chauffeur_relais."
            )
        return chauffeur

    def validate(self, attrs):
        request = self.context["request"]
        target_company_id = request.user.company_id

        ligne = attrs.get("ligne") or getattr(self.instance, "ligne", None)
        vehicule = attrs.get("vehicule") or getattr(self.instance, "vehicule", None)
        chauffeur = attrs.get("chauffeur") or getattr(self.instance, "chauffeur", None)

        for field_name, related in (
            ("ligne", ligne),
            ("vehicule", vehicule),
            ("chauffeur", chauffeur),
        ):
            if related is not None and related.company_id != target_company_id:
                raise serializers.ValidationError(
                    {field_name: "N'appartient pas à votre compagnie."}
                )

        self._verifier_reaffectation(vehicule, chauffeur)
        return attrs

    def _verifier_reaffectation(self, vehicule, chauffeur):
        """Changer de véhicule ou de chauffeur n'a de sens que pour un départ planifié, et
        le nouveau véhicule doit contenir tous les voyageurs déjà enregistrés."""
        depart = self.instance
        if depart is None:
            return
        vehicule_change = vehicule is not None and vehicule.pk != depart.vehicule_id
        chauffeur_change = chauffeur is not None and chauffeur.pk != depart.chauffeur_id
        if not (vehicule_change or chauffeur_change):
            return
        # `Depart.statut` reste « planifié » quand un chauffeur démarre sa feuille de route :
        # c'est donc aussi la feuille qui dit si le car est déjà parti.
        from personnel_roulant.models import FeuilleDeRoute

        deja_parti = FeuilleDeRoute.objects.filter(
            depart=depart, heure_depart_reelle__isnull=False
        ).exists()
        if depart.statut != DepartStatut.PLANIFIE or deja_parti:
            raise serializers.ValidationError(
                "Un départ déjà parti ou terminé ne peut plus changer de véhicule ni de chauffeur."
            )
        if vehicule_change:
            deja_pris = depart.places_vendues + depart.places_reservees
            if vehicule.capacite < deja_pris:
                raise serializers.ValidationError(
                    {
                        "vehicule": f"Ce véhicule ({vehicule.capacite} places) est trop petit : "
                        f"{deja_pris} place(s) déjà vendue(s) ou réservée(s) sur ce départ."
                    }
                )


class TicketSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    vendu_par = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "depart",
            "company",
            "passager_nom",
            "passager_telephone",
            "prix",
            "mode_paiement",
            "vendu_par",
            "date_vente",
        ]
        read_only_fields = ["company", "vendu_par", "date_vente"]

    def validate_depart(self, depart):
        request = self.context["request"]
        if depart.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce départ n'appartient pas à votre compagnie.")
        if depart.statut == DepartStatut.TERMINE:
            raise serializers.ValidationError("Ce départ est terminé, vente impossible.")
        return depart
