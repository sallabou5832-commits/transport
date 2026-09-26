import csv
import datetime

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.dates import lire_date
from core.mixins import ActeurAuditeMixin, CompanyScopedQuerysetMixin
from core.permissions import IsSameCompany
from finance import alertes, analyses
from finance.models import (
    BudgetCarburant,
    CategorieDepense,
    ConfigurationFinance,
    Depense,
    Facture,
    Fournisseur,
    StatutFacture,
    TypeFacture,
)
from finance.permissions import PeutGererLaFinance
from finance.serializers import (
    BudgetCarburantSerializer,
    ConfigurationFinanceSerializer,
    DepenseSerializer,
    FactureSerializer,
    FournisseurSerializer,
)


class FinanceViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSameCompany, PeutGererLaFinance]

    def perform_create(self, serializer):
        user = self.request.user
        champs = {"company": user.company}
        if "saisi_par" in {f.name for f in serializer.Meta.model._meta.fields}:
            champs["saisi_par"] = user
        return serializer.save(**champs)


def _periode(request):
    """`date_debut` et `date_fin` (AAAA-MM-JJ), par défaut le mois en cours jusqu'à aujourd'hui."""
    aujourdhui = timezone.localdate()
    debut = lire_date(request.query_params.get("date_debut")) or aujourdhui.replace(day=1)
    fin = lire_date(request.query_params.get("date_fin")) or aujourdhui
    if fin < debut:
        raise ValidationError({"date_fin": "La fin précède le début."})
    return debut, fin


class DepenseViewSet(FinanceViewSet):
    """Dépenses de la compagnie (`?date_debut=`, `?date_fin=`, `?categorie=`, `?ligne=`). Une dépense de carburant qui fait
    atteindre 80 % du budget de sa ligne, ou le dépasser, alerte la finance et le PDG."""

    queryset = Depense.objects.select_related("ligne", "vehicule", "gare", "saisi_par")
    serializer_class = DepenseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        parametres = self.request.query_params
        debut, fin = lire_date(parametres.get("date_debut")), lire_date(parametres.get("date_fin"))
        if debut:
            queryset = queryset.filter(date__gte=debut)
        if fin:
            queryset = queryset.filter(date__lte=fin)
        if parametres.get("categorie") in CategorieDepense.values:
            queryset = queryset.filter(categorie=parametres["categorie"])
        if parametres.get("ligne", "").isdigit():
            queryset = queryset.filter(ligne_id=int(parametres["ligne"]))
        return queryset

    def _verifier_budget(self, depense):
        if depense.categorie == CategorieDepense.CARBURANT and depense.ligne_id:
            list(alertes.alertes_budget(depense.company, depense.date))

    def perform_create(self, serializer):
        self._verifier_budget(super().perform_create(serializer))

    def perform_update(self, serializer):
        self._verifier_budget(serializer.save())


class BudgetCarburantViewSet(FinanceViewSet):
    queryset = BudgetCarburant.objects.select_related("ligne")
    serializer_class = BudgetCarburantSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        mois = lire_date(self.request.query_params.get("mois"))
        return queryset.filter(mois=mois.replace(day=1)) if mois else queryset


class FournisseurViewSet(FinanceViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer


class FactureViewSet(FinanceViewSet):
    """Échéancier des paiements aux fournisseurs et aux assureurs (`?statut=`). Payer une facture (`payer`) enregistre la
    dépense correspondante ; les rappels partent à 7 jours, à 1 jour et au retard."""

    queryset = Facture.objects.select_related("fournisseur")
    serializer_class = FactureSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("statut") in StatutFacture.values:
            queryset = queryset.filter(statut=self.request.query_params["statut"])
        return queryset

    def perform_update(self, serializer):
        if serializer.instance.statut != StatutFacture.A_PAYER:
            raise ValidationError("Cette facture est déjà réglée ou annulée : elle ne se modifie plus.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.statut != StatutFacture.A_PAYER:
            raise ValidationError("Une facture réglée ou annulée reste au registre : elle ne se supprime pas.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="payer")
    def payer(self, request, pk=None):
        """Marque la facture payée (`date` et `mode_paiement` facultatifs : aujourd'hui) et enregistre la dépense."""
        facture = self.get_object()
        if facture.statut != StatutFacture.A_PAYER:
            raise ValidationError("Cette facture est déjà réglée ou annulée.")
        date = lire_date(request.data.get("date")) or timezone.localdate()
        if date > timezone.localdate():
            raise ValidationError({"date": "Une facture ne se paie pas dans le futur."})
        categorie = CategorieDepense.ASSURANCE if facture.type == TypeFacture.ASSURANCE else CategorieDepense.FOURNISSEUR
        with transaction.atomic():
            depense = Depense.objects.create(
                company=facture.company, date=date, categorie=categorie, libelle=f"{facture.fournisseur.nom} — {facture.libelle}",
                montant=facture.montant, saisi_par=request.user,
            )
            facture.statut, facture.payee_le, facture.depense = StatutFacture.PAYEE, date, depense
            facture.mode_paiement = str(request.data.get("mode_paiement", ""))[:20]
            facture.save(update_fields=["statut", "payee_le", "depense", "mode_paiement"])
        return Response(self.get_serializer(facture).data)

    @action(detail=True, methods=["post"], url_path="annuler")
    def annuler(self, request, pk=None):
        facture = self.get_object()
        if facture.statut != StatutFacture.A_PAYER:
            raise ValidationError("Seule une facture à payer s'annule.")
        facture.statut = StatutFacture.ANNULEE
        facture.save(update_fields=["statut"])
        return Response(self.get_serializer(facture).data)


class _LectureFinance(ActeurAuditeMixin, APIView):
    permission_classes = [IsAuthenticated, PeutGererLaFinance]


class RentabiliteView(_LectureFinance):
    """Rentabilité par ligne et par gare (recettes contre dépenses) sur `date_debut` – `date_fin` (le mois en cours par défaut)."""

    def get(self, request):
        debut, fin = _periode(request)
        return Response(analyses.rentabilite(request.user.company, debut, fin))


class SuiviBudgetCarburantView(_LectureFinance):
    """Budget carburant du mois (`?mois=AAAA-MM-JJ`, le mois en cours par défaut) : prévu, réalisé, état par ligne."""

    def get(self, request):
        mois = lire_date(request.query_params.get("mois")) or timezone.localdate()
        return Response(analyses.suivi_budget_carburant(request.user.company, mois))


class TresorerieView(_LectureFinance):
    """Trésorerie en temps réel, visible de la finance et du PDG."""

    def get(self, request):
        return Response(analyses.tresorerie(request.user.company))


class ConfigurationFinanceView(_LectureFinance):
    """Le solde de départ de la trésorerie (GET pour tous les lecteurs, PUT pour la finance)."""

    def get_serializer(self, *args, **kwargs):  # OPTIONS annonce ainsi le PUT à qui peut l'utiliser
        return ConfigurationFinanceSerializer(*args, **kwargs)

    def get(self, request):
        reglages = ConfigurationFinance.objects.filter(company=request.user.company).first()
        return Response(ConfigurationFinanceSerializer(reglages).data if reglages else {"solde_initial": "0.00"})

    def put(self, request):
        reglages, _ = ConfigurationFinance.objects.get_or_create(company=request.user.company)
        serializer = ConfigurationFinanceSerializer(reglages, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


def _nombre(valeur):
    return "" if valeur is None else f"{valeur:.2f}".replace(".", ",")


class ExportView(_LectureFinance):
    """Reporting financier prêt à partager, en CSV (s'ouvre dans Excel) : `?type=rentabilite|depenses|factures|tresorerie`, avec
    `date_debut` et `date_fin`. Pour un PDF, le site imprime la même vue."""

    TYPES = ("rentabilite", "depenses", "factures", "tresorerie")

    def get(self, request):
        type_ = request.query_params.get("type")
        if type_ not in self.TYPES:
            raise ValidationError({"type": f"Types possibles : {', '.join(self.TYPES)}."})
        debut, fin = _periode(request)
        company = request.user.company
        if type_ == "rentabilite":
            donnees = analyses.rentabilite(company, debut, fin)
            entete = ["Ligne", "Gare de départ", "Recettes billets", "Recettes fret", "Recettes", "Dépenses", "Marge", "Taux de marge (%)"]
            lignes = [
                [l["nom"], l["gare"], _nombre(l["billets"]), _nombre(l["fret"]), _nombre(l["recettes"]), _nombre(l["depenses"]), _nombre(l["marge"]), l["taux_marge_pourcent"] if l["taux_marge_pourcent"] is not None else ""]
                for l in donnees["lignes"]
            ]
            t = donnees["total"]
            lignes.append(["Charges communes", "", "", "", "", _nombre(donnees["charges_communes"]), "", ""])
            lignes.append(["TOTAL", "", "", "", _nombre(t["recettes"]), _nombre(t["depenses"]), _nombre(t["marge"]), t["taux_marge_pourcent"] if t["taux_marge_pourcent"] is not None else ""])
        elif type_ == "depenses":
            entete = ["Date", "Catégorie", "Libellé", "Montant", "Ligne", "Véhicule", "Gare"]
            lignes = [
                [d.date.isoformat(), d.get_categorie_display(), d.libelle, _nombre(d.montant), d.ligne.nom if d.ligne else "", d.vehicule.immatriculation if d.vehicule else "", d.gare.nom if d.gare else ""]
                for d in Depense.objects.filter(company=company, date__gte=debut, date__lte=fin).select_related("ligne", "vehicule", "gare").order_by("date", "id")
            ]
        elif type_ == "factures":
            entete = ["Fournisseur", "Type", "Référence", "Libellé", "Montant", "Émission", "Échéance", "Statut", "Payée le"]
            lignes = [
                [f.fournisseur.nom, f.get_type_display(), f.reference, f.libelle, _nombre(f.montant), f.date_emission.isoformat(), f.echeance.isoformat(), f.get_statut_display(), f.payee_le.isoformat() if f.payee_le else ""]
                for f in Facture.objects.filter(company=company, echeance__gte=debut, echeance__lte=fin).select_related("fournisseur").order_by("echeance", "id")
            ]
        else:
            entete = ["Date", "Encaissements", "Décaissements", "Net"]
            serie = analyses.tresorerie(company, fin)["serie_30_jours"]
            lignes = [[s["date"].isoformat(), _nombre(s["encaissements"]), _nombre(s["decaissements"]), _nombre(s["encaissements"] - s["decaissements"])] for s in serie if debut <= s["date"] <= fin]

        reponse = HttpResponse(content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = f'attachment; filename="{type_}-{debut}-{fin}.csv"'
        reponse.write("﻿")  # signature UTF-8 : Excel affiche correctement les accents
        ecrivain = csv.writer(reponse, delimiter=";")
        ecrivain.writerow(entete)
        ecrivain.writerows(lignes)
        return reponse
