"""Chaque échelon règle l'échelon directement subordonné ; le PDG, qui fixe le cadre, règle tous les postes."""

import pytest

from configuration.regles import (
    FONCTIONS,
    POSTES,
    SUBORDONNES,
    gamification_par_defaut,
    peut_configurer,
    plafonner,
    roles_configurables_par,
    NiveauAutomatisation,
    NiveauGamification,
)
from core.models import Role


class TestQuiRegleQui:
    def test_le_directeur_des_operations_regle_chefs_de_gare_chefs_de_ligne_et_controleurs(self):
        assert roles_configurables_par(Role.DIRECTEUR_EXPLOITATION) == {Role.CHEF_GARE, Role.CHEF_LIGNE, Role.CONTROLEUR_LIGNE}

    def test_le_chef_de_gare_regle_guichetiers_et_bagagistes(self):
        assert roles_configurables_par(Role.CHEF_GARE) == {Role.GUICHETIER, Role.BAGAGISTE}

    def test_le_chef_de_ligne_regle_les_chauffeurs(self):
        assert roles_configurables_par(Role.CHEF_LIGNE) == {Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS}

    def test_le_directeur_technique_regle_magasinier_et_chef_d_atelier_qui_regle_les_mecaniciens(self):
        assert roles_configurables_par(Role.DIRECTEUR_TECHNIQUE) == {Role.MAGASINIER, Role.CHEF_ATELIER}
        assert roles_configurables_par(Role.CHEF_ATELIER) == {Role.MECANICIEN}

    def test_le_pdg_regle_tous_les_postes_sauf_le_sien(self):
        assert roles_configurables_par(Role.PDG) == set(POSTES) - {Role.PDG}

    @pytest.mark.parametrize(
        "role",
        [Role.GUICHETIER, Role.BAGAGISTE, Role.CHAUFFEUR_PRINCIPAL, Role.MECANICIEN, Role.MAGASINIER, Role.DRH,
         Role.QHSE, Role.SUPERADMIN, Role.DIRECTEUR_FINANCIER],
    )
    def test_les_postes_du_bas_de_l_echelle_ne_reglent_personne(self, role):
        assert roles_configurables_par(role) == set()

    def test_personne_ne_se_regle_lui_meme_ni_ses_pairs_ni_son_superieur(self):
        assert not peut_configurer(Role.CHEF_GARE, Role.CHEF_GARE)
        assert not peut_configurer(Role.CHEF_GARE, Role.CHEF_LIGNE)
        assert not peut_configurer(Role.CHEF_GARE, Role.DIRECTEUR_EXPLOITATION)
        assert not peut_configurer(Role.GUICHETIER, Role.CHEF_GARE)

    def test_un_poste_n_a_qu_un_echelon_direct(self):
        # Sauf le PDG (cadre), chaque poste est sous l'autorité d'un seul rôle : pas d'ordres contradictoires.
        parents = {}
        for parent, enfants in SUBORDONNES.items():
            if parent == Role.PDG:
                continue
            for enfant in enfants:
                assert enfant not in parents, f"{enfant} a deux échelons directs : {parents[enfant]} et {parent}"
                parents[enfant] = parent

    def test_tous_les_postes_du_socle_ont_un_niveau_par_defaut(self):
        for role in POSTES:
            assert gamification_par_defaut(role) in ("sobre", "complet")

    def test_direction_support_et_juridique_demarrent_sobres_et_le_terrain_complet(self):
        assert gamification_par_defaut(Role.RESPONSABLE_JURIDIQUE) == "sobre"
        assert gamification_par_defaut(Role.DRH) == "sobre"
        assert gamification_par_defaut(Role.GUICHETIER) == "complet"
        assert gamification_par_defaut(Role.CHAUFFEUR_PRINCIPAL) == "complet"


class TestPlafond:
    def test_le_plus_bas_des_deux_l_emporte(self):
        ordre = NiveauAutomatisation.ORDRE
        assert plafonner("automatique", "assiste", ordre) == "assiste"
        assert plafonner("manuel", "assiste", ordre) == "manuel"
        assert plafonner("assiste", "assiste", ordre) == "assiste"
        assert plafonner("complet", "aucun", NiveauGamification.ORDRE) == "aucun"

    def test_les_fonctions_configurables_ont_un_libelle(self):
        assert set(FONCTIONS) == {"vente_ticket", "enregistrement_colis", "planification_departs", "cloture_caisse"}
        assert all(FONCTIONS.values())
