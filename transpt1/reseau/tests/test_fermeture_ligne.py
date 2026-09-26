"""Fermer une ligne (PDG : « geler une ligne » ; directeur des opérations : validation d'ouverture/fermeture temporaire)
et arbitrer les véhicules entre gares (cahier des charges : Direction Générale et Exploitation & Réseau)."""

import datetime

import pytest
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte
from billetterie.models import Depart, DepartStatut
from core.models import Role
from reseau.models import ChangementLigne, Gare, Ligne, StatutChangementLigne, StatutLigne, Vehicule, VehiculeStatut


@pytest.fixture
def equipe(user_factory, company_a):
    return {
        "dirops": user_factory("dirops_ligne", Role.DIRECTEUR_EXPLOITATION, company=company_a),
        "pdg": user_factory("pdg_ligne", Role.PDG, company=company_a),
        "chef_ligne": user_factory("chef_ligne_ligne", Role.CHEF_LIGNE, company=company_a, first_name="Koffi", last_name="Yao"),
        "chef_gare": user_factory("chef_gare_depart", Role.CHEF_GARE, company=company_a),
        "chef_gare_arrivee": user_factory("chef_gare_arrivee", Role.CHEF_GARE, company=company_a),
        "guichetier": user_factory("guichetier_ligne", Role.GUICHETIER, company=company_a),
        "chauffeur": user_factory("chauffeur_ligne", Role.CHAUFFEUR_PRINCIPAL, company=company_a),
        "qhse": user_factory("qhse_ligne", Role.QHSE, company=company_a),
    }


@pytest.fixture
def ligne(company_a, equipe):
    depart = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=equipe["chef_gare"])
    arrivee = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a, chef=equipe["chef_gare_arrivee"])
    return Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=depart, gare_arrivee=arrivee, company=company_a)


@pytest.fixture
def depart_prevu(company_a, ligne, equipe):
    vehicule = Vehicule.objects.create(immatriculation="CI-LIGNE-1", capacite=50, company=company_a)
    return Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=equipe["chauffeur"], company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=3), statut=DepartStatut.PLANIFIE,
    )


def demander(api_client, utilisateur, ligne, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"/api/lignes/{ligne.id}/changement/", corps, format="json")


def fermer(api_client, utilisateur, ligne, motif="Route coupée par les pluies", **plus):
    return demander(api_client, utilisateur, ligne, action="fermer", motif=motif, **plus)


def demain():
    return (timezone.localdate() + datetime.timedelta(days=1)).isoformat()


@pytest.mark.django_db
class TestFermetureDirecte:
    @pytest.mark.parametrize("role", ["dirops", "pdg"])
    def test_la_direction_des_operations_et_le_pdg_ferment_aussitot(self, api_client, equipe, ligne, role):
        reponse = fermer(api_client, equipe[role], ligne, jusqu_au=demain())

        assert reponse.status_code == 201
        assert reponse.data["statut"] == StatutChangementLigne.VALIDE
        ligne.refresh_from_db()
        assert ligne.est_fermee and ligne.statut == StatutLigne.FERMEE
        assert ligne.fermee_jusqu_au.isoformat() == demain()
        assert ligne.motif_fermeture == "Route coupée par les pluies"

    def test_la_liste_des_lignes_dit_qu_elle_est_fermee(self, api_client, equipe, ligne):
        fermer(api_client, equipe["pdg"], ligne)

        api_client.force_authenticate(user=equipe["guichetier"])
        vue = next(entree for entree in api_client.get("/api/lignes/").data if entree["id"] == ligne.id)

        assert vue["est_fermee"] is True
        assert vue["motif_fermeture"] == "Route coupée par les pluies"

    def test_la_fermeture_previent_les_gares_aux_deux_bouts_la_regulation_et_la_direction(
        self, api_client, equipe, ligne, depart_prevu
    ):
        fermer(api_client, equipe["dirops"], ligne)

        alerte = Alerte.objects.get(type=TypeAlerte.LIGNE)
        assert set(alerte.destinataires.all()) == {equipe["chef_gare"], equipe["chef_gare_arrivee"]}
        assert {Role.CHEF_LIGNE, Role.PDG, Role.DIRECTEUR_EXPLOITATION} <= set(alerte.roles_destinataires)
        assert "1 départ(s) planifié(s) à réaffecter ou annuler" in alerte.message

    def test_sans_date_de_fin_la_ligne_reste_fermee_jusqu_a_reouverture(self, api_client, equipe, ligne):
        fermer(api_client, equipe["dirops"], ligne)

        ligne.refresh_from_db()
        assert ligne.est_fermee and ligne.fermee_jusqu_au is None

    def test_la_ligne_se_rouvre_d_elle_meme_le_lendemain_du_dernier_jour(self, api_client, equipe, ligne):
        fermer(api_client, equipe["dirops"], ligne, jusqu_au=demain())
        Ligne.objects.filter(pk=ligne.pk).update(fermee_jusqu_au=timezone.localdate() - datetime.timedelta(days=1))

        ligne.refresh_from_db()
        assert ligne.statut == StatutLigne.FERMEE and not ligne.est_fermee

    def test_le_dernier_jour_de_fermeture_est_inclus(self, api_client, equipe, ligne):
        fermer(api_client, equipe["dirops"], ligne)
        Ligne.objects.filter(pk=ligne.pk).update(fermee_jusqu_au=timezone.localdate())

        ligne.refresh_from_db()
        assert ligne.est_fermee


@pytest.mark.django_db
class TestReouverture:
    def test_le_directeur_des_operations_rouvre_et_les_gares_le_savent(self, api_client, equipe, ligne):
        fermer(api_client, equipe["pdg"], ligne)

        reponse = demander(api_client, equipe["dirops"], ligne, action="rouvrir", motif="Route dégagée")

        assert reponse.status_code == 201
        ligne.refresh_from_db()
        assert not ligne.est_fermee and ligne.statut == StatutLigne.OUVERTE
        assert ligne.motif_fermeture == "" and ligne.fermee_jusqu_au is None
        assert Alerte.objects.filter(type=TypeAlerte.LIGNE, titre="Ligne rouverte : Adjamé-Bouaké").exists()

    def test_on_ne_rouvre_pas_une_ligne_ouverte(self, api_client, equipe, ligne):
        reponse = demander(api_client, equipe["dirops"], ligne, action="rouvrir", motif="Par précaution")

        assert reponse.status_code == 400
        assert "n'est pas fermée" in str(reponse.data)

    def test_on_ne_ferme_pas_deux_fois_une_ligne(self, api_client, equipe, ligne):
        fermer(api_client, equipe["dirops"], ligne)

        reponse = fermer(api_client, equipe["pdg"], ligne)

        assert reponse.status_code == 400
        assert "déjà fermée" in str(reponse.data)


@pytest.mark.django_db
class TestValidationDesDonnees:
    def test_le_motif_est_obligatoire(self, api_client, equipe, ligne):
        assert fermer(api_client, equipe["dirops"], ligne, motif="  ").status_code == 400
        assert fermer(api_client, equipe["dirops"], ligne, motif="Non").status_code == 400
        assert not ChangementLigne.objects.exists()

    def test_l_action_doit_etre_connue(self, api_client, equipe, ligne):
        assert demander(api_client, equipe["dirops"], ligne, action="supprimer", motif="Ça ne marche pas").status_code == 400

    def test_la_date_de_fin_ne_peut_pas_etre_passee(self, api_client, equipe, ligne):
        hier = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()

        reponse = fermer(api_client, equipe["dirops"], ligne, jusqu_au=hier)

        assert reponse.status_code == 400
        assert "jusqu_au" in reponse.data

    def test_la_date_de_fin_doit_etre_une_date(self, api_client, equipe, ligne):
        assert fermer(api_client, equipe["dirops"], ligne, jusqu_au="bientôt").status_code == 400

    def test_une_demande_refusee_ne_laisse_rien_derriere_elle(self, api_client, equipe, ligne):
        fermer(api_client, equipe["dirops"], ligne)
        fermer(api_client, equipe["pdg"], ligne)  # refusée : déjà fermée

        assert ChangementLigne.objects.count() == 1


@pytest.mark.django_db
class TestDemandeParLeTerrain:
    @pytest.mark.parametrize("role", ["chef_ligne", "chef_gare"])
    def test_le_chef_de_ligne_et_le_chef_de_gare_demandent_sans_fermer(self, api_client, equipe, ligne, role):
        reponse = fermer(api_client, equipe[role], ligne, jusqu_au=demain())

        assert reponse.status_code == 201
        assert reponse.data["statut"] == StatutChangementLigne.EN_ATTENTE
        ligne.refresh_from_db()
        assert not ligne.est_fermee, "la ligne ne ferme qu'une fois la demande validée"

    def test_la_demande_alerte_le_directeur_des_operations(self, api_client, equipe, ligne):
        fermer(api_client, equipe["chef_ligne"], ligne)

        alerte = Alerte.objects.get(type=TypeAlerte.DEMANDE_LIGNE)
        assert alerte.roles_destinataires == [Role.DIRECTEUR_EXPLOITATION]
        assert "Koffi Yao" in alerte.message

    def test_une_demande_identique_en_attente_n_est_pas_doublee(self, api_client, equipe, ligne):
        fermer(api_client, equipe["chef_ligne"], ligne)

        reponse = fermer(api_client, equipe["chef_gare"], ligne)

        assert reponse.status_code == 400
        assert "déjà en attente" in str(reponse.data)

    def test_la_validation_ferme_la_ligne_et_previent_le_demandeur(self, api_client, equipe, ligne):
        demande = fermer(api_client, equipe["chef_ligne"], ligne, jusqu_au=demain()).data["id"]

        api_client.force_authenticate(user=equipe["dirops"])
        reponse = api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "valider", "commentaire": "D'accord"})

        assert reponse.status_code == 200
        assert reponse.data["statut"] == StatutChangementLigne.VALIDE and reponse.data["commentaire_decision"] == "D'accord"
        ligne.refresh_from_db()
        assert ligne.est_fermee
        reponse_alerte = Alerte.objects.filter(type=TypeAlerte.DEMANDE_LIGNE, titre__contains="acceptée").get()
        assert list(reponse_alerte.destinataires.all()) == [equipe["chef_ligne"]]

    def test_le_refus_laisse_la_ligne_ouverte_et_previent_le_demandeur(self, api_client, equipe, ligne):
        demande = fermer(api_client, equipe["chef_gare"], ligne).data["id"]

        api_client.force_authenticate(user=equipe["pdg"])
        reponse = api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "refuser", "commentaire": "Pas justifié"})

        assert reponse.status_code == 200 and reponse.data["statut"] == StatutChangementLigne.REFUSE
        ligne.refresh_from_db()
        assert not ligne.est_fermee
        assert list(Alerte.objects.get(titre__contains="refusée").destinataires.all()) == [equipe["chef_gare"]]

    def test_une_demande_ne_se_decide_qu_une_fois(self, api_client, equipe, ligne):
        demande = fermer(api_client, equipe["chef_ligne"], ligne).data["id"]
        api_client.force_authenticate(user=equipe["dirops"])
        api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "refuser"})

        reponse = api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "valider"})

        assert reponse.status_code == 400
        assert "déjà été traitée" in str(reponse.data)

    def test_la_decision_doit_etre_valider_ou_refuser(self, api_client, equipe, ligne):
        demande = fermer(api_client, equipe["chef_ligne"], ligne).data["id"]
        api_client.force_authenticate(user=equipe["dirops"])

        assert api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "peut-être"}).status_code == 400
        assert api_client.post(f"/api/changements-ligne/{demande}/decider/", {}).status_code == 400

    @pytest.mark.parametrize("role", ["chef_ligne", "chef_gare", "guichetier", "qhse", "chauffeur"])
    def test_les_autres_ne_decident_pas(self, api_client, equipe, ligne, role):
        demande = fermer(api_client, equipe["chef_ligne"], ligne).data["id"]

        api_client.force_authenticate(user=equipe[role])
        reponse = api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "valider"})

        assert reponse.status_code == 403
        ligne.refresh_from_db()
        assert not ligne.est_fermee

    def test_une_fermeture_directe_solde_les_demandes_en_attente(self, api_client, equipe, ligne):
        en_attente = fermer(api_client, equipe["chef_ligne"], ligne).data["id"]

        fermer(api_client, equipe["pdg"], ligne, motif="Décision de la direction")

        assert ChangementLigne.objects.get(pk=en_attente).statut == StatutChangementLigne.VALIDE

    def test_une_reouverture_directe_solde_la_demande_du_chef_de_ligne(self, api_client, equipe, ligne):
        fermer(api_client, equipe["dirops"], ligne)
        demande = demander(api_client, equipe["chef_ligne"], ligne, action="rouvrir", motif="La route est libre").data["id"]

        demander(api_client, equipe["pdg"], ligne, action="rouvrir", motif="Rouverte par la direction")

        assert ChangementLigne.objects.get(pk=demande).statut == StatutChangementLigne.VALIDE

    def test_une_reouverture_devenue_sans_objet_ne_se_valide_plus(self, api_client, equipe, ligne):
        fermer(api_client, equipe["dirops"], ligne, jusqu_au=demain())
        demande = demander(api_client, equipe["chef_ligne"], ligne, action="rouvrir", motif="La route est libre").data["id"]
        # La date de fin est passée : la ligne s'est rouverte d'elle-même avant que la demande ne soit décidée.
        Ligne.objects.filter(pk=ligne.pk).update(fermee_jusqu_au=timezone.localdate() - datetime.timedelta(days=1))

        api_client.force_authenticate(user=equipe["dirops"])
        reponse = api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "valider"})

        assert reponse.status_code == 400 and "n'a plus d'objet" in str(reponse.data)
        assert ChangementLigne.objects.get(pk=demande).statut == StatutChangementLigne.EN_ATTENTE


@pytest.mark.django_db
class TestQuiVoitLesDemandes:
    def test_le_decideur_voit_toutes_les_demandes_et_les_filtre(self, api_client, equipe, ligne):
        fermer(api_client, equipe["chef_ligne"], ligne)
        ChangementLigne.objects.filter(action="fermer").update(statut=StatutChangementLigne.REFUSE)
        fermer(api_client, equipe["chef_gare"], ligne)

        api_client.force_authenticate(user=equipe["dirops"])
        assert len(api_client.get("/api/changements-ligne/").data) == 2
        en_attente = api_client.get("/api/changements-ligne/?statut=en_attente").data
        assert [d["demandeur"] for d in en_attente] == [equipe["chef_gare"].id]
        assert len(api_client.get(f"/api/changements-ligne/?ligne={ligne.id}").data) == 2
        assert api_client.get("/api/changements-ligne/?ligne=999999").data == []

    def test_un_chef_ne_voit_que_ses_propres_demandes(self, api_client, equipe, ligne):
        fermer(api_client, equipe["chef_ligne"], ligne)
        ChangementLigne.objects.update(statut=StatutChangementLigne.REFUSE)
        fermer(api_client, equipe["chef_gare"], ligne)

        api_client.force_authenticate(user=equipe["chef_gare"])
        vues = api_client.get("/api/changements-ligne/").data

        assert [d["demandeur"] for d in vues] == [equipe["chef_gare"].id]

    @pytest.mark.parametrize("role", ["guichetier", "qhse", "chauffeur"])
    def test_les_autres_postes_ne_voient_rien(self, api_client, equipe, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/changements-ligne/").status_code == 403

    @pytest.mark.parametrize("role", ["guichetier", "qhse", "chauffeur"])
    def test_les_autres_postes_ne_demandent_pas(self, api_client, equipe, ligne, role):
        assert fermer(api_client, equipe[role], ligne).status_code == 403

    def test_le_cloisonnement_entre_compagnies_tient(self, api_client, equipe, ligne, user_factory, company_b):
        etranger = user_factory("dirops_b", Role.DIRECTEUR_EXPLOITATION, company=company_b)
        demande = fermer(api_client, equipe["chef_ligne"], ligne).data["id"]

        assert fermer(api_client, etranger, ligne).status_code == 404
        assert api_client.get("/api/changements-ligne/").data == []
        assert api_client.post(f"/api/changements-ligne/{demande}/decider/", {"decision": "valider"}).status_code == 404

    def test_sans_authentification_rien_n_est_possible(self, api_client, ligne):
        assert api_client.get("/api/changements-ligne/").status_code == 401
        assert api_client.post(f"/api/lignes/{ligne.id}/changement/", {}).status_code == 401


@pytest.mark.django_db
class TestLaFermetureNeSeContourneDirectementPas:
    def test_modifier_la_ligne_ne_change_pas_son_etat_de_fermeture(self, api_client, equipe, ligne):
        api_client.force_authenticate(user=equipe["chef_ligne"])

        reponse = api_client.patch(f"/api/lignes/{ligne.id}/", {"statut": "fermee", "motif_fermeture": "Tentative"}, format="json")

        assert reponse.status_code == 200
        ligne.refresh_from_db()
        assert ligne.statut == StatutLigne.OUVERTE and ligne.motif_fermeture == ""

    def test_la_creation_d_une_ligne_ne_peut_pas_naitre_fermee(self, api_client, equipe, ligne):
        api_client.force_authenticate(user=equipe["dirops"])

        reponse = api_client.post(
            "/api/lignes/",
            {"nom": "Nouvelle", "gare_depart": ligne.gare_depart_id, "gare_arrivee": ligne.gare_arrivee_id, "statut": "fermee"},
            format="json",
        )

        assert reponse.status_code == 201
        assert Ligne.objects.get(pk=reponse.data["id"]).statut == StatutLigne.OUVERTE


@pytest.mark.django_db
class TestEffetsSurLaBilletterie:
    def _corps_depart(self, ligne, depart_prevu, equipe):
        quand = (timezone.now() + datetime.timedelta(days=2)).replace(microsecond=0)
        return {"ligne": ligne.id, "vehicule": depart_prevu.vehicule_id, "chauffeur": equipe["chauffeur"].id, "date_heure": quand.isoformat()}

    def test_on_ne_planifie_plus_de_depart_sur_une_ligne_fermee(self, api_client, equipe, ligne, depart_prevu):
        fermer(api_client, equipe["pdg"], ligne, motif="Pont effondré", jusqu_au=demain())

        api_client.force_authenticate(user=equipe["chef_ligne"])
        reponse = api_client.post("/api/departs/planifier/", self._corps_depart(ligne, depart_prevu, equipe), format="json")

        assert reponse.status_code == 400
        assert "est fermée" in str(reponse.data["ligne"]) and "Pont effondré" in str(reponse.data["ligne"])
        assert Depart.objects.filter(ligne=ligne).count() == 1

    def test_on_ne_vend_plus_de_billet_sur_une_ligne_fermee(self, api_client, equipe, ligne, depart_prevu):
        fermer(api_client, equipe["dirops"], ligne)

        api_client.force_authenticate(user=equipe["guichetier"])
        reponse = api_client.post(
            "/api/tickets/",
            {"depart": depart_prevu.id, "passager_nom": "Awa", "passager_telephone": "0700000001", "prix": "5000", "mode_paiement": "especes"},
        )

        assert reponse.status_code == 400
        assert "vente impossible" in str(reponse.data)

    def test_la_vente_et_la_planification_reprennent_a_la_reouverture(self, api_client, equipe, ligne, depart_prevu):
        fermer(api_client, equipe["dirops"], ligne)
        demander(api_client, equipe["dirops"], ligne, action="rouvrir", motif="Route dégagée")

        api_client.force_authenticate(user=equipe["guichetier"])
        vente = api_client.post(
            "/api/tickets/",
            {"depart": depart_prevu.id, "passager_nom": "Awa", "passager_telephone": "0700000001", "prix": "5000", "mode_paiement": "especes"},
        )
        api_client.force_authenticate(user=equipe["chef_ligne"])
        planification = api_client.post("/api/departs/planifier/", self._corps_depart(ligne, depart_prevu, equipe), format="json")

        assert vente.status_code == 201 and planification.status_code == 201

    def test_une_autre_ligne_reste_ouverte(self, api_client, equipe, ligne, depart_prevu, company_a):
        autre = Ligne.objects.create(nom="Adjamé-Yakro", gare_depart=ligne.gare_depart, gare_arrivee=ligne.gare_arrivee, company=company_a)
        fermer(api_client, equipe["dirops"], ligne)

        api_client.force_authenticate(user=equipe["chef_ligne"])
        corps = self._corps_depart(autre, depart_prevu, equipe)
        assert api_client.post("/api/departs/planifier/", corps, format="json").status_code == 201

    def test_les_departs_deja_en_cours_ne_sont_pas_touches(self, api_client, equipe, ligne, depart_prevu):
        Depart.objects.filter(pk=depart_prevu.pk).update(statut=DepartStatut.EN_COURS)

        assert fermer(api_client, equipe["dirops"], ligne).status_code == 201
        assert "Aucun départ planifié" in Alerte.objects.get(type=TypeAlerte.LIGNE).message


@pytest.mark.django_db
class TestJournalDAudit:
    def test_la_fermeture_est_tracee_avec_son_auteur(self, api_client, equipe, ligne):
        from audit.models import JournalAudit

        fermer(api_client, equipe["pdg"], ligne)

        entree = JournalAudit.objects.filter(objet_type="reseau.ligne", objet_id=str(ligne.id)).latest("id")
        assert entree.acteur == equipe["pdg"]
        assert entree.changements["statut"] == ["ouverte", "fermee"]


@pytest.fixture
def parc(company_a, ligne, equipe):
    """Deux gares avec leur chef, un véhicule rattaché à l'une d'elles."""
    autre = Gare.objects.create(nom="Yopougon", ville="Abidjan", company=company_a)
    bus = Vehicule.objects.create(immatriculation="CI-ARB-1", capacite=60, company=company_a, gare=ligne.gare_depart)
    return {"origine": ligne.gare_depart, "cible": ligne.gare_arrivee, "autre": autre, "bus": bus}


def reaffecter(api_client, utilisateur, vehicule, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"/api/vehicules/{vehicule.id}/reaffecter-gare/", corps, format="json")


@pytest.mark.django_db
class TestArbitrageEntreGares:
    @pytest.mark.parametrize("role", ["dirops", "pdg"])
    def test_la_direction_rattache_un_vehicule_a_une_autre_gare(self, api_client, equipe, parc, role):
        reponse = reaffecter(api_client, equipe[role], parc["bus"], gare=parc["cible"].id, motif="Gare de Bouaké en tension")

        assert reponse.status_code == 200
        assert reponse.data["gare"] == parc["cible"].id and reponse.data["gare_nom"] == "Bouaké"
        parc["bus"].refresh_from_db()
        assert parc["bus"].gare == parc["cible"]

    def test_les_chefs_des_deux_gares_et_la_regulation_sont_prevenus(self, api_client, equipe, parc):
        reaffecter(api_client, equipe["dirops"], parc["bus"], gare=parc["cible"].id, motif="Gare de Bouaké en tension")

        alerte = Alerte.objects.get(type=TypeAlerte.REAFFECTATION)
        assert set(alerte.destinataires.all()) == {equipe["chef_gare"], equipe["chef_gare_arrivee"]}
        assert alerte.roles_destinataires == [Role.CHEF_LIGNE]
        assert "Depuis Adjamé" in alerte.message and "Bouaké en tension" in alerte.message

    def test_un_vehicule_sans_gare_d_attache_peut_etre_rattache(self, api_client, equipe, parc):
        Vehicule.objects.filter(pk=parc["bus"].pk).update(gare=None)

        reponse = reaffecter(api_client, equipe["dirops"], parc["bus"], gare=parc["autre"].id, motif="Rattachement du parc")

        assert reponse.status_code == 200
        assert "Sans gare d'attache" in Alerte.objects.get(type=TypeAlerte.REAFFECTATION).message

    def test_le_motif_est_obligatoire(self, api_client, equipe, parc):
        assert reaffecter(api_client, equipe["dirops"], parc["bus"], gare=parc["cible"].id).status_code == 400
        assert reaffecter(api_client, equipe["dirops"], parc["bus"], gare=parc["cible"].id, motif="ok").status_code == 400

    @pytest.mark.parametrize("gare", [None, "", "abc", 999999])
    def test_la_gare_doit_exister(self, api_client, equipe, parc, gare):
        reponse = reaffecter(api_client, equipe["dirops"], parc["bus"], gare=gare, motif="Gare de Bouaké en tension")

        assert reponse.status_code == 400 and "gare" in reponse.data

    def test_la_gare_d_une_autre_compagnie_est_refusee(self, api_client, equipe, parc, company_b):
        etrangere = Gare.objects.create(nom="Gare étrangère", ville="Bouaké", company=company_b)

        reponse = reaffecter(api_client, equipe["dirops"], parc["bus"], gare=etrangere.id, motif="Gare de Bouaké en tension")

        assert reponse.status_code == 400

    def test_une_gare_identique_est_refusee(self, api_client, equipe, parc):
        reponse = reaffecter(api_client, equipe["dirops"], parc["bus"], gare=parc["origine"].id, motif="Gare de Bouaké en tension")

        assert reponse.status_code == 400 and "déjà rattaché" in str(reponse.data)

    def test_un_vehicule_en_ligne_ne_change_pas_de_gare(self, api_client, equipe, parc):
        Vehicule.objects.filter(pk=parc["bus"].pk).update(statut=VehiculeStatut.EN_LIGNE)

        reponse = reaffecter(api_client, equipe["dirops"], parc["bus"], gare=parc["cible"].id, motif="Gare de Bouaké en tension")

        assert reponse.status_code == 400 and "en ligne" in str(reponse.data)

    @pytest.mark.parametrize("role", ["chef_gare", "chef_ligne", "guichetier", "qhse"])
    def test_les_autres_postes_n_arbitrent_pas(self, api_client, equipe, parc, role):
        reponse = reaffecter(api_client, equipe[role], parc["bus"], gare=parc["cible"].id, motif="Gare de Bouaké en tension")

        assert reponse.status_code == 403
        parc["bus"].refresh_from_db()
        assert parc["bus"].gare == parc["origine"]

    def test_la_gare_d_attache_ne_se_change_pas_par_une_simple_modification(self, api_client, equipe, parc):
        api_client.force_authenticate(user=equipe["dirops"])

        reponse = api_client.patch(f"/api/vehicules/{parc['bus'].id}/", {"gare": parc["autre"].id}, format="json")

        assert reponse.status_code == 200
        parc["bus"].refresh_from_db()
        assert parc["bus"].gare == parc["origine"]

    def test_un_vehicule_d_une_autre_compagnie_est_introuvable(self, api_client, equipe, parc, company_b):
        etranger = Vehicule.objects.create(immatriculation="CI-ETRANGER", capacite=40, company=company_b)

        assert reaffecter(api_client, equipe["dirops"], etranger, gare=parc["cible"].id, motif="Gare de Bouaké en tension").status_code == 404

    def test_le_changement_de_gare_est_trace(self, api_client, equipe, parc):
        from audit.models import JournalAudit

        reaffecter(api_client, equipe["dirops"], parc["bus"], gare=parc["cible"].id, motif="Gare de Bouaké en tension")

        entree = JournalAudit.objects.filter(objet_type="reseau.vehicule", objet_id=str(parc["bus"].id)).latest("id")
        assert entree.acteur == equipe["dirops"]
        assert entree.changements["gare_id"] == [parc["origine"].id, parc["cible"].id]


@pytest.mark.django_db
class TestGaresEnTension:
    def _departs(self, company, ligne, equipe, nombre, dans_heures=5):
        for i in range(nombre):
            bus = Vehicule.objects.create(immatriculation=f"CI-TENS-{i}", capacite=50, company=company)
            Depart.objects.create(
                ligne=ligne, vehicule=bus, chauffeur=equipe["chauffeur"], company=company,
                date_heure=timezone.now() + datetime.timedelta(hours=dans_heures + i), statut=DepartStatut.PLANIFIE,
            )

    def _gare(self, api_client, equipe, gare):
        api_client.force_authenticate(user=equipe["dirops"])
        return next(g for g in api_client.get("/api/dashboard/exploitation/").data["gares"] if g["id"] == gare.id)

    def test_une_gare_avec_plus_de_departs_que_de_vehicules_disponibles_est_en_tension(
        self, api_client, equipe, ligne, parc, company_a
    ):
        self._departs(company_a, ligne, equipe, 3)

        vue = self._gare(api_client, equipe, ligne.gare_depart)

        assert vue["departs_24h"] == 3 and vue["vehicules_attaches"] == 1 and vue["vehicules_disponibles"] == 1
        assert vue["tension"] == 2 and vue["en_tension"] is True

    def test_une_gare_avec_des_vehicules_en_surplus_a_de_quoi_en_preter(self, api_client, equipe, ligne, parc, company_a):
        Vehicule.objects.create(immatriculation="CI-SURPLUS", capacite=50, company=company_a, gare=parc["autre"])
        Vehicule.objects.create(immatriculation="CI-SURPLUS2", capacite=50, company=company_a, gare=parc["autre"])

        vue = self._gare(api_client, equipe, parc["autre"])

        assert vue["vehicules_disponibles"] == 2 and vue["departs_24h"] == 0
        assert vue["tension"] == -2 and vue["en_tension"] is False

    def test_seuls_les_vehicules_disponibles_comptent(self, api_client, equipe, ligne, parc):
        Vehicule.objects.filter(pk=parc["bus"].pk).update(statut=VehiculeStatut.EN_MAINTENANCE)

        vue = self._gare(api_client, equipe, ligne.gare_depart)

        assert vue["vehicules_attaches"] == 1 and vue["vehicules_disponibles"] == 0

    def test_les_departs_d_une_ligne_fermee_ne_comptent_pas(self, api_client, equipe, ligne, parc, company_a):
        self._departs(company_a, ligne, equipe, 2)
        fermer(api_client, equipe["pdg"], ligne)

        assert self._gare(api_client, equipe, ligne.gare_depart)["departs_24h"] == 0

    def test_les_departs_au_dela_de_24_heures_ne_comptent_pas(self, api_client, equipe, ligne, parc, company_a):
        self._departs(company_a, ligne, equipe, 1, dans_heures=30)

        assert self._gare(api_client, equipe, ligne.gare_depart)["departs_24h"] == 0

    def test_la_reaffectation_deplace_la_tension(self, api_client, equipe, ligne, parc, company_a):
        self._departs(company_a, ligne, equipe, 1)
        assert self._gare(api_client, equipe, ligne.gare_arrivee)["vehicules_disponibles"] == 0

        reaffecter(api_client, equipe["dirops"], parc["bus"], gare=ligne.gare_arrivee_id, motif="Renfort de la gare d'arrivée")

        assert self._gare(api_client, equipe, ligne.gare_arrivee)["vehicules_disponibles"] == 1
        assert self._gare(api_client, equipe, ligne.gare_depart)["tension"] == 1

    def test_le_tableau_de_bord_expose_l_etat_de_fermeture_des_lignes(self, api_client, equipe, ligne):
        fermer(api_client, equipe["pdg"], ligne, motif="Pont effondré", jusqu_au=demain())

        api_client.force_authenticate(user=equipe["dirops"])
        vue = next(l for l in api_client.get("/api/dashboard/exploitation/").data["lignes"] if l["id"] == ligne.id)

        assert vue["est_fermee"] is True and vue["motif_fermeture"] == "Pont effondré" and vue["fermee_jusqu_au"].isoformat() == demain()
