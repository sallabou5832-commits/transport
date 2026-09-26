"""Médiation sociale (cahier des charges : DRH — canal de médiation pour les doléances des agents et syndicats ; juridique — alerte
automatique de litige social au-delà d'un seuil de gravité)."""

import pytest

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from rh.models import Doleance


def deposer(api_client, utilisateur, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(
        "/api/doleances/", {"objet": "Heures supplémentaires impayées", "description": "Trois semaines de retard de paiement.", **corps}, format="json"
    )


def litiges(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get("/api/litiges-sociaux/")


@pytest.mark.django_db
class TestDepot:
    @pytest.mark.parametrize("poste", ["guichetier", "chauffeur_principal", "mecanicien", "qhse", "pdg", "responsable_juridique", "chef_gare"])
    def test_tout_agent_depose_sa_doleance(self, api_client, equipe, poste):
        reponse = deposer(api_client, equipe[poste])

        assert reponse.status_code == 201
        assert (reponse.data["origine"], reponse.data["statut"], reponse.data["gravite"]) == ("agent", "deposee", "moyenne")
        assert reponse.data["auteur"] == equipe[poste].id

    def test_le_superadmin_n_a_pas_de_compagnie(self, api_client, superadmin_user):
        assert deposer(api_client, superadmin_user).status_code == 403

    def test_un_agent_qualifie_sa_doleance_jusqu_a_grave(self, api_client, equipe):
        assert deposer(api_client, equipe["guichetier"], gravite="grave").status_code == 201
        assert deposer(api_client, equipe["guichetier"], gravite="critique").status_code == 400

    @pytest.mark.parametrize("corps", [{"statut": "resolue"}, {"origine": "syndicat"}, {"syndicat": "CSTCI"}])
    def test_un_agent_ne_touche_pas_au_traitement(self, api_client, equipe, corps):
        assert deposer(api_client, equipe["guichetier"], **corps).status_code == 400

    @pytest.mark.parametrize("corps", [{"objet": "x"}, {"description": "court"}, {"gravite": "extreme"}])
    def test_les_doleances_invalides_sont_refusees(self, api_client, equipe, corps):
        assert deposer(api_client, equipe["guichetier"], **corps).status_code == 400

    def test_le_drh_est_prevenu(self, api_client, equipe):
        deposer(api_client, equipe["guichetier"])

        (alerte,) = Alerte.objects.filter(type=TypeAlerte.DOLEANCE)
        assert alerte.titre == "Nouvelle doléance : Heures supplémentaires impayées" and alerte.roles_destinataires == ["drh"]
        assert "guichetier_rh" in alerte.message

    def test_le_drh_enregistre_la_doleance_d_un_syndicat(self, api_client, equipe):
        reponse = deposer(api_client, equipe["drh"], origine="syndicat", syndicat="Délégués du personnel", gravite="critique")

        assert reponse.status_code == 201 and reponse.data["auteur"] is None and reponse.data["syndicat"] == "Délégués du personnel"

    def test_le_drh_ne_depose_pas_a_la_place_d_un_agent(self, api_client, equipe):
        assert deposer(api_client, equipe["drh"]).status_code == 400
        assert deposer(api_client, equipe["drh"], origine="syndicat").status_code == 400  # sans dire quel syndicat

    def test_un_agent_ne_supprime_rien(self, api_client, equipe):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]

        assert api_client.delete(f"/api/doleances/{cree}/").status_code == 405


@pytest.mark.django_db
class TestTraitement:
    def test_chacun_ne_voit_que_les_siennes_le_drh_toutes(self, api_client, equipe):
        deposer(api_client, equipe["guichetier"])
        deposer(api_client, equipe["bagagiste"])

        def auteurs(poste):
            api_client.force_authenticate(user=equipe[poste])
            return {d["auteur"] for d in api_client.get("/api/doleances/").data}

        assert auteurs("guichetier") == {equipe["guichetier"].id}
        assert auteurs("chef_gare") == set()  # même leur supérieur ne les lit pas : la médiation est confidentielle
        assert auteurs("pdg") == set()
        assert auteurs("drh") == {equipe["guichetier"].id, equipe["bagagiste"].id}

    def test_seul_le_drh_modifie_une_doleance(self, api_client, equipe):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe["guichetier"])
        assert api_client.patch(f"/api/doleances/{cree}/", {"statut": "resolue"}, format="json").status_code == 403
        api_client.force_authenticate(user=equipe["drh"])
        reponse = api_client.patch(f"/api/doleances/{cree}/", {"statut": "en_mediation", "gravite": "critique"}, format="json")

        assert reponse.status_code == 200 and (reponse.data["statut"], reponse.data["gravite"]) == ("en_mediation", "critique")

    def test_les_etapes_de_suivi_sont_visibles_ou_non_du_deposant(self, api_client, equipe):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]
        api_client.force_authenticate(user=equipe["drh"])
        api_client.post(f"/api/doleances/{cree}/suivre/", {"texte": "Rencontre avec le chef de gare"}, format="json")
        api_client.post(f"/api/doleances/{cree}/suivre/", {"texte": "Note interne : dossier sensible", "visible_du_deposant": False}, format="json")

        vue_drh = api_client.get(f"/api/doleances/{cree}/").data
        api_client.force_authenticate(user=equipe["guichetier"])
        vue_agent = api_client.get(f"/api/doleances/{cree}/").data

        assert [s["texte"] for s in vue_drh["suivis"]] == ["Rencontre avec le chef de gare", "Note interne : dossier sensible"]
        assert [s["texte"] for s in vue_agent["suivis"]] == ["Rencontre avec le chef de gare"]

    def test_une_etape_peut_faire_avancer_le_statut_et_prevenir_l_agent(self, api_client, equipe):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe["drh"])
        reponse = api_client.post(f"/api/doleances/{cree}/suivre/", {"texte": "Accord trouvé", "statut": "resolue"}, format="json")

        assert reponse.status_code == 201 and Doleance.objects.get().statut == "resolue"
        alerte = Alerte.objects.filter(type=TypeAlerte.DOLEANCE, destinataires=equipe["guichetier"]).get()
        assert "Accord trouvé" in alerte.message

    def test_une_note_interne_ne_previent_pas_l_agent(self, api_client, equipe):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe["drh"])
        api_client.post(f"/api/doleances/{cree}/suivre/", {"texte": "Note interne", "visible_du_deposant": False}, format="json")

        assert not Alerte.objects.filter(type=TypeAlerte.DOLEANCE, destinataires=equipe["guichetier"]).exists()

    @pytest.mark.parametrize("corps", [{"texte": ""}, {"texte": "ok", "statut": "explose"}])
    def test_les_etapes_invalides_sont_refusees(self, api_client, equipe, corps):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe["drh"])
        assert api_client.post(f"/api/doleances/{cree}/suivre/", corps, format="json").status_code == 400

    @pytest.mark.parametrize("poste", ["guichetier", "pdg", "chef_gare"])
    def test_seul_le_drh_instruit(self, api_client, equipe, poste):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]

        api_client.force_authenticate(user=equipe[poste])
        assert api_client.post(f"/api/doleances/{cree}/suivre/", {"texte": "Je m'en occupe"}, format="json").status_code == 403

    def test_les_filtres_statut_et_gravite(self, api_client, equipe):
        deposer(api_client, equipe["guichetier"], gravite="faible")
        deposer(api_client, equipe["bagagiste"], gravite="grave")

        api_client.force_authenticate(user=equipe["drh"])
        assert len(api_client.get("/api/doleances/", {"gravite": "grave"}).data) == 1
        assert len(api_client.get("/api/doleances/", {"statut": "resolue"}).data) == 0

    def test_isolation_entre_compagnies(self, api_client, equipe, user_factory, company_b):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]
        drh_b = user_factory("drh_b_med", "drh", company=company_b)

        api_client.force_authenticate(user=drh_b)
        assert api_client.get("/api/doleances/").data == []
        assert api_client.get(f"/api/doleances/{cree}/").status_code == 404


@pytest.mark.django_db
class TestLitigeSocial:
    def alertes(self):
        return list(Alerte.objects.filter(type=TypeAlerte.LITIGE).order_by("id"))

    def test_en_dessous_du_seuil_le_juridique_n_est_pas_prevenu(self, api_client, equipe):
        deposer(api_client, equipe["guichetier"], gravite="moyenne")

        assert self.alertes() == [] and Doleance.objects.get().litige_signale_le is None

    def test_une_doleance_grave_previent_le_juridique_sans_l_identite_du_deposant(self, api_client, equipe):
        deposer(api_client, equipe["guichetier"], gravite="grave")

        (alerte,) = self.alertes()
        assert alerte.roles_destinataires == ["responsable_juridique"] and alerte.gravite == "attention"
        assert alerte.titre == "Risque de litige social (grave) : Heures supplémentaires impayées"
        assert "guichetier" not in alerte.message and "guichetier" not in alerte.titre
        assert Doleance.objects.get().litige_signale_le is not None

    def test_une_doleance_critique_previent_aussi_le_pdg(self, api_client, equipe):
        deposer(api_client, equipe["drh"], origine="syndicat", syndicat="CSTCI", gravite="critique")

        (alerte,) = self.alertes()
        assert set(alerte.roles_destinataires) == {"responsable_juridique", "pdg"} and alerte.gravite == "critique"

    def test_requalifier_une_doleance_au_dessus_du_seuil_declenche_l_alerte(self, api_client, equipe):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]
        assert self.alertes() == []

        api_client.force_authenticate(user=equipe["drh"])
        api_client.patch(f"/api/doleances/{cree}/", {"gravite": "grave"}, format="json")
        api_client.patch(f"/api/doleances/{cree}/", {"gravite": "critique"}, format="json")  # une nouvelle situation : une nouvelle alerte
        api_client.patch(f"/api/doleances/{cree}/", {"statut": "en_mediation"}, format="json")  # rien de neuf : pas de doublon

        assert [a.gravite for a in self.alertes()] == ["attention", "critique"]

    def test_une_doleance_resolue_ne_declenche_plus_rien(self, api_client, equipe):
        cree = deposer(api_client, equipe["guichetier"]).data["id"]
        api_client.force_authenticate(user=equipe["drh"])
        api_client.patch(f"/api/doleances/{cree}/", {"statut": "resolue", "gravite": "critique"}, format="json")

        assert self.alertes() == []

    def test_le_seuil_se_regle(self, api_client, equipe, settings):
        settings.MEDIATION_SEUIL_LITIGE = "moyenne"

        deposer(api_client, equipe["guichetier"], gravite="moyenne")

        assert len(self.alertes()) == 1

    def test_un_seuil_inconnu_retombe_sur_grave(self, api_client, equipe, settings):
        settings.MEDIATION_SEUIL_LITIGE = "n'importe quoi"

        deposer(api_client, equipe["guichetier"], gravite="moyenne")
        deposer(api_client, equipe["bagagiste"], gravite="grave")

        assert len(self.alertes()) == 1

    def test_le_passage_automatique_rattrape_une_doleance_creee_hors_de_l_api(self, equipe, company_a):
        Doleance.objects.create(company=company_a, auteur=equipe["guichetier"], objet="Harcèlement", description="Description détaillée.", gravite="grave")

        generer(company_a)
        generer(company_a)

        assert len(self.alertes()) == 1

    def test_le_juridique_voit_les_litiges_sans_identite(self, api_client, equipe):
        deposer(api_client, equipe["guichetier"], gravite="grave")
        deposer(api_client, equipe["bagagiste"], gravite="faible")  # sous le seuil : absent

        reponse = litiges(api_client, equipe["responsable_juridique"])

        assert reponse.status_code == 200 and reponse.data["seuil"] == "grave"
        (litige,) = reponse.data["litiges"]
        assert litige["objet"] == "Heures supplémentaires impayées" and litige["auteur_role"] == "guichetier" and litige["gravite"] == "grave"
        assert "auteur" not in litige and "auteur_nom" not in litige

    @pytest.mark.parametrize("poste", ["drh", "pdg"])
    def test_le_drh_et_le_pdg_lisent_aussi_les_litiges(self, api_client, equipe, poste):
        assert litiges(api_client, equipe[poste]).status_code == 200

    @pytest.mark.parametrize("poste", ["guichetier", "chef_gare", "qhse", "directeur_financier", "secretaire_general"])
    def test_les_autres_postes_ne_les_voient_pas(self, api_client, equipe, poste):
        assert litiges(api_client, equipe[poste]).status_code == 403

    def test_isolation_entre_compagnies(self, api_client, equipe, user_factory, company_b):
        deposer(api_client, equipe["guichetier"], gravite="grave")
        juriste_b = user_factory("juriste_b_lit", "responsable_juridique", company=company_b)

        assert litiges(api_client, juriste_b).data["litiges"] == []


@pytest.mark.django_db
class TestSyntheseRh:
    def test_le_drh_lit_les_chiffres_de_la_gestion_rh(self, api_client, equipe, oser):
        from rh.tests.test_conges import demander

        demander(api_client, equipe["guichetier"])
        deposer(api_client, equipe["bagagiste"], gravite="grave")
        api_client.force_authenticate(user=equipe["drh"])
        api_client.post("/api/offres-recrutement/", {"role": "guichetier", "nombre_postes": 1}, format="json")

        donnees = api_client.get("/api/rh/synthese/").data

        assert donnees["effectif"]["total"] == 17 and donnees["effectif"]["par_role"]["guichetier"] == 1
        assert donnees["formations"]["manquante"] == 2  # les deux conducteurs, aucune session
        assert donnees["conges"] == {"en_attente": 1, "en_cours": 0, "a_venir_30_jours": 0}
        assert donnees["recrutement"] == {"offres_ouvertes": 1, "candidatures_a_traiter": 0}
        assert donnees["mediation"] == {"ouvertes": 1, "litiges": 1, "a_traiter": 1}

    @pytest.mark.parametrize("poste", ["pdg", "secretaire_general"])
    def test_la_direction_la_lit_aussi(self, api_client, equipe, poste):
        api_client.force_authenticate(user=equipe[poste])

        assert api_client.get("/api/rh/synthese/").status_code == 200

    @pytest.mark.parametrize("poste", ["guichetier", "qhse", "chef_gare", "directeur_financier"])
    def test_les_autres_postes_non(self, api_client, equipe, poste):
        api_client.force_authenticate(user=equipe[poste])

        assert api_client.get("/api/rh/synthese/").status_code == 403
