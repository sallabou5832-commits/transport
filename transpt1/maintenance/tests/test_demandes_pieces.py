"""Demande de pièce de l'atelier au magasinier (cahier des charges : Chef d'atelier / Mécanicien — « demande de pièce en un geste …
au magasinier avec confirmation de disponibilité » ; Magasinier — « sortie de pièce … liée directement à l'ordre de réparation »)."""

import pytest

from alertes.models import Alerte, TypeAlerte
from core.models import Role
from maintenance.models import DemandePiece, SortiePiece, StatutDemandePiece, StatutOrdreReparation

DEMANDES = "/api/demandes-pieces/"


def demander(api_client, utilisateur, ordre, piece, quantite=2, **plus):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(DEMANDES, {"ordre_reparation": ordre.id, "piece": piece.id, "quantite": quantite, **plus}, format="json")


def traiter(api_client, utilisateur, demande, action, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"{DEMANDES}{demande}/{action}/", corps, format="json")


@pytest.mark.django_db
class TestDemander:
    @pytest.mark.parametrize("role", ["mecanicien_a", "chef_atelier_a"])
    def test_l_atelier_demande_une_piece_pour_un_ordre(self, api_client, ordre_a, piece_a, request, role):
        reponse = demander(api_client, request.getfixturevalue(role), ordre_a, piece_a, quantite=3)

        assert reponse.status_code == 201
        assert reponse.data["statut"] == "demandee" and reponse.data["piece_nom"] == "Plaquette de frein"
        assert reponse.data["vehicule_immatriculation"] == "CI-3000-AA" and reponse.data["stock_actuel"] == 10

    def test_la_disponibilite_est_confirmee_des_la_demande(self, api_client, mecanicien_a, ordre_a, piece_a, piece_basse_a):
        assert demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=10).data["disponible_a_la_demande"] is True
        assert demander(api_client, mecanicien_a, ordre_a, piece_basse_a, quantite=3).data["disponible_a_la_demande"] is False

    def test_le_magasinier_est_prevenu_avec_l_etat_du_stock(self, api_client, mecanicien_a, ordre_a, piece_a):
        demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=3)

        alerte = Alerte.objects.get(type=TypeAlerte.DEMANDE_PIECE)
        assert alerte.roles_destinataires == [Role.MAGASINIER] and alerte.titre == "Demande de pièce : 3 x Plaquette de frein"
        assert "CI-3000-AA" in alerte.message and "En stock : 10" in alerte.message and alerte.gravite == "info"

    def test_un_stock_insuffisant_est_signale_au_magasinier(self, api_client, mecanicien_a, ordre_a, piece_basse_a):
        demander(api_client, mecanicien_a, ordre_a, piece_basse_a, quantite=5)

        alerte = Alerte.objects.get(type=TypeAlerte.DEMANDE_PIECE)
        assert "Stock insuffisant (2 en stock)" in alerte.message and alerte.gravite == "attention"

    def test_le_mecanicien_ne_demande_que_pour_ses_ordres(self, api_client, mecanicien_a2, ordre_a, piece_a):
        reponse = demander(api_client, mecanicien_a2, ordre_a, piece_a)

        assert reponse.status_code == 400 and "propres ordres" in str(reponse.data)
        assert not DemandePiece.objects.exists()

    def test_le_chef_d_atelier_demande_pour_l_ordre_de_n_importe_qui(self, api_client, chef_atelier_a, ordre_a, piece_a):
        assert demander(api_client, chef_atelier_a, ordre_a, piece_a).status_code == 201

    def test_pas_de_demande_pour_un_ordre_termine(self, api_client, mecanicien_a, ordre_a, piece_a):
        ordre_a.statut = StatutOrdreReparation.TERMINE
        ordre_a.save()

        reponse = demander(api_client, mecanicien_a, ordre_a, piece_a)

        assert reponse.status_code == 400 and "terminé" in str(reponse.data)

    @pytest.mark.parametrize("quantite", [0, -1, "beaucoup", None])
    def test_la_quantite_doit_etre_positive(self, api_client, mecanicien_a, ordre_a, piece_a, quantite):
        assert demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=quantite).status_code == 400

    def test_le_demandeur_ne_choisit_ni_le_statut_ni_la_disponibilite(self, api_client, mecanicien_a, ordre_a, piece_basse_a):
        reponse = demander(
            api_client, mecanicien_a, ordre_a, piece_basse_a, quantite=5, statut="servie", disponible_a_la_demande=True, demandeur=1
        )

        assert reponse.status_code == 201
        demande = DemandePiece.objects.get()
        assert demande.statut == StatutDemandePiece.DEMANDEE and demande.disponible_a_la_demande is False
        assert demande.demandeur == mecanicien_a

    def test_la_piece_d_une_autre_compagnie_est_refusee(self, api_client, mecanicien_a, ordre_a, company_b):
        from maintenance.models import Piece

        etrangere = Piece.objects.create(nom="Étrangère", reference="B-1", quantite_stock=9, seuil_alerte=1, company=company_b)

        assert demander(api_client, mecanicien_a, ordre_a, etrangere).status_code == 400

    @pytest.mark.parametrize("role", ["guichetier", "pdg", "qhse", "drh"])
    def test_les_autres_postes_ne_demandent_pas(self, api_client, ordre_a, piece_a, user_factory, company_a, role):
        utilisateur = user_factory(f"{role}_demande", Role(role), company=company_a)

        assert demander(api_client, utilisateur, ordre_a, piece_a).status_code == 403

    def test_le_magasinier_ne_demande_pas_a_lui_meme(self, api_client, magasinier_a, ordre_a, piece_a):
        assert demander(api_client, magasinier_a, ordre_a, piece_a).status_code == 403


@pytest.mark.django_db
class TestServir:
    def test_servir_enregistre_la_sortie_sur_l_ordre_et_baisse_le_stock(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=4).data["id"]

        reponse = traiter(api_client, magasinier_a, demande, "servir")

        assert reponse.status_code == 200 and reponse.data["statut"] == "servie" and reponse.data["traitee_par_nom"] == "magasinier_a"
        sortie = SortiePiece.objects.get()
        assert (sortie.ordre_reparation, sortie.piece, sortie.quantite) == (ordre_a, piece_a, 4)
        assert reponse.data["sortie"] == sortie.id
        piece_a.refresh_from_db()
        assert piece_a.quantite_stock == 6

    def test_le_demandeur_est_prevenu(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=4).data["id"]
        traiter(api_client, magasinier_a, demande, "servir")

        alerte = Alerte.objects.get(titre__startswith="Pièce servie")
        assert list(alerte.destinataires.all()) == [mecanicien_a] and "4 x Plaquette de frein" in alerte.titre

    def test_une_sortie_sous_le_seuil_previent_le_magasin_comme_avant(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=6).data["id"]

        traiter(api_client, magasinier_a, demande, "servir")

        assert Alerte.objects.filter(type=TypeAlerte.STOCK_BAS, titre="Stock bas : Plaquette de frein").exists()

    def test_un_stock_insuffisant_refuse_et_laisse_la_demande_en_attente(
        self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_basse_a
    ):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_basse_a, quantite=5).data["id"]

        reponse = traiter(api_client, magasinier_a, demande, "servir")

        assert reponse.status_code == 400 and "Stock insuffisant" in str(reponse.data)
        assert DemandePiece.objects.get().statut == StatutDemandePiece.DEMANDEE and not SortiePiece.objects.exists()
        piece_basse_a.refresh_from_db()
        assert piece_basse_a.quantite_stock == 2

    def test_une_demande_ne_se_traite_qu_une_fois(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=1).data["id"]
        traiter(api_client, magasinier_a, demande, "servir")

        assert traiter(api_client, magasinier_a, demande, "servir").status_code == 400
        assert traiter(api_client, magasinier_a, demande, "refuser", commentaire="Trop tard").status_code == 400
        piece_a.refresh_from_db()
        assert piece_a.quantite_stock == 9, "une seule sortie"

    @pytest.mark.parametrize("role", ["mecanicien_a", "chef_atelier_a", "directeur_technique_a"])
    def test_seul_le_magasinier_sert(self, api_client, mecanicien_a, ordre_a, piece_a, request, role):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]

        assert traiter(api_client, request.getfixturevalue(role), demande, "servir").status_code == 403
        assert DemandePiece.objects.get().statut == StatutDemandePiece.DEMANDEE


@pytest.mark.django_db
class TestRefuserEtAnnuler:
    def test_le_magasinier_refuse_en_disant_pourquoi(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_basse_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_basse_a, quantite=5).data["id"]

        reponse = traiter(api_client, magasinier_a, demande, "refuser", commentaire="Commande en cours, livraison lundi")

        assert reponse.status_code == 200 and reponse.data["statut"] == "refusee"
        assert reponse.data["commentaire"] == "Commande en cours, livraison lundi"
        alerte = Alerte.objects.get(titre__startswith="Pièce indisponible")
        assert list(alerte.destinataires.all()) == [mecanicien_a] and "livraison lundi" in alerte.message

    def test_le_refus_sans_raison_est_refuse(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]

        assert traiter(api_client, magasinier_a, demande, "refuser").status_code == 400
        assert traiter(api_client, magasinier_a, demande, "refuser", commentaire=" ").status_code == 400
        assert DemandePiece.objects.get().statut == StatutDemandePiece.DEMANDEE

    def test_le_demandeur_annule_sa_demande(self, api_client, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]

        reponse = traiter(api_client, mecanicien_a, demande, "annuler")

        assert reponse.status_code == 200 and reponse.data["statut"] == "annulee"

    def test_le_chef_d_atelier_annule_la_demande_d_un_mecanicien(self, api_client, mecanicien_a, chef_atelier_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]

        assert traiter(api_client, chef_atelier_a, demande, "annuler").status_code == 200

    def test_un_autre_mecanicien_n_annule_pas_la_demande_d_un_collegue(self, api_client, mecanicien_a, mecanicien_a2, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]

        # Il ne voit même pas la demande de son collègue : elle lui est introuvable.
        assert traiter(api_client, mecanicien_a2, demande, "annuler").status_code == 404
        assert DemandePiece.objects.get().statut == StatutDemandePiece.DEMANDEE

    def test_une_demande_annulee_ne_se_sert_plus(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]
        traiter(api_client, mecanicien_a, demande, "annuler")

        assert traiter(api_client, magasinier_a, demande, "servir").status_code == 400

    def test_le_magasinier_n_annule_pas(self, api_client, magasinier_a, mecanicien_a, ordre_a, piece_a):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]

        assert traiter(api_client, magasinier_a, demande, "annuler").status_code == 403


@pytest.mark.django_db
class TestQuiVoitQuoi:
    def test_le_mecanicien_ne_voit_que_ses_demandes(self, api_client, mecanicien_a, mecanicien_a2, chef_atelier_a, ordre_a, piece_a, company_a):
        from maintenance.models import OrdreReparation

        autre_ordre = OrdreReparation.objects.create(vehicule=ordre_a.vehicule, company=company_a, description="Autre", mecanicien=mecanicien_a2)
        demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=1)
        demander(api_client, mecanicien_a2, autre_ordre, piece_a, quantite=2)

        api_client.force_authenticate(user=mecanicien_a)
        assert [d["quantite"] for d in api_client.get(DEMANDES).data] == [1]

    @pytest.mark.parametrize("role", ["magasinier_a", "chef_atelier_a", "directeur_technique_a"])
    def test_le_magasin_et_le_technique_voient_toutes_les_demandes_et_les_filtrent(
        self, api_client, mecanicien_a, ordre_a, piece_a, request, role
    ):
        premiere = demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=1).data["id"]
        demander(api_client, mecanicien_a, ordre_a, piece_a, quantite=2)
        traiter(api_client, mecanicien_a, premiere, "annuler")

        api_client.force_authenticate(user=request.getfixturevalue(role))
        assert len(api_client.get(DEMANDES).data) == 2
        assert [d["quantite"] for d in api_client.get(f"{DEMANDES}?statut=demandee").data] == [2]
        assert [d["quantite"] for d in api_client.get(f"{DEMANDES}?statut=annulee").data] == [1]
        assert len(api_client.get(f"{DEMANDES}?statut=nimporte").data) == 2

    @pytest.mark.parametrize("role", ["guichetier", "pdg", "drh", "qhse"])
    def test_les_autres_postes_ne_voient_pas_les_demandes(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_lit", Role(role), company=company_a))

        assert api_client.get(DEMANDES).status_code == 403

    def test_une_autre_compagnie_ne_voit_ni_ne_traite_les_demandes(self, api_client, mecanicien_a, ordre_a, piece_a, user_factory, company_b):
        demande = demander(api_client, mecanicien_a, ordre_a, piece_a).data["id"]
        magasinier_b = user_factory("magasinier_b_demande", Role.MAGASINIER, company=company_b)

        api_client.force_authenticate(user=magasinier_b)
        assert api_client.get(DEMANDES).data == []
        assert traiter(api_client, magasinier_b, demande, "servir").status_code == 404

    def test_sans_authentification_rien(self, api_client):
        assert api_client.get(DEMANDES).status_code == 401
