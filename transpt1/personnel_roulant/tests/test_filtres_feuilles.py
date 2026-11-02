"""`GET /api/feuilles-de-route/?chauffeur=&date=` : l'écran d'un chauffeur ne télécharge que sa feuille du jour, et la
feuille porte la ligne et le véhicule (plus besoin des listes complètes des départs, lignes et véhicules).

Les dates sont fixes (2030) pour que les essais ne dépendent ni du jour ni de l'heure où ils tournent."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute

URL = "/api/feuilles-de-route/"


def _local(jour, heure, minute=0):
    return timezone.make_aware(datetime.datetime.combine(jour, datetime.time(heure, minute)))


@pytest.fixture
def agenda(company_a, ligne_a, vehicule_a, chauffeur_a, chauffeur_a2):
    """chauffeur_a : une feuille le 17 mai (à 00 h 05 et à 23 h 55), une le 18 ; chauffeur_a2 : une le 17."""
    jour = datetime.date(2030, 5, 17)

    def feuille(chauffeur, quand):
        depart = Depart.objects.create(
            ligne=ligne_a, vehicule=vehicule_a, chauffeur=chauffeur, company=company_a, date_heure=quand,
            statut=DepartStatut.PLANIFIE,
        )
        return FeuilleDeRoute.objects.create(
            depart=depart, chauffeur=chauffeur, company=company_a, heure_depart_prevue=quand
        )

    return {
        "debut_de_journee": feuille(chauffeur_a, _local(jour, 0, 5)),
        "fin_de_journee": feuille(chauffeur_a, _local(jour, 23, 55)),
        "lendemain": feuille(chauffeur_a, _local(jour + datetime.timedelta(days=1), 8)),
        "collegue": feuille(chauffeur_a2, _local(jour, 9)),
    }


def _ids(reponse):
    assert reponse.status_code == 200, reponse.data
    return {f["id"] for f in reponse.data}


@pytest.mark.django_db
class TestFiltres:
    def test_sans_filtre_toute_la_compagnie_est_listee_pour_un_role_de_gestion(self, api_client, chef_ligne_a, agenda):
        api_client.force_authenticate(user=chef_ligne_a)

        assert _ids(api_client.get(URL)) == {f.id for f in agenda.values()}

    def test_filtre_par_chauffeur(self, api_client, chef_ligne_a, chauffeur_a, agenda):
        api_client.force_authenticate(user=chef_ligne_a)

        ids = _ids(api_client.get(URL, {"chauffeur": chauffeur_a.id}))

        assert ids == {agenda["debut_de_journee"].id, agenda["fin_de_journee"].id, agenda["lendemain"].id}

    def test_filtre_par_date_prend_toute_la_journee_et_rien_d_autre(self, api_client, chef_ligne_a, agenda):
        api_client.force_authenticate(user=chef_ligne_a)

        ids = _ids(api_client.get(URL, {"date": "2030-05-17"}))

        # 00 h 05 et 23 h 55 sont bien du 17 ; le lendemain 08 h n'en est pas.
        assert ids == {agenda["debut_de_journee"].id, agenda["fin_de_journee"].id, agenda["collegue"].id}

    def test_chauffeur_et_date_se_combinent(self, api_client, chauffeur_a, agenda):
        api_client.force_authenticate(user=chauffeur_a)

        ids = _ids(api_client.get(URL, {"chauffeur": chauffeur_a.id, "date": "2030-05-17"}))

        assert ids == {agenda["debut_de_journee"].id, agenda["fin_de_journee"].id}

    def test_une_autre_compagnie_ne_voit_rien_meme_en_demandant_un_chauffeur_d_ailleurs(
        self, api_client, user_factory, company_b, chauffeur_a, agenda
    ):
        directeur_b = user_factory("directeur_b_feuilles", Role.DIRECTEUR_EXPLOITATION, company=company_b)
        api_client.force_authenticate(user=directeur_b)

        assert _ids(api_client.get(URL, {"chauffeur": chauffeur_a.id})) == set()

    @pytest.mark.parametrize(
        ("parametres", "champ"),
        [
            ({"chauffeur": "abc"}, "chauffeur"),
            ({"chauffeur": "-3"}, "chauffeur"),
            ({"date": "demain"}, "date"),
            ({"date": "2030-13-45"}, "date"),  # bien formée mais impossible : ne doit pas faire une erreur 500
            ({"date": ""}, "date"),
        ],
    )
    def test_un_filtre_invalide_est_refuse_clairement(self, api_client, chauffeur_a, agenda, parametres, champ):
        api_client.force_authenticate(user=chauffeur_a)

        reponse = api_client.get(URL, parametres)

        assert reponse.status_code == 400 and champ in reponse.data

    def test_les_filtres_ne_touchent_pas_le_detail(self, api_client, chef_ligne_a, chauffeur_a, agenda):
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.get(f"{URL}{agenda['collegue'].id}/", {"chauffeur": chauffeur_a.id})

        assert reponse.status_code == 200 and reponse.data["id"] == agenda["collegue"].id


@pytest.mark.django_db
class TestFeuillePorteLaLigneEtLeVehicule:
    def test_ligne_et_vehicule_sont_dans_la_feuille(self, api_client, chauffeur_a, feuille_a, ligne_a, vehicule_a):
        api_client.force_authenticate(user=chauffeur_a)

        donnees = api_client.get(f"{URL}{feuille_a.id}/").data

        assert donnees["ligne_nom"] == ligne_a.nom
        assert donnees["vehicule"] == vehicule_a.id
        assert donnees["vehicule_immatriculation"] == vehicule_a.immatriculation

    def test_la_liste_ne_fait_pas_une_requete_par_feuille(
        self, api_client, chauffeur_a, agenda, django_assert_max_num_queries
    ):
        api_client.force_authenticate(user=chauffeur_a)

        # Quatre feuilles (donc quatre départs, une ligne, un véhicule) : le nombre de requêtes ne doit pas dépendre de leur
        # nombre. Le plafond est large (authentification, compagnie) mais très en dessous de « une requête par feuille ».
        with django_assert_max_num_queries(8):
            assert api_client.get(URL).status_code == 200

    def test_les_champs_ajoutes_ne_sont_pas_modifiables(self, api_client, chauffeur_a, feuille_a, vehicule_a):
        api_client.force_authenticate(user=chauffeur_a)

        reponse = api_client.patch(f"{URL}{feuille_a.id}/", {"ligne_nom": "Pirate", "vehicule": 999999}, format="json")

        assert reponse.status_code == 200
        feuille_a.depart.refresh_from_db()
        assert feuille_a.depart.vehicule_id == vehicule_a.id
        assert reponse.data["ligne_nom"] != "Pirate"
