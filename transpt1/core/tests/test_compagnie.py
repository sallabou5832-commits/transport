"""La fiche « Ma compagnie » (`/api/compagnie/`) et son logo (`/api/compagnie/logo/`) : chacun lit celle de sa compagnie, seul le
PDG la modifie, et rien ne touche une autre compagnie."""

import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from audit.models import JournalAudit
from core.models import Role

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def pdg_a(user_factory, company_a):
    return user_factory("pdg_fiche_a", Role.PDG, company=company_a)


@pytest.fixture
def pdg_b(user_factory, company_b):
    return user_factory("pdg_fiche_b", Role.PDG, company=company_b)


@pytest.fixture
def guichetier_a(user_factory, company_a):
    return user_factory("guichetier_fiche_a", Role.GUICHETIER, company=company_a)


def fichier(nom, contenu):
    return SimpleUploadedFile(nom, contenu, content_type="application/octet-stream")


@pytest.mark.django_db
class TestFicheCompagnie:
    def test_une_compagnie_sans_fiche_garde_ses_valeurs(self, api_client, guichetier_a, company_a):
        api_client.force_authenticate(user=guichetier_a)

        reponse = api_client.get("/api/compagnie/")

        assert reponse.status_code == 200
        assert reponse.data["id"] == company_a.id
        assert reponse.data["name"] == company_a.name
        assert reponse.data["sigle"] == "" and reponse.data["autorisation_echeance"] is None
        assert reponse.data["a_un_logo"] is False

    def test_le_pdg_remplit_la_fiche(self, api_client, pdg_a, company_a):
        api_client.force_authenticate(user=pdg_a)

        reponse = api_client.patch(
            "/api/compagnie/",
            {
                "sigle": "STC",
                "adresse": "Boulevard de Marseille, Abidjan",
                "telephone": "07 00 00 00 00",
                "email": "contact@stc.ci",
                "rccm": "CI-ABJ-2005-B-12345",
                "compte_contribuable": "0512345A",
                "autorisation_numero": "AT-2024-118",
                "autorisation_echeance": "2027-06-30",
            },
            format="json",
        )

        assert reponse.status_code == 200, reponse.data
        company_a.refresh_from_db()
        assert company_a.sigle == "STC"
        assert company_a.telephone == "07 00 00 00 00"
        assert company_a.autorisation_echeance == datetime.date(2027, 6, 30)
        # La modification est tracée, avec son auteur.
        entree = JournalAudit.objects.filter(objet_type="core.company", objet_id=str(company_a.id)).latest("id")
        assert entree.acteur_id == pdg_a.id
        assert entree.changements["sigle"] == ["", "STC"]

    @pytest.mark.parametrize("role", [Role.SECRETAIRE_GENERAL, Role.DIRECTEUR_FINANCIER, Role.GUICHETIER])
    def test_les_autres_postes_ne_la_modifient_pas(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_fiche", role, company=company_a))

        assert api_client.patch("/api/compagnie/", {"sigle": "X"}, format="json").status_code == 403
        company_a.refresh_from_db()
        assert company_a.sigle == ""

    def test_le_pdg_ne_touche_que_sa_compagnie(self, api_client, pdg_a, company_a, company_b):
        api_client.force_authenticate(user=pdg_a)

        api_client.patch("/api/compagnie/", {"sigle": "STC", "name": "STC Voyages SA"}, format="json")

        company_b.refresh_from_db()
        assert company_b.sigle == "" and company_b.name == "Express Savane"
        # L'ancienne route par identifiant reste fermée à une autre compagnie.
        assert api_client.get(f"/api/companies/{company_b.id}/").status_code == 403

    def test_le_superadmin_n_a_pas_de_fiche_propre(self, api_client, superadmin_user):
        api_client.force_authenticate(user=superadmin_user)

        assert api_client.get("/api/compagnie/").status_code == 403

    def test_numero_et_email_invalides_refuses(self, api_client, pdg_a):
        api_client.force_authenticate(user=pdg_a)

        reponse = api_client.patch("/api/compagnie/", {"telephone": "12ab", "email": "pas-un-email"}, format="json")

        assert reponse.status_code == 400
        assert set(reponse.data) == {"telephone", "email"}

    def test_la_raison_sociale_ne_peut_pas_etre_videe(self, api_client, pdg_a):
        api_client.force_authenticate(user=pdg_a)

        assert api_client.patch("/api/compagnie/", {"name": "  "}, format="json").status_code == 400

    def test_les_reponses_des_autres_objets_n_exposent_pas_la_fiche(self, api_client, pdg_a, company_a):
        """Les objets métier portent toujours la compagnie en abrégé (id, nom, ville, date) : la fiche n'est servie qu'ici."""
        company_a.rccm = "CI-ABJ-2005-B-12345"
        company_a.save()
        api_client.force_authenticate(user=pdg_a)

        moi = api_client.get("/api/auth/me/").data

        assert set(moi["company"]) == {"id", "name", "headquarters_city", "created_at"}


@pytest.mark.django_db
class TestLogoCompagnie:
    def test_le_pdg_envoie_puis_tous_recuperent_le_logo(self, api_client, pdg_a, guichetier_a, company_a):
        api_client.force_authenticate(user=pdg_a)
        envoi = api_client.post("/api/compagnie/logo/", {"fichier": fichier("logo.png", PNG)}, format="multipart")
        assert envoi.status_code == 200, envoi.data
        assert envoi.data["a_un_logo"] is True

        api_client.force_authenticate(user=guichetier_a)
        reponse = api_client.get("/api/compagnie/logo/")

        assert reponse.status_code == 200
        assert reponse["Content-Type"] == "image/png"
        assert reponse["X-Content-Type-Options"] == "nosniff"
        assert b"".join(reponse.streaming_content) == PNG

    def test_un_nouveau_logo_remplace_et_efface_l_ancien(self, api_client, pdg_a, company_a, media):
        api_client.force_authenticate(user=pdg_a)
        api_client.post("/api/compagnie/logo/", {"fichier": fichier("ancien.png", PNG)}, format="multipart")
        company_a.refresh_from_db()
        ancien = media / company_a.logo.name
        assert ancien.exists()

        assert api_client.post("/api/compagnie/logo/", {"fichier": fichier("neuf.jpg", JPEG)}, format="multipart").status_code == 200

        company_a.refresh_from_db()
        assert company_a.logo.name.endswith(".jpg")
        assert not ancien.exists()
        assert (media / company_a.logo.name).exists()

    def test_le_pdg_retire_le_logo(self, api_client, pdg_a, company_a, media):
        api_client.force_authenticate(user=pdg_a)
        api_client.post("/api/compagnie/logo/", {"fichier": fichier("logo.png", PNG)}, format="multipart")
        company_a.refresh_from_db()
        chemin = media / company_a.logo.name

        reponse = api_client.post("/api/compagnie/logo/retirer/")

        assert reponse.status_code == 200 and reponse.data["a_un_logo"] is False
        company_a.refresh_from_db()
        assert not company_a.logo and not chemin.exists()
        assert api_client.get("/api/compagnie/logo/").status_code == 404

    @pytest.mark.parametrize(
        "nom,contenu,attendu",
        [
            ("logo.pdf", PDF, "PNG ou JPEG"),  # type accepté ailleurs, pas pour un logo
            ("logo.png", b"MZ\x90\x00" + b"\x00" * 64, "ne correspond pas"),  # exécutable renommé
            ("logo.gif", b"GIF89a" + b"\x00" * 64, "Types acceptés"),
        ],
    )
    def test_fichier_refuse(self, api_client, pdg_a, company_a, nom, contenu, attendu):
        api_client.force_authenticate(user=pdg_a)

        reponse = api_client.post("/api/compagnie/logo/", {"fichier": fichier(nom, contenu)}, format="multipart")

        assert reponse.status_code == 400
        assert attendu in str(reponse.data["fichier"])
        company_a.refresh_from_db()
        assert not company_a.logo

    def test_logo_trop_lourd_refuse(self, api_client, pdg_a):
        api_client.force_authenticate(user=pdg_a)
        lourd = b"\x89PNG\r\n\x1a\n" + b"\x00" * (1024 * 1024)

        reponse = api_client.post("/api/compagnie/logo/", {"fichier": fichier("logo.png", lourd)}, format="multipart")

        assert reponse.status_code == 400
        assert "1 Mo" in str(reponse.data["fichier"])

    def test_envoi_sans_fichier_refuse(self, api_client, pdg_a):
        api_client.force_authenticate(user=pdg_a)

        assert api_client.post("/api/compagnie/logo/", {}, format="multipart").status_code == 400

    def test_seul_le_pdg_envoie_ou_retire(self, api_client, guichetier_a):
        api_client.force_authenticate(user=guichetier_a)

        assert api_client.post("/api/compagnie/logo/", {"fichier": fichier("logo.png", PNG)}, format="multipart").status_code == 403
        assert api_client.post("/api/compagnie/logo/retirer/").status_code == 403
        # Pas de DELETE : le retrait passe par sa route, comme le fichier d'un modèle juridique.
        assert api_client.delete("/api/compagnie/logo/").status_code in (403, 405)

    def test_le_logo_d_une_compagnie_reste_a_elle(self, api_client, pdg_a, pdg_b, company_b):
        api_client.force_authenticate(user=pdg_a)
        api_client.post("/api/compagnie/logo/", {"fichier": fichier("logo.png", PNG)}, format="multipart")

        api_client.force_authenticate(user=pdg_b)

        assert api_client.get("/api/compagnie/logo/").status_code == 404
        company_b.refresh_from_db()
        assert not company_b.logo
