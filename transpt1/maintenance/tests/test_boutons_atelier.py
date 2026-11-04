"""Les gestes de l'atelier et du magasin donnés aux écrans : corriger ou annuler une sortie (le stock suit), confier son ordre à
un collègue (qui en est prévenu), la liste des collègues, et la remise en service d'un car bloqué par le QHSE selon le règlement
intérieur de la compagnie."""

import pytest

from alertes.models import Alerte, TypeAlerte
from configuration.models import ReglementInterieur
from core.models import Role
from maintenance.models import OrdreReparation, Piece, SortiePiece, StatutOrdreReparation
from personnel_roulant.models import BlocageSecurite
from reseau.models import VehiculeStatut


@pytest.fixture
def sortie_a(db, company_a, ordre_a, piece_a):
    """Une sortie de 2 pièces : le stock (10) est passé à 8."""
    Piece.objects.filter(pk=piece_a.pk).update(quantite_stock=8)
    return SortiePiece.objects.create(ordre_reparation=ordre_a, piece=piece_a, company=company_a, quantite=2)


def stock(piece):
    piece.refresh_from_db()
    return piece.quantite_stock


@pytest.mark.django_db
class TestSortiesCorrigees:
    def test_annuler_une_sortie_remet_ses_pieces_en_stock(self, api_client, magasinier_a, sortie_a, piece_a):
        api_client.force_authenticate(user=magasinier_a)

        assert api_client.delete(f"/api/sorties-pieces/{sortie_a.id}/").status_code == 204
        assert stock(piece_a) == 10 and not SortiePiece.objects.filter(pk=sortie_a.pk).exists()

    @pytest.mark.parametrize("quantite, attendu", [(5, 5), (1, 9)])
    def test_corriger_la_quantite_reporte_l_ecart_sur_le_stock(self, api_client, magasinier_a, sortie_a, piece_a, quantite, attendu):
        api_client.force_authenticate(user=magasinier_a)

        reponse = api_client.patch(f"/api/sorties-pieces/{sortie_a.id}/", {"quantite": quantite}, format="json")

        assert reponse.status_code == 200 and reponse.data["quantite"] == quantite
        assert stock(piece_a) == attendu

    def test_une_correction_que_le_stock_ne_couvre_pas_est_refusee(self, api_client, magasinier_a, sortie_a, piece_a):
        api_client.force_authenticate(user=magasinier_a)

        reponse = api_client.patch(f"/api/sorties-pieces/{sortie_a.id}/", {"quantite": 11}, format="json")

        assert reponse.status_code == 400 and "insuffisant" in str(reponse.data["quantite"])
        assert stock(piece_a) == 8
        sortie_a.refresh_from_db()
        assert sortie_a.quantite == 2

    def test_une_sortie_ne_change_pas_de_piece(self, api_client, magasinier_a, sortie_a, piece_a, piece_basse_a):
        api_client.force_authenticate(user=magasinier_a)

        reponse = api_client.patch(f"/api/sorties-pieces/{sortie_a.id}/", {"piece": piece_basse_a.id}, format="json")

        assert reponse.status_code == 400 and "annulez-la" in str(reponse.data)
        assert stock(piece_a) == 8 and stock(piece_basse_a) == 2

    def test_une_correction_qui_fait_passer_sous_le_seuil_previent_le_magasin(
        self, api_client, magasinier_a, sortie_a, piece_a
    ):
        api_client.force_authenticate(user=magasinier_a)

        api_client.patch(f"/api/sorties-pieces/{sortie_a.id}/", {"quantite": 7}, format="json")

        assert stock(piece_a) == 3
        assert Alerte.objects.filter(type=TypeAlerte.STOCK_BAS, titre__contains=piece_a.nom).exists()

    def test_interdite_par_le_reglement_le_stock_ne_bouge_pas(self, api_client, company_a, magasinier_a, sortie_a, piece_a):
        ReglementInterieur.objects.create(company=company_a, regles={"sorties_pieces_corrigeables": False})
        api_client.force_authenticate(user=magasinier_a)

        assert api_client.delete(f"/api/sorties-pieces/{sortie_a.id}/").status_code == 403
        assert stock(piece_a) == 8


@pytest.mark.django_db
class TestConfierSonOrdre:
    def test_le_collegue_et_le_chef_d_atelier_sont_prevenus(
        self, api_client, mecanicien_a, mecanicien_a2, chef_atelier_a, ordre_a
    ):
        api_client.force_authenticate(user=mecanicien_a)

        reponse = api_client.patch(f"/api/ordres-reparation/{ordre_a.id}/", {"mecanicien": mecanicien_a2.id}, format="json")

        assert reponse.status_code == 200
        alerte = Alerte.objects.get(type=TypeAlerte.ORDRE_REPARATION, titre__startswith="Ordre de réparation confié")
        assert set(alerte.destinataires.all()) == {mecanicien_a, mecanicien_a2}
        assert alerte.roles_destinataires == [Role.CHEF_ATELIER]

    def test_mettre_a_jour_son_ordre_sans_le_confier_ne_previent_personne(self, api_client, mecanicien_a, ordre_a):
        api_client.force_authenticate(user=mecanicien_a)

        api_client.patch(f"/api/ordres-reparation/{ordre_a.id}/", {"statut": StatutOrdreReparation.EN_COURS}, format="json")

        assert not Alerte.objects.filter(titre__startswith="Ordre de réparation confié").exists()


@pytest.mark.django_db
class TestIntervenants:
    @pytest.mark.parametrize("role", ["mecanicien_a", "chef_atelier_a", "directeur_technique_a"])
    def test_l_atelier_lit_la_liste_de_ses_intervenants(
        self, request, api_client, role, mecanicien_a, mecanicien_a2, chef_atelier_a, user_factory, company_b
    ):
        user_factory("mecanicien_b", Role.MECANICIEN, company=company_b)
        api_client.force_authenticate(user=request.getfixturevalue(role))

        reponse = api_client.get("/api/maintenance/intervenants/")

        assert reponse.status_code == 200
        assert {i["id"] for i in reponse.data} == {mecanicien_a.id, mecanicien_a2.id, chef_atelier_a.id}

    def test_un_intervenant_suspendu_n_y_figure_pas(self, api_client, mecanicien_a, mecanicien_a2):
        mecanicien_a2.is_active = False
        mecanicien_a2.save()
        api_client.force_authenticate(user=mecanicien_a)

        assert [i["id"] for i in api_client.get("/api/maintenance/intervenants/").data] == [mecanicien_a.id]

    @pytest.mark.parametrize("role", [Role.GUICHETIER, Role.MAGASINIER, Role.DRH])
    def test_hors_de_l_atelier_on_ne_la_lit_pas(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"intervenants_{role}", role, company=company_a))

        assert api_client.get("/api/maintenance/intervenants/").status_code == 403


@pytest.mark.django_db
class TestRemiseEnServiceApresBlocageQhse:
    @pytest.fixture
    def bloque(self, company_a, vehicule_a, user_factory):
        qhse = user_factory("qhse_remise", Role.QHSE, company=company_a)
        vehicule_a.statut = VehiculeStatut.BLOQUE_SECURITE
        vehicule_a.save()
        BlocageSecurite.objects.create(vehicule=vehicule_a, company=company_a, motif="Pneus lisses", pose_par=qhse)
        return qhse

    def ordre(self, company_a, vehicule_a, mecanicien_a):
        return OrdreReparation.objects.create(
            vehicule=vehicule_a, company=company_a, description="Pneus", statut=StatutOrdreReparation.EN_COURS, mecanicien=mecanicien_a
        )

    def cloturer(self, api_client, mecanicien, ordre):
        api_client.force_authenticate(user=mecanicien)
        return api_client.patch(f"/api/ordres-reparation/{ordre.id}/", {"statut": StatutOrdreReparation.TERMINE}, format="json")

    def test_par_defaut_la_reparation_terminee_remet_le_car_en_service(
        self, api_client, company_a, vehicule_a, mecanicien_a, bloque
    ):
        assert self.cloturer(api_client, mecanicien_a, self.ordre(company_a, vehicule_a, mecanicien_a)).status_code == 200

        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_le_reglement_peut_exiger_la_levee_du_qhse(self, api_client, company_a, vehicule_a, mecanicien_a, bloque):
        ReglementInterieur.objects.create(company=company_a, regles={"reparation_leve_le_blocage_qhse": False})
        ordre = self.ordre(company_a, vehicule_a, mecanicien_a)

        assert self.cloturer(api_client, mecanicien_a, ordre).status_code == 200

        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.BLOQUE_SECURITE
        alerte = Alerte.objects.get(titre__contains="attend la levée du blocage")
        assert alerte.roles_destinataires == [Role.QHSE]
        assert not Alerte.objects.filter(type=TypeAlerte.VEHICULE_LIBERE).exists()

        api_client.force_authenticate(user=bloque)
        blocage = BlocageSecurite.objects.get(vehicule=vehicule_a)
        assert api_client.post(f"/api/blocages-securite/{blocage.id}/lever/", {"motif": "Pneus changés, vérifiés"}, format="json").status_code == 200
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_sans_blocage_du_qhse_la_regle_ne_change_rien(self, api_client, company_a, vehicule_a, mecanicien_a):
        ReglementInterieur.objects.create(company=company_a, regles={"reparation_leve_le_blocage_qhse": False})
        vehicule_a.statut = VehiculeStatut.EN_MAINTENANCE
        vehicule_a.save()

        self.cloturer(api_client, mecanicien_a, self.ordre(company_a, vehicule_a, mecanicien_a))

        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE

    def test_seul_le_reglement_de_sa_compagnie_compte(self, api_client, company_a, company_b, vehicule_a, mecanicien_a, bloque):
        ReglementInterieur.objects.create(company=company_b, regles={"reparation_leve_le_blocage_qhse": False})

        self.cloturer(api_client, mecanicien_a, self.ordre(company_a, vehicule_a, mecanicien_a))

        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.DISPONIBLE
