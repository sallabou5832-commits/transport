"""L'import du fichier de ventes exporté par le logiciel de la compagnie (CSV ou Excel), et le contrôle à bord des billets reçus."""

import datetime
import io
from decimal import Decimal

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from billetterie.models import SourceTicket, Ticket
from lien_billetterie.models import ImportVentes, ModeBilletterie
from lien_billetterie.services import enregistrer_vente
from lien_billetterie.tests.conftest import passer_en, vente
from personnel_roulant.tests.conftest_suivi import equipe, trajet  # noqa: F401

URL = "/api/lien-billetterie/imports/"


def csv_de(lignes, encodage="utf-8", separateur=";"):
    return "\r\n".join(separateur.join(cellules) for cellules in lignes).encode(encodage)


def deposer(api_client, utilisateur, contenu, nom="ventes.csv", logiciel="BilletPro"):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(URL, {"fichier": SimpleUploadedFile(nom, contenu), "logiciel": logiciel}, format="multipart")


@pytest.fixture
def mixte(company_a):
    passer_en(company_a, ModeBilletterie.MIXTE)


@pytest.fixture
def jour_heure(reseau):
    heure = timezone.localtime(reseau["demain_8h"])
    return f"{heure:%d/%m/%Y}", f"{heure:%H:%M}"


@pytest.mark.django_db
class TestImportCsv:
    def test_un_export_a_la_francaise_est_compris(self, api_client, agents, reseau, mixte, jour_heure):
        jour, heure = jour_heure
        contenu = csv_de(
            [
                ["N° billet", "Trajet", "Date", "Heure", "Client", "Téléphone", "Montant", "Moyen de paiement", "Date de vente"],
                ["BP-1", "Adjamé-Bouaké", jour, heure, "Awa Koné", "0700000001", "5 000 FCFA", "Espèces", ""],
                ["BP-2", "Adjamé-Bouaké", jour, heure, "Yao Kouassi", "0700000002", "4500,00", "Orange Money", ""],
                ["", "", "", "", "", "", "", "", ""],
            ],
            encodage="cp1252",  # « CSV (séparateur : point-virgule) » d'Excel en français
        )

        reponse = deposer(api_client, agents["directeur_exploitation"], contenu)

        assert reponse.status_code == 201, reponse.data
        assert reponse.data["lignes"] == 2 and reponse.data["creees"] == 2 and reponse.data["refusees"] == 0
        assert [ligne["ligne"] for ligne in reponse.data["rapport"]] == [2, 3]
        billets = {t.reference_externe: t for t in Ticket.objects.all()}
        assert billets["BP-1"].prix == Decimal("5000") and billets["BP-1"].mode_paiement == "especes"
        assert billets["BP-2"].prix == Decimal("4500") and billets["BP-2"].mode_paiement == "mobile_money"
        assert {t.source for t in billets.values()} == {SourceTicket.IMPORT} and billets["BP-1"].logiciel == "BilletPro"
        importation = ImportVentes.objects.get()
        assert importation.depose_par == agents["directeur_exploitation"] and importation.fichier == "ventes.csv"

    def test_reimporter_le_meme_fichier_ne_double_rien(self, api_client, agents, reseau, mixte):
        contenu = csv_de([["reference", "depart", "passager", "paiement"], ["BP-1", str(reseau["depart"].id), "Awa", "cash"]])
        deposer(api_client, agents["pdg"], contenu)

        reponse = deposer(api_client, agents["pdg"], contenu)

        assert reponse.data["deja_recues"] == 1 and reponse.data["creees"] == 0
        assert Ticket.objects.count() == 1

    def test_les_lignes_refusees_disent_pourquoi(self, api_client, agents, reseau, mixte):
        contenu = csv_de(
            [
                ["reference", "depart", "nom", "mode", "prix"],
                ["OK", str(reseau["depart"].id), "Awa", "momo", ""],
                ["KO-1", "999999", "Yao", "especes", ""],
                ["KO-2", str(reseau["depart"].id), "Ali", "chèque", ""],
                ["KO-3", str(reseau["depart"].id), "Ama", "especes", "gratuit"],
            ],
            separateur=",",
        )

        rapport = deposer(api_client, agents["pdg"], contenu).data["rapport"]

        assert [(ligne["reference"], ligne["statut"]) for ligne in rapport] == [
            ("OK", "creee"), ("KO-1", "refusee"), ("KO-2", "refusee"), ("KO-3", "refusee"),
        ]
        assert "depart" in rapport[1]["erreurs"] and "mode_paiement" in rapport[2]["erreurs"] and "prix" in rapport[3]["erreurs"]

    def test_un_en_tete_incomplet_est_refuse_en_entier(self, api_client, agents, reseau, mixte):
        reponse = deposer(api_client, agents["pdg"], csv_de([["billet", "client"], ["BP-1", "Awa"]]))

        assert reponse.status_code == 400
        assert "mode_paiement" in str(reponse.data["fichier"]) and "depart" in str(reponse.data["fichier"])
        assert not ImportVentes.objects.exists()

    @pytest.mark.parametrize("nom,contenu", [("ventes.pdf", b"%PDF-1.4"), ("ventes.csv", b""), ("ventes.xlsx", b"pas un zip")])
    def test_un_fichier_illisible_est_refuse(self, api_client, agents, mixte, nom, contenu):
        assert deposer(api_client, agents["pdg"], contenu, nom=nom).status_code == 400

    def test_le_fichier_et_le_logiciel_sont_obligatoires(self, api_client, agents, mixte):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.post(URL, {"logiciel": "BilletPro"}, format="multipart").status_code == 400
        assert deposer(api_client, agents["pdg"], csv_de([["reference"]]), logiciel="").status_code == 400

    def test_en_billetterie_integree_l_import_est_ferme(self, api_client, agents, reseau):
        contenu = csv_de([["reference", "depart", "passager", "paiement"], ["BP-1", str(reseau["depart"].id), "Awa", "cash"]])

        assert deposer(api_client, agents["pdg"], contenu).status_code == 403
        assert not Ticket.objects.exists()


@pytest.mark.django_db
class TestImportExcel:
    def test_un_classeur_excel_est_lu_avec_ses_dates_et_ses_nombres(self, api_client, agents, reseau, mixte):
        classeur = openpyxl.Workbook()
        feuille = classeur.active
        feuille.append(["Numéro billet", "Ligne", "Date et heure", "Passager", "Prix", "Mode de paiement", "Vendu le"])
        depart_local = timezone.localtime(reseau["demain_8h"]).replace(tzinfo=None)
        hier = (timezone.localtime() - datetime.timedelta(days=1)).replace(tzinfo=None, microsecond=0)
        feuille.append([12345, "Adjamé-Bouaké", depart_local, "Awa Koné", 5000, "Wave", hier])
        tampon = io.BytesIO()
        classeur.save(tampon)

        reponse = deposer(api_client, agents["pdg"], tampon.getvalue(), nom="export.xlsx")

        assert reponse.status_code == 201 and reponse.data["creees"] == 1, reponse.data
        billet = Ticket.objects.get()
        assert billet.reference_externe == "12345" and billet.depart == reseau["depart"]
        assert billet.mode_paiement == "mobile_money" and billet.prix == Decimal("5000")
        assert timezone.localtime(billet.date_vente).replace(tzinfo=None) == hier


@pytest.mark.django_db
class TestImportParLeChefDeGare:
    def test_le_chef_de_gare_n_importe_que_les_departs_de_sa_gare(self, api_client, agents, reseau, mixte):
        contenu = csv_de(
            [
                ["reference", "depart", "passager", "paiement"],
                ["A-1", str(reseau["depart"].id), "Awa", "especes"],
                ["Y-1", str(reseau["depart_yakro"].id), "Yao", "especes"],
            ]
        )

        rapport = deposer(api_client, agents["chef_gare"], contenu).data["rapport"]

        assert [ligne["statut"] for ligne in rapport] == ["creee", "refusee"]
        assert "votre gare" in str(rapport[1]["erreurs"]["depart"])

    def test_chacun_voit_les_imports_qu_il_doit_voir(self, api_client, agents, reseau, mixte):
        contenu = csv_de([["reference", "depart", "passager", "paiement"], ["A-1", str(reseau["depart"].id), "Awa", "cash"]])
        deposer(api_client, agents["chef_gare"], contenu)
        deposer(api_client, agents["pdg"], contenu, nom="autre.csv")

        api_client.force_authenticate(user=agents["chef_gare"])
        assert [i["fichier"] for i in api_client.get(URL).data] == ["ventes.csv"]
        assert "rapport" not in api_client.get(URL).data[0]
        api_client.force_authenticate(user=agents["directeur_exploitation"])
        assert len(api_client.get(URL).data) == 2

    @pytest.mark.parametrize("role", ["guichetier", "chef_ligne", "directeur_financier", "qhse"])
    def test_les_autres_postes_n_importent_pas(self, api_client, agents, reseau, mixte, role):
        contenu = csv_de([["reference", "depart", "passager", "paiement"], ["A-1", str(reseau["depart"].id), "Awa", "cash"]])

        assert deposer(api_client, agents[role], contenu).status_code == 403


@pytest.mark.django_db
class TestControleABord:
    def test_le_controleur_reconnait_le_code_imprime_par_le_logiciel(self, api_client, equipe, trajet):  # noqa: F811
        company = trajet["ligne"].company
        passer_en(company, ModeBilletterie.EXTERNE)
        recue = enregistrer_vente(
            company, vente(trajet["depart"], reference="bp-77 31", prix="5000"), source=SourceTicket.LIEN, logiciel="BilletPro"
        )
        assert recue["statut"] == "creee", recue
        api_client.force_authenticate(user=equipe["controleur_ligne"])
        controle = api_client.post("/api/controles/", {"feuille_de_route": trajet["feuille"].id}, format="json").data

        premiere = api_client.post(f"/api/controles/{controle['id']}/verifier/", {"code": "BP7731"}, format="json")
        seconde = api_client.post(f"/api/controles/{controle['id']}/verifier/", {"code": "bp-77 31"}, format="json")

        assert premiere.data["resultat"] == "valide" and seconde.data["resultat"] == "deja_utilise"
