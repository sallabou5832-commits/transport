"""Recrutement simplifié (cahier des charges : DRH — fiche de poste type par rôle de l'organigramme)."""

import pytest

from core.models import Role
from rh.fiches_types import FICHES_TYPES
from rh.models import FicheDePoste, OffreRecrutement
from rh.tests.conftest import jour


def fiches(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get("/api/fiches-poste/")


def ouvrir_offre(api_client, utilisateur, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/offres-recrutement/", {"role": "guichetier", "nombre_postes": 2, **corps}, format="json")


def candidater(api_client, utilisateur, offre, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/candidatures/", {"offre": offre, "nom": "Awa Koné", "telephone": "0707070707", **corps}, format="json")


@pytest.mark.django_db
class TestFichesDePoste:
    def test_une_fiche_type_par_role_de_l_organigramme(self, api_client, equipe):
        donnees = fiches(api_client, equipe["drh"]).data

        assert {f["role"] for f in donnees} == {r.value for r in Role if r != Role.SUPERADMIN} and len(donnees) == 18
        assert all(not f["personnalisee"] and f["missions"].startswith("- ") and f["intitule"] for f in donnees)
        chauffeur = next(f for f in donnees if f["role"] == "chauffeur_principal")
        assert "OSER" in chauffeur["profil"] and chauffeur["role_libelle"] == "Chauffeur principal"

    def test_le_drh_personnalise_une_fiche_puis_revient_a_la_fiche_type(self, api_client, equipe):
        api_client.force_authenticate(user=equipe["drh"])
        corps = {"role": "guichetier", "intitule": "Guichetier senior", "missions": "- Vendre", "profil": "- Rigoureux", "conditions": "8 h par jour"}

        reponse = api_client.put("/api/fiches-poste/", corps, format="json")
        assert reponse.status_code == 200 and reponse.data["personnalisee"] is True
        guichetier = next(f for f in fiches(api_client, equipe["drh"]).data if f["role"] == "guichetier")
        assert (guichetier["intitule"], guichetier["personnalisee"]) == ("Guichetier senior", True)
        assert sum(f["personnalisee"] for f in fiches(api_client, equipe["drh"]).data) == 1

        retour = api_client.post("/api/fiches-poste/reinitialiser/", {"role": "guichetier"}, format="json")
        assert retour.status_code == 200 and retour.data["personnalisee"] is False and retour.data["intitule"] == FICHES_TYPES["guichetier"]["intitule"]
        assert not FicheDePoste.objects.exists()

    def test_la_personnalisation_ne_touche_que_sa_compagnie(self, api_client, equipe, user_factory, company_b):
        api_client.force_authenticate(user=equipe["drh"])
        api_client.put("/api/fiches-poste/", {"role": "guichetier", "intitule": "Spécial A", "missions": "- a", "profil": "- b"}, format="json")

        drh_b = user_factory("drh_b_fiche", "drh", company=company_b)
        guichetier_b = next(f for f in fiches(api_client, drh_b).data if f["role"] == "guichetier")

        assert guichetier_b["intitule"] == FICHES_TYPES["guichetier"]["intitule"]

    @pytest.mark.parametrize("corps", [{"role": "astronaute"}, {"role": "superadmin"}, {"missions": ""}, {"intitule": ""}])
    def test_les_fiches_invalides_sont_refusees(self, api_client, equipe, corps):
        api_client.force_authenticate(user=equipe["drh"])
        base = {"role": "guichetier", "intitule": "X", "missions": "- a", "profil": "- b"}

        assert api_client.put("/api/fiches-poste/", {**base, **corps}, format="json").status_code == 400

    @pytest.mark.parametrize("poste", ["pdg", "secretaire_general"])
    def test_la_direction_lit_les_fiches_sans_les_ecrire(self, api_client, equipe, poste):
        assert fiches(api_client, equipe[poste]).status_code == 200
        assert api_client.put("/api/fiches-poste/", {"role": "guichetier", "intitule": "X", "missions": "a", "profil": "b"}, format="json").status_code == 403
        assert api_client.post("/api/fiches-poste/reinitialiser/", {"role": "guichetier"}, format="json").status_code == 403

    @pytest.mark.parametrize("poste", ["guichetier", "chef_gare", "qhse", "responsable_juridique", "directeur_financier"])
    def test_les_autres_postes_n_y_ont_pas_acces(self, api_client, equipe, poste):
        assert fiches(api_client, equipe[poste]).status_code == 403


@pytest.mark.django_db
class TestOffres:
    def test_l_offre_reprend_la_fiche_type_du_role(self, api_client, equipe):
        reponse = ouvrir_offre(api_client, equipe["drh"], role="chauffeur_principal", date_limite=jour(30).isoformat())

        assert reponse.status_code == 201
        assert reponse.data["intitule"] == FICHES_TYPES["chauffeur_principal"]["intitule"] and reponse.data["statut"] == "ouverte"
        assert "Missions" in reponse.data["description"] and "Profil recherché" in reponse.data["description"] and "OSER" in reponse.data["description"]
        assert OffreRecrutement.objects.get().cree_par == equipe["drh"]

    def test_l_offre_reprend_la_fiche_personnalisee(self, api_client, equipe):
        api_client.force_authenticate(user=equipe["drh"])
        api_client.put("/api/fiches-poste/", {"role": "guichetier", "intitule": "Guichetier senior", "missions": "- Vendre", "profil": "- Rigoureux", "conditions": "Nuit"}, format="json")

        reponse = ouvrir_offre(api_client, equipe["drh"])

        assert reponse.data["intitule"] == "Guichetier senior" and "Conditions\nNuit" in reponse.data["description"]

    def test_on_peut_donner_son_propre_intitule_et_lieu(self, api_client, equipe, ligne_a):
        reponse = ouvrir_offre(api_client, equipe["drh"], intitule="Guichetier de nuit", gare=ligne_a.gare_depart.id)

        assert reponse.data["intitule"] == "Guichetier de nuit" and reponse.data["gare_nom"] == "Gare Départ RH"

    @pytest.mark.parametrize("corps", [{"role": "superadmin"}, {"role": "astronaute"}, {"nombre_postes": 0}, {"date_limite": "2020-01-01"}])
    def test_les_offres_invalides_sont_refusees(self, api_client, equipe, corps):
        assert ouvrir_offre(api_client, equipe["drh"], **corps).status_code == 400

    def test_la_gare_doit_etre_de_la_compagnie(self, api_client, equipe, user_factory, company_b):
        from reseau.models import Gare

        etrangere = Gare.objects.create(nom="Gare B", ville="Bouaké", company=company_b)

        assert ouvrir_offre(api_client, equipe["drh"], gare=etrangere.id).status_code == 400

    @pytest.mark.parametrize("poste", ["pdg", "secretaire_general"])
    def test_la_direction_voit_les_offres(self, api_client, equipe, poste):
        ouvrir_offre(api_client, equipe["drh"])

        api_client.force_authenticate(user=equipe[poste])
        assert len(api_client.get("/api/offres-recrutement/").data) == 1
        assert ouvrir_offre(api_client, equipe[poste]).status_code == 403

    @pytest.mark.parametrize("poste", ["chef_gare", "guichetier", "qhse"])
    def test_les_autres_postes_ne_les_voient_pas(self, api_client, equipe, poste):
        api_client.force_authenticate(user=equipe[poste])

        assert api_client.get("/api/offres-recrutement/").status_code == 403

    def test_le_filtre_par_statut(self, api_client, equipe):
        cree = ouvrir_offre(api_client, equipe["drh"]).data["id"]
        ouvrir_offre(api_client, equipe["drh"], role="bagagiste")
        api_client.patch(f"/api/offres-recrutement/{cree}/", {"statut": "cloturee"}, format="json")

        assert [o["role"] for o in api_client.get("/api/offres-recrutement/", {"statut": "ouverte"}).data] == ["bagagiste"]


@pytest.mark.django_db
class TestCandidatures:
    def test_une_candidature_suit_son_parcours(self, api_client, equipe):
        offre = ouvrir_offre(api_client, equipe["drh"], nombre_postes=2).data["id"]
        cree = candidater(api_client, equipe["drh"], offre)
        assert cree.status_code == 201 and cree.data["statut"] == "recue" and cree.data["offre_intitule"]

        for statut in ("preselectionnee", "entretien", "retenue"):
            assert api_client.patch(f"/api/candidatures/{cree.data['id']}/", {"statut": statut}, format="json").data["statut_libelle"]
        assert api_client.get("/api/offres-recrutement/").data[0]["retenues"] == 1

    def test_l_offre_est_pourvue_quand_assez_de_candidats_sont_retenus(self, api_client, equipe):
        offre = ouvrir_offre(api_client, equipe["drh"], nombre_postes=2).data["id"]
        premier = candidater(api_client, equipe["drh"], offre, nom="A").data["id"]
        second = candidater(api_client, equipe["drh"], offre, nom="B").data["id"]

        api_client.patch(f"/api/candidatures/{premier}/", {"statut": "retenue"}, format="json")
        assert api_client.get("/api/offres-recrutement/").data[0]["statut"] == "ouverte"
        api_client.patch(f"/api/candidatures/{second}/", {"statut": "retenue"}, format="json")

        offre_lue = api_client.get("/api/offres-recrutement/").data[0]
        assert offre_lue["statut"] == "pourvue" and offre_lue["retenues"] == 2 and offre_lue["candidatures_total"] == 2

    def test_on_ne_candidate_pas_a_une_offre_close(self, api_client, equipe):
        offre = ouvrir_offre(api_client, equipe["drh"]).data["id"]
        api_client.patch(f"/api/offres-recrutement/{offre}/", {"statut": "cloturee"}, format="json")

        assert candidater(api_client, equipe["drh"], offre).status_code == 400

    def test_les_candidatures_d_une_autre_compagnie_sont_intouchables(self, api_client, equipe, user_factory, company_b):
        offre = ouvrir_offre(api_client, equipe["drh"]).data["id"]
        cree = candidater(api_client, equipe["drh"], offre).data["id"]
        drh_b = user_factory("drh_b_cand", "drh", company=company_b)

        assert candidater(api_client, drh_b, offre).status_code == 400
        api_client.force_authenticate(user=drh_b)
        assert api_client.get("/api/candidatures/").data == []
        assert api_client.patch(f"/api/candidatures/{cree}/", {"statut": "retenue"}, format="json").status_code == 404

    def test_le_filtre_par_offre_et_par_statut(self, api_client, equipe):
        premiere = ouvrir_offre(api_client, equipe["drh"]).data["id"]
        seconde = ouvrir_offre(api_client, equipe["drh"], role="bagagiste").data["id"]
        candidater(api_client, equipe["drh"], premiere, nom="A")
        refusee = candidater(api_client, equipe["drh"], seconde, nom="B").data["id"]
        api_client.patch(f"/api/candidatures/{refusee}/", {"statut": "refusee"}, format="json")

        assert [c["nom"] for c in api_client.get("/api/candidatures/", {"offre": seconde}).data] == ["B"]
        assert [c["nom"] for c in api_client.get("/api/candidatures/", {"statut": "recue"}).data] == ["A"]

    @pytest.mark.parametrize("corps", [{"statut": "embauchee"}, {"email": "pas-un-mail"}, {"nom": ""}, {"telephone": ""}])
    def test_les_candidatures_invalides_sont_refusees(self, api_client, equipe, corps):
        offre = ouvrir_offre(api_client, equipe["drh"]).data["id"]

        assert candidater(api_client, equipe["drh"], offre, **corps).status_code == 400

    @pytest.mark.parametrize("poste", ["pdg", "secretaire_general", "chef_gare", "guichetier"])
    def test_seul_le_drh_gere_les_candidatures(self, api_client, equipe, poste):
        offre = ouvrir_offre(api_client, equipe["drh"]).data["id"]

        assert candidater(api_client, equipe[poste], offre).status_code == 403
