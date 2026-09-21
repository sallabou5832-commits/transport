from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from billetterie import planning
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
        """Un changement de chauffeur ou d'heure suit sur la feuille de route pas encore démarrée : c'est elle que
        le chauffeur consulte. Une feuille déjà transférée à un relais garde son chauffeur. Chaque feuille est
        enregistrée une à une (et non par `update()` groupé) pour que le journal d'audit voie le changement."""
        ancien_chauffeur_id, ancienne_heure = instance.chauffeur_id, instance.date_heure
        with transaction.atomic():
            depart = super().update(instance, validated_data)
            from personnel_roulant.models import FeuilleDeRoute

            for feuille in FeuilleDeRoute.objects.filter(depart=depart, heure_depart_reelle__isnull=True):
                champs = []
                if depart.chauffeur_id != ancien_chauffeur_id and feuille.chauffeur_id == ancien_chauffeur_id:
                    feuille.chauffeur = depart.chauffeur
                    champs.append("chauffeur")
                if depart.date_heure != ancienne_heure:
                    feuille.heure_depart_prevue = depart.date_heure
                    champs.append("heure_depart_prevue")
                if champs:
                    feuille.save(update_fields=champs)
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

        date_heure = attrs.get("date_heure") or getattr(self.instance, "date_heure", None)
        self._verifier_reaffectation(vehicule, chauffeur, date_heure)
        self._verifier_planning(vehicule, chauffeur, date_heure)
        return attrs

    def _verifier_planning(self, vehicule, chauffeur, date_heure):
        """Un départ se planifie sur un véhicule et un chauffeur libres : ni immobilisé, ni déjà pris par un autre
        départ proche. Ne contrôle que ce qui change (un départ existant garde son véhicule actuel)."""
        depart = self.instance
        exclure = depart.pk if depart else None
        neuf = depart is None
        vehicule_change = neuf or (vehicule is not None and vehicule.pk != depart.vehicule_id)
        chauffeur_change = neuf or (chauffeur is not None and chauffeur.pk != depart.chauffeur_id)
        heure_change = neuf or (date_heure is not None and date_heure != depart.date_heure)
        erreurs = {}

        if neuf and date_heure is not None and date_heure < timezone.now() - planning.TOLERANCE_DATE_PASSEE:
            erreurs["date_heure"] = "Cette date est déjà passée."

        def message(conflit, sujet, autre):
            heure = timezone.localtime(conflit.date_heure).strftime("%d/%m à %H:%M")
            return f"{sujet} déjà affecté au départ {conflit.ligne.nom} du {heure} : choisissez une autre heure ou {autre}."

        if vehicule is not None and date_heure is not None and (vehicule_change or heure_change):
            if vehicule_change and vehicule.statut in planning.STATUTS_VEHICULE_IMMOBILISES:
                erreurs["vehicule"] = (
                    f"Ce véhicule est immobilisé ({vehicule.get_statut_display().lower()}) : il ne peut pas être planifié."
                )
            else:
                conflit = planning.depart_en_conflit(vehicule=vehicule, date_heure=date_heure, exclure_depart_id=exclure)
                if conflit:
                    erreurs["vehicule"] = message(conflit, "Ce véhicule est", "un autre véhicule")
        if chauffeur is not None and date_heure is not None and (chauffeur_change or heure_change):
            conflit = planning.depart_en_conflit(chauffeur=chauffeur, date_heure=date_heure, exclure_depart_id=exclure)
            if conflit:
                erreurs["chauffeur"] = message(conflit, "Ce chauffeur est", "un autre chauffeur")
        if erreurs:
            raise serializers.ValidationError(erreurs)

    def _verifier_reaffectation(self, vehicule, chauffeur, date_heure=None):
        """Changer de véhicule, de chauffeur ou d'heure n'a de sens que pour un départ planifié, et
        le nouveau véhicule doit contenir tous les voyageurs déjà enregistrés."""
        depart = self.instance
        if depart is None:
            return
        vehicule_change = vehicule is not None and vehicule.pk != depart.vehicule_id
        chauffeur_change = chauffeur is not None and chauffeur.pk != depart.chauffeur_id
        heure_change = date_heure is not None and date_heure != depart.date_heure
        if not (vehicule_change or chauffeur_change or heure_change):
            return
        # `Depart.statut` reste « planifié » quand un chauffeur démarre sa feuille de route :
        # c'est donc aussi la feuille qui dit si le car est déjà parti.
        from personnel_roulant.models import FeuilleDeRoute

        deja_parti = FeuilleDeRoute.objects.filter(
            depart=depart, heure_depart_reelle__isnull=False
        ).exists()
        if depart.statut != DepartStatut.PLANIFIE or deja_parti:
            raise serializers.ValidationError(
                "Un départ déjà parti ou terminé ne peut plus changer de véhicule, de chauffeur ni d'heure."
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
            "statut",
            "annule_par",
            "annule_le",
            "motif_annulation",
        ]
        # Le statut ne se change que par l'action `annuler` : jamais à la création ni par une modification.
        read_only_fields = [
            "company", "vendu_par", "date_vente", "statut", "annule_par", "annule_le", "motif_annulation",
        ]

    def validate_depart(self, depart):
        request = self.context["request"]
        if depart.company_id != request.user.company_id:
            raise serializers.ValidationError("Ce départ n'appartient pas à votre compagnie.")
        if depart.statut == DepartStatut.TERMINE:
            raise serializers.ValidationError("Ce départ est terminé, vente impossible.")
        return depart
