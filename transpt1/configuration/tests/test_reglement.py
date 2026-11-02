"""Le règlement intérieur de la compagnie : tous le lisent, le PDG règle toutes les règles, chaque directeur celles de son pôle.
Ses effets (refus côté atelier, magasin et chauffeurs) sont vérifiés dans les tests de ces apps."""

import pytest

from audit.models import JournalAudit
from configuration.models import ReglementInterieur
from configuration.regles import REGLEMENT
from core.models import Role

URL = "/api/configuration/reglement/"
TECHNIQUE = {"sorties_pieces_corrigeables", "mecanicien_confie_ses_ordres", "mecanicien_supprime_ses_ordres"}
EXPLOITATION = {"chauffeur_supprime_ses_feuilles", "chauffeur_supprime_ses_incidents"}


def lire(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    reponse = api_client.get(URL)
    assert reponse.status_code == 200
    return {regle["code"]: regle for regle in reponse.data}


def regler(api_client, utilisateur, **regles):
    api_client.force_authenticate(user=utilisateur)
    return api_client.patch(URL, regles, format="json")


@pytest.mark.django_db
class TestLecture:
    def test_sans_reglage_tout_suit_le_defaut_du_socle(self, api_client, agents):
        regles = lire(api_client, agents["guichetier"])

        assert set(regles) == set(REGLEMENT) == TECHNIQUE | EXPLOITATION
        assert all(regle["permis"] is True and regle["defaut"] is True for regle in regles.values())

    def test_chaque_regle_dit_a_qui_elle_s_applique_et_quel_pole_la_regle(self, api_client, agents):
        regles = lire(api_client, agents["guichetier"])

        assert regles["sorties_pieces_corrigeables"]["postes"] == ["chef_atelier", "directeur_technique", "magasinier"]
        assert regles["sorties_pieces_corrigeables"]["pole"] == "directeur_technique"
        assert regles["chauffeur_supprime_ses_feuilles"]["postes"] == ["chauffeur_principal", "chauffeur_relais"]
        assert regles["chauffeur_supprime_ses_feuilles"]["pole"] == "directeur_exploitation"

    @pytest.mark.parametrize(
        "role,modifiables",
        [
            ("pdg", TECHNIQUE | EXPLOITATION),
            ("directeur_technique", TECHNIQUE),
            ("directeur_exploitation", EXPLOITATION),
            ("chef_atelier", set()),
            ("mecanicien", set()),
            ("chauffeur_principal", set()),
            ("secretaire_general", set()),
        ],
    )
    def test_chacun_voit_ce_qu_il_peut_regler(self, api_client, agents, role, modifiables):
        regles = lire(api_client, agents[role])

        assert {code for code, regle in regles.items() if regle["modifiable"]} == modifiables

    def test_refuse_sans_authentification(self, api_client, db):
        assert api_client.get(URL).status_code == 401


@pytest.mark.django_db
class TestReglage:
    def test_le_pdg_regle_toutes_les_regles(self, api_client, agents, company_a):
        reponse = regler(
            api_client, agents["pdg"], sorties_pieces_corrigeables=False, chauffeur_supprime_ses_feuilles=False
        )

        assert reponse.status_code == 200
        permis = {regle["code"]: regle["permis"] for regle in reponse.data}
        assert permis == {
            "sorties_pieces_corrigeables": False,
            "mecanicien_confie_ses_ordres": True,
            "mecanicien_supprime_ses_ordres": True,
            "chauffeur_supprime_ses_feuilles": False,
            "chauffeur_supprime_ses_incidents": True,
        }
        assert ReglementInterieur.objects.get(company=company_a).modifie_par == agents["pdg"]

    def test_un_reglage_partiel_garde_les_regles_deja_reglees(self, api_client, agents):
        regler(api_client, agents["pdg"], sorties_pieces_corrigeables=False)
        regler(api_client, agents["pdg"], mecanicien_supprime_ses_ordres=False)

        regles = lire(api_client, agents["pdg"])
        assert regles["sorties_pieces_corrigeables"]["permis"] is False
        assert regles["mecanicien_supprime_ses_ordres"]["permis"] is False

    def test_une_regle_se_remet_comme_avant(self, api_client, agents):
        regler(api_client, agents["pdg"], chauffeur_supprime_ses_incidents=False)
        regler(api_client, agents["pdg"], chauffeur_supprime_ses_incidents=True)

        assert lire(api_client, agents["pdg"])["chauffeur_supprime_ses_incidents"]["permis"] is True

    def test_le_directeur_technique_regle_l_atelier_et_le_magasin(self, api_client, agents, company_a):
        reponse = regler(api_client, agents["directeur_technique"], mecanicien_confie_ses_ordres=False)

        assert reponse.status_code == 200
        assert ReglementInterieur.objects.get(company=company_a).regles == {"mecanicien_confie_ses_ordres": False}

    def test_le_directeur_des_operations_regle_les_chauffeurs(self, api_client, agents):
        reponse = regler(api_client, agents["directeur_exploitation"], chauffeur_supprime_ses_feuilles=False)

        assert reponse.status_code == 200

    def test_un_directeur_ne_regle_pas_le_pole_d_un_autre(self, api_client, agents):
        reponse = regler(api_client, agents["directeur_technique"], chauffeur_supprime_ses_feuilles=False)

        assert reponse.status_code == 403
        assert not ReglementInterieur.objects.exists()

    def test_une_demande_qui_deborde_du_pole_est_refusee_en_entier(self, api_client, agents):
        reponse = regler(
            api_client, agents["directeur_exploitation"],
            chauffeur_supprime_ses_incidents=False, sorties_pieces_corrigeables=False,
        )

        assert reponse.status_code == 403
        assert "sorties_pieces_corrigeables" in str(reponse.data["detail"])
        assert lire(api_client, agents["pdg"])["chauffeur_supprime_ses_incidents"]["permis"] is True

    @pytest.mark.parametrize("role", ["chef_atelier", "mecanicien", "chef_ligne", "secretaire_general", "qhse", "drh"])
    def test_les_autres_postes_ne_reglent_rien(self, api_client, agents, role):
        assert regler(api_client, agents[role], sorties_pieces_corrigeables=False).status_code == 403
        # Le refus vient avant tout examen de la demande.
        assert regler(api_client, agents[role], inconnue="oui").status_code == 403

    def test_le_superadmin_sans_compagnie_ne_regle_rien(self, api_client, superadmin_user):
        assert regler(api_client, superadmin_user, sorties_pieces_corrigeables=False).status_code == 403

    @pytest.mark.parametrize(
        "corps,champ",
        [
            ({"inconnue": False}, "inconnue"),
            ({"sorties_pieces_corrigeables": "non"}, "sorties_pieces_corrigeables"),
            ({"sorties_pieces_corrigeables": 0}, "sorties_pieces_corrigeables"),
            ({"sorties_pieces_corrigeables": None}, "sorties_pieces_corrigeables"),
        ],
    )
    def test_une_valeur_invalide_est_refusee(self, api_client, agents, corps, champ):
        api_client.force_authenticate(user=agents["pdg"])

        reponse = api_client.patch(URL, corps, format="json")

        assert reponse.status_code == 400
        assert champ in reponse.data
        assert not ReglementInterieur.objects.exists()

    def test_un_corps_vide_est_refuse(self, api_client, agents):
        api_client.force_authenticate(user=agents["pdg"])

        assert api_client.patch(URL, {}, format="json").status_code == 400

    def test_une_compagnie_ne_touche_pas_au_reglement_d_une_autre(self, api_client, agents, user_factory, company_b):
        pdg_b = user_factory("pdg_b", Role.PDG, company=company_b)

        regler(api_client, agents["pdg"], sorties_pieces_corrigeables=False)

        assert lire(api_client, pdg_b)["sorties_pieces_corrigeables"]["permis"] is True

    def test_le_reglage_est_trace_dans_le_journal_d_audit(self, api_client, agents):
        regler(api_client, agents["pdg"], sorties_pieces_corrigeables=False)

        assert JournalAudit.objects.filter(objet_type="configuration.reglementinterieur", acteur=agents["pdg"]).exists()
