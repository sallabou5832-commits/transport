from django.urls import path
from rest_framework.routers import DefaultRouter

from finance.views import (
    BudgetCarburantViewSet,
    ConfigurationFinanceView,
    DepenseViewSet,
    ExportView,
    FactureViewSet,
    FournisseurViewSet,
    RentabiliteView,
    SuiviBudgetCarburantView,
    TresorerieView,
)

router = DefaultRouter()
router.register("depenses", DepenseViewSet, basename="depense")
router.register("budgets-carburant", BudgetCarburantViewSet, basename="budget-carburant")
router.register("fournisseurs", FournisseurViewSet, basename="fournisseur")
router.register("factures", FactureViewSet, basename="facture")

urlpatterns = [
    path("finance/rentabilite/", RentabiliteView.as_view(), name="finance-rentabilite"),
    path("finance/budget-carburant/", SuiviBudgetCarburantView.as_view(), name="finance-budget-carburant"),
    path("finance/tresorerie/", TresorerieView.as_view(), name="finance-tresorerie"),
    path("finance/configuration/", ConfigurationFinanceView.as_view(), name="finance-configuration"),
    path("finance/export/", ExportView.as_view(), name="finance-export"),
    *router.urls,
]
