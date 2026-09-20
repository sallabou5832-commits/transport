import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ReservationHorsLigne
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Vehicule, VehiculeStatut

ROLES_PLANIFICATION = ["chef_ligne", "chef_gare", "directeur_exploitation", "secretaire_general", "pdg"]


def _url(depart):
    return f"/api/departs/{depart.id}/remplacants-possibles/"


@pytest.fixture
def chef_ligne_a(user_factory, company_a):
    return user_factory("chef_ligne_reaffectation", Role.CHEF_LIGNE, company=company_a)


@pytest.fixture
def parc(db, company_a, user_factory):
    """Un véhicule assez grand, un trop petit, un en panne ; deux autres chauffeurs."""
    return {
        "grand": Vehicule.objects.create(immatriculation="CI-GRAND", capacite=60, company=company_a),
        "petit": Vehicule.objects.create(immatriculation="CI-PETIT", capacite=5, company=company_a),
        "en_panne": Vehicule.objects.create(
            immatriculation="CI-PANNE", capacite=60, statut=VehiculeStatut.EN_MAINTENANCE, company=company_a
        ),
        "chauffeur2": user_factory("chauffeur_remplacant", Role.CHAUFFEUR_RELAIS, company=company_a,
                                   first_name="Moussa", last_name="Diallo"),
        "chauffeur3": user_factory("chauffeur_remplacant2", Role.CHAUFFEUR_PRINCIPAL, company=company_a),
    }


@pytest.mark.django_db
class TestRemplacantsPossibles:
    def test_propose_les_vehicules_libres_assez_grands_et_les_chauffeurs_libres(
        self, api_client, chef_ligne_a, depart_a, parc
    ):
        depart_a.places_vendues = 10
        depart_a.save()
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.get(_url(depart_a))

        assert reponse.status_code == 200
        immats = [v["immatriculation"] for v in reponse.data["vehicules"]]
        assert "CI-GRAND" in immats
        assert "CI-PETIT" not in immats  # 5 places < 10 déjà vendues
        assert "CI-PANNE" not in immats  # pas disponible
        assert depart_a.vehicule.immatriculation not in immats  # ce n'est pas un remplaçant
        noms = {c["nom"] for c in reponse.data["chauffeurs"]}
        assert "Moussa Diallo" in noms and "chauffeur_remplacant2" in noms
        assert depart_a.chauffeur.username not in noms

    def test_les_places_reservees_hors_ligne_comptent_pour_la_capacite(
        self, api_client, chef_ligne_a, depart_a, parc, guichetier_a
    ):
        depart_a.places_vendues = 2
        depart_a.save()
        ReservationHorsLigne.objects.create(
            depart=depart_a, guichetier=guichetier_a, company=depart_a.company, places=4,
            expire_le=timezone.now() + datetime.timedelta(hours=1),
        )
        api_client.force_authenticate(user=chef_ligne_a)

        immats = [v["immatriculation"] for v in api_client.get(_url(depart_a)).data["vehicules"]]

        assert "CI-PETIT" not in immats  # 5 places < 2 vendues + 4 réservées

    def test_exclut_ceux_qui_ont_un_autre_depart_proche(
        self, api_client, chef_ligne_a, depart_a, parc, ligne_a, company_a
    ):
        Depart.objects.create(
            ligne=ligne_a, vehicule=parc["grand"], chauffeur=parc["chauffeur2"], company=company_a,
            date_heure=depart_a.date_heure + datetime.timedelta(hours=3), statut=DepartStatut.PLANIFIE,
        )
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.get(_url(depart_a))

        assert "CI-GRAND" not in [v["immatriculation"] for v in reponse.data["vehicules"]]
        assert "Moussa Diallo" not in [c["nom"] for c in reponse.data["chauffeurs"]]

    def test_un_depart_lointain_ou_termine_ne_bloque_pas(
        self, api_client, chef_ligne_a, depart_a, parc, ligne_a, company_a
    ):
        Depart.objects.create(  # 9 h plus tard : hors de la fenêtre de 8 h
            ligne=ligne_a, vehicule=parc["grand"], chauffeur=parc["chauffeur2"], company=company_a,
            date_heure=depart_a.date_heure + datetime.timedelta(hours=9), statut=DepartStatut.PLANIFIE,
        )
        Depart.objects.create(  # proche mais terminé
            ligne=ligne_a, vehicule=parc["grand"], chauffeur=parc["chauffeur3"], company=company_a,
            date_heure=depart_a.date_heure + datetime.timedelta(hours=1), statut=DepartStatut.TERMINE,
        )
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.get(_url(depart_a))

        assert "CI-GRAND" in [v["immatriculation"] for v in reponse.data["vehicules"]]
        noms = [c["nom"] for c in reponse.data["chauffeurs"]]
        assert "Moussa Diallo" in noms and "chauffeur_remplacant2" in noms

    def test_n_expose_rien_d_une_autre_compagnie(
        self, api_client, chef_ligne_a, depart_a, parc, user_factory, company_b
    ):
        Vehicule.objects.create(immatriculation="CI-ETRANGER", capacite=99, company=company_b)
        user_factory("chauffeur_etranger", Role.CHAUFFEUR_PRINCIPAL, company=company_b)
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.get(_url(depart_a))

        assert "CI-ETRANGER" not in [v["immatriculation"] for v in reponse.data["vehicules"]]
        assert "chauffeur_etranger" not in [c["nom"] for c in reponse.data["chauffeurs"]]

    def test_un_depart_d_une_autre_compagnie_est_introuvable(
        self, api_client, depart_a, user_factory, company_b
    ):
        chef_b = user_factory("chef_ligne_b", Role.CHEF_LIGNE, company=company_b)
        api_client.force_authenticate(user=chef_b)

        assert api_client.get(_url(depart_a)).status_code == 404

    @pytest.mark.parametrize("role", ROLES_PLANIFICATION)
    def test_roles_de_planification_autorises(self, api_client, user_factory, company_a, depart_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_remp", Role(role), company=company_a))

        assert api_client.get(_url(depart_a)).status_code == 200

    @pytest.mark.parametrize(
        "role",
        [r.value for r in Role if r.value not in ROLES_PLANIFICATION and r != Role.SUPERADMIN],
    )
    def test_les_autres_roles_sont_refuses(self, api_client, user_factory, company_a, depart_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_remp", Role(role), company=company_a))

        assert api_client.get(_url(depart_a)).status_code == 403

    def test_non_authentifie_refuse(self, api_client, depart_a):
        assert api_client.get(_url(depart_a)).status_code == 401


@pytest.mark.django_db
class TestGardeFousDeLaReaffectation:
    def test_changer_de_vehicule_sur_un_depart_planifie(self, api_client, chef_ligne_a, depart_a, parc):
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.patch(f"/api/departs/{depart_a.id}/", {"vehicule": parc["grand"].id})

        assert reponse.status_code == 200
        depart_a.refresh_from_db()
        assert depart_a.vehicule_id == parc["grand"].id

    def test_changer_de_chauffeur_sur_un_depart_planifie(self, api_client, chef_ligne_a, depart_a, parc):
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.patch(f"/api/departs/{depart_a.id}/", {"chauffeur": parc["chauffeur2"].id})

        assert reponse.status_code == 200
        assert reponse.data["chauffeur_nom"] == "Moussa Diallo"

    def test_un_vehicule_trop_petit_est_refuse(self, api_client, chef_ligne_a, depart_a, parc):
        depart_a.places_vendues = 10
        depart_a.save()
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.patch(f"/api/departs/{depart_a.id}/", {"vehicule": parc["petit"].id})

        assert reponse.status_code == 400
        assert "trop petit" in str(reponse.data["vehicule"])
        depart_a.refresh_from_db()
        assert depart_a.vehicule_id != parc["petit"].id

    @pytest.mark.parametrize("statut", [DepartStatut.EN_COURS, DepartStatut.TERMINE])
    def test_un_depart_parti_ne_change_plus_de_vehicule_ni_de_chauffeur(
        self, api_client, chef_ligne_a, depart_a, parc, statut
    ):
        depart_a.statut = statut
        depart_a.save()
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.patch(f"/api/departs/{depart_a.id}/", {"vehicule": parc["grand"].id}).status_code == 400
        assert api_client.patch(f"/api/departs/{depart_a.id}/", {"chauffeur": parc["chauffeur2"].id}).status_code == 400

    def test_un_depart_dont_la_feuille_a_demarre_ne_change_plus_meme_s_il_est_encore_planifie(
        self, api_client, chef_ligne_a, depart_a, parc
    ):
        # Démarrer la feuille de route ne change pas Depart.statut : c'est la feuille qui dit
        # si le car est parti.
        FeuilleDeRoute.objects.create(
            depart=depart_a, chauffeur=depart_a.chauffeur, company=depart_a.company,
            heure_depart_prevue=depart_a.date_heure, heure_depart_reelle=timezone.now(),
        )
        assert depart_a.statut == DepartStatut.PLANIFIE
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.patch(f"/api/departs/{depart_a.id}/", {"vehicule": parc["grand"].id}).status_code == 400
        assert api_client.patch(f"/api/departs/{depart_a.id}/", {"chauffeur": parc["chauffeur2"].id}).status_code == 400

    def test_le_changement_de_chauffeur_suit_sur_la_feuille_de_route_pas_demarree(
        self, api_client, chef_ligne_a, depart_a, parc
    ):
        feuille = FeuilleDeRoute.objects.create(
            depart=depart_a, chauffeur=depart_a.chauffeur, company=depart_a.company,
            heure_depart_prevue=depart_a.date_heure,
        )
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.patch(f"/api/departs/{depart_a.id}/", {"chauffeur": parc["chauffeur2"].id})

        assert reponse.status_code == 200
        feuille.refresh_from_db()
        assert feuille.chauffeur_id == parc["chauffeur2"].id  # le nouveau chauffeur la voit, l'ancien plus

    def test_une_feuille_deja_transferee_a_un_relais_n_est_pas_ecrasee(
        self, api_client, chef_ligne_a, depart_a, parc
    ):
        feuille = FeuilleDeRoute.objects.create(
            depart=depart_a, chauffeur=parc["chauffeur3"], company=depart_a.company,
            heure_depart_prevue=depart_a.date_heure,
        )
        api_client.force_authenticate(user=chef_ligne_a)

        api_client.patch(f"/api/departs/{depart_a.id}/", {"chauffeur": parc["chauffeur2"].id})

        feuille.refresh_from_db()
        assert feuille.chauffeur_id == parc["chauffeur3"].id

    def test_changer_seulement_de_vehicule_ne_touche_pas_a_la_feuille(
        self, api_client, chef_ligne_a, depart_a, parc
    ):
        feuille = FeuilleDeRoute.objects.create(
            depart=depart_a, chauffeur=depart_a.chauffeur, company=depart_a.company,
            heure_depart_prevue=depart_a.date_heure,
        )
        chauffeur_avant = depart_a.chauffeur_id
        api_client.force_authenticate(user=chef_ligne_a)

        api_client.patch(f"/api/departs/{depart_a.id}/", {"vehicule": parc["grand"].id})

        feuille.refresh_from_db()
        assert feuille.chauffeur_id == chauffeur_avant

    def test_un_depart_en_cours_peut_encore_changer_de_statut(self, api_client, chef_ligne_a, depart_a):
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.patch(f"/api/departs/{depart_a.id}/", {"statut": "en_cours"})

        assert reponse.status_code == 200

    def test_renvoyer_le_meme_vehicule_n_est_pas_un_changement(self, api_client, chef_ligne_a, depart_a):
        depart_a.statut = DepartStatut.EN_COURS
        depart_a.save()
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.patch(f"/api/departs/{depart_a.id}/", {"vehicule": depart_a.vehicule_id})

        assert reponse.status_code == 200

    def test_le_nom_du_chauffeur_est_expose_sur_les_departs(self, api_client, chef_ligne_a, depart_a):
        depart_a.chauffeur.first_name, depart_a.chauffeur.last_name = "Awa", "Kone"
        depart_a.chauffeur.save()
        api_client.force_authenticate(user=chef_ligne_a)

        departs = api_client.get("/api/departs/").data

        assert departs[0]["chauffeur_nom"] == "Awa Kone"
