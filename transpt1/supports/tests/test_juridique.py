"""Volet juridique (cahier des charges : sinistres liés à l'incident déclaré, avec pièces jointes et statut ; bibliothèque de documents
juridiques types accessible aux autres pôles ; reporting juridique remonté à la Direction Générale)."""

import datetime
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte
from core.models import Role
from personnel_roulant.models import GraviteIncident, Incident, TypeIncident
from reseau.models import Vehicule
from rh.models import Doleance
from supports.models import Assurance, ModeleJuridique, PieceSinistre, Sinistre

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
DOCX = b"PK\x03\x04" + b"\x00" * 32


@pytest.fixture
def media(settings, tmp_path):
    """Les pièces jointes vont dans un dossier jetable, pas dans le vrai dossier de la compagnie."""
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def chauffeur_j(user_factory, company_a):
    return user_factory("chauffeur_j", Role.CHAUFFEUR_PRINCIPAL, company=company_a)


def declarer(api_client, acteur, vehicule, **corps):
    api_client.force_authenticate(user=acteur)
    return api_client.post(
        "/api/incidents/",
        {"vehicule": vehicule.id, "chauffeur": acteur.id, "type_incident": "accident", "description": "Collision à un carrefour.", "gravite": "moyenne", **corps},
        format="json",
    )


def fichier(nom="constat.pdf", contenu=PDF):
    return SimpleUploadedFile(nom, contenu, content_type="application/octet-stream")


@pytest.mark.django_db
class TestSinistreOuvertParUnAccident:
    def test_un_accident_declare_ouvre_le_dossier_de_sinistre(self, api_client, chauffeur_j, vehicule_a, responsable_juridique_a):
        reponse = declarer(api_client, chauffeur_j, vehicule_a)

        assert reponse.status_code == 201
        sinistre = Sinistre.objects.get()
        assert (sinistre.incident_id, sinistre.vehicule_id, sinistre.company_id, sinistre.statut) == (reponse.data["id"], vehicule_a.id, vehicule_a.company_id, "ouvert")
        assert sinistre.description == "Accident déclaré : Collision à un carrefour."

    def test_le_juridique_est_prevenu(self, api_client, chauffeur_j, vehicule_a):
        declarer(api_client, chauffeur_j, vehicule_a, gravite="grave")

        alerte = Alerte.objects.get(type=TypeAlerte.SINISTRE)
        assert alerte.roles_destinataires == ["responsable_juridique"] and alerte.gravite == "critique"
        assert alerte.titre == "Sinistre à instruire : accident du véhicule CI-4000-AA"

    def test_un_accident_moins_grave_alerte_en_attention(self, api_client, chauffeur_j, vehicule_a):
        declarer(api_client, chauffeur_j, vehicule_a, gravite="faible")

        assert Alerte.objects.get(type=TypeAlerte.SINISTRE).gravite == "attention"

    @pytest.mark.parametrize("type_incident", ["panne", "retard", "cargaison", "autre"])
    def test_les_autres_incidents_n_ouvrent_pas_de_sinistre(self, api_client, chauffeur_j, vehicule_a, type_incident):
        declarer(api_client, chauffeur_j, vehicule_a, type_incident=type_incident)

        assert not Sinistre.objects.exists() and not Alerte.objects.filter(type=TypeAlerte.SINISTRE).exists()

    def test_un_incident_requalifie_en_accident_ouvre_son_dossier_une_seule_fois(self, api_client, chauffeur_j, vehicule_a):
        cree = declarer(api_client, chauffeur_j, vehicule_a, type_incident="panne").data["id"]
        assert not Sinistre.objects.exists()

        api_client.patch(f"/api/incidents/{cree}/", {"type_incident": "accident"}, format="json")
        api_client.patch(f"/api/incidents/{cree}/", {"description": "Précisions après constat sur place."}, format="json")

        assert Sinistre.objects.count() == 1 and Alerte.objects.filter(type=TypeAlerte.SINISTRE).count() == 1

    def test_le_qhse_qui_declare_l_accident_ouvre_aussi_le_dossier(self, api_client, user_factory, company_a, chauffeur_j, vehicule_a):
        qhse = user_factory("qhse_j", Role.QHSE, company=company_a)

        reponse = declarer(api_client, qhse, vehicule_a, chauffeur=chauffeur_j.id)

        assert reponse.status_code == 201 and Sinistre.objects.filter(incident_id=reponse.data["id"]).exists()

    def test_un_echec_du_sinistre_n_empeche_pas_de_declarer_l_incident(self, api_client, chauffeur_j, vehicule_a, monkeypatch):
        def casse(incident):
            raise RuntimeError("panne du juridique")

        monkeypatch.setattr("personnel_roulant.views.ouvrir_sinistre_pour_incident", casse)

        reponse = declarer(api_client, chauffeur_j, vehicule_a)

        assert reponse.status_code == 201 and Incident.objects.count() == 1 and not Sinistre.objects.exists()


@pytest.mark.django_db
class TestSuiviDuSinistre:
    def sinistre_de(self, api_client, juriste, **corps):
        api_client.force_authenticate(user=juriste)
        return api_client.post("/api/sinistres/", {"description": "Dégât des eaux au dépôt.", **corps}, format="json")

    def test_le_sinistre_repris_d_un_incident_reprend_ses_informations(self, api_client, responsable_juridique_a, chauffeur_j, vehicule_a, company_a):
        incident = Incident.objects.create(
            company=company_a, vehicule=vehicule_a, chauffeur=chauffeur_j, type_incident=TypeIncident.PANNE,
            description="Moteur noyé.", gravite=GraviteIncident.MOYENNE,
        )

        reponse = self.sinistre_de(api_client, responsable_juridique_a, incident=incident.id, description="")

        assert reponse.status_code == 201
        assert reponse.data["vehicule"] == vehicule_a.id and reponse.data["description"] == "Panne — Moteur noyé."
        assert reponse.data["incident_resume"]["type"] == "Panne" and reponse.data["vehicule_immatriculation"] == "CI-4000-AA"

    def test_un_incident_n_a_qu_un_dossier(self, api_client, responsable_juridique_a, chauffeur_j, vehicule_a):
        declarer(api_client, chauffeur_j, vehicule_a)  # ouvre déjà le sinistre
        incident = Incident.objects.get()

        assert self.sinistre_de(api_client, responsable_juridique_a, incident=incident.id).status_code == 400

    def test_sans_incident_la_description_est_obligatoire(self, api_client, responsable_juridique_a):
        assert self.sinistre_de(api_client, responsable_juridique_a, description="").status_code == 400

    def test_la_cloture_est_datee_et_se_defait_a_la_reouverture(self, api_client, responsable_juridique_a):
        cree = self.sinistre_de(api_client, responsable_juridique_a).data["id"]
        assert Sinistre.objects.get().clos_le is None

        api_client.patch(f"/api/sinistres/{cree}/", {"statut": "clos"}, format="json")
        assert Sinistre.objects.get().clos_le is not None
        api_client.patch(f"/api/sinistres/{cree}/", {"statut": "en_cours"}, format="json")

        assert Sinistre.objects.get().clos_le is None

    def test_les_montants_et_la_reference_de_l_assureur(self, api_client, responsable_juridique_a):
        reponse = self.sinistre_de(api_client, responsable_juridique_a, montant_estime="1500000", reference_assureur="NSIA-2026-0042")

        assert reponse.data["montant_estime"] == "1500000.00" and reponse.data["reference_assureur"] == "NSIA-2026-0042"
        assert self.sinistre_de(api_client, responsable_juridique_a, montant_estime="-5").status_code == 400

    def test_le_filtre_par_statut(self, api_client, responsable_juridique_a):
        self.sinistre_de(api_client, responsable_juridique_a)
        clos = self.sinistre_de(api_client, responsable_juridique_a, statut="clos").data["id"]

        assert [s["id"] for s in api_client.get("/api/sinistres/", {"statut": "clos"}).data] == [clos]

    @pytest.mark.parametrize("poste", ["guichetier", "chef_ligne", "qhse", "pdg", "drh"])
    def test_les_autres_postes_n_y_accedent_pas(self, api_client, user_factory, company_a, poste):
        api_client.force_authenticate(user=user_factory(f"{poste}_sin", Role(poste), company=company_a))

        assert api_client.get("/api/sinistres/").status_code == 403


@pytest.mark.django_db
class TestPiecesJointes:
    @pytest.fixture
    def sinistre(self, company_a, vehicule_a):
        return Sinistre.objects.create(company=company_a, vehicule=vehicule_a, description="Collision.")

    def envoyer(self, api_client, utilisateur, sinistre, envoi=None, **corps):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post("/api/pieces-sinistre/", {"sinistre": sinistre.id, "fichier": envoi or fichier(), "libelle": "Constat amiable", **corps}, format="multipart")

    def test_le_juridique_joint_un_constat(self, api_client, responsable_juridique_a, sinistre, media):
        reponse = self.envoyer(api_client, responsable_juridique_a, sinistre)

        assert reponse.status_code == 201
        assert (reponse.data["nom_fichier"], reponse.data["libelle"], reponse.data["taille"]) == ("constat.pdf", "Constat amiable", len(PDF))
        assert reponse.data["ajoute_par_nom"] == "responsable_juridique_a" and "fichier" not in reponse.data
        piece = PieceSinistre.objects.get()
        assert os.path.exists(piece.fichier.path) and str(media) in piece.fichier.path

    def test_le_fichier_est_range_sous_un_nom_aleatoire_sans_rien_du_nom_envoye(self, api_client, responsable_juridique_a, sinistre, media):
        self.envoyer(api_client, responsable_juridique_a, sinistre, fichier("../../etc/passwd.pdf"))

        piece = PieceSinistre.objects.get()
        assert piece.nom_fichier == "passwd.pdf" and "passwd" not in piece.fichier.name and ".." not in piece.fichier.name
        assert piece.fichier.name.startswith(f"sinistres/{sinistre.company_id}/") and piece.fichier.name.endswith(".pdf")

    @pytest.mark.parametrize("nom,contenu", [("photo.png", PNG), ("photo.jpg", JPEG), ("photo.JPEG", JPEG), ("rapport.docx", DOCX), ("etat.xlsx", DOCX)])
    def test_les_types_courants_sont_acceptes(self, api_client, responsable_juridique_a, sinistre, media, nom, contenu):
        assert self.envoyer(api_client, responsable_juridique_a, sinistre, fichier(nom, contenu)).status_code == 201

    @pytest.mark.parametrize(
        "nom,contenu",
        [
            ("virus.exe", b"MZ\x90\x00"),
            ("script.js", b"alert(1)"),
            ("faux.pdf", b"MZ\x90\x00 pas un pdf"),  # extension mensongère : le contenu ne correspond pas
            ("faux.png", PDF),
            ("vide.pdf", b""),
            ("sans_extension", PDF),
        ],
    )
    def test_les_fichiers_douteux_sont_refuses(self, api_client, responsable_juridique_a, sinistre, media, nom, contenu):
        reponse = self.envoyer(api_client, responsable_juridique_a, sinistre, fichier(nom, contenu))

        assert reponse.status_code == 400 and "fichier" in reponse.data and not PieceSinistre.objects.exists()

    def test_un_fichier_trop_lourd_est_refuse(self, api_client, responsable_juridique_a, sinistre, media, settings):
        settings.PIECES_JOINTES_TAILLE_MAX_MO = 1

        assert self.envoyer(api_client, responsable_juridique_a, sinistre, fichier("gros.pdf", PDF + b"0" * (1024 * 1024))).status_code == 400
        assert self.envoyer(api_client, responsable_juridique_a, sinistre, fichier("petit.pdf", PDF + b"0" * 1000)).status_code == 201

    def test_le_sinistre_doit_etre_de_la_compagnie(self, api_client, responsable_juridique_a, company_b, media):
        etranger = Sinistre.objects.create(company=company_b, description="Chez un autre.")

        assert self.envoyer(api_client, responsable_juridique_a, etranger).status_code == 400

    def test_le_telechargement_se_fait_par_l_api_en_piece_jointe(self, api_client, responsable_juridique_a, sinistre, media):
        cree = self.envoyer(api_client, responsable_juridique_a, sinistre).data["id"]

        reponse = api_client.get(f"/api/pieces-sinistre/{cree}/telecharger/")

        assert reponse.status_code == 200 and b"".join(reponse.streaming_content) == PDF
        assert reponse["Content-Type"] == "application/pdf" and reponse["X-Content-Type-Options"] == "nosniff"
        assert reponse["Content-Disposition"].startswith("attachment") and "constat.pdf" in reponse["Content-Disposition"]

    def test_le_technique_peut_aussi_joindre_et_lire(self, api_client, directeur_technique_a, sinistre, media):
        cree = self.envoyer(api_client, directeur_technique_a, sinistre).data["id"]

        assert api_client.get(f"/api/pieces-sinistre/{cree}/telecharger/").status_code == 200

    @pytest.mark.parametrize("poste", ["guichetier", "qhse", "pdg", "chauffeur_principal"])
    def test_les_autres_postes_n_y_touchent_pas(self, api_client, user_factory, company_a, sinistre, media, responsable_juridique_a, poste):
        cree = self.envoyer(api_client, responsable_juridique_a, sinistre).data["id"]
        autre = user_factory(f"{poste}_pj", Role(poste), company=company_a)

        assert self.envoyer(api_client, autre, sinistre).status_code == 403
        assert api_client.get("/api/pieces-sinistre/").status_code == 403
        assert api_client.get(f"/api/pieces-sinistre/{cree}/telecharger/").status_code == 403

    def test_une_autre_compagnie_ne_telecharge_rien(self, api_client, responsable_juridique_a, sinistre, media, user_factory, company_b):
        cree = self.envoyer(api_client, responsable_juridique_a, sinistre).data["id"]
        juriste_b = user_factory("juriste_b_pj", Role.RESPONSABLE_JURIDIQUE, company=company_b)

        api_client.force_authenticate(user=juriste_b)
        assert api_client.get("/api/pieces-sinistre/").data == []
        assert api_client.get(f"/api/pieces-sinistre/{cree}/telecharger/").status_code == 404
        assert api_client.delete(f"/api/pieces-sinistre/{cree}/").status_code == 404

    def test_supprimer_une_piece_efface_le_fichier(self, api_client, responsable_juridique_a, sinistre, media):
        cree = self.envoyer(api_client, responsable_juridique_a, sinistre).data["id"]
        chemin = PieceSinistre.objects.get().fichier.path

        assert api_client.delete(f"/api/pieces-sinistre/{cree}/").status_code == 204
        assert not os.path.exists(chemin) and not PieceSinistre.objects.exists()

    def test_le_sinistre_compte_ses_pieces_et_le_filtre_par_sinistre(self, api_client, responsable_juridique_a, sinistre, company_a, media):
        autre = Sinistre.objects.create(company=company_a, description="Autre dossier.")
        self.envoyer(api_client, responsable_juridique_a, sinistre)
        self.envoyer(api_client, responsable_juridique_a, sinistre, fichier("photo.png", PNG))
        self.envoyer(api_client, responsable_juridique_a, autre)

        comptes = {s["id"]: s["pieces_total"] for s in api_client.get("/api/sinistres/").data}
        assert comptes == {sinistre.id: 2, autre.id: 1}
        assert len(api_client.get("/api/pieces-sinistre/", {"sinistre": sinistre.id}).data) == 2

    def test_on_corrige_le_libelle_mais_pas_le_fichier_ni_le_dossier(self, api_client, responsable_juridique_a, sinistre, company_a, media):
        cree = self.envoyer(api_client, responsable_juridique_a, sinistre).data["id"]
        autre = Sinistre.objects.create(company=company_a, description="Autre dossier.")
        avant = PieceSinistre.objects.get().fichier.name

        reponse = api_client.patch(
            f"/api/pieces-sinistre/{cree}/", {"libelle": "Constat signé", "sinistre": autre.id, "fichier": fichier("autre.pdf")}, format="multipart"
        )

        piece = PieceSinistre.objects.get()
        assert reponse.status_code == 200 and reponse.data["libelle"] == "Constat signé"
        assert piece.sinistre_id == sinistre.id and piece.fichier.name == avant and piece.nom_fichier == "constat.pdf"

    def test_sans_authentification(self, api_client):
        assert api_client.get("/api/pieces-sinistre/").status_code == 401


@pytest.mark.django_db
class TestBibliothequeDeModeles:
    def creer(self, api_client, utilisateur, **corps):
        api_client.force_authenticate(user=utilisateur)
        return api_client.post(
            "/api/modeles-juridiques/",
            {"titre": "Attestation de travail", "categorie": "travail", "contenu": "Je soussigné [nom], atteste que [agent]…", **corps},
            format="json",
        )

    def test_le_juridique_publie_un_modele(self, api_client, responsable_juridique_a):
        reponse = self.creer(api_client, responsable_juridique_a, description="À délivrer sur demande", version="2.1")

        assert reponse.status_code == 201
        assert (reponse.data["categorie_libelle"], reponse.data["version"], reponse.data["poles_libelles"]) == ("Contrats et documents de travail", "2.1", ["Tous les pôles"])
        assert reponse.data["auteur_nom"] == "responsable_juridique_a" and reponse.data["a_un_fichier"] is False

    @pytest.mark.parametrize("corps", [{"titre": " "}, {"contenu": ""}, {"categorie": "poesie"}, {"poles": ["astronomie"]}, {"poles": "technique"}])
    def test_les_modeles_invalides_sont_refuses(self, api_client, responsable_juridique_a, corps):
        assert self.creer(api_client, responsable_juridique_a, **corps).status_code == 400

    def test_un_titre_par_compagnie(self, api_client, responsable_juridique_a):
        self.creer(api_client, responsable_juridique_a)

        assert self.creer(api_client, responsable_juridique_a, titre="attestation de travail").status_code == 400

    @pytest.mark.parametrize("poste", ["guichetier", "drh", "pdg", "directeur_technique", "qhse"])
    def test_les_autres_pôles_consultent_sans_ecrire(self, api_client, user_factory, company_a, responsable_juridique_a, poste):
        self.creer(api_client, responsable_juridique_a)
        lecteur = user_factory(f"{poste}_mod", Role(poste), company=company_a)

        api_client.force_authenticate(user=lecteur)
        assert len(api_client.get("/api/modeles-juridiques/").data) == 1
        assert self.creer(api_client, lecteur, titre="Autre").status_code == 403

    def test_un_modele_reserve_a_certains_poles(self, api_client, user_factory, company_a, responsable_juridique_a):
        self.creer(api_client, responsable_juridique_a, titre="Pour tous")
        self.creer(api_client, responsable_juridique_a, titre="Atelier seulement", poles=["technique"])
        self.creer(api_client, responsable_juridique_a, titre="Direction et supports", poles=["direction", "supports"])

        def titres(poste):
            api_client.force_authenticate(user=user_factory(f"{poste}_pole", Role(poste), company=company_a))
            return {m["titre"] for m in api_client.get("/api/modeles-juridiques/").data}

        assert titres("mecanicien") == {"Pour tous", "Atelier seulement"}
        assert titres("guichetier") == {"Pour tous"}
        assert titres("pdg") == {"Pour tous", "Direction et supports"}
        assert titres("drh") == {"Pour tous", "Direction et supports"}
        api_client.force_authenticate(user=responsable_juridique_a)
        assert len(api_client.get("/api/modeles-juridiques/").data) == 3  # le juridique voit tout

    def test_recherche_et_filtre_par_categorie(self, api_client, responsable_juridique_a):
        self.creer(api_client, responsable_juridique_a, titre="Contrat CDD", contenu="Durée déterminée")
        self.creer(api_client, responsable_juridique_a, titre="Constat amiable", categorie="sinistre", description="Accident de la route")

        assert [m["titre"] for m in api_client.get("/api/modeles-juridiques/", {"q": "accident"}).data] == ["Constat amiable"]
        assert [m["titre"] for m in api_client.get("/api/modeles-juridiques/", {"q": "déterminée"}).data] == ["Contrat CDD"]
        assert [m["titre"] for m in api_client.get("/api/modeles-juridiques/", {"categorie": "sinistre"}).data] == ["Constat amiable"]

    def test_le_juridique_joint_remplace_puis_retire_un_fichier(self, api_client, responsable_juridique_a, media):
        cree = self.creer(api_client, responsable_juridique_a).data["id"]

        premier = api_client.post(f"/api/modeles-juridiques/{cree}/fichier/", {"fichier": fichier("modele.pdf")}, format="multipart")
        ancien = ModeleJuridique.objects.get().fichier.path
        assert premier.status_code == 200 and premier.data["a_un_fichier"] is True and premier.data["nom_fichier"] == "modele.pdf"

        api_client.post(f"/api/modeles-juridiques/{cree}/fichier/", {"fichier": fichier("v2.docx", DOCX)}, format="multipart")
        assert not os.path.exists(ancien) and ModeleJuridique.objects.get().nom_fichier == "v2.docx"

        retire = api_client.post(f"/api/modeles-juridiques/{cree}/retirer-fichier/")
        assert retire.data["a_un_fichier"] is False and not ModeleJuridique.objects.get().fichier

    def test_les_autres_pôles_telechargent_le_fichier_du_modele(self, api_client, responsable_juridique_a, user_factory, company_a, media):
        cree = self.creer(api_client, responsable_juridique_a).data["id"]
        api_client.post(f"/api/modeles-juridiques/{cree}/fichier/", {"fichier": fichier("modele.pdf")}, format="multipart")

        api_client.force_authenticate(user=user_factory("guichetier_dl", Role.GUICHETIER, company=company_a))
        reponse = api_client.get(f"/api/modeles-juridiques/{cree}/telecharger/")

        assert reponse.status_code == 200 and b"".join(reponse.streaming_content) == PDF and reponse["Content-Disposition"].startswith("attachment")

    def test_un_modele_sans_fichier_ne_se_telecharge_pas(self, api_client, responsable_juridique_a):
        cree = self.creer(api_client, responsable_juridique_a).data["id"]

        assert api_client.get(f"/api/modeles-juridiques/{cree}/telecharger/").status_code == 404

    def test_un_fichier_douteux_ou_absent_est_refuse(self, api_client, responsable_juridique_a, media):
        cree = self.creer(api_client, responsable_juridique_a).data["id"]

        assert api_client.post(f"/api/modeles-juridiques/{cree}/fichier/", {"fichier": fichier("x.exe", b"MZ")}, format="multipart").status_code == 400
        assert api_client.post(f"/api/modeles-juridiques/{cree}/fichier/", {}, format="multipart").status_code == 400
        assert not ModeleJuridique.objects.get().fichier

    def test_seul_le_juridique_joint_un_fichier(self, api_client, responsable_juridique_a, user_factory, company_a, media):
        cree = self.creer(api_client, responsable_juridique_a).data["id"]

        api_client.force_authenticate(user=user_factory("pdg_fic", Role.PDG, company=company_a))
        assert api_client.post(f"/api/modeles-juridiques/{cree}/fichier/", {"fichier": fichier()}, format="multipart").status_code == 403

    def test_supprimer_un_modele_efface_son_fichier(self, api_client, responsable_juridique_a, media):
        cree = self.creer(api_client, responsable_juridique_a).data["id"]
        api_client.post(f"/api/modeles-juridiques/{cree}/fichier/", {"fichier": fichier()}, format="multipart")
        chemin = ModeleJuridique.objects.get().fichier.path

        assert api_client.delete(f"/api/modeles-juridiques/{cree}/").status_code == 204
        assert not os.path.exists(chemin)

    def test_isolation_entre_compagnies(self, api_client, responsable_juridique_a, user_factory, company_b):
        cree = self.creer(api_client, responsable_juridique_a).data["id"]
        juriste_b = user_factory("juriste_b_mod", Role.RESPONSABLE_JURIDIQUE, company=company_b)

        api_client.force_authenticate(user=juriste_b)
        assert api_client.get("/api/modeles-juridiques/").data == []
        assert api_client.get(f"/api/modeles-juridiques/{cree}/").status_code == 404

    def test_le_superadmin_n_a_pas_de_compagnie(self, api_client, superadmin_user):
        api_client.force_authenticate(user=superadmin_user)

        assert api_client.get("/api/modeles-juridiques/").status_code == 403


@pytest.mark.django_db
class TestReportingJuridique:
    def reporting(self, api_client, utilisateur):
        api_client.force_authenticate(user=utilisateur)
        return api_client.get("/api/juridique/reporting/")

    def test_une_compagnie_sans_donnees_donne_un_rapport_vide(self, api_client, responsable_juridique_a):
        donnees = self.reporting(api_client, responsable_juridique_a).data

        assert donnees["sinistres"]["total"] == 0 and donnees["sinistres"]["delai_moyen_cloture_jours"] is None
        assert donnees["assurances"]["couverts_pourcent"] is None and donnees["points_de_vigilance"] == []

    def test_les_assurances_la_flotte_couverte_et_les_alertes(self, api_client, responsable_juridique_a, company_a, vehicule_a):
        aujourdhui = timezone.localdate()
        Assurance.objects.create(vehicule=vehicule_a, company=company_a, compagnie_assurance="NSIA", numero_police="P1", date_echeance=aujourdhui + datetime.timedelta(days=200))
        expiree = Vehicule.objects.create(immatriculation="CI-EXP-1", capacite=30, company=company_a)
        Assurance.objects.create(vehicule=expiree, company=company_a, compagnie_assurance="NSIA", numero_police="P2", date_echeance=aujourdhui - datetime.timedelta(days=3))
        Vehicule.objects.create(immatriculation="CI-SANS-1", capacite=30, company=company_a)
        Vehicule.objects.create(immatriculation="CI-BIENTOT-1", capacite=30, company=company_a)
        Assurance.objects.create(vehicule=Vehicule.objects.get(immatriculation="CI-BIENTOT-1"), company=company_a, compagnie_assurance="NSIA", numero_police="P3", date_echeance=aujourdhui + datetime.timedelta(days=10))

        donnees = self.reporting(api_client, responsable_juridique_a).data

        assert donnees["assurances"] == {"vehicules": 4, "couverts_pourcent": 50, "expirees": 1, "absentes": 1, "a_renouveler_30_jours": 1}
        assert "1 véhicule(s) avec une assurance expirée" in donnees["points_de_vigilance"]
        assert "1 véhicule(s) sans assurance enregistrée" in donnees["points_de_vigilance"]
        assert "1 assurance(s) à renouveler sous 30 jours" in donnees["points_de_vigilance"]

    def test_les_sinistres_par_statut_montants_delai_et_anciennete(self, api_client, responsable_juridique_a, company_a, vehicule_a):
        maintenant = timezone.now()
        ancien = Sinistre.objects.create(company=company_a, vehicule=vehicule_a, description="Ancien dossier", montant_estime=2000000, date=maintenant - datetime.timedelta(days=45))
        Sinistre.objects.create(company=company_a, vehicule=vehicule_a, description="Récent", statut="en_cours", montant_estime=500000, date=maintenant - datetime.timedelta(days=3))
        Sinistre.objects.create(
            company=company_a, description="Réglé", statut="clos", montant_indemnise=750000, date=maintenant - datetime.timedelta(days=40), clos_le=maintenant - datetime.timedelta(days=30)
        )

        donnees = self.reporting(api_client, responsable_juridique_a).data["sinistres"]

        assert (donnees["total"], donnees["ouvert"], donnees["en_cours"], donnees["clos"]) == (3, 1, 1, 1)
        assert donnees["anciens_ouverts"] == 1 and donnees["delai_moyen_cloture_jours"] == 10
        assert float(donnees["montant_estime_en_cours"]) == 2500000 and float(donnees["montant_indemnise"]) == 750000
        assert donnees["recents"][0]["description"] == "Récent" and ancien.id in [s["id"] for s in donnees["recents"]]
        assert "1 sinistre(s) ouvert(s) depuis plus de 30 jours" in self.reporting(api_client, responsable_juridique_a).data["points_de_vigilance"]

    def test_les_litiges_sociaux_ne_sont_que_comptes(self, api_client, responsable_juridique_a, company_a, user_factory):
        auteur = user_factory("auteur_lit", Role.GUICHETIER, company=company_a)
        for gravite in ("grave", "critique"):
            Doleance.objects.create(company=company_a, auteur=auteur, objet=f"Litige {gravite}", description="Description détaillée.", gravite=gravite, litige_signale_le=timezone.now())
        Doleance.objects.create(company=company_a, auteur=auteur, objet="Réglé", description="Description détaillée.", gravite="grave", statut="resolue", litige_signale_le=timezone.now())
        Doleance.objects.create(company=company_a, auteur=auteur, objet="Mineure", description="Description détaillée.", gravite="faible")  # jamais signalée

        reponse = self.reporting(api_client, responsable_juridique_a)

        assert reponse.data["litiges_sociaux"] == {"ouverts": 2, "critiques": 1, "resolus_30_jours": 1}
        assert "1 litige(s) social(aux) critique(s) ouvert(s)" in reponse.data["points_de_vigilance"]
        assert "auteur_lit" not in str(reponse.data) and "Litige" not in str(reponse.data)  # ni identité ni intitulé

    def test_la_conformite_et_les_modeles(self, api_client, responsable_juridique_a, company_a, vehicule_a):
        ModeleJuridique.objects.create(company=company_a, titre="Modèle", contenu="x", auteur=responsable_juridique_a)

        donnees = self.reporting(api_client, responsable_juridique_a).data

        assert donnees["modeles_disponibles"] == 1
        assert donnees["conformite"]["vehicules_non_conformes"] == 1 and donnees["conformite"]["taux_pourcent"] == 0  # le véhicule n'a aucune assurance

    @pytest.mark.parametrize("poste", ["responsable_juridique", "pdg", "secretaire_general"])
    def test_le_juridique_et_la_direction_le_lisent(self, api_client, user_factory, company_a, poste):
        assert self.reporting(api_client, user_factory(f"{poste}_rep", Role(poste), company=company_a)).status_code == 200

    @pytest.mark.parametrize("poste", ["drh", "directeur_financier", "qhse", "guichetier", "directeur_technique"])
    def test_les_autres_postes_ne_le_lisent_pas(self, api_client, user_factory, company_a, poste):
        assert self.reporting(api_client, user_factory(f"{poste}_rep", Role(poste), company=company_a)).status_code == 403

    def test_une_autre_compagnie_ne_voit_pas_ces_donnees(self, api_client, responsable_juridique_a, company_a, vehicule_a, user_factory, company_b):
        Sinistre.objects.create(company=company_a, description="Chez A")
        juriste_b = user_factory("juriste_b_rep", Role.RESPONSABLE_JURIDIQUE, company=company_b)

        assert self.reporting(api_client, juriste_b).data["sinistres"]["total"] == 0
