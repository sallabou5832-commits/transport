from django.urls import path
from rest_framework.routers import DefaultRouter

from rh.views import (
    CandidatureViewSet,
    ContratAgentViewSet,
    DemandeCongeViewSet,
    DoleanceViewSet,
    EvaluationAgentViewSet,
    FichesPosteView,
    FormationSuivieViewSet,
    LitigesSociauxView,
    MesureDisciplinaireViewSet,
    ObligationFormationViewSet,
    OffreRecrutementViewSet,
    ReinitialiserFicheView,
    SuiviFormationsView,
    SyntheseRhView,
)

router = DefaultRouter()
router.register("obligations-formation", ObligationFormationViewSet, basename="obligation-formation")
router.register("formations-suivies", FormationSuivieViewSet, basename="formation-suivie")
router.register("contrats", ContratAgentViewSet, basename="contrat")
router.register("evaluations", EvaluationAgentViewSet, basename="evaluation")
router.register("mesures-disciplinaires", MesureDisciplinaireViewSet, basename="mesure-disciplinaire")
router.register("conges", DemandeCongeViewSet, basename="conge")
router.register("offres-recrutement", OffreRecrutementViewSet, basename="offre-recrutement")
router.register("candidatures", CandidatureViewSet, basename="candidature")
router.register("doleances", DoleanceViewSet, basename="doleance")

urlpatterns = [
    path("formations-obligatoires/suivi/", SuiviFormationsView.as_view(), name="formations-suivi"),
    path("fiches-poste/", FichesPosteView.as_view(), name="fiches-poste"),
    path("fiches-poste/reinitialiser/", ReinitialiserFicheView.as_view(), name="fiches-poste-reinitialiser"),
    path("litiges-sociaux/", LitigesSociauxView.as_view(), name="litiges-sociaux"),
    path("rh/synthese/", SyntheseRhView.as_view(), name="rh-synthese"),
    *router.urls,
]
