"""Contrat entre les tableaux de bord web et l'API.

Le code des pages (frontend/src/pages) est lu tel quel : chaque appel `apiFetch` est extrait, puis
confronté aux permissions de l'API pour **chaque rôle auquel la page est proposée** (frontend/src/auth/roles.js).
Une page qui appelle une route interdite à l'un de ses rôles afficherait une erreur 403 à l'utilisateur :
ce test l'attrape avant lui.

- lectures (GET) : la route doit répondre 200 ;
- actions (POST, PATCH, DELETE) : la route doit annoncer l'action au rôle (OPTIONS liste POST/PUT quand les
  permissions le permettent), sans avoir à fabriquer de données pour chacune.
"""

import re
from pathlib import Path

import pytest
from django.utils import timezone

from core.models import Role

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"

# Ressource en tête de chemin -> clé de la donnée d'exemple dans `monde_a`.
RESSOURCES = {
    "departs": "depart",
    "incidents": "incident",
    "dossiers-agents": "dossier",
    "assurances": "assurance",
    "sinistres": "sinistre",
    "feuilles-de-route": "feuille",
    "ordres-reparation": "ordre",
    "tickets": "ticket",
    "alertes": "alerte",
    "blocages-securite": "blocage",
    "colis": "colis",
    "controles": "controle",
    "lignes": "ligne",
    "vehicules": "vehicule",
    "changements-ligne": "changement_ligne",
    "comptes": "compte",
    "investissements": "investissement",
    "plans-entretien": "plan_entretien",
    "demandes-pieces": "demande_piece",
    "fiche-vehicule": "vehicule",
    "affectations-gare": "affectation",
    "archives": "archive",
    "agenda": "evenement",
    "depenses": "depense",
    "factures": "facture",
    "budgets-carburant": "budget_carburant",
    "fournisseurs": "fournisseur",
    "conges": "conge",
    "obligations-formation": "obligation_formation",
    "contrats": "contrat",
    "evaluations": "evaluation",
    "mesures-disciplinaires": "mesure",
    "offres-recrutement": "offre",
    "candidatures": "candidature",
    "doleances": "doleance",
    "pieces-sinistre": "piece_sinistre",
    "modeles-juridiques": "modele",
    "relais": "relais",
}

# Chemins « /postes/{}/ » et « /agents/{}/ » de la configuration : la valeur dépend de celui qui appelle, puisqu'il ne
# règle que les postes directement sous son autorité. Rôle appelant -> un poste (et son agent) sous cette autorité.
SOUS_AUTORITE = {
    "pdg": "guichetier",
    "directeur_exploitation": "chef_gare",
    "chef_gare": "guichetier",
    "chef_ligne": "chauffeur_principal",
    "directeur_technique": "magasinier",
    "chef_atelier": "mecanicien",
}

# apiFetch ; apiTelecharger (exports et pièces jointes : toujours une lecture) ; apiEnvoyer (envoi d'un fichier : toujours un POST).
APPEL = re.compile(r"api(?:Fetch|Telecharger|Envoyer)\(\s*(`[^`]*`|'[^']*'|\"[^\"]*\")", re.S)
DEBUT_APPEL = re.compile(r"api(?:Fetch|Telecharger|Envoyer)\(")
METHODE = re.compile(r"method:\s*'(\w+)'")


def _bloc(texte, debut, fin):
    return texte[texte.index(debut) : texte.index(fin, texte.index(debut))]


def _roles_par_route():
    texte = (FRONTEND / "auth" / "roles.js").read_text(encoding="utf-8")
    bloc = _bloc(texte, "export const DASHBOARD_ROLES", "\n}")
    return {
        route: re.findall(r"'([a-z_]+)'", roles)
        for route, roles in re.findall(r"'(/dashboard/[a-z]+)':\s*\[(.*?)\]", bloc)
    }


def _roles_annexes():
    """Pages en plus du tableau de bord propre à chaque poste (ex. le journal d'audit)."""
    texte = (FRONTEND / "auth" / "roles.js").read_text(encoding="utf-8")
    bloc = _bloc(texte, "export const PAGES_ANNEXES", "\n}")
    return {
        route: re.findall(r"'([a-z_]+)'", roles) for route, roles in re.findall(r"'(/[a-z]+)':\s*\[(.*?)\]", bloc, re.S)
    }


def _pages_par_route():
    texte = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    bloc = _bloc(texte, "const PAGES = {", "\n}")
    return dict(re.findall(r"'(/[a-z/]+)':\s*(\w+),", bloc))


def _appels(nom_page):
    """[(méthode, chemin normalisé)] de tous les apiFetch d'une page **et des composants qu'elle importe** (leurs
    appels s'exécutent avec les droits du rôle qui voit la page) ; `${…}` devient `{}`."""
    texte = (FRONTEND / "pages" / f"{nom_page}.jsx").read_text(encoding="utf-8")
    vus, a_lire = set(), re.findall(r"from '\.\./components/(\w+)\.jsx'", texte)
    while a_lire:  # un composant qui en importe un autre (le Layout et la cloche d'alertes) compte aussi
        composant = a_lire.pop()
        if composant in vus:
            continue
        vus.add(composant)
        source = (FRONTEND / "components" / f"{composant}.jsx").read_text(encoding="utf-8")
        texte += "\n" + source
        a_lire += re.findall(r"from '\./(\w+)\.jsx'", source)
    appels = []
    for correspondance in APPEL.finditer(texte):
        chemin = re.sub(r"\$\{[^}]*\}", "{}", correspondance.group(1)[1:-1])
        suite = texte[correspondance.end() : correspondance.end() + 200]
        if correspondance.group(0).startswith("apiEnvoyer"):
            appels.append(("POST", chemin))
            continue
        methode = None if correspondance.group(0).startswith("apiTelecharger") else METHODE.search(DEBUT_APPEL.split(suite)[0])
        appels.append((methode.group(1) if methode else "GET", chemin))
    return sorted(set(appels))


ROLES_PAR_ROUTE = _roles_par_route()
ROLES_ANNEXES = _roles_annexes()
PAGES_PAR_ROUTE = _pages_par_route()
COUPLES = [(route, role) for route, roles in {**ROLES_PAR_ROUTE, **ROLES_ANNEXES}.items() for role in roles]


def _resoudre(chemin, monde_a, role=None, tous_les_roles=None):
    """Remplace les `{}` par des valeurs réelles : dates du jour, ou id de la donnée d'exemple."""
    aujourdhui = timezone.localdate().isoformat()
    chemin = chemin.replace("date_debut={}&date_fin={}", f"date_debut={aujourdhui}&date_fin={aujourdhui}")
    chemin = chemin.replace("chauffeur={}&date={}", f"chauffeur=1&date={aujourdhui}")  # feuille du jour d'un chauffeur
    chemin = chemin.replace("date_heure={}", "date_heure=2030-05-17T08:00")
    chemin = chemin.replace("?{}", "")  # requête construite dynamiquement (ex. les filtres du journal d'audit)

    def id_de(correspondance):
        ressource = correspondance.group(1)
        if ressource in ("postes", "agents"):
            if role not in SOUS_AUTORITE:
                pytest.fail(f"{role} n'a aucun poste sous son autorité : il ne devrait pas voir cette page.")
            sous_role = SOUS_AUTORITE[role]
            return f"/{ressource}/{sous_role if ressource == 'postes' else tous_les_roles[sous_role].id}/"
        if ressource not in RESSOURCES:
            pytest.fail(f"Chemin dynamique inconnu : /{ressource}/{{}}/ — ajoutez la ressource à RESSOURCES.")
        return f"/{ressource}/{monde_a[RESSOURCES[ressource]].id}/"

    return "/api" + re.sub(r"/([a-z-]+)/\{\}/", id_de, chemin)


class TestCouvertureDesRoles:
    def test_chaque_route_a_une_page_et_inversement(self):
        assert set(ROLES_PAR_ROUTE) | set(ROLES_ANNEXES) == set(PAGES_PAR_ROUTE)

    def test_chaque_role_a_exactement_un_tableau_de_bord(self):
        attribues = [role for roles in ROLES_PAR_ROUTE.values() for role in roles]

        assert sorted(attribues) == sorted(role.value for role in Role), (
            "Chaque rôle doit avoir exactement un tableau de bord : "
            f"manquants {set(r.value for r in Role) - set(attribues)}, "
            f"en double {[r for r in set(attribues) if attribues.count(r) > 1]}"
        )

    @pytest.mark.parametrize("route", list(PAGES_PAR_ROUTE))
    def test_chaque_page_charge_ses_donnees_par_l_api(self, route):
        # Une page sans aucun appel serait une page vide : à signaler, pas à laisser passer.
        assert _appels(PAGES_PAR_ROUTE[route]), f"{PAGES_PAR_ROUTE[route]} n'appelle aucune route de l'API"


@pytest.mark.django_db
class TestLecturesDesPages:
    @pytest.mark.parametrize("route,role", COUPLES)
    def test_chaque_lecture_est_autorisee_a_chaque_role_de_la_page(
        self, api_client, tous_les_roles, monde_a, route, role
    ):
        api_client.force_authenticate(user=tous_les_roles[role])

        for methode, chemin in _appels(PAGES_PAR_ROUTE[route]):
            if methode != "GET" or chemin.startswith("/auth/"):
                continue
            url = _resoudre(chemin, monde_a, role, tous_les_roles)
            statut = api_client.get(url).status_code
            assert statut == 200, f"{route} : {role} reçoit {statut} sur GET {url}"


@pytest.mark.django_db
class TestActionsDesPages:
    @pytest.mark.parametrize("route,role", COUPLES)
    def test_chaque_action_est_permise_a_chaque_role_de_la_page(
        self, api_client, tous_les_roles, monde_a, route, role
    ):
        api_client.force_authenticate(user=tous_les_roles[role])

        for methode, chemin in _appels(PAGES_PAR_ROUTE[route]):
            if methode == "GET" or chemin.startswith("/auth/"):
                continue
            url = _resoudre(chemin, monde_a, role, tous_les_roles)
            reponse = api_client.options(url)
            assert reponse.status_code == 200, f"{route} : {role} reçoit {reponse.status_code} sur OPTIONS {url}"
            annonce = set(reponse.json().get("actions", {}))
            # PATCH passe par le même contrôle que PUT ; DELETE n'est pas annoncé par OPTIONS.
            attendu = {"POST"} if methode == "POST" else {"PUT"}
            assert attendu <= annonce, f"{route} : {role} n'a pas le droit de {methode} {url} (permis : {annonce})"
