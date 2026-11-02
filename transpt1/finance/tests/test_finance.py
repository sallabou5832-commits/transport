"""Finance (cahier des charges : Directeur financier — consolidation des recettes, budget carburant avec alerte de dépassement par
ligne, rentabilité par ligne/gare, paiements fournisseurs et assurances avec échéancier et rappels, trésorerie visible du PDG,
export de reporting)."""

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from billetterie.models import Depart, DepartStatut, ModePaiement, StatutTicket, Ticket
from colis.models import Colis, StatutColis
from core.models import Role
from finance.models import BudgetCarburant, Depense, Facture, Fournisseur
from reseau.models import Gare, Ligne, Vehicule

D = Decimal


def jour(decalage=0):
    return timezone.localdate() + datetime.timedelta(days=decalage)


def mois_courant():
    return jour().replace(day=1)


@pytest.fixture
def equipe(user_factory, company_a):
    return {r: user_factory(f"{r}_fin", Role(r), company=company_a) for r in ("directeur_financier", "pdg", "secretaire_general", "drh", "guichetier", "qhse", "directeur_exploitation", "chef_gare")}


@pytest.fixture
def reseau(company_a):
    adjame = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a)
    yopougon = Gare.objects.create(nom="Yopougon", ville="Abidjan", company=company_a)
    bouake = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a)
    return {
        "adjame": adjame, "yopougon": yopougon,
        "bouake_ligne": Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=adjame, gare_arrivee=bouake, company=company_a),
        "yakro_ligne": Ligne.objects.create(nom="Yopougon-Yakro", gare_depart=yopougon, gare_arrivee=bouake, company=company_a),
    }


def vendre(ligne, guichetier, prix, *, statut=StatutTicket.VALIDE, mode=ModePaiement.ESPECES, decalage=0):
    company = ligne.company
    bus = Vehicule.objects.create(immatriculation=f"CI-FIN-{Vehicule.objects.count()}", capacite=50, company=company)
    depart = Depart.objects.create(ligne=ligne, vehicule=bus, chauffeur=guichetier, company=company, date_heure=timezone.now(), statut=DepartStatut.PLANIFIE)
    ticket = Ticket.objects.create(depart=depart, company=company, passager_nom="P", passager_telephone="+225", prix=prix, mode_paiement=mode, vendu_par=guichetier, statut=statut)
    if decalage:
        Ticket.objects.filter(pk=ticket.pk).update(date_vente=timezone.now() + datetime.timedelta(days=decalage))
    return depart


def expedier(depart, agent, frais, statut=StatutColis.ENREGISTRE):
    return Colis.objects.create(
        company=depart.company, depart=depart, description="Colis", poids_kg=5, frais=frais, statut=statut, mode_paiement=ModePaiement.ESPECES,
        expediteur_nom="E", destinataire_nom="D", destinataire_telephone="07", enregistre_par=agent,
    )


def depenser(api_client, utilisateur, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/depenses/", {"date": jour().isoformat(), "categorie": "carburant", "libelle": "Plein de la semaine", "montant": "50000", **corps}, format="json")


@pytest.mark.django_db
class TestDepenses:
    def test_la_finance_saisit_une_depense(self, api_client, equipe, reseau):
        reponse = depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id)

        assert reponse.status_code == 201
        assert reponse.data["ligne_nom"] == "Adjamé-Bouaké" and reponse.data["categorie_libelle"] == "Carburant"
        assert reponse.data["saisi_par_nom"] == "directeur_financier_fin"
        assert Depense.objects.get().company == equipe["directeur_financier"].company

    @pytest.mark.parametrize("corps", [{"montant": "0"}, {"montant": "-5"}, {"libelle": " "}, {"categorie": "cadeaux"}, {"date": "demain"}])
    def test_les_depenses_invalides_sont_refusees(self, api_client, equipe, corps):
        assert depenser(api_client, equipe["directeur_financier"], **corps).status_code == 400

    def test_une_depense_ne_peut_pas_etre_datee_du_futur(self, api_client, equipe):
        assert depenser(api_client, equipe["directeur_financier"], date=jour(3).isoformat()).status_code == 400

    def test_les_rattachements_doivent_etre_de_la_compagnie(self, api_client, equipe, company_b):
        etrangere = Ligne.objects.create(
            nom="Étrangère", gare_depart=(g := Gare.objects.create(nom="G", ville="V", company=company_b)), gare_arrivee=g, company=company_b
        )
        vehicule = Vehicule.objects.create(immatriculation="CI-ETR-1", capacite=30, company=company_b)

        assert depenser(api_client, equipe["directeur_financier"], ligne=etrangere.id).status_code == 400
        assert depenser(api_client, equipe["directeur_financier"], vehicule=vehicule.id).status_code == 400
        assert depenser(api_client, equipe["directeur_financier"], gare=g.id).status_code == 400

    def test_filtres_par_periode_categorie_et_ligne(self, api_client, equipe, reseau):
        depenser(api_client, equipe["directeur_financier"], libelle="Carburant Bouaké", ligne=reseau["bouake_ligne"].id)
        depenser(api_client, equipe["directeur_financier"], libelle="Vidange", categorie="maintenance", date=jour(-40).isoformat())
        depenser(api_client, equipe["directeur_financier"], libelle="Carburant Yakro", ligne=reseau["yakro_ligne"].id)

        def libelles(requete):
            return {d["libelle"] for d in api_client.get(f"/api/depenses/?{requete}").data}

        assert libelles("categorie=maintenance") == {"Vidange"}
        assert libelles(f"ligne={reseau['yakro_ligne'].id}") == {"Carburant Yakro"}
        assert libelles(f"date_debut={jour(-10)}") == {"Carburant Bouaké", "Carburant Yakro"}
        assert libelles(f"date_fin={jour(-10)}") == {"Vidange"}
        assert len(libelles("")) == 3

    @pytest.mark.parametrize("role", ["pdg", "secretaire_general"])
    def test_le_pdg_et_le_secretaire_general_lisent_sans_ecrire(self, api_client, equipe, role):
        depenser(api_client, equipe["directeur_financier"])

        api_client.force_authenticate(user=equipe[role])
        assert len(api_client.get("/api/depenses/").data) == 1
        assert depenser(api_client, equipe[role]).status_code == 403

    @pytest.mark.parametrize("role", ["drh", "guichetier", "qhse", "directeur_exploitation", "chef_gare"])
    def test_les_autres_postes_n_ont_pas_acces(self, api_client, equipe, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/depenses/").status_code == 403
        assert depenser(api_client, equipe[role]).status_code == 403

    def test_isolation_entre_compagnies(self, api_client, equipe, user_factory, company_b):
        cree = depenser(api_client, equipe["directeur_financier"]).data["id"]
        df_b = user_factory("df_b_fin", Role.DIRECTEUR_FINANCIER, company=company_b)

        api_client.force_authenticate(user=df_b)
        assert api_client.get("/api/depenses/").data == []
        assert api_client.get(f"/api/depenses/{cree}/").status_code == 404
        assert api_client.delete(f"/api/depenses/{cree}/").status_code == 404

    def test_la_depense_se_corrige_et_se_supprime(self, api_client, equipe):
        cree = depenser(api_client, equipe["directeur_financier"]).data["id"]

        assert api_client.patch(f"/api/depenses/{cree}/", {"montant": "60000"}, format="json").data["montant"] == "60000.00"
        assert api_client.delete(f"/api/depenses/{cree}/").status_code == 204

    def test_sans_authentification_rien(self, api_client):
        assert api_client.get("/api/depenses/").status_code == 401


def budgeter(api_client, utilisateur, ligne, montant="100000", mois=None):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/budgets-carburant/", {"ligne": ligne.id, "mois": (mois or mois_courant()).isoformat(), "montant": montant}, format="json")


@pytest.mark.django_db
class TestBudgetCarburant:
    def test_la_finance_fixe_un_budget_par_ligne_et_par_mois(self, api_client, equipe, reseau):
        reponse = budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], mois=jour().replace(day=17))

        assert reponse.status_code == 201 and reponse.data["mois"] == mois_courant().isoformat() and reponse.data["ligne_nom"] == "Adjamé-Bouaké"

    def test_un_seul_budget_par_ligne_et_par_mois(self, api_client, equipe, reseau):
        budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"])

        doublon = budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], mois=jour().replace(day=20))

        assert doublon.status_code == 400 and "déjà un budget" in str(doublon.data)
        assert budgeter(api_client, equipe["directeur_financier"], reseau["yakro_ligne"]).status_code == 201
        assert budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], mois=(mois_courant() - datetime.timedelta(days=1)).replace(day=1)).status_code == 201

    @pytest.mark.parametrize("montant", ["0", "-1", "abc"])
    def test_le_montant_doit_etre_positif(self, api_client, equipe, reseau, montant):
        assert budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], montant=montant).status_code == 400

    def test_le_suivi_donne_prevu_realise_et_etat_par_ligne(self, api_client, equipe, reseau):
        budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], "100000")
        budgeter(api_client, equipe["directeur_financier"], reseau["yakro_ligne"], "100000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="30000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["yakro_ligne"].id, montant="85000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["yakro_ligne"].id, montant="20000", categorie="maintenance")  # pas du carburant

        lignes = {l["nom"]: l for l in api_client.get("/api/finance/budget-carburant/").data["lignes"]}

        assert (lignes["Adjamé-Bouaké"]["etat"], lignes["Adjamé-Bouaké"]["pourcentage"], lignes["Adjamé-Bouaké"]["reste"]) == ("ok", 30, 70000)
        assert (lignes["Yopougon-Yakro"]["etat"], lignes["Yopougon-Yakro"]["realise"]) == ("alerte", 85000)

    def test_un_depassement_est_signale_et_une_ligne_sans_budget_aussi(self, api_client, equipe, reseau):
        budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], "100000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="120000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["yakro_ligne"].id, montant="10000")

        suivi = api_client.get("/api/finance/budget-carburant/").data

        etats = {l["nom"]: l["etat"] for l in suivi["lignes"]}
        assert etats == {"Adjamé-Bouaké": "depasse", "Yopougon-Yakro": "sans_budget"} and suivi["depasses"] == 1

    def test_atteindre_80_pour_cent_alerte_la_finance_et_le_pdg(self, api_client, equipe, reseau):
        budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], "100000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="79000")
        assert not Alerte.objects.filter(type=TypeAlerte.BUDGET).exists()

        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="2000")

        alerte = Alerte.objects.get(type=TypeAlerte.BUDGET)
        assert alerte.titre == "Budget carburant à 80 % : Adjamé-Bouaké" and alerte.gravite == "attention"
        assert set(alerte.roles_destinataires) == {"directeur_financier", "pdg"} and "81 000 FCFA" in alerte.message

    def test_le_depassement_alerte_une_seconde_fois_en_critique_sans_doublon(self, api_client, equipe, reseau):
        budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], "100000")
        for montant in ("85000", "20000", "5000"):
            depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant=montant)

        alertes = list(Alerte.objects.filter(type=TypeAlerte.BUDGET).order_by("id"))

        assert [a.gravite for a in alertes] == ["attention", "critique"]
        assert alertes[1].titre == "Budget carburant dépassé : Adjamé-Bouaké"

    def test_une_depense_hors_carburant_ne_touche_pas_au_budget(self, api_client, equipe, reseau):
        budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], "100000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="500000", categorie="maintenance")

        assert not Alerte.objects.filter(type=TypeAlerte.BUDGET).exists()

    def test_le_passage_automatique_rattrape_un_budget_baisse_apres_coup(self, api_client, equipe, reseau, company_a):
        budgeter(api_client, equipe["directeur_financier"], reseau["bouake_ligne"], "100000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="60000")
        BudgetCarburant.objects.update(montant=D("50000"))

        generer(company_a)

        assert Alerte.objects.get(type=TypeAlerte.BUDGET).gravite == "critique"

    @pytest.mark.parametrize("role", ["pdg", "secretaire_general"])
    def test_le_pdg_lit_le_suivi_sans_fixer_de_budget(self, api_client, equipe, reseau, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/finance/budget-carburant/").status_code == 200
        assert budgeter(api_client, equipe[role], reseau["bouake_ligne"]).status_code == 403


def facturer(api_client, utilisateur, fournisseur, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(
        "/api/factures/",
        {"fournisseur": fournisseur, "libelle": "Pièces de rechange", "montant": "250000", "date_emission": jour(-10).isoformat(), "echeance": jour(20).isoformat(), **corps},
        format="json",
    )


@pytest.fixture
def fournisseur(api_client, equipe):
    api_client.force_authenticate(user=equipe["directeur_financier"])
    return api_client.post("/api/fournisseurs/", {"nom": "Garage Central", "categorie": "Pièces", "telephone": "0700000000"}, format="json").data["id"]


@pytest.mark.django_db
class TestFournisseursEtFactures:
    def test_un_fournisseur_par_nom(self, api_client, equipe, fournisseur):
        assert api_client.post("/api/fournisseurs/", {"nom": "garage central"}, format="json").status_code == 400
        assert api_client.post("/api/fournisseurs/", {"nom": "Total Énergies"}, format="json").status_code == 201

    def test_une_facture_a_payer_a_son_echeance(self, api_client, equipe, fournisseur):
        reponse = facturer(api_client, equipe["directeur_financier"], fournisseur)

        assert reponse.status_code == 201
        assert reponse.data["statut"] == "a_payer" and reponse.data["jours_restants"] == 20 and reponse.data["en_retard"] is False
        assert reponse.data["fournisseur_nom"] == "Garage Central"

    @pytest.mark.parametrize("corps", [{"montant": "0"}, {"echeance": jour(-30).isoformat()}, {"libelle": ""}, {"type": "cadeau"}])
    def test_les_factures_invalides_sont_refusees(self, api_client, equipe, fournisseur, corps):
        assert facturer(api_client, equipe["directeur_financier"], fournisseur, **corps).status_code == 400

    def test_le_statut_ne_se_choisit_pas(self, api_client, equipe, fournisseur):
        reponse = facturer(api_client, equipe["directeur_financier"], fournisseur, statut="payee", payee_le=jour().isoformat())

        assert reponse.status_code == 201 and reponse.data["statut"] == "a_payer" and reponse.data["payee_le"] is None

    def test_payer_enregistre_la_depense_correspondante(self, api_client, equipe, fournisseur):
        facture = facturer(api_client, equipe["directeur_financier"], fournisseur).data["id"]

        reponse = api_client.post(f"/api/factures/{facture}/payer/", {"mode_paiement": "virement"}, format="json")

        assert reponse.status_code == 200 and reponse.data["statut"] == "payee" and reponse.data["payee_le"] == jour().isoformat()
        depense = Depense.objects.get()
        assert (depense.montant, depense.categorie, depense.date) == (D("250000.00"), "fournisseur", jour())
        assert depense.libelle == "Garage Central — Pièces de rechange" and Facture.objects.get().depense == depense

    def test_une_prime_d_assurance_devient_une_depense_d_assurance(self, api_client, equipe, fournisseur):
        facture = facturer(api_client, equipe["directeur_financier"], fournisseur, type="assurance", libelle="Prime flotte").data["id"]

        api_client.post(f"/api/factures/{facture}/payer/", {}, format="json")

        assert Depense.objects.get().categorie == "assurance"

    def test_on_ne_paie_ni_deux_fois_ni_dans_le_futur(self, api_client, equipe, fournisseur):
        facture = facturer(api_client, equipe["directeur_financier"], fournisseur).data["id"]

        assert api_client.post(f"/api/factures/{facture}/payer/", {"date": jour(2).isoformat()}, format="json").status_code == 400
        api_client.post(f"/api/factures/{facture}/payer/", {}, format="json")
        assert api_client.post(f"/api/factures/{facture}/payer/", {}, format="json").status_code == 400
        assert Depense.objects.count() == 1

    def test_annuler_puis_rien_d_autre(self, api_client, equipe, fournisseur):
        facture = facturer(api_client, equipe["directeur_financier"], fournisseur).data["id"]

        assert api_client.post(f"/api/factures/{facture}/annuler/").data["statut"] == "annulee"
        assert api_client.post(f"/api/factures/{facture}/annuler/").status_code == 400
        assert api_client.post(f"/api/factures/{facture}/payer/", {}, format="json").status_code == 400

    def test_une_facture_reglee_ne_se_modifie_ni_ne_se_supprime(self, api_client, equipe, fournisseur):
        facture = facturer(api_client, equipe["directeur_financier"], fournisseur).data["id"]
        api_client.post(f"/api/factures/{facture}/payer/", {}, format="json")

        assert api_client.patch(f"/api/factures/{facture}/", {"montant": "1"}, format="json").status_code == 400
        assert api_client.delete(f"/api/factures/{facture}/").status_code == 400
        assert Facture.objects.filter(pk=facture).exists()

    def test_une_facture_a_payer_se_corrige_et_se_supprime(self, api_client, equipe, fournisseur):
        facture = facturer(api_client, equipe["directeur_financier"], fournisseur).data["id"]

        assert api_client.patch(f"/api/factures/{facture}/", {"montant": "260000"}, format="json").data["montant"] == "260000.00"
        assert api_client.delete(f"/api/factures/{facture}/").status_code == 204

    def test_le_filtre_par_statut(self, api_client, equipe, fournisseur):
        payee = facturer(api_client, equipe["directeur_financier"], fournisseur, libelle="Réglée").data["id"]
        facturer(api_client, equipe["directeur_financier"], fournisseur, libelle="En attente")
        api_client.post(f"/api/factures/{payee}/payer/", {}, format="json")

        assert [f["libelle"] for f in api_client.get("/api/factures/?statut=a_payer").data] == ["En attente"]
        assert [f["libelle"] for f in api_client.get("/api/factures/?statut=payee").data] == ["Réglée"]

    def test_le_fournisseur_d_une_autre_compagnie_est_refuse(self, api_client, equipe, company_b):
        etranger = Fournisseur.objects.create(company=company_b, nom="Étranger")

        assert facturer(api_client, equipe["directeur_financier"], etranger.id).status_code == 400

    @pytest.mark.parametrize("role", ["drh", "guichetier", "qhse", "directeur_exploitation"])
    def test_les_autres_postes_n_ont_pas_acces(self, api_client, equipe, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/factures/").status_code == 403 and api_client.get("/api/fournisseurs/").status_code == 403

    def test_le_pdg_lit_l_echeancier_sans_payer(self, api_client, equipe, fournisseur):
        facture = facturer(api_client, equipe["directeur_financier"], fournisseur).data["id"]

        api_client.force_authenticate(user=equipe["pdg"])
        assert len(api_client.get("/api/factures/").data) == 1
        assert api_client.post(f"/api/factures/{facture}/payer/", {}, format="json").status_code == 403


@pytest.mark.django_db
class TestRappelsDePaiement:
    def echeance(self, api_client, equipe, fournisseur, dans_jours):
        return facturer(api_client, equipe["directeur_financier"], fournisseur, echeance=jour(dans_jours).isoformat(), date_emission=jour(-60).isoformat()).data["id"]

    def test_rappel_a_sept_jours_puis_a_un_jour_puis_en_retard(self, api_client, equipe, fournisseur, company_a):
        self.echeance(api_client, equipe, fournisseur, 7)
        generer(company_a)
        assert Alerte.objects.get(type=TypeAlerte.PAIEMENT).gravite == "attention"

        Facture.objects.update(echeance=jour(1))
        generer(company_a)
        Facture.objects.update(echeance=jour(-3))
        generer(company_a)

        alertes = list(Alerte.objects.filter(type=TypeAlerte.PAIEMENT).order_by("id"))
        assert [a.gravite for a in alertes] == ["attention", "critique", "critique"]
        assert [a.titre.split(" : ")[0] for a in alertes] == ["Paiement à payer dans 7 jour(s)", "Paiement à payer demain", "Paiement en retard de 3 jour(s)"]
        assert all(set(a.roles_destinataires) == {"directeur_financier", "pdg"} for a in alertes)

    def test_relancer_ne_previent_pas_dix_fois(self, api_client, equipe, fournisseur, company_a):
        self.echeance(api_client, equipe, fournisseur, 5)

        generer(company_a)
        generer(company_a)

        assert Alerte.objects.filter(type=TypeAlerte.PAIEMENT).count() == 1

    def test_une_echeance_lointaine_ne_rappelle_rien(self, api_client, equipe, fournisseur, company_a):
        self.echeance(api_client, equipe, fournisseur, 30)

        assert not [a for a in generer(company_a) if a.type == TypeAlerte.PAIEMENT]

    def test_une_facture_payee_ou_annulee_ne_rappelle_plus(self, api_client, equipe, fournisseur, company_a):
        payee = self.echeance(api_client, equipe, fournisseur, -2)
        annulee = self.echeance(api_client, equipe, fournisseur, -2)
        api_client.post(f"/api/factures/{payee}/payer/", {}, format="json")
        api_client.post(f"/api/factures/{annulee}/annuler/")

        assert not [a for a in generer(company_a) if a.type == TypeAlerte.PAIEMENT]


@pytest.mark.django_db
class TestRentabilite:
    def rentabilite(self, api_client, utilisateur, requete=""):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get(f"/api/finance/rentabilite/?{requete}")

    def test_recettes_contre_depenses_par_ligne_et_par_gare(self, api_client, equipe, reseau):
        guichetier = equipe["guichetier"]
        depart = vendre(reseau["bouake_ligne"], guichetier, 10000)
        vendre(reseau["bouake_ligne"], guichetier, 5000, mode=ModePaiement.MOBILE_MONEY)
        vendre(reseau["yakro_ligne"], guichetier, 4000)
        expedier(depart, guichetier, 3000)
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="6000")
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="2000", categorie="maintenance")
        depenser(api_client, equipe["directeur_financier"], gare=reseau["yopougon"].id, montant="1000", categorie="autre")

        donnees = self.rentabilite(api_client, equipe["directeur_financier"]).data

        bouake = next(l for l in donnees["lignes"] if l["nom"] == "Adjamé-Bouaké")
        assert (bouake["billets"], bouake["fret"], bouake["recettes"], bouake["depenses"], bouake["marge"]) == (15000, 3000, 18000, 8000, 10000)
        assert bouake["taux_marge_pourcent"] == 56 and bouake["depenses_par_categorie"] == {"carburant": 6000, "maintenance": 2000}
        yakro = next(l for l in donnees["lignes"] if l["nom"] == "Yopougon-Yakro")
        assert (yakro["recettes"], yakro["depenses"], yakro["marge"]) == (4000, 0, 4000)
        gares = {g["nom"]: g for g in donnees["gares"]}
        assert (gares["Adjamé"]["recettes"], gares["Adjamé"]["depenses"]) == (18000, 8000)
        assert (gares["Yopougon"]["recettes"], gares["Yopougon"]["depenses"]) == (4000, 1000)

    def test_les_charges_communes_pesent_sur_le_total_pas_sur_une_ligne(self, api_client, equipe, reseau):
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 10000)
        depenser(api_client, equipe["directeur_financier"], categorie="salaires", libelle="Salaires du mois", montant="4000")

        donnees = self.rentabilite(api_client, equipe["directeur_financier"]).data

        assert donnees["charges_communes"] == 4000
        assert donnees["lignes"][0]["depenses"] == 0
        assert (donnees["total"]["recettes"], donnees["total"]["depenses"], donnees["total"]["marge"], donnees["total"]["taux_marge_pourcent"]) == (10000, 4000, 6000, 60)

    def test_les_lignes_sont_classees_par_marge_decroissante(self, api_client, equipe, reseau):
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 5000)
        vendre(reseau["yakro_ligne"], equipe["guichetier"], 9000)

        assert [l["nom"] for l in self.rentabilite(api_client, equipe["directeur_financier"]).data["lignes"]] == ["Yopougon-Yakro", "Adjamé-Bouaké"]

    def test_un_billet_annule_un_colis_annule_et_une_autre_periode_sont_exclus(self, api_client, equipe, reseau):
        guichetier = equipe["guichetier"]
        depart = vendre(reseau["bouake_ligne"], guichetier, 5000)
        vendre(reseau["bouake_ligne"], guichetier, 9000, statut=StatutTicket.ANNULE)
        vendre(reseau["bouake_ligne"], guichetier, 7000, decalage=-40)
        expedier(depart, guichetier, 4000, statut=StatutColis.ANNULE)

        donnees = self.rentabilite(api_client, equipe["directeur_financier"]).data

        assert donnees["total"]["recettes"] == 5000

    def test_la_periode_se_choisit(self, api_client, equipe, reseau):
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 7000, decalage=-40)

        vide = self.rentabilite(api_client, equipe["directeur_financier"]).data
        ancienne = self.rentabilite(api_client, equipe["directeur_financier"], f"date_debut={jour(-60)}&date_fin={jour(-20)}").data

        assert vide["total"]["recettes"] == 0 and vide["lignes"] == []
        assert ancienne["total"]["recettes"] == 7000

    def test_une_periode_a_l_envers_est_refusee(self, api_client, equipe):
        assert self.rentabilite(api_client, equipe["directeur_financier"], f"date_debut={jour()}&date_fin={jour(-5)}").status_code == 400

    def test_une_autre_compagnie_n_apparait_pas(self, api_client, equipe, reseau, user_factory, company_b):
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 5000)
        df_b = user_factory("df_b_rent", Role.DIRECTEUR_FINANCIER, company=company_b)

        assert self.rentabilite(api_client, df_b).data["total"]["recettes"] == 0

    @pytest.mark.parametrize("role", ["directeur_financier", "pdg", "secretaire_general"])
    def test_finance_et_direction_lisent_la_rentabilite(self, api_client, equipe, role):
        assert self.rentabilite(api_client, equipe[role]).status_code == 200

    @pytest.mark.parametrize("role", ["drh", "guichetier", "qhse", "directeur_exploitation"])
    def test_les_autres_postes_ne_la_lisent_pas(self, api_client, equipe, role):
        assert self.rentabilite(api_client, equipe[role]).status_code == 403


@pytest.mark.django_db
class TestTresorerie:
    def tresorerie(self, api_client, utilisateur):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get("/api/finance/tresorerie/")

    def test_solde_initial_plus_encaissements_moins_depenses(self, api_client, equipe, reseau):
        api_client.force_authenticate(user=equipe["directeur_financier"])
        assert api_client.put("/api/finance/configuration/", {"solde_initial": "1000000"}, format="json").status_code == 200
        depart = vendre(reseau["bouake_ligne"], equipe["guichetier"], 10000)
        expedier(depart, equipe["guichetier"], 2000)
        depenser(api_client, equipe["directeur_financier"], montant="4000")

        donnees = self.tresorerie(api_client, equipe["directeur_financier"]).data

        assert donnees["solde_initial"] == 1000000 and donnees["solde"] == 1008000
        assert (donnees["mois"]["encaissements"], donnees["mois"]["decaissements"]) == (12000, 4000)

    def test_ce_qui_reste_a_payer_et_le_solde_previsionnel(self, api_client, equipe, fournisseur, reseau):
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 100000)
        facturer(api_client, equipe["directeur_financier"], fournisseur, montant="30000", echeance=jour(3).isoformat(), libelle="Dans 3 jours")
        facturer(api_client, equipe["directeur_financier"], fournisseur, montant="20000", echeance=jour(25).isoformat(), libelle="Dans 25 jours")
        facturer(api_client, equipe["directeur_financier"], fournisseur, montant="9000", echeance=jour(60).isoformat(), libelle="Plus tard", date_emission=jour(-1).isoformat())
        retard = facturer(api_client, equipe["directeur_financier"], fournisseur, montant="5000", echeance=jour(-2).isoformat(), date_emission=jour(-30).isoformat(), libelle="En retard").data["id"]
        payee = facturer(api_client, equipe["directeur_financier"], fournisseur, montant="7000", echeance=jour(2).isoformat(), libelle="Déjà payée").data["id"]
        api_client.post(f"/api/factures/{payee}/payer/", {}, format="json")

        donnees = self.tresorerie(api_client, equipe["directeur_financier"]).data

        assert donnees["a_payer"]["en_retard"] == 5000 and donnees["a_payer"]["factures_en_retard"] == 1
        assert donnees["a_payer"]["sous_7_jours"] == 30000 and donnees["a_payer"]["sous_30_jours"] == 50000 and donnees["a_payer"]["factures_sous_30_jours"] == 2
        # 100 000 encaissés, 7 000 déjà payés : 93 000 en caisse ; 5 000 + 50 000 à payer d'ici 30 jours.
        assert donnees["solde"] == 93000 and donnees["solde_previsionnel_30_jours"] == 38000
        assert retard

    def test_la_serie_couvre_les_trente_derniers_jours(self, api_client, equipe, reseau):
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 8000)
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 3000, decalage=-3)

        serie = self.tresorerie(api_client, equipe["directeur_financier"]).data["serie_30_jours"]

        assert len(serie) == 30 and serie[-1]["date"] == jour() and serie[-1]["encaissements"] == 8000
        assert serie[-4]["encaissements"] == 3000 and serie[0]["encaissements"] == 0

    def test_sans_reglage_le_solde_de_depart_est_nul(self, api_client, equipe):
        assert self.tresorerie(api_client, equipe["directeur_financier"]).data["solde_initial"] == 0

    @pytest.mark.parametrize("role", ["directeur_financier", "pdg", "secretaire_general"])
    def test_la_tresorerie_est_visible_de_la_finance_et_du_pdg(self, api_client, equipe, role):
        assert self.tresorerie(api_client, equipe[role]).status_code == 200

    @pytest.mark.parametrize("role", ["drh", "guichetier", "qhse"])
    def test_pas_pour_les_autres(self, api_client, equipe, role):
        assert self.tresorerie(api_client, equipe[role]).status_code == 403

    def test_seule_la_finance_regle_le_solde_de_depart(self, api_client, equipe):
        api_client.force_authenticate(user=equipe["pdg"])

        assert api_client.get("/api/finance/configuration/").data["solde_initial"] == "0.00"
        assert api_client.put("/api/finance/configuration/", {"solde_initial": "5"}, format="json").status_code == 403


@pytest.mark.django_db
class TestExport:
    def exporter(self, api_client, utilisateur, **params):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get("/api/finance/export/", params)

    def lignes(self, reponse):
        texte = reponse.content.decode("utf-8")
        assert texte.startswith("﻿"), "signature UTF-8 pour Excel"
        return [ligne.split(";") for ligne in texte.lstrip("﻿").strip().splitlines()]

    def test_la_rentabilite_s_exporte_en_csv_pour_excel(self, api_client, equipe, reseau):
        vendre(reseau["bouake_ligne"], equipe["guichetier"], 10000)
        depenser(api_client, equipe["directeur_financier"], ligne=reseau["bouake_ligne"].id, montant="2500")

        reponse = self.exporter(api_client, equipe["directeur_financier"], type="rentabilite")

        assert reponse.status_code == 200 and reponse["Content-Type"].startswith("text/csv")
        assert reponse["Content-Disposition"].startswith('attachment; filename="rentabilite-')
        lignes = self.lignes(reponse)
        assert lignes[0][:2] == ["Ligne", "Gare de départ"]
        assert lignes[1][:7] == ["Adjamé-Bouaké", "Adjamé", "10000,00", "0,00", "10000,00", "2500,00", "7500,00"]
        assert lignes[-1][0] == "TOTAL" and lignes[-1][4:7] == ["10000,00", "2500,00", "7500,00"]

    def test_les_depenses_les_factures_et_la_tresorerie_s_exportent(self, api_client, equipe, fournisseur):
        depenser(api_client, equipe["directeur_financier"], libelle="Gasoil", montant="1500.50")
        facturer(api_client, equipe["directeur_financier"], fournisseur, echeance=jour(5).isoformat())

        depenses = self.lignes(self.exporter(api_client, equipe["directeur_financier"], type="depenses"))
        factures = self.lignes(self.exporter(api_client, equipe["directeur_financier"], type="factures", date_fin=jour(30).isoformat()))
        tresorerie = self.lignes(self.exporter(api_client, equipe["directeur_financier"], type="tresorerie"))

        assert depenses[0] == ["Date", "Catégorie", "Libellé", "Montant", "Ligne", "Véhicule", "Gare"] and depenses[1][2:4] == ["Gasoil", "1500,50"]
        assert factures[1][:2] == ["Garage Central", "Fournisseur"] and factures[1][4] == "250000,00" and factures[1][7] == "À payer"
        assert tresorerie[0] == ["Date", "Encaissements", "Décaissements", "Net"] and tresorerie[-1][1:] == ["0,00", "1500,50", "-1500,50"]

    def test_un_type_inconnu_ou_absent_est_refuse(self, api_client, equipe):
        assert self.exporter(api_client, equipe["directeur_financier"], type="secret").status_code == 400
        assert self.exporter(api_client, equipe["directeur_financier"]).status_code == 400

    @pytest.mark.parametrize("role", ["pdg", "secretaire_general"])
    def test_la_direction_peut_exporter(self, api_client, equipe, role):
        assert self.exporter(api_client, equipe[role], type="rentabilite").status_code == 200

    @pytest.mark.parametrize("role", ["drh", "guichetier", "qhse"])
    def test_les_autres_postes_ne_peuvent_pas_exporter(self, api_client, equipe, role):
        assert self.exporter(api_client, equipe[role], type="rentabilite").status_code == 403

    def test_les_donnees_d_une_autre_compagnie_ne_sortent_pas(self, api_client, equipe, user_factory, company_b):
        depenser(api_client, equipe["directeur_financier"], libelle="Secret de A")
        df_b = user_factory("df_b_exp", Role.DIRECTEUR_FINANCIER, company=company_b)

        assert "Secret de A" not in self.exporter(api_client, df_b, type="depenses").content.decode("utf-8")

    def test_un_texte_qui_ressemble_a_une_formule_n_est_pas_execute_par_excel(self, api_client, equipe):
        df = equipe["directeur_financier"]
        depenser(api_client, df, libelle="=2+5", montant="1500.50")
        depenser(api_client, df, libelle="-Remise exceptionnelle", montant="100")
        piege = api_client.post("/api/fournisseurs/", {"nom": "@SOMME(A1:A9)", "categorie": "Pièces"}, format="json").data["id"]
        facturer(api_client, df, piege, echeance=jour(5).isoformat(), reference="+225 07 00")

        depenses = self.lignes(self.exporter(api_client, df, type="depenses"))
        factures = self.lignes(self.exporter(api_client, df, type="factures", date_fin=jour(30).isoformat()))
        tresorerie = self.lignes(self.exporter(api_client, df, type="tresorerie"))

        assert sorted(ligne[2] for ligne in depenses[1:]) == ["'-Remise exceptionnelle", "'=2+5"]
        assert factures[1][0] == "'@SOMME(A1:A9)" and factures[1][2] == "'+225 07 00"
        # Les montants, même négatifs, restent des nombres pour Excel.
        assert tresorerie[-1][1:] == ["0,00", "1600,50", "-1600,50"]
