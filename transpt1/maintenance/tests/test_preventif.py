"""Maintenance préventive (cahier des charges : Directeur technique — « planning de maintenance préventive automatisé avec alerte
avant échéance » ; Mécanicien — « ordre de réparation … déclenché par une alerte de maintenance préventive »)."""

import datetime

import pytest
from django.utils import timezone

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from core.models import Role
from maintenance import preventif
from maintenance.models import OrdreReparation, PlanEntretien, StatutOrdreReparation, UrgenceReparation
from reseau.models import Vehicule

PLANS = "/api/plans-entretien/"


@pytest.fixture(autouse=True)
def seuils(settings):
    settings.ENTRETIEN_PREAVIS_JOURS = 15
    settings.ENTRETIEN_PREAVIS_KM = 1000


def jours(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def declarer(vehicule, *, libelle="Vidange", periodicite_jours=180, periodicite_km=10000, restant_jours=80, restant_km=5000, **plus):
    """Un plan dont l'échéance tombe dans `restant_jours` jours / `restant_km` kilomètres (négatif : dépassée)."""
    vehicule.kilometrage = 50000
    vehicule.save(update_fields=["kilometrage"])
    return PlanEntretien.objects.create(
        vehicule=vehicule, company=vehicule.company, libelle=libelle, periodicite_jours=periodicite_jours, periodicite_km=periodicite_km,
        derniere_date=jours(restant_jours - periodicite_jours) if periodicite_jours else None,
        dernier_km=50000 + restant_km - periodicite_km if periodicite_km else None, **plus,
    )


@pytest.mark.django_db
class TestEcheance:
    @pytest.mark.parametrize(
        "restant_jours,restant_km,etat",
        [
            (80, 5000, "a_jour"),
            (15, 5000, "bientot"),  # à 15 jours pile : dans le préavis
            (16, 5000, "a_jour"),
            (80, 1000, "bientot"),
            (80, 1001, "a_jour"),
            (0, 5000, "bientot"),  # le jour même n'est pas encore en retard
            (-1, 5000, "en_retard"),
            (80, -1, "en_retard"),
            (-5, 200, "en_retard"),
        ],
    )
    def test_l_etat_suit_le_premier_seuil_atteint(self, vehicule_a, restant_jours, restant_km, etat):
        plan = declarer(vehicule_a, restant_jours=restant_jours, restant_km=restant_km)

        resultat = preventif.echeance(plan)

        assert resultat["etat"] == etat
        assert resultat["jours_restants"] == restant_jours and resultat["km_restants"] == restant_km

    def test_un_plan_en_jours_seulement_ignore_le_kilometrage(self, vehicule_a):
        plan = declarer(vehicule_a, periodicite_km=None, restant_jours=40)

        resultat = preventif.echeance(plan)

        assert resultat["etat"] == "a_jour" and resultat["km_restants"] is None and resultat["prochain_km"] is None

    def test_un_plan_en_kilometres_seulement_ignore_les_jours(self, vehicule_a):
        plan = declarer(vehicule_a, periodicite_jours=None, restant_km=300)

        resultat = preventif.echeance(plan)

        assert resultat["etat"] == "bientot" and resultat["jours_restants"] is None and resultat["prochaine_date"] is None

    def test_les_prochaines_echeances_sont_calculees_depuis_le_dernier_entretien(self, vehicule_a):
        plan = declarer(vehicule_a, restant_jours=80, restant_km=5000)

        resultat = preventif.echeance(plan)

        assert resultat["prochaine_date"] == jours(80) and resultat["prochain_km"] == 55000


@pytest.mark.django_db
class TestGererLesPlans:
    def creer(self, api_client, utilisateur, vehicule, **corps):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(PLANS, {"vehicule": vehicule.id, "libelle": "Vidange", "periodicite_km": 10000, **corps}, format="json")

    @pytest.mark.parametrize("role", ["directeur_technique_a", "chef_atelier_a"])
    def test_le_technique_declare_un_plan(self, api_client, vehicule_a, request, role):
        reponse = self.creer(api_client, request.getfixturevalue(role), vehicule_a)

        assert reponse.status_code == 201
        assert reponse.data["vehicule_immatriculation"] == "CI-3000-AA" and reponse.data["actif"] is True
        assert PlanEntretien.objects.get().company == vehicule_a.company

    def test_sans_precision_le_plan_part_d_aujourd_hui_au_kilometrage_actuel(self, api_client, vehicule_a, directeur_technique_a):
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=42000)

        reponse = self.creer(api_client, directeur_technique_a, vehicule_a)

        assert reponse.data["derniere_date"] == jours(0).isoformat() and reponse.data["dernier_km"] == 42000
        assert reponse.data["echeance"]["prochain_km"] == 52000 and reponse.data["echeance"]["etat"] == "a_jour"

    def test_une_derniere_date_et_un_dernier_km_precises_sont_respectes(self, api_client, vehicule_a, directeur_technique_a):
        reponse = self.creer(api_client, directeur_technique_a, vehicule_a, derniere_date=jours(-30).isoformat(), dernier_km=1000)

        assert reponse.data["derniere_date"] == jours(-30).isoformat() and reponse.data["dernier_km"] == 1000

    def test_une_periodicite_est_obligatoire(self, api_client, vehicule_a, directeur_technique_a):
        api_client.force_authenticate(user=directeur_technique_a)

        reponse = api_client.post(PLANS, {"vehicule": vehicule_a.id, "libelle": "Contrôle technique"}, format="json")

        assert reponse.status_code == 400 and "périodicité" in str(reponse.data)

    @pytest.mark.parametrize("corps", [{"periodicite_km": 0}, {"periodicite_km": -5}, {"duree_estimee_heures": 0}, {"libelle": ""}])
    def test_les_valeurs_invalides_sont_refusees(self, api_client, vehicule_a, directeur_technique_a, corps):
        assert self.creer(api_client, directeur_technique_a, vehicule_a, **corps).status_code == 400

    def test_le_vehicule_d_une_autre_compagnie_est_refuse(self, api_client, directeur_technique_a, company_b):
        etranger = Vehicule.objects.create(immatriculation="CI-B-PLAN", capacite=40, company=company_b)

        assert self.creer(api_client, directeur_technique_a, etranger).status_code == 400

    def test_le_plan_se_modifie_et_se_retire(self, api_client, vehicule_a, chef_atelier_a):
        plan = declarer(vehicule_a)
        api_client.force_authenticate(user=chef_atelier_a)

        assert api_client.patch(f"{PLANS}{plan.id}/", {"periodicite_km": 8000}, format="json").status_code == 200
        plan.refresh_from_db()
        assert plan.periodicite_km == 8000
        assert api_client.delete(f"{PLANS}{plan.id}/").status_code == 204

    def test_on_ne_retire_pas_la_derniere_periodicite(self, api_client, vehicule_a, chef_atelier_a):
        plan = declarer(vehicule_a, periodicite_jours=None)
        api_client.force_authenticate(user=chef_atelier_a)

        reponse = api_client.patch(f"{PLANS}{plan.id}/", {"periodicite_km": None}, format="json")

        assert reponse.status_code == 400

    @pytest.mark.parametrize("role", ["mecanicien_a", "magasinier_a"])
    def test_les_autres_postes_lisent_mais_n_ecrivent_pas(self, api_client, vehicule_a, request, role):
        plan = declarer(vehicule_a)
        api_client.force_authenticate(user=request.getfixturevalue(role))

        assert api_client.get(PLANS).status_code == 200
        assert api_client.get(f"{PLANS}echeances/").status_code == 200
        assert api_client.post(PLANS, {"vehicule": vehicule_a.id, "libelle": "X", "periodicite_km": 1}, format="json").status_code == 403
        assert api_client.patch(f"{PLANS}{plan.id}/", {"libelle": "Y"}, format="json").status_code == 403
        assert api_client.delete(f"{PLANS}{plan.id}/").status_code == 403
        assert api_client.post(f"{PLANS}{plan.id}/realise/", {}, format="json").status_code == 403

    def test_la_liste_ne_montre_que_les_plans_de_la_compagnie_et_se_filtre_par_vehicule(
        self, api_client, vehicule_a, directeur_technique_a, company_b
    ):
        autre = Vehicule.objects.create(immatriculation="CI-3999-AA", capacite=30, company=vehicule_a.company)
        declarer(vehicule_a, libelle="Vidange")
        declarer(autre, libelle="Freins")
        etranger = Vehicule.objects.create(immatriculation="CI-B-2", capacite=40, company=company_b)
        declarer(etranger, libelle="Étranger")
        api_client.force_authenticate(user=directeur_technique_a)

        assert {p["libelle"] for p in api_client.get(PLANS).data} == {"Vidange", "Freins"}
        assert [p["libelle"] for p in api_client.get(f"{PLANS}?vehicule={autre.id}").data] == ["Freins"]

    def test_les_echeances_mettent_les_retards_en_tete(self, api_client, vehicule_a, directeur_technique_a):
        declarer(vehicule_a, libelle="À jour", restant_jours=100)
        declarer(vehicule_a, libelle="Bientôt", restant_jours=10)
        declarer(vehicule_a, libelle="En retard", restant_jours=-3)
        api_client.force_authenticate(user=directeur_technique_a)

        reponse = api_client.get(f"{PLANS}echeances/")

        assert [p["libelle"] for p in reponse.data] == ["En retard", "Bientôt", "À jour"]

    def test_un_plan_inactif_n_apparait_pas_dans_les_echeances(self, api_client, vehicule_a, directeur_technique_a):
        declarer(vehicule_a, restant_jours=-3, actif=False)
        api_client.force_authenticate(user=directeur_technique_a)

        assert api_client.get(f"{PLANS}echeances/").data == []


@pytest.mark.django_db
class TestEntretienFaitHorsOrdre:
    def realise(self, api_client, utilisateur, plan, **corps):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(f"{PLANS}{plan.id}/realise/", corps, format="json")

    def test_le_plan_repart_d_aujourd_hui_au_kilometrage_actuel(self, api_client, vehicule_a, chef_atelier_a):
        plan = declarer(vehicule_a, restant_jours=-3, restant_km=-200)
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=61000)

        reponse = self.realise(api_client, chef_atelier_a, plan)

        assert reponse.status_code == 200 and reponse.data["echeance"]["etat"] == "a_jour"
        plan.refresh_from_db()
        assert plan.derniere_date == jours(0) and plan.dernier_km == 61000

    def test_la_date_et_le_kilometrage_reels_peuvent_etre_donnes(self, api_client, vehicule_a, chef_atelier_a):
        plan = declarer(vehicule_a)

        self.realise(api_client, chef_atelier_a, plan, date=jours(-4).isoformat(), km=49000)

        plan.refresh_from_db()
        assert plan.derniere_date == jours(-4) and plan.dernier_km == 49000

    @pytest.mark.parametrize("corps", [{"date": "demain"}, {"date": (timezone.localdate() + datetime.timedelta(days=2)).isoformat()}, {"km": "beaucoup"}])
    def test_une_date_future_ou_un_kilometrage_invalide_est_refuse(self, api_client, vehicule_a, chef_atelier_a, corps):
        plan = declarer(vehicule_a)

        assert self.realise(api_client, chef_atelier_a, plan, **corps).status_code == 400


@pytest.mark.django_db
class TestDeclenchementAutomatique:
    def alertes(self, type_):
        return list(Alerte.objects.filter(type=type_))

    def test_un_entretien_qui_approche_previent_l_atelier_et_ouvre_l_ordre(self, vehicule_a, mecanicien_a, company_a):
        plan = declarer(vehicule_a, libelle="Vidange", restant_jours=10, duree_estimee_heures=5)

        generer(company_a)

        alerte = self.alertes(TypeAlerte.ENTRETIEN)[0]
        assert alerte.titre == "Entretien à prévoir : Vidange — CI-3000-AA"
        assert set(alerte.roles_destinataires) == {Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER} and "10 jour(s)" in alerte.message
        ordre = OrdreReparation.objects.get()
        assert ordre.plan_entretien == plan and ordre.description == "Entretien préventif : Vidange"
        assert ordre.mecanicien == mecanicien_a and ordre.urgence == UrgenceReparation.NORMALE
        assert ordre.delai_estime_heures == 5 and ordre.statut == StatutOrdreReparation.OUVERT

    def test_le_mecanicien_est_prevenu_de_l_ordre_ouvert_pour_lui(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=10)

        generer(company_a)

        alerte = self.alertes(TypeAlerte.ORDRE_REPARATION)[0]
        assert list(alerte.destinataires.all()) == [mecanicien_a] and alerte.roles_destinataires == [Role.CHEF_ATELIER]
        assert "Entretien préventif" in alerte.titre

    def test_l_ordre_va_au_mecanicien_le_moins_charge(self, vehicule_a, mecanicien_a, mecanicien_a2, company_a):
        for _ in range(2):
            OrdreReparation.objects.create(vehicule=vehicule_a, company=company_a, description="Déjà là", mecanicien=mecanicien_a)
        declarer(vehicule_a, restant_jours=10)

        generer(company_a)

        assert OrdreReparation.objects.get(plan_entretien__isnull=False).mecanicien == mecanicien_a2

    def test_relancer_ne_previent_ni_ne_duplique(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=10)
        generer(company_a)

        deuxieme = generer(company_a)

        assert deuxieme == []
        assert Alerte.objects.filter(type=TypeAlerte.ENTRETIEN).count() == 1 and OrdreReparation.objects.count() == 1

    def test_l_echeance_depassee_previent_de_nouveau_sans_ouvrir_un_second_ordre(self, vehicule_a, mecanicien_a, company_a):
        plan = declarer(vehicule_a, restant_jours=10)
        generer(company_a)
        PlanEntretien.objects.filter(pk=plan.pk).update(derniere_date=jours(-200))

        generer(company_a)

        alertes = self.alertes(TypeAlerte.ENTRETIEN)
        assert len(alertes) == 2 and {a.gravite for a in alertes} == {"attention", "critique"}
        assert any(a.titre.startswith("Entretien en retard") for a in alertes)
        assert OrdreReparation.objects.count() == 1, "un ordre est déjà ouvert pour ce plan"

    def test_un_entretien_deja_en_retard_ouvre_un_ordre_d_urgence_haute(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=-4)

        generer(company_a)

        assert OrdreReparation.objects.get().urgence == UrgenceReparation.HAUTE

    def test_un_entretien_a_jour_ne_declenche_rien(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=100)

        assert generer(company_a) == []
        assert not OrdreReparation.objects.exists()

    def test_un_plan_sans_declenchement_automatique_n_ouvre_que_l_alerte(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=10, declenche_ordre=False)

        generer(company_a)

        assert self.alertes(TypeAlerte.ENTRETIEN) and not OrdreReparation.objects.exists()

    def test_sans_intervenant_l_alerte_part_quand_meme(self, vehicule_a, company_a):
        declarer(vehicule_a, restant_jours=10)

        generer(company_a)

        assert self.alertes(TypeAlerte.ENTRETIEN) and not OrdreReparation.objects.exists()

    def test_un_plan_inactif_est_ignore(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=-4, actif=False)

        assert generer(company_a) == []

    def test_le_kilometrage_declenche_comme_les_jours(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=100, restant_km=500)

        generer(company_a)

        assert "500 km" in self.alertes(TypeAlerte.ENTRETIEN)[0].message and OrdreReparation.objects.count() == 1

    def test_les_plans_d_une_autre_compagnie_ne_declenchent_rien_ici(self, vehicule_a, mecanicien_a, company_a, company_b):
        etranger = Vehicule.objects.create(immatriculation="CI-B-3", capacite=40, company=company_b)
        declarer(etranger, restant_jours=-4)

        assert generer(company_a) == []


@pytest.mark.django_db
class TestLaClotureRenouvelleLePlan:
    def test_l_ordre_termine_remet_le_plan_a_zero(self, vehicule_a, mecanicien_a, company_a):
        plan = declarer(vehicule_a, restant_jours=-4, restant_km=-100)
        generer(company_a)
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=60500)
        ordre = OrdreReparation.objects.get()

        ordre = OrdreReparation.objects.get(pk=ordre.pk)
        ordre.statut = StatutOrdreReparation.TERMINE
        ordre.save()

        plan.refresh_from_db()
        assert plan.derniere_date == jours(0)
        assert plan.dernier_km == 60500
        assert preventif.echeance(plan)["etat"] == "a_jour"

    def test_apres_la_cloture_plus_aucune_alerte_jusqu_a_la_prochaine_echeance(self, vehicule_a, mecanicien_a, company_a):
        declarer(vehicule_a, restant_jours=-4)
        generer(company_a)
        ordre = OrdreReparation.objects.get()
        ordre.statut = StatutOrdreReparation.TERMINE
        ordre.save()

        assert generer(company_a) == []
        assert OrdreReparation.objects.count() == 1

    def test_l_echeance_suivante_relance_un_cycle_complet(self, vehicule_a, mecanicien_a, company_a):
        plan = declarer(vehicule_a, restant_jours=10)
        generer(company_a)
        ordre = OrdreReparation.objects.get()
        ordre.statut = StatutOrdreReparation.TERMINE
        ordre.save()
        # Six mois plus tard, le plan est de nouveau à échéance : nouvelle alerte, nouvel ordre.
        PlanEntretien.objects.filter(pk=plan.pk).update(derniere_date=jours(-175))

        generer(company_a)

        assert Alerte.objects.filter(type=TypeAlerte.ENTRETIEN).count() == 2 and OrdreReparation.objects.count() == 2

    def test_un_ordre_ordinaire_ne_touche_a_aucun_plan(self, vehicule_a, mecanicien_a, company_a):
        plan = declarer(vehicule_a, restant_jours=10)
        avant = (plan.derniere_date, plan.dernier_km)
        ordre = OrdreReparation.objects.create(vehicule=vehicule_a, company=company_a, description="Panne", mecanicien=mecanicien_a)

        ordre.statut = StatutOrdreReparation.TERMINE
        ordre.save()

        plan.refresh_from_db()
        assert (plan.derniere_date, plan.dernier_km) == avant
