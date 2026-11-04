"""Le guide suit l'application : chaque fiche cite toutes les pages que le site ouvre à son poste (frontend/src/auth/roles.js), et
seulement celles-là ; les écrans communs sont ouverts à tous les postes d'une compagnie."""

import re
from pathlib import Path

import pytest

from communication.guides import COMMUNS, FICHES, MOBILE, PLATEFORME, SITE
from communication.poles import POLES, TOUS_LES_POSTES
from core.models import Role
from role_coverage_tests.test_contrat_frontend import ROLES_ANNEXES, ROLES_PAR_ROUTE

ROUTES_DU_POSTE = {}
for _route, _roles in {**ROLES_PAR_ROUTE, **ROLES_ANNEXES}.items():
    for _role in _roles:
        ROUTES_DU_POSTE.setdefault(_role, set()).add(_route)

ROUTES_COMMUNES = {e["chemin"] for e in COMMUNS["ecrans"] if e["support"] == SITE}

# Les postes qui ont un écran mobile dédié (mobile/lib/ui/home_screen.dart) ; les autres ont un accueil générique.
POSTES_MOBILES = {Role.GUICHETIER, Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS}

CONTENUS = {**FICHES, Role.SUPERADMIN: PLATEFORME["fiche"]}


def test_les_ecrans_communs_sont_ouverts_a_tous_les_postes_d_une_compagnie():
    for role in TOUS_LES_POSTES:
        assert ROUTES_COMMUNES <= ROUTES_DU_POSTE[role.value], role


@pytest.mark.parametrize("role", list(CONTENUS), ids=lambda r: r.value)
def test_la_fiche_cite_toutes_les_pages_du_poste_et_elles_seules(role):
    citees = [e["chemin"] for e in CONTENUS[role]["ecrans"] if e["support"] == SITE]

    assert len(citees) == len(set(citees)), "une page citée deux fois"
    assert set(citees) == ROUTES_DU_POSTE[role.value] - ROUTES_COMMUNES, (
        f"oubliées : {ROUTES_DU_POSTE[role.value] - ROUTES_COMMUNES - set(citees)}, "
        f"en trop : {set(citees) - ROUTES_DU_POSTE[role.value]}"
    )


def test_seuls_les_postes_a_ecran_mobile_dedie_citent_le_telephone():
    avec_mobile = {role for role, contenu in CONTENUS.items() if any(e["support"] == MOBILE for e in contenu["ecrans"])}

    assert avec_mobile == POSTES_MOBILES


def test_le_site_range_chaque_poste_dans_le_meme_pole_que_le_serveur():
    """La couleur de pôle de l'interface (frontend/src/auth/roles.js, POLE_DU_ROLE) suit le rangement des notes de service et du
    guide (communication/poles.py)."""
    texte = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "auth" / "roles.js").read_text(encoding="utf-8")
    bloc = texte[texte.index("export const POLE_DU_ROLE") : texte.index("\n}", texte.index("export const POLE_DU_ROLE"))]
    site = dict(re.findall(r"^\s+(\w+): '(\w+)',$", bloc, re.M))

    assert site.pop("superadmin") == "plateforme"
    assert site == {role.value: cle for cle, (_, roles) in POLES.items() for role in roles}
