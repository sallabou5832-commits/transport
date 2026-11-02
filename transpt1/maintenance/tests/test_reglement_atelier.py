"""Ce que le règlement intérieur de la compagnie permet à l'atelier et au magasin. Par défaut, rien ne change : le socle
permet tout ce qui est réglé ici ; une compagnie peut l'interdire."""

import pytest

from configuration.models import ReglementInterieur
from maintenance.models import OrdreReparation, SortiePiece

CORRIGEURS = ["magasinier_a", "chef_atelier_a", "directeur_technique_a"]


def interdire(company, *codes):
    ReglementInterieur.objects.create(company=company, regles={code: False for code in codes})


@pytest.fixture
def sortie_a(db, company_a, ordre_a, piece_a):
    return SortiePiece.objects.create(ordre_reparation=ordre_a, piece=piece_a, company=company_a, quantite=2)


@pytest.mark.django_db
class TestSortiesDePieces:
    @pytest.mark.parametrize("corrigeur", CORRIGEURS)
    def test_par_defaut_une_sortie_se_corrige_et_s_annule(self, request, api_client, sortie_a, corrigeur):
        api_client.force_authenticate(user=request.getfixturevalue(corrigeur))

        assert api_client.patch(f"/api/sorties-pieces/{sortie_a.id}/", {"quantite": 3}, format="json").status_code == 200
        assert api_client.delete(f"/api/sorties-pieces/{sortie_a.id}/").status_code == 204

    @pytest.mark.parametrize("corrigeur", CORRIGEURS)
    def test_le_reglement_peut_l_interdire(self, request, api_client, company_a, sortie_a, corrigeur):
        interdire(company_a, "sorties_pieces_corrigeables")
        api_client.force_authenticate(user=request.getfixturevalue(corrigeur))

        reponse = api_client.patch(f"/api/sorties-pieces/{sortie_a.id}/", {"quantite": 3}, format="json")
        assert reponse.status_code == 403
        assert "règlement intérieur" in str(reponse.data["detail"])
        assert api_client.delete(f"/api/sorties-pieces/{sortie_a.id}/").status_code == 403
        sortie_a.refresh_from_db()
        assert sortie_a.quantite == 2

    def test_l_interdiction_n_empeche_pas_d_enregistrer_une_sortie(
        self, api_client, company_a, magasinier_a, ordre_a, piece_a
    ):
        interdire(company_a, "sorties_pieces_corrigeables")
        api_client.force_authenticate(user=magasinier_a)

        reponse = api_client.post(
            "/api/sorties-pieces/", {"ordre_reparation": ordre_a.id, "piece": piece_a.id, "quantite": 1}, format="json"
        )

        assert reponse.status_code == 201

    def test_seul_le_reglement_de_sa_compagnie_compte(self, api_client, company_b, magasinier_a, sortie_a):
        interdire(company_b, "sorties_pieces_corrigeables")
        api_client.force_authenticate(user=magasinier_a)

        assert api_client.delete(f"/api/sorties-pieces/{sortie_a.id}/").status_code == 204


@pytest.mark.django_db
class TestOrdresDuMecanicien:
    def test_par_defaut_le_mecanicien_confie_son_ordre_a_un_collegue(self, api_client, mecanicien_a, mecanicien_a2, ordre_a):
        api_client.force_authenticate(user=mecanicien_a)

        reponse = api_client.patch(f"/api/ordres-reparation/{ordre_a.id}/", {"mecanicien": mecanicien_a2.id}, format="json")

        assert reponse.status_code == 200
        ordre_a.refresh_from_db()
        assert ordre_a.mecanicien == mecanicien_a2

    def test_le_reglement_peut_lui_interdire_de_confier_son_ordre(
        self, api_client, company_a, mecanicien_a, mecanicien_a2, ordre_a
    ):
        interdire(company_a, "mecanicien_confie_ses_ordres")
        api_client.force_authenticate(user=mecanicien_a)

        reponse = api_client.patch(f"/api/ordres-reparation/{ordre_a.id}/", {"mecanicien": mecanicien_a2.id}, format="json")

        assert reponse.status_code == 403
        assert "réaffectation" in str(reponse.data["detail"])
        ordre_a.refresh_from_db()
        assert ordre_a.mecanicien == mecanicien_a

    def test_l_interdiction_laisse_le_mecanicien_mettre_a_jour_son_ordre(self, api_client, company_a, mecanicien_a, ordre_a):
        interdire(company_a, "mecanicien_confie_ses_ordres")
        api_client.force_authenticate(user=mecanicien_a)

        # Renvoyer son propre nom avec le reste (un formulaire complet) n'est pas confier l'ordre à quelqu'un d'autre.
        reponse = api_client.patch(
            f"/api/ordres-reparation/{ordre_a.id}/", {"mecanicien": mecanicien_a.id, "temps_passe_minutes": 30}, format="json"
        )

        assert reponse.status_code == 200

    def test_le_chef_d_atelier_reste_libre_de_confier_l_ordre(
        self, api_client, company_a, chef_atelier_a, mecanicien_a2, ordre_a
    ):
        interdire(company_a, "mecanicien_confie_ses_ordres")
        api_client.force_authenticate(user=chef_atelier_a)

        reponse = api_client.patch(f"/api/ordres-reparation/{ordre_a.id}/", {"mecanicien": mecanicien_a2.id}, format="json")

        assert reponse.status_code == 200

    def test_par_defaut_le_mecanicien_supprime_son_ordre(self, api_client, mecanicien_a, ordre_a):
        api_client.force_authenticate(user=mecanicien_a)

        assert api_client.delete(f"/api/ordres-reparation/{ordre_a.id}/").status_code == 204

    def test_le_reglement_peut_lui_interdire_de_supprimer_son_ordre(
        self, api_client, company_a, mecanicien_a, chef_atelier_a, ordre_a
    ):
        interdire(company_a, "mecanicien_supprime_ses_ordres")

        api_client.force_authenticate(user=mecanicien_a)
        assert api_client.delete(f"/api/ordres-reparation/{ordre_a.id}/").status_code == 403
        assert OrdreReparation.objects.filter(pk=ordre_a.pk).exists()

        api_client.force_authenticate(user=chef_atelier_a)
        assert api_client.delete(f"/api/ordres-reparation/{ordre_a.id}/").status_code == 204
