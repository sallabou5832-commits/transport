"""Entrées hostiles : une valeur fantaisiste est une erreur 400/409 claire, jamais une erreur serveur (500).

Couvre les aides `core.entiers`, `core.textes`, `core.dates`, le gestionnaire d'exceptions et l'analyseur JSON.
"""

import pytest

from core.dates import lire_date, lire_date_heure
from core.entiers import lire_entier
from core.models import Role
from core.textes import champ_du_corps, lire_texte
from reseau.models import Gare, Ligne


class TestLireEntier:
    @pytest.mark.parametrize("valeur, attendu", [("12", 12), (" 7 ", 7), (0, 0), (42, 42), ("0", 0)])
    def test_un_entier_valide(self, valeur, attendu):
        assert lire_entier(valeur) == attendu

    @pytest.mark.parametrize(
        "valeur",
        [None, "", "abc", "-1", -1, "1.5", 1.5, True, False, [], {}, "²", "٣", "9" * 30, 10**30, "1e5", float("inf")],
    )
    def test_tout_le_reste_donne_none_sans_exception(self, valeur):
        assert lire_entier(valeur) is None


class TestLireTexte:
    def test_retire_espaces_et_caracteres_nuls(self):
        assert lire_texte("  bonjour\x00 ") == "bonjour"

    def test_absent_donne_une_chaine_vide(self):
        assert lire_texte(None) == ""

    @pytest.mark.parametrize("valeur, attendu", [(123, "123"), ([1], "[1]")])
    def test_un_non_texte_est_converti_au_lieu_de_lever(self, valeur, attendu):
        assert lire_texte(valeur) == attendu

    def test_coupe_au_maximum(self):
        assert lire_texte("abcdef", 3) == "abc"

    @pytest.mark.parametrize("corps", [[], 5, "x", None, True])
    def test_champ_d_un_corps_qui_n_est_pas_un_objet(self, corps):
        assert champ_du_corps(corps, "username", 150) == ""

    def test_champ_d_un_objet(self):
        assert champ_du_corps({"username": " ab "}, "username") == "ab"


class TestDatesNonTextuelles:
    @pytest.mark.parametrize("valeur", [123, 20260101, [], {}, True])
    def test_lire_date(self, valeur):
        assert lire_date(valeur) is None

    @pytest.mark.parametrize("valeur", [123, [], {}, True])
    def test_lire_date_heure(self, valeur):
        assert lire_date_heure(valeur) is None


@pytest.fixture
def pdg(user_factory, company_a):
    return user_factory("pdg_hostile", Role.PDG, company=company_a)


@pytest.fixture
def ligne(company_a):
    depart = Gare.objects.create(nom="Gare A", ville="Abidjan", company=company_a)
    arrivee = Gare.objects.create(nom="Gare B", ville="Bouaké", company=company_a)
    return Ligne.objects.create(nom="A-B", gare_depart=depart, gare_arrivee=arrivee, company=company_a)


@pytest.mark.django_db
class TestCorpsQuiNEstPasUnObjet:
    """L'analyseur central refuse un corps JSON qui n'est pas un objet, pour toutes les vues."""

    @pytest.mark.parametrize("corps", ["[]", "123", '"x"', "true", "null"])
    def test_action_qui_lit_ses_champs_par_get(self, api_client, pdg, ligne, corps):
        api_client.force_authenticate(user=pdg)

        reponse = api_client.post(f"/api/lignes/{ligne.pk}/changement/", data=corps, content_type="application/json")

        assert reponse.status_code == 400
        assert "objet JSON" in str(reponse.data)

    @pytest.mark.parametrize("corps", ["[]", "123", '"x"', "true", "null"])
    def test_connexion(self, api_client, corps):
        reponse = api_client.post("/api/auth/login/", data=corps, content_type="application/json")

        assert reponse.status_code == 400

    def test_un_objet_est_accepte(self, api_client, pdg, ligne):
        api_client.force_authenticate(user=pdg)

        reponse = api_client.post(f"/api/lignes/{ligne.pk}/changement/", data="{}", content_type="application/json")

        # Le corps a été lu : la 400 vient de la règle métier (action manquante), pas de l'analyseur.
        assert reponse.status_code == 400
        assert "objet JSON" not in str(reponse.data) and "Action attendue" in str(reponse.data)

    def test_l_envoi_de_positions_en_lot_reste_une_liste(self, api_client, user_factory, company_a):
        chauffeur = user_factory("chauffeur_lot", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        api_client.force_authenticate(user=chauffeur)

        reponse = api_client.post("/api/positions/", data="[]", content_type="application/json")

        # La liste est lue (et refusée parce qu'elle est vide), pas rejetée par l'analyseur.
        assert reponse.status_code == 400
        assert "objet JSON" not in str(reponse.data) and "Envoyez entre 1 et" in str(reponse.data)


@pytest.mark.django_db
class TestSuppressionProtegee:
    def test_supprimer_une_gare_utilisee_par_une_ligne_est_un_conflit(self, api_client, pdg, ligne):
        api_client.force_authenticate(user=pdg)

        reponse = api_client.delete(f"/api/gares/{ligne.gare_depart_id}/")

        assert reponse.status_code == 409
        assert Gare.objects.filter(pk=ligne.gare_depart_id).exists()


@pytest.mark.django_db
class TestFiltresEntiers:
    """`?ligne=²` : le caractère passait `isdigit()` mais pas `int()` (erreur 500)."""

    @pytest.mark.parametrize("valeur", ["²", "٣", "9" * 30, "abc", "-1", "%00"])
    @pytest.mark.parametrize("chemin", ["/api/depenses/?ligne=", "/api/changements-ligne/?ligne=", "/api/controles/?chauffeur="])
    def test_un_filtre_fantaisiste_n_est_pas_une_erreur_serveur(self, api_client, user_factory, company_a, chemin, valeur):
        api_client.force_authenticate(user=user_factory("dg_filtres", Role.DIRECTEUR_EXPLOITATION, company=company_a))

        reponse = api_client.get(chemin + valeur)

        assert reponse.status_code < 500
