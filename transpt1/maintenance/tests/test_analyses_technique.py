"""Ce que la maintenance dit de la flotte : fiche véhicule complète (historique, pannes récurrentes, pièces montées), suggestion de
commande de réapprovisionnement, rapport de besoin de renouvellement pour la Direction Générale."""

import datetime

import pytest
from django.utils import timezone

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from core.models import Role
from maintenance.models import OrdreReparation, Piece, SortiePiece, StatutOrdreReparation
from personnel_roulant.models import GraviteIncident, Incident, StatutIncident, TypeIncident
from reseau.models import Vehicule

pytestmark = pytest.mark.django_db


def il_y_a(jours):
    return timezone.now() - datetime.timedelta(days=jours)


def sortir(ordre, piece, quantite=1, *, jours=0):
    sortie = SortiePiece.objects.create(ordre_reparation=ordre, piece=piece, company=ordre.company, quantite=quantite)
    SortiePiece.objects.filter(pk=sortie.pk).update(date=il_y_a(jours))
    return sortie


def ouvrir(vehicule, mecanicien, description="Réparation", *, jours=0, duree_jours=None, statut=StatutOrdreReparation.TERMINE):
    """Un ordre ouvert il y a `jours` jours, et clos `duree_jours` plus tard (sans durée : encore ouvert)."""
    ordre = OrdreReparation.objects.create(vehicule=vehicule, company=vehicule.company, description=description, mecanicien=mecanicien)
    ouverture = il_y_a(jours)
    cloture = ouverture + datetime.timedelta(days=duree_jours) if duree_jours is not None else None
    OrdreReparation.objects.filter(pk=ordre.pk).update(
        date_creation=ouverture, date_cloture=cloture, statut=statut if duree_jours is not None else StatutOrdreReparation.EN_COURS
    )
    ordre.refresh_from_db()
    return ordre


class TestFicheVehicule:
    def fiche(self, api_client, utilisateur, vehicule):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get(f"/api/fiche-vehicule/{vehicule.id}/")

    def test_la_fiche_reunit_l_identite_les_ordres_et_les_indicateurs(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a):
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=123456)
        vehicule_a.refresh_from_db()
        ouvrir(vehicule_a, mecanicien_a, "Boîte de vitesses", jours=40, duree_jours=5)

        fiche = self.fiche(api_client, directeur_technique_a, vehicule_a).data

        assert fiche["vehicule"]["immatriculation"] == "CI-3000-AA" and fiche["vehicule"]["kilometrage"] == 123456
        assert [o["description"] for o in fiche["ordres"]] == ["Boîte de vitesses"] and fiche["ordres"][0]["mecanicien_nom"] == "mecanicien_a"
        assert fiche["indicateurs"]["ordres_12_mois"] == 1 and fiche["indicateurs"]["jours_immobilise_12_mois"] == 5

    def test_les_pieces_montees_sont_totalisees_par_piece(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a, piece_a, piece_basse_a):
        premier, second = ouvrir(vehicule_a, mecanicien_a, "Freins", jours=60, duree_jours=1), ouvrir(vehicule_a, mecanicien_a, "Freins 2", jours=20, duree_jours=1)
        sortir(premier, piece_a, 2, jours=60)
        sortir(second, piece_a, 3, jours=20)
        sortir(second, piece_basse_a, 1, jours=20)

        pieces = self.fiche(api_client, directeur_technique_a, vehicule_a).data["pieces_montees"]

        assert [(p["nom"], p["quantite"], p["interventions"]) for p in pieces] == [("Plaquette de frein", 5, 2), ("Filtre à huile", 1, 1)]

    def test_une_piece_remplacee_deux_fois_en_six_mois_signale_une_panne_recurrente(
        self, api_client, directeur_technique_a, vehicule_a, mecanicien_a, piece_a, piece_basse_a
    ):
        premier, second = ouvrir(vehicule_a, mecanicien_a, "Freins", jours=100, duree_jours=1), ouvrir(vehicule_a, mecanicien_a, "Freins bis", jours=10, duree_jours=1)
        sortir(premier, piece_a, jours=100)
        sortir(second, piece_a, jours=10)
        sortir(second, piece_basse_a, jours=10)

        recurrentes = self.fiche(api_client, directeur_technique_a, vehicule_a).data["pannes_recurrentes"]

        assert [(r["nom"], r["interventions"]) for r in recurrentes] == [("Plaquette de frein", 2)]

    def test_deux_remplacements_trop_espaces_ne_sont_pas_une_recurrence(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a, piece_a):
        premier, second = ouvrir(vehicule_a, mecanicien_a, "Freins", jours=400, duree_jours=1), ouvrir(vehicule_a, mecanicien_a, "Freins bis", jours=10, duree_jours=1)
        sortir(premier, piece_a, jours=400)
        sortir(second, piece_a, jours=10)

        assert self.fiche(api_client, directeur_technique_a, vehicule_a).data["pannes_recurrentes"] == []

    def test_les_pannes_declarees_par_les_chauffeurs_sont_comptees(self, api_client, directeur_technique_a, vehicule_a, user_factory, company_a):
        chauffeur = user_factory("chauffeur_fiche", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
        for jours in (5, 30, 200):
            incident = Incident.objects.create(
                vehicule=vehicule_a, chauffeur=chauffeur, company=company_a, type_incident=TypeIncident.PANNE,
                description="Panne", gravite=GraviteIncident.MOYENNE, statut=StatutIncident.OUVERT,
            )
            Incident.objects.filter(pk=incident.pk).update(date=il_y_a(jours))

        assert self.fiche(api_client, directeur_technique_a, vehicule_a).data["indicateurs"]["pannes_declarees_90_jours"] == 2

    def test_les_entretiens_a_venir_figurent_sur_la_fiche(self, api_client, directeur_technique_a, vehicule_a):
        from maintenance.models import PlanEntretien

        PlanEntretien.objects.create(
            vehicule=vehicule_a, company=vehicule_a.company, libelle="Vidange", periodicite_jours=30,
            derniere_date=timezone.localdate() - datetime.timedelta(days=25),
        )

        plans = self.fiche(api_client, directeur_technique_a, vehicule_a).data["plans_entretien"]

        assert [(p["libelle"], p["etat"], p["jours_restants"]) for p in plans] == [("Vidange", "bientot", 5)]

    def test_les_jours_d_immobilisation_ne_comptent_pas_deux_fois_les_ordres_qui_se_chevauchent(
        self, api_client, directeur_technique_a, vehicule_a, mecanicien_a
    ):
        ouvrir(vehicule_a, mecanicien_a, "A", jours=50, duree_jours=10)  # du J-50 au J-40
        ouvrir(vehicule_a, mecanicien_a, "B", jours=45, duree_jours=10)  # du J-45 au J-35 : chevauche A
        ouvrir(vehicule_a, mecanicien_a, "C", jours=20, duree_jours=2)  # du J-20 au J-18

        assert self.fiche(api_client, directeur_technique_a, vehicule_a).data["indicateurs"]["jours_immobilise_12_mois"] == 17

    def test_un_ordre_encore_ouvert_immobilise_jusqu_a_aujourd_hui(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a):
        ouvrir(vehicule_a, mecanicien_a, "En cours", jours=6)

        assert self.fiche(api_client, directeur_technique_a, vehicule_a).data["indicateurs"]["jours_immobilise_12_mois"] == 6

    @pytest.mark.parametrize(
        "role", ["directeur_technique", "chef_atelier", "mecanicien", "magasinier", "directeur_exploitation", "pdg", "secretaire_general", "qhse"]
    )
    def test_les_postes_concernes_lisent_la_fiche(self, api_client, vehicule_a, user_factory, company_a, role):
        assert self.fiche(api_client, user_factory(f"{role}_fiche", Role(role), company=company_a), vehicule_a).status_code == 200

    @pytest.mark.parametrize("role", ["guichetier", "drh", "directeur_financier", "chauffeur_principal"])
    def test_les_autres_ne_lisent_pas_la_fiche(self, api_client, vehicule_a, user_factory, company_a, role):
        assert self.fiche(api_client, user_factory(f"{role}_fiche", Role(role), company=company_a), vehicule_a).status_code == 403

    def test_le_vehicule_d_une_autre_compagnie_est_introuvable(self, api_client, directeur_technique_a, company_b):
        etranger = Vehicule.objects.create(immatriculation="CI-B-FICHE", capacite=40, company=company_b)

        assert self.fiche(api_client, directeur_technique_a, etranger).status_code == 404


class TestSuggestionsDeCommande:
    URL = "/api/pieces/suggestions-commande/"

    def suggestions(self, api_client, utilisateur):
        api_client.force_authenticate(user=utilisateur)
        return {s["nom"]: s for s in api_client.get(self.URL).data}

    def test_une_piece_sous_son_seuil_est_a_commander(self, api_client, magasinier_a, piece_basse_a):
        suggestion = self.suggestions(api_client, magasinier_a)["Filtre à huile"]

        assert suggestion["degre"] == "critique" and suggestion["quantite_stock"] == 2 and suggestion["jours_restants"] is None
        # Aucune consommation connue : on reconstitue le stock de sécurité (seuil 5 - stock 2).
        assert suggestion["quantite_suggeree"] == 3

    def test_une_piece_en_rupture_est_en_tete(self, api_client, magasinier_a, piece_basse_a, piece_a):
        Piece.objects.filter(pk=piece_a.pk).update(quantite_stock=0)
        api_client.force_authenticate(user=magasinier_a)

        assert [s["nom"] for s in api_client.get(self.URL).data] == ["Plaquette de frein", "Filtre à huile"]
        assert api_client.get(self.URL).data[0]["degre"] == "rupture"

    def test_la_consommation_des_90_derniers_jours_fixe_le_rythme_et_la_quantite(self, api_client, magasinier_a, vehicule_a, mecanicien_a, piece_a):
        ordre = ouvrir(vehicule_a, mecanicien_a, jours=30, duree_jours=1)
        sortir(ordre, piece_a, 45, jours=30)  # 45 pièces sur 90 jours = 0,5 par jour
        Piece.objects.filter(pk=piece_a.pk).update(quantite_stock=10, seuil_alerte=2)  # 20 jours de stock : proche de la rupture

        suggestion = self.suggestions(api_client, magasinier_a)["Plaquette de frein"]

        assert suggestion["consommation_90_jours"] == 45 and suggestion["consommation_par_jour"] == 0.5
        assert suggestion["jours_restants"] == 20.0 and suggestion["degre"] == "a_prevoir"
        # Deux mois de consommation (30) + stock de sécurité (2) - stock actuel (10).
        assert suggestion["quantite_suggeree"] == 22

    def test_moins_d_une_semaine_de_stock_est_critique(self, api_client, magasinier_a, vehicule_a, mecanicien_a, piece_a):
        ordre = ouvrir(vehicule_a, mecanicien_a, jours=30, duree_jours=1)
        sortir(ordre, piece_a, 90, jours=30)  # 1 par jour
        Piece.objects.filter(pk=piece_a.pk).update(quantite_stock=6, seuil_alerte=2)

        assert self.suggestions(api_client, magasinier_a)["Plaquette de frein"]["degre"] == "critique"

    def test_une_consommation_ancienne_ne_compte_pas(self, api_client, magasinier_a, vehicule_a, mecanicien_a, piece_a):
        ordre = ouvrir(vehicule_a, mecanicien_a, jours=200, duree_jours=1)
        sortir(ordre, piece_a, 500, jours=200)

        assert "Plaquette de frein" not in self.suggestions(api_client, magasinier_a)

    def test_une_piece_bien_approvisionnee_n_est_pas_suggeree(self, api_client, magasinier_a, piece_a):
        assert self.suggestions(api_client, magasinier_a) == {}

    def test_les_plus_proches_de_la_rupture_passent_d_abord(self, api_client, magasinier_a, vehicule_a, mecanicien_a, company_a):
        ordre = ouvrir(vehicule_a, mecanicien_a, jours=30, duree_jours=1)
        lente = Piece.objects.create(nom="Lente", reference="L-1", quantite_stock=20, seuil_alerte=1, company=company_a)
        rapide = Piece.objects.create(nom="Rapide", reference="R-1", quantite_stock=20, seuil_alerte=1, company=company_a)
        sortir(ordre, lente, 45, jours=30)  # 0,5 / jour : 40 jours de stock, hors horizon
        sortir(ordre, rapide, 90, jours=30)  # 1 / jour : 20 jours de stock

        assert list(self.suggestions(api_client, magasinier_a)) == ["Rapide"]

    @pytest.mark.parametrize("role", ["magasinier_a", "directeur_technique_a", "chef_atelier_a"])
    def test_le_magasin_et_le_technique_voient_les_suggestions(self, api_client, request, role):
        api_client.force_authenticate(user=request.getfixturevalue(role))

        assert api_client.get(self.URL).status_code == 200

    @pytest.mark.parametrize("role", ["mecanicien_a"])
    def test_les_autres_ne_les_voient_pas(self, api_client, request, role):
        api_client.force_authenticate(user=request.getfixturevalue(role))

        assert api_client.get(self.URL).status_code == 403


class TestBesoinDeRenouvellement:
    URL = "/api/maintenance/besoin-renouvellement/"

    @pytest.fixture(autouse=True)
    def seuils(self, settings):
        settings.RENOUVELLEMENT_KM = 500000
        settings.RENOUVELLEMENT_ORDRES_12_MOIS = 3
        settings.RENOUVELLEMENT_JOURS_IMMOBILISE_12_MOIS = 30

    def rapport(self, api_client, utilisateur):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get(self.URL).data

    def test_un_seul_seuil_atteint_place_le_vehicule_sous_surveillance(self, api_client, directeur_technique_a, vehicule_a):
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=520000)

        rapport = self.rapport(api_client, directeur_technique_a)

        (vehicule,) = rapport["vehicules"]
        assert vehicule["recommandation"] == "a_surveiller" and vehicule["immatriculation"] == "CI-3000-AA"
        assert "520 000 km au compteur" in vehicule["raisons"][0]
        assert (rapport["a_renouveler"], rapport["a_surveiller"], rapport["flotte"]) == (0, 1, 1)

    def test_deux_seuils_atteints_recommandent_le_renouvellement(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a):
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=520000)
        for i in range(3):
            ouvrir(vehicule_a, mecanicien_a, f"Panne {i}", jours=100 - 30 * i, duree_jours=2)

        (vehicule,) = self.rapport(api_client, directeur_technique_a)["vehicules"]

        assert vehicule["recommandation"] == "a_renouveler" and len(vehicule["raisons"]) == 2
        assert vehicule["ordres_12_mois"] == 3 and vehicule["kilometrage"] == 520000

    def test_l_immobilisation_prolongee_est_un_critere(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a):
        ouvrir(vehicule_a, mecanicien_a, "Moteur", jours=60, duree_jours=35)

        (vehicule,) = self.rapport(api_client, directeur_technique_a)["vehicules"]

        assert vehicule["jours_immobilise_12_mois"] == 35 and "35 jours d'immobilisation" in vehicule["raisons"][0]

    def test_un_vehicule_sain_ne_figure_pas_au_rapport(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a):
        ouvrir(vehicule_a, mecanicien_a, "Vidange", jours=10, duree_jours=1)

        rapport = self.rapport(api_client, directeur_technique_a)

        assert rapport["vehicules"] == [] and rapport["flotte"] == 1

    def test_les_ordres_vieux_de_plus_d_un_an_ne_comptent_pas(self, api_client, directeur_technique_a, vehicule_a, mecanicien_a):
        for i in range(5):
            ouvrir(vehicule_a, mecanicien_a, f"Ancien {i}", jours=400 + i, duree_jours=2)

        assert self.rapport(api_client, directeur_technique_a)["vehicules"] == []

    def test_les_vehicules_a_renouveler_passent_avant_ceux_a_surveiller(self, api_client, directeur_technique_a, vehicule_a, company_a):
        surveille = Vehicule.objects.create(immatriculation="CI-3500-AA", capacite=30, company=company_a, kilometrage=900000)
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=510000)
        for i in range(3):
            ouvrir(vehicule_a, directeur_technique_a, f"Panne {i}", jours=50 + i, duree_jours=1)

        vehicules = self.rapport(api_client, directeur_technique_a)["vehicules"]

        assert [v["recommandation"] for v in vehicules] == ["a_renouveler", "a_surveiller"] and vehicules[1]["id"] == surveille.id

    def test_les_criteres_appliques_sont_indiques(self, api_client, directeur_technique_a):
        assert self.rapport(api_client, directeur_technique_a)["criteres"] == {
            "kilometrage": 500000, "ordres_12_mois": 3, "jours_immobilise_12_mois": 30,
        }

    @pytest.mark.parametrize("role", ["directeur_technique", "pdg", "secretaire_general", "directeur_exploitation", "directeur_financier"])
    def test_la_direction_et_le_technique_lisent_le_rapport(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_renouv", Role(role), company=company_a))

        assert api_client.get(self.URL).status_code == 200

    @pytest.mark.parametrize("role", ["chef_atelier", "mecanicien", "guichetier", "qhse", "drh"])
    def test_les_autres_ne_lisent_pas_le_rapport(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_renouv", Role(role), company=company_a))

        assert api_client.get(self.URL).status_code == 403

    def test_le_rapport_ne_contient_que_la_compagnie(self, api_client, directeur_technique_a, company_b):
        Vehicule.objects.create(immatriculation="CI-B-USE", capacite=40, company=company_b, kilometrage=900000)

        rapport = self.rapport(api_client, directeur_technique_a)

        assert rapport["vehicules"] == [] and rapport["flotte"] == 0

    def test_un_vehicule_a_renouveler_previent_la_direction_une_fois_par_trimestre(
        self, api_client, vehicule_a, mecanicien_a, company_a
    ):
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=520000)
        for i in range(3):
            ouvrir(vehicule_a, mecanicien_a, f"Panne {i}", jours=100 - 30 * i, duree_jours=2)

        generer(company_a)
        generer(company_a)

        alerte = Alerte.objects.get(type=TypeAlerte.RENOUVELLEMENT)
        assert alerte.titre == "Renouvellement à envisager : CI-3000-AA"
        assert set(alerte.roles_destinataires) == {Role.PDG, Role.DIRECTEUR_TECHNIQUE} and "520 000 km" in alerte.message

    def test_un_vehicule_seulement_a_surveiller_ne_previent_pas(self, vehicule_a, company_a):
        Vehicule.objects.filter(pk=vehicule_a.pk).update(kilometrage=520000)

        generer(company_a)

        assert not Alerte.objects.filter(type=TypeAlerte.RENOUVELLEMENT).exists()


class TestKilometrage:
    def test_le_technique_releve_le_kilometrage_du_vehicule(self, api_client, directeur_technique_a, vehicule_a):
        api_client.force_authenticate(user=directeur_technique_a)

        reponse = api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"kilometrage": 87500}, format="json")

        assert reponse.status_code == 200 and reponse.data["kilometrage"] == 87500

    def test_un_guichetier_ne_le_change_pas(self, api_client, user_factory, company_a, vehicule_a):
        api_client.force_authenticate(user=user_factory("guichetier_km", Role.GUICHETIER, company=company_a))

        assert api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"kilometrage": 1}, format="json").status_code == 403

    def test_le_kilometrage_ne_peut_pas_etre_negatif(self, api_client, directeur_technique_a, vehicule_a):
        api_client.force_authenticate(user=directeur_technique_a)

        assert api_client.patch(f"/api/vehicules/{vehicule_a.id}/", {"kilometrage": -5}, format="json").status_code == 400
