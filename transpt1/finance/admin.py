from django.contrib import admin

from finance.models import BudgetCarburant, ConfigurationFinance, Depense, Facture, Fournisseur


class _LectureSeule(admin.ModelAdmin):
    """Lecture seule : la comptabilité se tient par l'API (alertes, trace d'audit et cohérence factures / dépenses), jamais à la main."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Depense)
class DepenseAdmin(_LectureSeule):
    list_display = ["id", "date", "categorie", "libelle", "montant", "company"]
    list_filter = ["company", "categorie"]


@admin.register(BudgetCarburant)
class BudgetCarburantAdmin(_LectureSeule):
    list_display = ["id", "ligne", "mois", "montant", "company"]


@admin.register(Fournisseur)
class FournisseurAdmin(_LectureSeule):
    list_display = ["id", "nom", "categorie", "company"]


@admin.register(Facture)
class FactureAdmin(_LectureSeule):
    list_display = ["id", "fournisseur", "libelle", "montant", "echeance", "statut", "company"]
    list_filter = ["company", "statut"]


@admin.register(ConfigurationFinance)
class ConfigurationFinanceAdmin(_LectureSeule):
    list_display = ["company", "solde_initial"]
