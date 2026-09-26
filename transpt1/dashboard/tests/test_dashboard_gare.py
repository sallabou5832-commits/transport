"""« Santé de la gare » du chef de gare (cahier des charges : ponctualité, remplissage, incidents, recettes du jour calculées
automatiquement depuis la billetterie) : `/api/dashboard/gare/`."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, StatutTicket, Ticket
from colis.models import Colis, StatutColis
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute, GraviteIncident, Incident, StatutIncident, TypeIncident
from reseau.models import AffectationGare, Gare, Ligne, Vehicule

URL = "/api/dashboard/gare/"


@pytest.fixture(autouse=True)
def pas_trop_pres_de_minuit():
    local = timezone.localtime()
    if local.hour == 0 and local.minute < 25:
        pytest.skip("trop près de minuit : les départs « du jour » de ce scénario ne seraient pas encore en retard")


@pytest.fixture
def monde(user_factory, company_a):
    chef = user_factory("chef_sante_gare", Role.CHEF_GARE, company=company_a)
    gare = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=chef)
    voisine = Gare.objects.create(nom="Yopougon", ville="Abidjan", company=company_a)
    arrivee = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=gare, gare_arrivee=arrivee, company=company_a)
    ligne_voisine = Ligne.objects.create(nom="Yopougon-Bouaké", gare_depart=voisine, gare_arrivee=arrivee, company=company_a)
    chauffeur = user_factory("chauffeur_sante", Role.CHAUFFEUR_PRINCIPAL, company=company_a, first_name="Awa", last_name="Kone")
    guichetier = user_factory("guichetier_sante", Role.GUICHETIER, company=company_a)
    bagagiste = user_factory("bagagiste_sante", Role.BAGAGISTE, company=company_a)
    debut = timezone.localtime().replace(hour=0, minute=5, second=0, microsecond=0)

    def depart(ligne_, immatriculation, prevu, capacite=40, reel=None, statut=DepartStatut.PLANIFIE, vendues=0):
        bus = Vehicule.objects.create(immatriculation=immatriculation, capacite=capacite, company=company_a, gare=ligne_.gare_depart)
        d = Depart.objects.create(ligne=ligne_, vehicule=bus, chauffeur=chauffeur, company=company_a, date_heure=prevu, statut=statut, places_vendues=vendues)
        f = FeuilleDeRoute.objects.create(depart=d, chauffeur=chauffeur, company=company_a, heure_depart_prevue=prevu, heure_depart_reelle=reel)
        return d, f

    a_l_heure, feuille_ok = depart(ligne, "CI-SANTE-1", debut, reel=debut + datetime.timedelta(minutes=3), statut=DepartStatut.EN_COURS, vendues=30)
    en_retard, feuille_retard = depart(ligne, "CI-SANTE-2", debut, vendues=10)
    _, _ = depart(ligne_voisine, "CI-SANTE-3", debut, vendues=40)  # une autre gare : ne compte pas
    return {
        "chef": chef, "gare": gare, "voisine": voisine, "ligne": ligne, "chauffeur": chauffeur, "guichetier": guichetier,
        "bagagiste": bagagiste, "a_l_heure": a_l_heure, "en_retard": en_retard, "feuille_retard": feuille_retard,
        "ligne_voisine": ligne_voisine, "company": company_a,
    }


def vendre(depart, guichetier, prix, mode=ModePaiement.ESPECES, statut=StatutTicket.VALIDE):
    return Ticket.objects.create(
        depart=depart, company=depart.company, passager_nom="Passager", passager_telephone="+225", prix=prix,
        mode_paiement=mode, vendu_par=guichetier, statut=statut,
    )


def sante(api_client, utilisateur, **params):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get(URL, params)


@pytest.mark.django_db
class TestLaSanteDeLaGare:
    def test_le_chef_de_gare_voit_sa_gare(self, api_client, monde):
        reponse = sante(api_client, monde["chef"])

        assert reponse.status_code == 200
        assert reponse.data["gare"]["nom"] == "Adjamé"

    def test_ponctualite_et_remplissage_ne_comptent_que_les_departs_de_la_gare(self, api_client, monde):
        jour = sante(api_client, monde["chef"]).data["jour"]

        assert jour["departs"] == 2
        assert (jour["a_l_heure"], jour["en_retard"]) == (1, 1) and jour["ponctualite_pourcent"] == 50
        assert (jour["places_vendues"], jour["capacite"], jour["remplissage_pourcent"]) == (40, 80, 50)

    def test_les_recettes_du_jour_reunissent_billets_par_mode_et_fret(self, api_client, monde):
        vendre(monde["a_l_heure"], monde["guichetier"], 5000)
        vendre(monde["a_l_heure"], monde["guichetier"], 5000, ModePaiement.MOBILE_MONEY)
        vendre(monde["en_retard"], monde["guichetier"], 3000, ModePaiement.MOBILE_MONEY)
        Colis.objects.create(
            company=monde["company"], depart=monde["a_l_heure"], description="Carton", poids_kg=10, frais=2000,
            mode_paiement=ModePaiement.ESPECES, expediteur_nom="E", destinataire_nom="D", destinataire_telephone="07", enregistre_par=monde["bagagiste"],
        )

        recettes = sante(api_client, monde["chef"]).data["recettes"]

        assert recettes["billets"] == 13000 and recettes["nombre_de_billets"] == 3
        assert recettes["billets_par_mode"] == {"especes": 5000, "mobile_money": 8000}
        assert recettes["fret"] == 2000 and recettes["nombre_de_colis"] == 1 and recettes["total"] == 15000

    def test_un_billet_annule_un_colis_annule_et_les_ventes_d_une_autre_gare_sont_exclus(self, api_client, monde):
        vendre(monde["a_l_heure"], monde["guichetier"], 5000)
        vendre(monde["a_l_heure"], monde["guichetier"], 9000, statut=StatutTicket.ANNULE)
        autre_depart = Depart.objects.get(ligne=monde["ligne_voisine"])
        vendre(autre_depart, monde["guichetier"], 7000)
        Colis.objects.create(
            company=monde["company"], depart=monde["a_l_heure"], description="Annulé", poids_kg=5, frais=4000, statut=StatutColis.ANNULE,
            mode_paiement=ModePaiement.ESPECES, expediteur_nom="E", destinataire_nom="D", destinataire_telephone="07", enregistre_par=monde["bagagiste"],
        )

        recettes = sante(api_client, monde["chef"]).data["recettes"]

        assert recettes["billets"] == 5000 and recettes["fret"] == 0 and recettes["total"] == 5000

    def test_une_vente_d_un_autre_jour_ne_compte_pas(self, api_client, monde):
        hier = vendre(monde["a_l_heure"], monde["guichetier"], 5000)
        Ticket.objects.filter(pk=hier.pk).update(date_vente=timezone.now() - datetime.timedelta(days=2))

        assert sante(api_client, monde["chef"]).data["recettes"]["billets"] == 0

    def test_les_incidents_ouverts_de_la_gare_sont_comptes_dont_les_graves(self, api_client, monde):
        for gravite, statut in (
            (GraviteIncident.GRAVE, StatutIncident.OUVERT),
            (GraviteIncident.FAIBLE, StatutIncident.OUVERT),
            (GraviteIncident.GRAVE, StatutIncident.TRAITE),
        ):
            Incident.objects.create(
                feuille_de_route=FeuilleDeRoute.objects.get(depart=monde["a_l_heure"]), vehicule=monde["a_l_heure"].vehicule,
                chauffeur=monde["chauffeur"], company=monde["company"], type_incident=TypeIncident.PANNE, description="x",
                gravite=gravite, statut=statut,
            )
        Incident.objects.create(  # un incident d'une autre gare
            feuille_de_route=FeuilleDeRoute.objects.get(depart__ligne=monde["ligne_voisine"]), vehicule=Depart.objects.get(ligne=monde["ligne_voisine"]).vehicule,
            chauffeur=monde["chauffeur"], company=monde["company"], type_incident=TypeIncident.PANNE, description="y",
            gravite=GraviteIncident.GRAVE, statut=StatutIncident.OUVERT,
        )

        assert sante(api_client, monde["chef"]).data["incidents_ouverts"] == {"total": 2, "graves": 1}

    def test_les_departs_en_retard_sont_listes(self, api_client, monde):
        retards = sante(api_client, monde["chef"]).data["departs_en_retard"]

        assert [(r["depart"], r["ligne"], r["chauffeur_nom"]) for r in retards] == [(monde["en_retard"].id, "Adjamé-Bouaké", "Awa Kone")]
        assert retards[0]["retard_minutes"] > 0

    def test_les_vehicules_et_l_equipe_de_la_gare_sont_indiques(self, api_client, monde):
        AffectationGare.objects.create(agent=monde["guichetier"], gare=monde["gare"], company=monde["company"])
        AffectationGare.objects.create(agent=monde["bagagiste"], gare=monde["gare"], company=monde["company"])

        donnees = sante(api_client, monde["chef"]).data

        assert donnees["equipe"] == {"total": 2, "par_role": {"guichetier": 1, "bagagiste": 1}}
        assert donnees["vehicules"]["vehicules_attaches"] == 2 and donnees["vehicules"]["vehicules_disponibles"] == 2

    def test_la_ponctualite_sur_sept_jours_est_donnee(self, api_client, monde):
        assert sante(api_client, monde["chef"]).data["ponctualite_7_jours_pourcent"] == 50

    def test_une_gare_sans_activite_repond_par_des_zeros(self, api_client, user_factory, company_a):
        chef = user_factory("chef_sans_depart", Role.CHEF_GARE, company=company_a)
        Gare.objects.create(nom="Calme", ville="Abidjan", company=company_a, chef=chef)

        donnees = sante(api_client, chef).data

        assert donnees["jour"]["departs"] == 0 and donnees["jour"]["ponctualite_pourcent"] is None
        assert donnees["recettes"]["total"] == 0 and donnees["incidents_ouverts"] == {"total": 0, "graves": 0}
        assert donnees["departs_en_retard"] == [] and donnees["equipe"]["total"] == 0


@pytest.mark.django_db
class TestQuiPeutVoir:
    def test_un_chef_de_gare_sans_gare_n_a_rien_a_voir(self, api_client, user_factory, company_a):
        chef = user_factory("chef_sans_gare", Role.CHEF_GARE, company=company_a)

        assert sante(api_client, chef).status_code == 404

    @pytest.mark.parametrize("role", ["directeur_exploitation", "pdg", "secretaire_general"])
    def test_le_pilotage_choisit_la_gare(self, api_client, monde, user_factory, company_a, role):
        utilisateur = user_factory(f"{role}_sante", Role(role), company=company_a)

        assert sante(api_client, utilisateur, gare=monde["gare"].id).data["jour"]["departs"] == 2
        assert sante(api_client, utilisateur, gare=monde["voisine"].id).data["jour"]["departs"] == 1

    @pytest.mark.parametrize("params", [{}, {"gare": "abc"}, {"gare": 999999}])
    def test_le_pilotage_doit_indiquer_une_gare_existante(self, api_client, monde, user_factory, company_a, params):
        pdg = user_factory("pdg_sante_param", Role.PDG, company=company_a)

        assert sante(api_client, pdg, **params).status_code == 400

    def test_une_gare_d_une_autre_compagnie_est_refusee(self, api_client, monde, user_factory, company_b):
        etrangere = Gare.objects.create(nom="Étrangère", ville="Bouaké", company=company_b)
        pdg = user_factory("pdg_sante_a", Role.PDG, company=monde["company"])

        assert sante(api_client, pdg, gare=etrangere.id).status_code == 400

    def test_le_chef_de_gare_ne_choisit_pas_la_gare_d_un_autre(self, api_client, monde):
        assert sante(api_client, monde["chef"], gare=monde["voisine"].id).data["gare"]["nom"] == "Adjamé"

    @pytest.mark.parametrize("role", ["guichetier", "chef_ligne", "qhse", "directeur_financier", "drh", "chauffeur_principal"])
    def test_les_autres_postes_ne_la_voient_pas(self, api_client, monde, user_factory, company_a, role):
        assert sante(api_client, user_factory(f"{role}_sante_x", Role(role), company=company_a), gare=monde["gare"].id).status_code == 403

    def test_sans_authentification_rien(self, api_client):
        assert api_client.get(URL).status_code == 401
