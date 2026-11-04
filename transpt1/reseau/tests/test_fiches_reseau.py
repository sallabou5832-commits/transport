"""Les fiches du réseau tenues sans l'administration Django : coordonnées et horaires des gares, quais, distance et durée des
lignes, fiche complète des véhicules. Tout est facultatif : un objet existant garde ses valeurs."""

import datetime

import pytest
from django.utils import timezone

from audit.models import JournalAudit
from core.models import Role
from reseau.models import Gare, Quai, Vehicule


@pytest.fixture
def guichetier_a(user_factory, company_a):
    return user_factory("guichetier_reseau_a", Role.GUICHETIER, company=company_a)


@pytest.fixture
def quai_a(db, company_a, gare_a):
    return Quai.objects.create(gare=gare_a, company=company_a, nom="Quai 1")


@pytest.fixture
def quai_a2(db, company_a, gare_a2):
    return Quai.objects.create(gare=gare_a2, company=company_a, nom="Quai 1")


@pytest.fixture
def quai_b(db, company_b, gare_b):
    return Quai.objects.create(gare=gare_b, company=company_b, nom="Quai 1")


@pytest.mark.django_db
class TestFicheGare:
    def test_coordonnees_et_horaires(self, api_client, company_a_manager, gare_a):
        api_client.force_authenticate(user=company_a_manager)

        reponse = api_client.patch(
            f"/api/gares/{gare_a.id}/",
            {"adresse": "Adjamé, face au marché", "telephone": "+225 27 20 00 00 00", "heure_ouverture": "05:30", "heure_fermeture": "22:00"},
            format="json",
        )

        assert reponse.status_code == 200, reponse.data
        assert reponse.data["heure_ouverture"] == "05:30:00"
        gare_a.refresh_from_db()
        assert gare_a.heure_fermeture == datetime.time(22, 0)
        assert gare_a.telephone == "+225 27 20 00 00 00"

    def test_une_gare_sans_fiche_garde_ses_valeurs(self, api_client, company_a_manager, gare_a):
        api_client.force_authenticate(user=company_a_manager)

        donnees = api_client.get(f"/api/gares/{gare_a.id}/").data

        assert donnees["adresse"] == "" and donnees["telephone"] == ""
        assert donnees["heure_ouverture"] is None and donnees["chef_nom"] is None

    def test_numero_invalide_refuse(self, api_client, company_a_manager, gare_a):
        api_client.force_authenticate(user=company_a_manager)

        reponse = api_client.patch(f"/api/gares/{gare_a.id}/", {"telephone": "abc"}, format="json")

        assert reponse.status_code == 400 and "telephone" in reponse.data

    def test_le_chef_de_gare_renseigne_sa_gare(self, api_client, chef_gare_a, gare_a, gare_a2):
        api_client.force_authenticate(user=chef_gare_a)

        assert api_client.patch(f"/api/gares/{gare_a.id}/", {"telephone": "0700000000"}, format="json").status_code == 200
        assert api_client.patch(f"/api/gares/{gare_a2.id}/", {"telephone": "0700000000"}, format="json").status_code == 403

    def test_le_nom_du_chef_est_rendu(self, api_client, company_a_manager, chef_gare_a, gare_a):
        chef_gare_a.first_name, chef_gare_a.last_name = "Awa", "Koné"
        chef_gare_a.save()
        api_client.force_authenticate(user=company_a_manager)

        assert api_client.get(f"/api/gares/{gare_a.id}/").data["chef_nom"] == "Awa Koné"

    def test_un_chef_ne_dirige_qu_une_gare(self, api_client, company_a_manager, chef_gare_a, gare_a, gare_a2):
        api_client.force_authenticate(user=company_a_manager)

        reponse = api_client.patch(f"/api/gares/{gare_a2.id}/", {"chef": chef_gare_a.id}, format="json")

        assert reponse.status_code == 400
        assert gare_a.nom in str(reponse.data["chef"])
        # Le reconduire à sa propre gare n'est pas un doublon.
        assert api_client.patch(f"/api/gares/{gare_a.id}/", {"chef": chef_gare_a.id}, format="json").status_code == 200


@pytest.mark.django_db
class TestChefsPossibles:
    def test_la_direction_voit_les_chefs_de_sa_compagnie(
        self, api_client, company_a_manager, chef_gare_a, gare_a, user_factory, company_a, company_b
    ):
        libre = user_factory("chef_libre_a", Role.CHEF_GARE, company=company_a)
        user_factory("chef_autre_compagnie", Role.CHEF_GARE, company=company_b)
        suspendu = user_factory("chef_suspendu_a", Role.CHEF_GARE, company=company_a, is_active=False)
        api_client.force_authenticate(user=company_a_manager)

        reponse = api_client.get("/api/gares/chefs-possibles/")

        assert reponse.status_code == 200
        par_id = {chef["id"]: chef for chef in reponse.data}
        assert set(par_id) == {chef_gare_a.id, libre.id}
        assert suspendu.id not in par_id
        assert par_id[chef_gare_a.id]["gare"] == {"id": gare_a.id, "nom": gare_a.nom}
        assert par_id[libre.id]["gare"] is None

    @pytest.mark.parametrize("role", [Role.PDG, Role.SECRETAIRE_GENERAL, Role.DIRECTEUR_EXPLOITATION])
    def test_roles_de_direction(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_chefs", role, company=company_a))

        assert api_client.get("/api/gares/chefs-possibles/").status_code == 200

    @pytest.mark.parametrize("role", [Role.CHEF_GARE, Role.CHEF_LIGNE, Role.GUICHETIER, Role.DRH])
    def test_pas_d_annuaire_pour_les_autres(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_chefs", role, company=company_a))

        assert api_client.get("/api/gares/chefs-possibles/").status_code == 403


@pytest.mark.django_db
class TestQuais:
    def test_la_direction_declare_un_quai_dans_toute_gare(self, api_client, company_a_manager, company_a, gare_a2):
        api_client.force_authenticate(user=company_a_manager)

        reponse = api_client.post("/api/quais/", {"gare": gare_a2.id, "nom": "Quai A"}, format="json")

        assert reponse.status_code == 201, reponse.data
        quai = Quai.objects.get(pk=reponse.data["id"])
        assert quai.company == company_a and quai.actif is True
        assert reponse.data["gare_nom"] == gare_a2.nom
        entree = JournalAudit.objects.filter(objet_type="reseau.quai", objet_id=str(quai.id)).get()
        assert entree.acteur_id == company_a_manager.id

    def test_le_chef_de_gare_ne_tient_que_les_quais_de_sa_gare(self, api_client, chef_gare_a, gare_a, gare_a2, quai_a2):
        api_client.force_authenticate(user=chef_gare_a)

        assert api_client.post("/api/quais/", {"gare": gare_a.id, "nom": "Quai 2"}, format="json").status_code == 201
        refus = api_client.post("/api/quais/", {"gare": gare_a2.id, "nom": "Quai 2"}, format="json")
        assert refus.status_code == 400 and "gare" in refus.data
        assert api_client.patch(f"/api/quais/{quai_a2.id}/", {"actif": False}, format="json").status_code == 403
        assert api_client.delete(f"/api/quais/{quai_a2.id}/").status_code == 403
        assert Quai.objects.filter(pk=quai_a2.id, actif=True).exists()

    def test_fermer_puis_supprimer_un_quai(self, api_client, chef_gare_a, quai_a):
        api_client.force_authenticate(user=chef_gare_a)

        assert api_client.patch(f"/api/quais/{quai_a.id}/", {"actif": False}, format="json").data["actif"] is False
        assert api_client.delete(f"/api/quais/{quai_a.id}/").status_code == 204
        assert not Quai.objects.filter(pk=quai_a.id).exists()

    def test_deux_quais_d_une_gare_ne_portent_pas_le_meme_nom(self, api_client, company_a_manager, gare_a, quai_a, gare_a2):
        api_client.force_authenticate(user=company_a_manager)

        refus = api_client.post("/api/quais/", {"gare": gare_a.id, "nom": "quai 1"}, format="json")
        assert refus.status_code == 400 and "nom" in refus.data
        # Le même nom dans une autre gare est permis.
        assert api_client.post("/api/quais/", {"gare": gare_a2.id, "nom": "Quai 1"}, format="json").status_code == 201

    def test_un_quai_ne_change_pas_de_gare(self, api_client, company_a_manager, quai_a, gare_a2):
        api_client.force_authenticate(user=company_a_manager)

        reponse = api_client.patch(f"/api/quais/{quai_a.id}/", {"gare": gare_a2.id}, format="json")

        assert reponse.status_code == 400
        quai_a.refresh_from_db()
        assert quai_a.gare_id != gare_a2.id

    def test_filtre_par_gare_et_lecture_pour_tous(self, api_client, guichetier_a, quai_a, quai_a2, gare_a):
        api_client.force_authenticate(user=guichetier_a)

        reponse = api_client.get(f"/api/quais/?gare={gare_a.id}")

        assert reponse.status_code == 200
        assert [quai["id"] for quai in reponse.data] == [quai_a.id]
        assert api_client.post("/api/quais/", {"gare": gare_a.id, "nom": "Quai 9"}, format="json").status_code == 403

    def test_cloisonnement(self, api_client, company_a_manager, quai_a, quai_b, gare_b):
        api_client.force_authenticate(user=company_a_manager)

        assert [quai["id"] for quai in api_client.get("/api/quais/").data] == [quai_a.id]
        assert api_client.get(f"/api/quais/{quai_b.id}/").status_code == 404
        assert api_client.patch(f"/api/quais/{quai_b.id}/", {"nom": "X"}, format="json").status_code == 404
        refus = api_client.post("/api/quais/", {"gare": gare_b.id, "nom": "Quai X"}, format="json")
        assert refus.status_code == 400
        assert not Quai.objects.filter(nom="Quai X").exists()

    def test_supprimer_une_gare_supprime_ses_quais(self, api_client, company_a_manager, company_a, quai_a):
        gare = Gare.objects.create(nom="Gare provisoire", ville="Abidjan", company=company_a)
        Quai.objects.create(gare=gare, company=company_a, nom="Quai 1")
        api_client.force_authenticate(user=company_a_manager)

        assert api_client.delete(f"/api/gares/{gare.id}/").status_code == 204
        assert not Quai.objects.filter(gare_id=gare.id).exists()
        assert Quai.objects.filter(pk=quai_a.id).exists()


@pytest.mark.django_db
class TestFicheLigne:
    def test_distance_duree_et_noms_des_gares(self, api_client, company_a_manager, ligne_a, gare_a, gare_a2):
        api_client.force_authenticate(user=company_a_manager)

        reponse = api_client.patch(
            f"/api/lignes/{ligne_a.id}/", {"distance_km": 350, "duree_prevue_minutes": 330, "tarif": "7000"}, format="json"
        )

        assert reponse.status_code == 200, reponse.data
        assert reponse.data["distance_km"] == 350 and reponse.data["duree_prevue_minutes"] == 330
        assert reponse.data["gare_depart_nom"] == gare_a.nom and reponse.data["gare_arrivee_nom"] == gare_a2.nom

    def test_creation_complete_par_le_chef_de_ligne(self, api_client, user_factory, company_a, gare_a, gare_a2):
        api_client.force_authenticate(user=user_factory("chef_ligne_fiche", Role.CHEF_LIGNE, company=company_a))

        reponse = api_client.post(
            "/api/lignes/",
            {"nom": "Adjamé – Yopougon express", "gare_depart": gare_a.id, "gare_arrivee": gare_a2.id, "tarif": "1500",
             "distance_km": 18, "duree_prevue_minutes": 45},
            format="json",
        )

        assert reponse.status_code == 201, reponse.data
        assert reponse.data["statut"] == "ouverte"

    @pytest.mark.parametrize("champ", ["distance_km", "duree_prevue_minutes"])
    def test_valeur_nulle_ou_negative_refusee(self, api_client, company_a_manager, ligne_a, champ):
        api_client.force_authenticate(user=company_a_manager)

        assert api_client.patch(f"/api/lignes/{ligne_a.id}/", {champ: 0}, format="json").status_code == 400
        assert api_client.patch(f"/api/lignes/{ligne_a.id}/", {champ: -5}, format="json").status_code == 400

    def test_une_ligne_sans_fiche_garde_ses_valeurs(self, api_client, company_a_manager, ligne_a):
        api_client.force_authenticate(user=company_a_manager)

        donnees = api_client.get(f"/api/lignes/{ligne_a.id}/").data

        assert donnees["distance_km"] is None and donnees["duree_prevue_minutes"] is None and donnees["tarif"] is None


@pytest.mark.django_db
class TestFicheVehicule:
    def test_creation_avec_fiche_complete(self, api_client, user_factory, company_a):
        api_client.force_authenticate(user=user_factory("dt_fiche", Role.DIRECTEUR_TECHNIQUE, company=company_a))

        reponse = api_client.post(
            "/api/vehicules/",
            {
                "immatriculation": "AB-1234-CI", "capacite": 70, "marque": "Higer", "modele": "KLQ6129", "annee_mise_en_circulation": 2019,
                "classe": "climatise", "numero_carte_grise": "CG-778899", "carte_transport_numero": "CT-2025-55",
                "carte_transport_echeance": "2026-12-31",
            },
            format="json",
        )

        assert reponse.status_code == 201, reponse.data
        vehicule = Vehicule.objects.get(pk=reponse.data["id"])
        assert (vehicule.marque, vehicule.annee_mise_en_circulation, vehicule.classe) == ("Higer", 2019, "climatise")
        assert vehicule.carte_transport_echeance == datetime.date(2026, 12, 31)
        assert vehicule.statut == "disponible" and vehicule.company == company_a

    def test_un_vehicule_sans_fiche_garde_ses_valeurs(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        donnees = api_client.get(f"/api/vehicules/{vehicule_a.id}/").data

        assert donnees["classe"] == "" and donnees["annee_mise_en_circulation"] is None and donnees["marque"] == ""

    def test_annee_bornee(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)
        annee = timezone.localdate().year

        for refusee in (1949, annee + 2):
            assert api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"annee_mise_en_circulation": refusee}, format="json").status_code == 400
        for acceptee in (1950, annee, annee + 1):
            assert api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"annee_mise_en_circulation": acceptee}, format="json").status_code == 200
        assert api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"annee_mise_en_circulation": None}, format="json").status_code == 200

    def test_classe_inconnue_refusee(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        assert api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"classe": "premium"}, format="json").status_code == 400

    def test_la_gare_d_attache_reste_en_lecture_seule(self, api_client, company_a_manager, vehicule_a, gare_a):
        api_client.force_authenticate(user=company_a_manager)

        api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"gare": gare_a.id, "marque": "Yutong"}, format="json")

        vehicule_a.refresh_from_db()
        assert vehicule_a.gare_id is None and vehicule_a.marque == "Yutong"
