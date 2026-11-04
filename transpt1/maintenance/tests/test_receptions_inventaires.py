"""Pièces et stock : la fiche d'une pièce (prix, fournisseur, emplacement), les réceptions (le stock monte, coût moyen pondéré) et
les inventaires (le stock prend la quantité comptée, l'écart est gardé avec son motif). Rien ne touche une autre compagnie."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from alertes.models import Alerte
from audit.models import JournalAudit
from core.models import Role
from maintenance.models import EntreePiece, InventairePiece, Piece
from maintenance.stock import cout_moyen


@pytest.fixture
def magasinier(user_factory, company_a):
    return user_factory("magasinier_stock", Role.MAGASINIER, company=company_a)


@pytest.fixture
def directeur_technique(user_factory, company_a):
    return user_factory("dt_stock", Role.DIRECTEUR_TECHNIQUE, company=company_a)


@pytest.fixture
def filtre(company_a):
    return Piece.objects.create(
        nom="Filtre à huile", reference="FH-100", quantite_stock=10, seuil_alerte=4, company=company_a,
        prix_unitaire=Decimal("2000"),
    )


@pytest.fixture
def piece_b(company_b):
    return Piece.objects.create(nom="Courroie", reference="CR-1", quantite_stock=5, seuil_alerte=1, company=company_b)


def client_de(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def recevoir(user, piece, **corps):
    return client_de(user).post("/api/entrees-pieces/", {"piece": piece.id, "quantite": 5, **corps}, format="json")


def inventorier(user, piece, **corps):
    return client_de(user).post("/api/inventaires-pieces/", {"piece": piece.id, **corps}, format="json")


class TestCoutMoyen:
    def test_le_prix_recu_se_pondere_avec_le_stock(self):
        assert cout_moyen(10, Decimal("2000"), 5, Decimal("2600")) == Decimal("2200.00")

    def test_sans_prix_recu_le_prix_reste(self):
        assert cout_moyen(10, Decimal("2000"), 5, None) == Decimal("2000")

    def test_sans_prix_actuel_ou_sans_stock_le_prix_recu_s_impose(self):
        assert cout_moyen(10, None, 5, Decimal("2600")) == Decimal("2600")
        assert cout_moyen(0, Decimal("2000"), 5, Decimal("2600")) == Decimal("2600")

    def test_arrondi_au_centime(self):
        assert cout_moyen(2, Decimal("1000"), 1, Decimal("1001")) == Decimal("1000.33")


@pytest.mark.django_db
class TestFicheDeLaPiece:
    def test_une_piece_sans_fiche_fonctionne_comme_avant(self, magasinier, company_a):
        reponse = client_de(magasinier).post(
            "/api/pieces/", {"nom": "Ampoule", "reference": "AMP-1", "quantite_stock": 3, "seuil_alerte": 1}, format="json"
        )

        assert reponse.status_code == 201
        assert (reponse.data["prix_unitaire"], reponse.data["fournisseur"], reponse.data["valeur_stock"]) == (None, "", None)

    def test_la_fiche_complete_et_la_valeur_du_stock(self, magasinier, filtre):
        reponse = client_de(magasinier).patch(
            f"/api/pieces/{filtre.id}/", {"fournisseur": "CFAO Motors", "emplacement": "Rayon B2"}, format="json"
        )

        assert reponse.status_code == 200
        assert (reponse.data["fournisseur"], reponse.data["emplacement"]) == ("CFAO Motors", "Rayon B2")
        assert Decimal(reponse.data["valeur_stock"]) == Decimal("20000")

    def test_un_prix_negatif_est_refuse(self, magasinier, filtre):
        assert client_de(magasinier).patch(f"/api/pieces/{filtre.id}/", {"prix_unitaire": "-1"}, format="json").status_code == 400

    def test_la_correction_directe_du_stock_reste_possible_comme_avant(self, magasinier, filtre):
        reponse = client_de(magasinier).patch(f"/api/pieces/{filtre.id}/", {"quantite_stock": 12}, format="json")

        assert reponse.status_code == 200
        assert JournalAudit.objects.filter(objet_type="maintenance.piece", objet_id=str(filtre.id), action="modification").exists()


@pytest.mark.django_db
class TestReception:
    def test_le_stock_monte_et_le_prix_devient_le_cout_moyen(self, magasinier, filtre):
        reponse = recevoir(
            magasinier, filtre, prix_unitaire="2600", fournisseur="CFAO Motors", reference_document="BL-2026-114"
        )

        assert reponse.status_code == 201
        filtre.refresh_from_db()
        assert filtre.quantite_stock == 15
        assert filtre.prix_unitaire == Decimal("2200.00")
        entree = EntreePiece.objects.get()
        assert (entree.recue_par, entree.reference_document, entree.fournisseur) == (magasinier, "BL-2026-114", "CFAO Motors")
        assert reponse.data["recue_par_nom"] == "magasinier_stock" and reponse.data["piece_nom"] == "Filtre à huile"

    def test_sans_prix_le_prix_de_la_piece_ne_bouge_pas(self, magasinier, filtre):
        recevoir(magasinier, filtre)

        filtre.refresh_from_db()
        assert (filtre.quantite_stock, filtre.prix_unitaire) == (15, Decimal("2000"))

    def test_la_reception_est_tracee_au_journal(self, magasinier, filtre):
        recevoir(magasinier, filtre)

        assert JournalAudit.objects.filter(objet_type="maintenance.entreepiece", action="creation", acteur=magasinier).exists()

    @pytest.mark.parametrize("quantite", [0, -3])
    def test_une_quantite_nulle_ou_negative_est_refusee(self, magasinier, filtre, quantite):
        assert recevoir(magasinier, filtre, quantite=quantite).status_code == 400
        filtre.refresh_from_db()
        assert filtre.quantite_stock == 10

    def test_une_piece_d_une_autre_compagnie_est_refusee(self, magasinier, piece_b):
        assert recevoir(magasinier, piece_b).status_code == 400
        piece_b.refresh_from_db()
        assert piece_b.quantite_stock == 5

    def test_une_reception_ne_se_modifie_ni_ne_se_supprime(self, magasinier, filtre):
        entree = recevoir(magasinier, filtre).data

        client = client_de(magasinier)
        assert client.patch(f"/api/entrees-pieces/{entree['id']}/", {"quantite": 50}, format="json").status_code == 405
        assert client.delete(f"/api/entrees-pieces/{entree['id']}/").status_code == 405

    @pytest.mark.parametrize("role", [Role.MECANICIEN, Role.GUICHETIER, Role.DIRECTEUR_FINANCIER, Role.PDG])
    def test_seuls_le_magasin_et_le_technique_recoivent(self, user_factory, company_a, filtre, role):
        assert recevoir(user_factory(f"r_{role}", role, company=company_a), filtre).status_code == 403

    @pytest.mark.parametrize("role", [Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE])
    def test_le_chef_d_atelier_et_le_directeur_technique_recoivent_aussi(self, user_factory, company_a, filtre, role):
        assert recevoir(user_factory(f"r_{role}", role, company=company_a), filtre).status_code == 201

    def test_tous_lisent_les_receptions_de_leur_compagnie_seulement(self, magasinier, filtre, user_factory, company_b, piece_b):
        recevoir(magasinier, filtre)
        etranger = user_factory("mag_b", Role.MAGASINIER, company=company_b)
        recevoir(etranger, piece_b)
        lecteur = user_factory("lecteur", Role.DIRECTEUR_FINANCIER, company=filtre.company)

        vues = client_de(lecteur).get("/api/entrees-pieces/").data
        assert [e["piece_nom"] for e in vues] == ["Filtre à huile"]
        assert client_de(lecteur).get(f"/api/entrees-pieces/?piece={piece_b.id}").data == []


@pytest.mark.django_db
class TestInventaire:
    def test_sans_ecart_pas_besoin_de_motif(self, magasinier, filtre):
        reponse = inventorier(magasinier, filtre, quantite_comptee=10)

        assert reponse.status_code == 201
        assert (reponse.data["quantite_attendue"], reponse.data["ecart"]) == (10, 0)

    def test_un_ecart_exige_son_motif(self, magasinier, filtre):
        reponse = inventorier(magasinier, filtre, quantite_comptee=8)

        assert reponse.status_code == 400
        assert "-2" in str(reponse.data["motif"])
        filtre.refresh_from_db()
        assert filtre.quantite_stock == 10
        assert not InventairePiece.objects.exists()

    def test_le_stock_prend_la_quantite_comptee_et_l_ecart_est_garde(self, magasinier, filtre):
        reponse = inventorier(magasinier, filtre, quantite_comptee=7, motif="Deux filtres abîmés, un perdu")

        assert reponse.status_code == 201
        filtre.refresh_from_db()
        assert filtre.quantite_stock == 7
        inventaire = InventairePiece.objects.get()
        assert (inventaire.quantite_attendue, inventaire.quantite_comptee, inventaire.ecart) == (10, 7, -3)
        assert inventaire.compte_par == magasinier

    def test_un_manque_previent_le_directeur_technique(self, magasinier, filtre):
        inventorier(magasinier, filtre, quantite_comptee=7, motif="Deux filtres abîmés, un perdu")

        alerte = Alerte.objects.get(titre="Écart d'inventaire : Filtre à huile")
        assert alerte.roles_destinataires == ["directeur_technique"]
        assert "3 manquant(s)" in alerte.message

    def test_un_surplus_ne_previent_personne(self, magasinier, filtre):
        inventorier(magasinier, filtre, quantite_comptee=12, motif="Carton retrouvé en réserve")

        assert not Alerte.objects.filter(titre__startswith="Écart d'inventaire").exists()

    def test_passer_sous_le_seuil_previent_comme_une_sortie(self, magasinier, filtre):
        inventorier(magasinier, filtre, quantite_comptee=2, motif="Casse au déchargement")

        assert Alerte.objects.filter(titre="Stock bas : Filtre à huile").exists()

    def test_une_quantite_negative_est_refusee(self, magasinier, filtre):
        assert inventorier(magasinier, filtre, quantite_comptee=-1, motif="Erreur de saisie").status_code == 400

    def test_le_mecanicien_n_inventorie_pas(self, user_factory, company_a, filtre):
        mecanicien = user_factory("meca_stock", Role.MECANICIEN, company=company_a)

        assert inventorier(mecanicien, filtre, quantite_comptee=10).status_code == 403

    def test_le_filtre_par_piece(self, magasinier, filtre, company_a):
        autre = Piece.objects.create(nom="Ampoule", reference="AMP-1", quantite_stock=3, company=company_a)
        inventorier(magasinier, filtre, quantite_comptee=10)
        inventorier(magasinier, autre, quantite_comptee=3)

        assert [i["piece_nom"] for i in client_de(magasinier).get(f"/api/inventaires-pieces/?piece={autre.id}").data] == ["Ampoule"]


@pytest.mark.django_db
class TestHistoriqueDesSorties:
    def test_les_sorties_se_filtrent_par_piece(self, magasinier, filtre, company_a, user_factory):
        from maintenance.models import OrdreReparation, SortiePiece
        from reseau.models import Vehicule

        vehicule = Vehicule.objects.create(immatriculation="CI-9-AB", capacite=50, company=company_a)
        mecanicien = user_factory("meca_historique", Role.MECANICIEN, company=company_a)
        ordre = OrdreReparation.objects.create(vehicule=vehicule, company=company_a, description="Vidange", mecanicien=mecanicien)
        autre = Piece.objects.create(nom="Ampoule", reference="AMP-1", quantite_stock=3, company=company_a)
        SortiePiece.objects.create(ordre_reparation=ordre, piece=filtre, company=company_a, quantite=1)
        SortiePiece.objects.create(ordre_reparation=ordre, piece=autre, company=company_a, quantite=1)

        vues = client_de(magasinier).get(f"/api/sorties-pieces/?piece={filtre.id}").data
        assert [s["piece"] for s in vues] == [filtre.id]
        assert len(client_de(magasinier).get("/api/sorties-pieces/").data) == 2
