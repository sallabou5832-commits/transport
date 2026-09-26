"""La liste des comptes des essais de bout en bout (frontend/e2e/comptes.json) reste alignée sur les données de
démonstration et sur les routes du frontend : un poste ajouté sans compte d'essai, ou une page déplacée, se voit ici
plutôt que dans un scénario de navigateur qui échouerait sans qu'on sache pourquoi."""

import json
from pathlib import Path

from core.management.commands.seed_demo_users import DEMO_USERS
from core.models import Role
from role_coverage_tests.test_contrat_frontend import ROLES_PAR_ROUTE

COMPTES = json.loads((Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "comptes.json").read_text(encoding="utf-8"))
DEMO = {compte["username"]: compte for compte in DEMO_USERS}


def test_chaque_compte_d_essai_existe_dans_les_donnees_de_demonstration_avec_le_meme_role():
    for compte in COMPTES:
        assert compte["username"] in DEMO, f"{compte['username']} n'est pas créé par seed_demo_users"
        assert DEMO[compte["username"]]["role"] == compte["role"], compte["username"]


def test_chaque_role_a_un_compte_d_essai():
    assert {compte["role"] for compte in COMPTES} == {role.value for role in Role}


def test_la_page_attendue_est_celle_que_le_frontend_propose_a_ce_role():
    for compte in COMPTES:
        assert compte["role"] in ROLES_PAR_ROUTE[compte["page"]], (
            f"{compte['username']} : {compte['page']} n'est pas la page du rôle {compte['role']}"
        )
