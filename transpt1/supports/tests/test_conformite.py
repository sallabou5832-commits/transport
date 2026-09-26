"""Tableau de conformité réglementaire partagé par le QHSE et le juridique (cahier des charges : QHSE « tableau de conformité
réglementaire » ; Responsable juridique « tableau de conformité réglementaire partagé avec le QHSE »)."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from maintenance.models import PlanEntretien
from personnel_roulant.models import BlocageSecurite, ChecklistDepart, EtatChecklist, FeuilleDeRoute
from reseau.models import Vehicule, VehiculeStatut
from supports.models import Assurance

URL = "/api/conformite/"


def jours(n):
    return timezone.localdate() + datetime.timedelta(days=n)


@pytest.fixture
def flotte(company_a):
    return {
        nom: Vehicule.objects.create(immatriculation=f"CI-CONF-{nom}", capacite=40, company=company_a)
        for nom in ("A", "B", "C", "D")
    }


def assurer(vehicule, echeance, police="POL-1"):
    return Assurance.objects.create(vehicule=vehicule, company=vehicule.company, compagnie_assurance="NSIA", numero_police=police, date_echeance=echeance)


def obligation(vehicule, libelle="Contrôle technique", *, restant_jours=100, **plus):
    return PlanEntretien.objects.create(
        vehicule=vehicule, company=vehicule.company, libelle=libelle, periodicite_jours=180, reglementaire=True,
        derniere_date=jours(restant_jours - 180), **plus,
    )


@pytest.fixture
def qhse(user_factory, company_a):
    return user_factory("qhse_conf", Role.QHSE, company=company_a)


def tableau(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get(URL)


def ligne(reponse, immatriculation):
    return next(v for v in reponse.data["vehicules"] if v["immatriculation"] == f"CI-CONF-{immatriculation}")


@pytest.mark.django_db
class TestConformiteDUnVehicule:
    def test_un_vehicule_assure_et_a_jour_est_conforme(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(200))
        obligation(flotte["A"], restant_jours=100)

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["conforme"] is True and vue["motifs"] == []
        assert vue["assurance"]["etat"] == "valide" and vue["assurance"]["police"] == "POL-1" and vue["assurance"]["jours_restants"] == 200
        assert [(o["libelle"], o["etat"]) for o in vue["obligations"]] == [("Contrôle technique", "a_jour")]

    @pytest.mark.parametrize(
        "echeance,etat,conforme", [(-1, "expiree", False), (0, "bientot", True), (30, "bientot", True), (31, "valide", True)]
    )
    def test_l_etat_de_l_assurance_suit_son_echeance(self, api_client, qhse, flotte, echeance, etat, conforme):
        assurer(flotte["A"], jours(echeance))

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["assurance"]["etat"] == etat and vue["conforme"] is conforme

    def test_une_assurance_expiree_est_un_motif_de_non_conformite(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(-12))

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["conforme"] is False and vue["motifs"] == ["Assurance expirée depuis 12 jour(s)"]

    def test_un_vehicule_sans_assurance_n_est_pas_conforme(self, api_client, qhse, flotte):
        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["assurance"]["etat"] == "absente" and vue["conforme"] is False and "Aucune assurance enregistrée" in vue["motifs"]

    def test_c_est_l_assurance_la_plus_recente_qui_compte(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(-200), "ANCIENNE")
        assurer(flotte["A"], jours(150), "RENOUVELEE")

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["assurance"]["etat"] == "valide" and vue["assurance"]["police"] == "RENOUVELEE"

    def test_une_obligation_reglementaire_en_retard_rend_le_vehicule_non_conforme(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(200))
        obligation(flotte["A"], "Visite technique", restant_jours=-9)

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["conforme"] is False and vue["motifs"] == ["Visite technique en retard"]
        assert vue["obligations"][0]["jours_restants"] == -9

    def test_une_obligation_bientot_due_ne_rend_pas_non_conforme(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(200))
        obligation(flotte["A"], restant_jours=10)

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["conforme"] is True and vue["obligations"][0]["etat"] == "bientot"

    def test_un_plan_d_entretien_ordinaire_n_est_pas_une_obligation(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(200))
        PlanEntretien.objects.create(
            vehicule=flotte["A"], company=flotte["A"].company, libelle="Vidange", periodicite_jours=30, derniere_date=jours(-100),
        )

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["obligations"] == [] and vue["conforme"] is True

    def test_un_plan_inactif_est_ignore(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(200))
        obligation(flotte["A"], restant_jours=-50, actif=False)

        assert ligne(tableau(api_client, qhse), "A")["obligations"] == []

    def test_un_blocage_de_securite_actif_rend_non_conforme(self, api_client, qhse, flotte, company_a):
        assurer(flotte["A"], jours(200))
        BlocageSecurite.objects.create(vehicule=flotte["A"], company=company_a, motif="Fissure", pose_par=qhse)

        vue = ligne(tableau(api_client, qhse), "A")

        assert vue["bloque"] is True and vue["conforme"] is False and "Véhicule bloqué pour raison de sécurité" in vue["motifs"]

    def test_un_blocage_leve_ne_compte_plus(self, api_client, qhse, flotte, company_a):
        assurer(flotte["A"], jours(200))
        BlocageSecurite.objects.create(
            vehicule=flotte["A"], company=company_a, motif="Fissure", pose_par=qhse, leve_le=timezone.now(), leve_par=qhse
        )

        assert ligne(tableau(api_client, qhse), "A")["bloque"] is False

    def test_un_vehicule_bloque_par_la_checklist_est_non_conforme(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(200))
        Vehicule.objects.filter(pk=flotte["A"].pk).update(statut=VehiculeStatut.BLOQUE_SECURITE)

        assert ligne(tableau(api_client, qhse), "A")["conforme"] is False

    def test_les_defauts_de_checklist_ouverts_sont_comptes_jusqu_a_l_arrivee_du_car(self, api_client, qhse, flotte, company_a, user_factory):
        assurer(flotte["A"], jours(200))
        chauffeur = user_factory("chauffeur_conf", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        depart = Depart.objects.create(
            ligne=_ligne(company_a), vehicule=flotte["A"], chauffeur=chauffeur, company=company_a,
            date_heure=timezone.now(), statut=DepartStatut.PLANIFIE,
        )
        feuille = FeuilleDeRoute.objects.create(depart=depart, chauffeur=chauffeur, company=company_a, heure_depart_prevue=depart.date_heure)
        ChecklistDepart.objects.create(feuille_de_route=feuille, company=company_a, item="Éclairage", etat=EtatChecklist.DEFAUT)
        ChecklistDepart.objects.create(feuille_de_route=feuille, company=company_a, item="Pneus", etat=EtatChecklist.OK)

        vue = ligne(tableau(api_client, qhse), "A")
        assert vue["defauts_ouverts"] == 1 and "1 défaut(s) de checklist ouvert(s)" in vue["motifs"]

        FeuilleDeRoute.objects.filter(pk=feuille.pk).update(heure_arrivee_reelle=timezone.now())
        assert ligne(tableau(api_client, qhse), "A")["defauts_ouverts"] == 0


def _ligne(company):
    from reseau.models import Gare, Ligne

    depart = Gare.objects.create(nom="G1", ville="V", company=company)
    arrivee = Gare.objects.create(nom="G2", ville="W", company=company)
    return Ligne.objects.create(nom="L", gare_depart=depart, gare_arrivee=arrivee, company=company)


@pytest.mark.django_db
class TestLeTableauDeLaFlotte:
    def test_le_resume_compte_ce_qui_va_et_ce_qui_ne_va_pas(self, api_client, qhse, flotte, company_a):
        assurer(flotte["A"], jours(200))
        obligation(flotte["A"], restant_jours=100)  # conforme
        assurer(flotte["B"], jours(-3))  # assurance expirée
        assurer(flotte["C"], jours(10))  # bientôt échue
        obligation(flotte["C"], restant_jours=-2)  # contrôle en retard
        # D : ni assurance, ni obligation

        resume = tableau(api_client, qhse).data["resume"]

        assert resume["vehicules"] == 4 and resume["conformes"] == 1 and resume["taux_conformite_pourcent"] == 25
        assert (resume["assurances_expirees"], resume["assurances_absentes"], resume["assurances_bientot_echues"]) == (1, 1, 1)
        assert resume["obligations_en_retard"] == 1 and resume["obligations_bientot_dues"] == 0
        assert resume["vehicules_sans_obligation_declaree"] == 2 and resume["vehicules_bloques"] == 0

    def test_les_non_conformes_passent_en_premier(self, api_client, qhse, flotte):
        assurer(flotte["A"], jours(200))
        obligation(flotte["A"])

        immatriculations = [v["immatriculation"] for v in tableau(api_client, qhse).data["vehicules"]]

        assert immatriculations[-1] == "CI-CONF-A" and immatriculations[0] == "CI-CONF-B"

    def test_sans_vehicule_le_taux_est_vide(self, api_client, qhse):
        resume = tableau(api_client, qhse).data["resume"]

        assert resume["vehicules"] == 0 and resume["taux_conformite_pourcent"] is None

    def test_le_tableau_ne_contient_que_les_vehicules_de_la_compagnie(self, api_client, qhse, flotte, company_b):
        Vehicule.objects.create(immatriculation="CI-CONF-ETRANGER", capacite=40, company=company_b)

        assert "CI-CONF-ETRANGER" not in [v["immatriculation"] for v in tableau(api_client, qhse).data["vehicules"]]


@pytest.mark.django_db
class TestQuiPeutLeVoir:
    @pytest.mark.parametrize(
        "role", ["qhse", "responsable_juridique", "directeur_technique", "directeur_exploitation", "pdg", "secretaire_general"]
    )
    def test_les_postes_concernes_le_lisent(self, api_client, user_factory, company_a, role):
        assert tableau(api_client, user_factory(f"{role}_conf_lit", Role(role), company=company_a)).status_code == 200

    @pytest.mark.parametrize("role", ["guichetier", "chef_gare", "chef_atelier", "mecanicien", "drh", "directeur_financier", "chauffeur_principal"])
    def test_les_autres_ne_le_lisent_pas(self, api_client, user_factory, company_a, role):
        assert tableau(api_client, user_factory(f"{role}_conf_non", Role(role), company=company_a)).status_code == 403

    def test_le_superadmin_sans_compagnie_n_y_a_pas_acces(self, api_client, superadmin_user):
        assert tableau(api_client, superadmin_user).status_code == 403

    def test_sans_authentification_rien(self, api_client):
        assert api_client.get(URL).status_code == 401


@pytest.mark.django_db
class TestDeclarerUneObligation:
    def test_le_technique_declare_un_plan_comme_obligation_reglementaire(self, api_client, user_factory, company_a, flotte):
        dt = user_factory("dt_conf", Role.DIRECTEUR_TECHNIQUE, company=company_a)
        api_client.force_authenticate(user=dt)

        reponse = api_client.post(
            "/api/plans-entretien/",
            {"vehicule": flotte["A"].id, "libelle": "Contrôle technique", "periodicite_jours": 180, "reglementaire": True},
            format="json",
        )

        assert reponse.status_code == 201 and reponse.data["reglementaire"] is True
        assert ligne(tableau(api_client, dt), "A")["obligations"][0]["libelle"] == "Contrôle technique"
