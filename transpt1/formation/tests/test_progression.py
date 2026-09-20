import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import Role
from formation.models import EtapeFormation, ParcoursFormation, ProgressionFormation, TypeAction
from formation.parcours_de_base import PARCOURS_DE_BASE, charger_parcours_de_base

MON_PARCOURS = "/api/formation/mon-parcours/"
DEMARRER = "/api/formation/mon-parcours/demarrer/"


def terminer_url(etape_id):
    return f"/api/formation/mon-parcours/etapes/{etape_id}/terminer/"


def ids_etapes(user):
    parcours = ParcoursFormation.objects.get(role=user.role)
    return list(parcours.etapes.order_by("ordre").values_list("id", flat=True))


@pytest.mark.django_db
class TestParcoursDeBase:
    def test_au_moins_trois_roles_de_3_a_5_etapes_simulees(self, parcours_de_base):
        roles = set(ParcoursFormation.objects.values_list("role", flat=True))
        assert {Role.GUICHETIER, Role.CHAUFFEUR_PRINCIPAL, Role.MAGASINIER} <= roles
        for parcours in ParcoursFormation.objects.all():
            assert parcours.role in Role.values
            assert 3 <= parcours.etapes.count() <= 5
            assert set(parcours.etapes.values_list("type_action", flat=True)) == {TypeAction.SIMULEE}
            ordres = list(parcours.etapes.order_by("ordre").values_list("ordre", flat=True))
            assert ordres == list(range(1, len(ordres) + 1))

    @pytest.mark.parametrize(
        "role, scenario",
        [
            (Role.GUICHETIER, "vente_ticket"),
            (Role.CHAUFFEUR_PRINCIPAL, "checklist_avant_depart"),
            (Role.MAGASINIER, "demande_piece"),
        ],
    )
    def test_reprend_les_missions_du_cahier_des_charges(self, parcours_de_base, role, scenario):
        scenarios = ParcoursFormation.objects.get(role=role).etapes.values_list("scenario", flat=True)
        assert scenario in scenarios

    def test_chargement_idempotent(self, parcours_de_base):
        crees, ignores = charger_parcours_de_base()

        assert crees == []
        assert len(ignores) == len(PARCOURS_DE_BASE)
        assert ParcoursFormation.objects.count() == len(PARCOURS_DE_BASE)
        assert EtapeFormation.objects.count() == sum(len(p["etapes"]) for p in PARCOURS_DE_BASE)

    def test_un_parcours_modifie_n_est_pas_ecrase_sans_force(self, parcours_de_base):
        ParcoursFormation.objects.filter(role=Role.GUICHETIER).update(titre="Titre personnalisé")

        charger_parcours_de_base()
        assert ParcoursFormation.objects.get(role=Role.GUICHETIER).titre == "Titre personnalisé"

        charger_parcours_de_base(force=True)
        assert ParcoursFormation.objects.get(role=Role.GUICHETIER).titre != "Titre personnalisé"

    def test_commande_seed_formation(self, db):
        call_command("seed_formation", verbosity=0)

        assert ParcoursFormation.objects.count() == len(PARCOURS_DE_BASE)


@pytest.mark.django_db
class TestConsultationDuParcours:
    def test_chaque_role_recoit_son_propre_parcours(
        self, api_client, parcours_de_base, guichetier_a, chauffeur_a, magasinier_a
    ):
        for user in (guichetier_a, chauffeur_a, magasinier_a):
            api_client.force_authenticate(user=user)
            response = api_client.get(MON_PARCOURS)

            assert response.status_code == 200
            assert response.data["role"] == user.role
            assert response.data["progression"] is None
            ordres = [etape["ordre"] for etape in response.data["etapes"]]
            assert ordres == sorted(ordres) and len(ordres) >= 3
            assert {etape["type_action"] for etape in response.data["etapes"]} == {"simulee"}
            assert {etape["statut"] for etape in response.data["etapes"]} == {"a_venir"}

    def test_role_sans_parcours(self, api_client, parcours_de_base, pdg_a):
        api_client.force_authenticate(user=pdg_a)

        assert api_client.get(MON_PARCOURS).status_code == 404
        assert api_client.post(DEMARRER).status_code == 404

    def test_authentification_requise(self, api_client, parcours_de_base):
        assert api_client.get(MON_PARCOURS).status_code == 401
        assert api_client.post(DEMARRER).status_code == 401
        assert api_client.post(terminer_url(1)).status_code == 401


@pytest.mark.django_db
class TestProgression:
    def test_demarrer_positionne_la_premiere_etape(self, api_client, parcours_de_base, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)
        premiere = ids_etapes(guichetier_a)[0]

        response = api_client.post(DEMARRER)

        assert response.status_code == 200
        progression = response.data["progression"]
        assert progression["etape_courante"] == premiere
        assert progression["termine"] is False
        assert progression["date_fin"] is None
        assert progression["etapes_terminees"] == 0
        assert response.data["etapes"][0]["statut"] == "en_cours"
        assert {e["statut"] for e in response.data["etapes"][1:]} == {"a_venir"}

    def test_demarrer_deux_fois_ne_reinitialise_rien(self, api_client, parcours_de_base, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)
        api_client.post(DEMARRER)
        etapes = ids_etapes(guichetier_a)
        api_client.post(terminer_url(etapes[0]))

        response = api_client.post(DEMARRER)

        assert response.data["progression"]["etape_courante"] == etapes[1]
        assert ProgressionFormation.objects.filter(user=guichetier_a).count() == 1

    def test_terminer_une_etape_avance_a_la_suivante(self, api_client, parcours_de_base, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)
        api_client.post(DEMARRER)
        etapes = ids_etapes(guichetier_a)

        response = api_client.post(terminer_url(etapes[0]))

        assert response.status_code == 200
        assert response.data["progression"]["etape_courante"] == etapes[1]
        assert response.data["progression"]["etapes_terminees"] == 1
        statuts = [e["statut"] for e in response.data["etapes"]]
        assert statuts[:2] == ["terminee", "en_cours"]
        assert set(statuts[2:]) == {"a_venir"}

    @pytest.mark.parametrize("fixture", ["guichetier_a", "chauffeur_a", "magasinier_a"])
    def test_terminer_toutes_les_etapes_termine_le_parcours(
        self, api_client, parcours_de_base, request, fixture
    ):
        user = request.getfixturevalue(fixture)
        api_client.force_authenticate(user=user)
        api_client.post(DEMARRER)
        etapes = ids_etapes(user)

        for etape_id in etapes:
            response = api_client.post(terminer_url(etape_id))
            assert response.status_code == 200

        progression = response.data["progression"]
        assert progression["termine"] is True
        assert progression["etape_courante"] is None
        assert progression["date_fin"] is not None
        assert progression["etapes_terminees"] == progression["etapes_total"] == len(etapes)
        assert {e["statut"] for e in response.data["etapes"]} == {"terminee"}
        assert api_client.get(MON_PARCOURS).data["progression"]["termine"] is True

    def test_terminer_sans_avoir_demarre(self, api_client, parcours_de_base, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)

        response = api_client.post(terminer_url(ids_etapes(guichetier_a)[0]))

        assert response.status_code == 400
        assert not ProgressionFormation.objects.exists()

    def test_on_ne_saute_pas_d_etape(self, api_client, parcours_de_base, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)
        api_client.post(DEMARRER)
        etapes = ids_etapes(guichetier_a)

        response = api_client.post(terminer_url(etapes[2]))

        assert response.status_code == 400
        assert ProgressionFormation.objects.get().etape_courante_id == etapes[0]

    def test_on_ne_rejoue_pas_une_etape_terminee(self, api_client, parcours_de_base, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)
        api_client.post(DEMARRER)
        etapes = ids_etapes(guichetier_a)
        api_client.post(terminer_url(etapes[0]))

        response = api_client.post(terminer_url(etapes[0]))

        assert response.status_code == 400
        assert ProgressionFormation.objects.get().etape_courante_id == etapes[1]

    def test_rien_a_terminer_une_fois_le_parcours_fini(self, api_client, parcours_de_base, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)
        api_client.post(DEMARRER)
        etapes = ids_etapes(guichetier_a)
        for etape_id in etapes:
            api_client.post(terminer_url(etape_id))
        date_fin = ProgressionFormation.objects.get().date_fin

        response = api_client.post(terminer_url(etapes[-1]))

        assert response.status_code == 400
        assert ProgressionFormation.objects.get().date_fin == date_fin

    def test_impossible_de_terminer_une_etape_du_parcours_d_un_autre_role(
        self, api_client, parcours_de_base, guichetier_a, chauffeur_a
    ):
        api_client.force_authenticate(user=guichetier_a)
        api_client.post(DEMARRER)
        etape_chauffeur = ids_etapes(chauffeur_a)[0]

        response = api_client.post(terminer_url(etape_chauffeur))

        assert response.status_code == 404
        assert ProgressionFormation.objects.get().etape_courante_id == ids_etapes(guichetier_a)[0]

    def test_les_progressions_sont_individuelles(
        self, api_client, parcours_de_base, guichetier_a, guichetier_b
    ):
        etapes = ids_etapes(guichetier_a)
        api_client.force_authenticate(user=guichetier_a)
        api_client.post(DEMARRER)
        api_client.post(terminer_url(etapes[0]))

        api_client.force_authenticate(user=guichetier_b)
        avant_demarrage = api_client.get(MON_PARCOURS)
        api_client.post(DEMARRER)

        assert avant_demarrage.data["progression"] is None
        assert ProgressionFormation.objects.get(user=guichetier_b).etape_courante_id == etapes[0]
        assert ProgressionFormation.objects.get(user=guichetier_a).etape_courante_id == etapes[1]

    def test_parcours_sans_etape_ne_peut_pas_demarrer(self, api_client, db, guichetier_a):
        ParcoursFormation.objects.create(role=Role.GUICHETIER, titre="Vide")
        api_client.force_authenticate(user=guichetier_a)

        assert api_client.post(DEMARRER).status_code == 400
        assert not ProgressionFormation.objects.exists()


@pytest.mark.django_db
class TestContraintes:
    def test_un_seul_parcours_par_role(self, db):
        ParcoursFormation.objects.create(role=Role.GUICHETIER, titre="A")

        with pytest.raises(IntegrityError), transaction.atomic():
            ParcoursFormation.objects.create(role=Role.GUICHETIER, titre="B")

    def test_ordre_unique_par_parcours(self, db):
        parcours = ParcoursFormation.objects.create(role=Role.GUICHETIER, titre="A")
        EtapeFormation.objects.create(parcours=parcours, ordre=1, titre="Un", instructions="x")

        with pytest.raises(IntegrityError), transaction.atomic():
            EtapeFormation.objects.create(parcours=parcours, ordre=1, titre="Bis", instructions="x")

    def test_etape_simulee_par_defaut(self, db):
        parcours = ParcoursFormation.objects.create(role=Role.GUICHETIER, titre="A")
        etape = EtapeFormation.objects.create(parcours=parcours, ordre=1, titre="Un", instructions="x")

        assert etape.type_action == TypeAction.SIMULEE
        assert etape.donnees_simulees == {}

    def test_une_progression_terminee_doit_avoir_une_date_de_fin(self, db, guichetier_a):
        parcours = ParcoursFormation.objects.create(role=Role.GUICHETIER, titre="A")

        with pytest.raises(IntegrityError), transaction.atomic():
            ProgressionFormation.objects.create(user=guichetier_a, parcours=parcours, termine=True)

    def test_une_progression_en_cours_ne_peut_pas_avoir_de_date_de_fin(self, db, guichetier_a):
        parcours = ParcoursFormation.objects.create(role=Role.GUICHETIER, titre="A")

        with pytest.raises(IntegrityError), transaction.atomic():
            ProgressionFormation.objects.create(
                user=guichetier_a, parcours=parcours, date_fin=timezone.now()
            )
