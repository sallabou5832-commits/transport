"""Inventaire des boutons : chaque action d'écriture de l'API (POST, PATCH/PUT, DELETE) est appelée par au moins un écran, du site
ou de l'application mobile, ou figure dans EXCLUSIONS avec le motif qui justifie l'absence de bouton.

Les routes sont lues dans le routage de Django (pas de filtre sur leur nom) ; seules les variantes de format de réponse (`.json`)
sont écartées, d'après la structure de la route. Une nouvelle action sans écran fait échouer le test tant qu'on n'a ni construit
son bouton ni écrit pourquoi elle n'en a pas ; une exclusion devenue inutile (route disparue, ou désormais appelée) aussi.
"""

import re
from pathlib import Path

from django.urls import URLPattern, URLResolver, get_resolver

RACINE = Path(__file__).resolve().parents[2]
SITE = RACINE / "frontend" / "src"
MOBILE = RACINE / "mobile" / "lib"

# (méthode, chemin) -> motif. PATCH vaut pour « modifier » (PUT, quand il double PATCH, n'est pas compté à part).
_O13 = "O-13, prévu au lot P9 (côté RH) : le parcours de formation et la gestion des sessions n'ont pas encore d'écran"
EXCLUSIONS = {
    # Appelées par un autre logiciel, jamais par un écran.
    ("POST", "/api/lien-billetterie/ventes/"): "Appelée par le logiciel de billetterie de la compagnie, authentifié par sa clé",
    ("POST", "/api/lien-billetterie/annulations/"): "Appelée par le logiciel de billetterie de la compagnie, authentifié par sa clé",
    ("POST", "/api/tutelle/entrant/"): "Appelée par un compte de la tutelle (ministère, OSER, AMUGA, OFT), authentifié par sa clé",
    # Ce que l'application fait par un autre geste.
    ("POST", "/api/departs/"): "Un départ se crée par « Planifier un départ » (/departs/planifier/), qui ne propose que les cars et chauffeurs libres",
    ("POST", "/api/feuilles-de-route/"): "La feuille de route est créée par la planification du départ",
    ("PATCH", "/api/feuilles-de-route/{}/"): "La feuille avance par ses actions (démarrer, pause, relais, arriver), pas par une modification libre",
    ("PATCH", "/api/affectations-gare/{}/"): "L'équipe d'une gare se compose en affectant ou en retirant un agent (création, suppression)",
    # Ce qui ne se modifie ni ne s'efface, par conception.
    ("PATCH", "/api/tickets/{}/"): "Un billet vendu est verrouillé, refusé à tous : il s'annule (chef de gare, avec motif)",
    ("DELETE", "/api/tickets/{}/"): "Un billet vendu est verrouillé, refusé à tous : il ne s'efface pas, il s'annule (chef de gare, avec motif)",
    ("PATCH", "/api/checklists/{}/"): "Une checklist est une preuve de sécurité : elle se refait (l'envoi met l'item à jour), ne se corrige pas après coup",
    ("DELETE", "/api/checklists/{}/"): "Une checklist est une preuve de sécurité : elle ne s'efface pas",
    ("DELETE", "/api/dossiers-agents/{}/"): "Un dossier agent se termine par son statut, il ne s'efface pas",
    ("DELETE", "/api/offres-recrutement/{}/"): "Une offre se clôt par son statut (pourvue, annulée), elle ne s'efface pas",
    ("DELETE", "/api/candidatures/{}/"): "Une candidature se décide (retenue, refusée) et reste dans l'historique de l'offre",
    # Corriger, c'est retirer puis ressaisir (chaque version reste au journal d'audit).
    ("PATCH", "/api/agenda/{}/"): "Un rendez-vous se retire et se replanifie",
    ("PATCH", "/api/archives/{}/"): "Un dossier se classe, s'archive ou sort des archives par ses actions ; sa fiche ne se réécrit pas",
    ("PATCH", "/api/contrats/{}/"): "Un contrat saisi par erreur se retire de la fiche agent et se ressaisit",
    ("PATCH", "/api/evaluations/{}/"): "Une évaluation saisie par erreur se retire de la fiche agent et se ressaisit",
    ("PATCH", "/api/mesures-disciplinaires/{}/"): "Une mesure saisie par erreur se retire de la fiche agent et se ressaisit",
    ("PATCH", "/api/depenses/{}/"): "Une dépense erronée se supprime et se ressaisit",
    ("PATCH", "/api/factures/{}/"): "Une facture erronée s'annule ou se supprime et se ressaisit ; payée, elle est figée",
    ("PATCH", "/api/fournisseurs/{}/"): "Un fournisseur sans facture se retire et se ressaisit",
    ("PATCH", "/api/pieces-sinistre/{}/"): "Une pièce jointe se retire et se joint de nouveau",
    ("PATCH", "/api/plans-entretien/{}/"): "Un plan se retire et se redéclare ; « Fait » le remet à zéro",
    # Prévu, pas encore construit.
    ("POST", "/api/formation/mon-parcours/demarrer/"): _O13,
    ("POST", "/api/formation/mon-parcours/etapes/{}/terminer/"): _O13,
    ("PATCH", "/api/formations-suivies/{}/"): _O13,
    ("DELETE", "/api/formations-suivies/{}/"): _O13,
    ("PATCH", "/api/obligations-formation/{}/"): _O13,
}


def _chemin(motif):
    """`^api/lignes/(?P<pk>[^/.]+)/$` ou `api/lignes/<int:pk>/` -> `/api/lignes/{}/`."""
    chemin = re.sub(r"\(\?P<\w+>[^)]*\)", "{}", motif)
    chemin = re.sub(r"<(?:\w+:)?\w+>", "{}", chemin)
    chemin = chemin.replace("^", "").replace("$", "").replace("\\", "")
    return "/" + chemin.lstrip("/")


def _parcourir(motifs, prefixe=""):
    for motif in motifs:
        if isinstance(motif, URLResolver):
            yield from _parcourir(motif.url_patterns, prefixe + str(motif.pattern))
        elif isinstance(motif, URLPattern):
            yield prefixe + str(motif.pattern), motif


def routes_d_ecriture():
    """{(méthode, chemin) : vue} pour toutes les actions d'écriture de l'API."""
    routes = {}
    for brut, motif in _parcourir(get_resolver().url_patterns):
        vue = getattr(motif.callback, "cls", None)
        if vue is None or "format" in motif.pattern.regex.groupindex:  # variante « .json » d'une route déjà comptée
            continue
        chemin = _chemin(brut)
        if not chemin.startswith("/api/"):
            continue
        actions = getattr(motif.callback, "actions", None)
        methodes = (
            [m.upper() for m in actions if m not in ("get", "head", "options")]
            if actions
            else [m.upper() for m in ("post", "put", "patch", "delete") if hasattr(vue, m)]
        )
        methodes = [m for m in methodes if m.lower() in vue.http_method_names]  # ce que la vue accepte vraiment
        if "PATCH" in methodes and "PUT" in methodes:
            methodes.remove("PUT")
        for methode in methodes:
            routes[(methode, chemin if chemin.endswith("/") else chemin + "/")] = vue.__name__
    return routes


APPEL_SITE = re.compile(r"api(?:Fetch|Envoyer|Telecharger)\(\s*(`[^`]*`|'[^']*')")
APPEL_BRUT_SITE = re.compile(r"fetch\(\s*`\$\{API_BASE_URL\}([^`]*)`")
# Une petite fonction de la page qui reçoit le chemin : `function supprimer(chemin, …) { … apiFetch(chemin, { method: 'DELETE' }) }`,
# appelée avec des chemins écrits en clair (`supprimer(`/assurances/${a.id}/`, …)`).
FONCTION_RELAIS = re.compile(r"function (\w+)\((\w+)[^)]*\)\s*\{(.{0,600}?)apiFetch\(\2,\s*\{\s*method:\s*'(\w+)'", re.S)
APPEL_MOBILE = re.compile(r"\b_?api\.(get|post|patch|put|delete)\(\s*'([^']*)'")
APPEL_MOBILE_CONSTANTE = re.compile(r"\b_?api\.(get|post|patch|put|delete)\(\s*(\w+)\s*[,)]")
ENVOI_MOBILE = re.compile(r"_send\(\s*'(\w+)',\s*'([^']*)'")
CONSTANTE_MOBILE = re.compile(r"(?:static\s+)?const\s+(\w+)\s*=\s*'(/[^']*)'")


def _normaliser(chemin):
    chemin = re.sub(r"\$\{[^}]*\}|\$\w+", "{}", chemin).split("?")[0]
    return "/api" + (chemin if chemin.endswith("/") else chemin + "/")


def appels_des_ecrans():
    """{(méthode, chemin normalisé)} de tous les appels du site et du mobile."""
    appels = set()
    for fichier in SITE.rglob("*.js*"):
        if ".test." in fichier.name:
            continue
        texte = fichier.read_text(encoding="utf-8")
        for expression in (APPEL_SITE, APPEL_BRUT_SITE):
            for trouve in expression.finditer(texte):
                chemin = trouve.group(1).strip("`'")
                suite = re.split(r"api(?:Fetch|Envoyer|Telecharger)\(|fetch\(", texte[trouve.end() : trouve.end() + 300])[0]
                if trouve.group(0).startswith("apiEnvoyer"):
                    methode = "POST"
                else:
                    explicite = re.search(r"method:\s*'(\w+)'", suite)
                    methode = explicite.group(1) if explicite else "GET"
                appels.add((methode.upper(), _normaliser(chemin)))
        for nom, _, _, methode in FONCTION_RELAIS.findall(texte):
            for chemin in re.findall(rf"\b{nom}\(\s*(`[^`]*`|'[^']*')", texte):
                appels.add((methode.upper(), _normaliser(chemin.strip("`'"))))
    for fichier in MOBILE.rglob("*.dart"):
        texte = fichier.read_text(encoding="utf-8")
        constantes = dict(CONSTANTE_MOBILE.findall(texte))
        for methode, chemin in APPEL_MOBILE.findall(texte):
            appels.add((methode.upper(), _normaliser(chemin)))
        for methode, nom in APPEL_MOBILE_CONSTANTE.findall(texte):
            if nom in constantes:
                appels.add((methode.upper(), _normaliser(constantes[nom])))
        for methode, chemin in ENVOI_MOBILE.findall(texte):
            appels.add((methode.upper(), _normaliser(chemin)))
    return appels


def _appelee(methode, chemin, appels):
    # Un paramètre de la route ne correspond qu'à une valeur variable de l'écran (ou à un nombre écrit en clair) : jamais à un mot,
    # sans quoi `DELETE /tickets/reserver-hors-ligne/` passerait pour la suppression d'un billet (`DELETE /tickets/{}/`).
    modele = re.compile("^" + re.escape(chemin).replace(r"\{\}", r"(?:\{\}|\d+)") + "$")
    equivalentes = {"PATCH", "PUT"} if methode in ("PATCH", "PUT") else {methode}
    return any(m in equivalentes and modele.match(c) for m, c in appels)


ROUTES = routes_d_ecriture()
APPELS = appels_des_ecrans()


def test_l_inventaire_lit_bien_les_routes_et_les_ecrans():
    # Garde-fou : un routage ou des sources mal lus rendraient le test vide, donc faussement vert.
    assert len(ROUTES) > 150
    assert ("POST", "/api/tickets/") in APPELS and ("POST", "/api/auth/refresh/") in APPELS


def test_toute_action_de_l_api_a_un_bouton_ou_un_motif():
    sans_bouton = sorted(
        cle for cle in ROUTES if cle not in EXCLUSIONS and not _appelee(cle[0], cle[1], APPELS)
    )
    assert not sans_bouton, "Actions sans écran ni motif d'exclusion :\n" + "\n".join(
        f"  ({m!r}, {c!r}): {ROUTES[(m, c)]}" for m, c in sans_bouton
    )


def test_chaque_exclusion_designe_une_action_qui_existe_et_reste_sans_bouton():
    disparues = sorted(cle for cle in EXCLUSIONS if cle not in ROUTES)
    appelees = sorted(cle for cle in EXCLUSIONS if cle in ROUTES and _appelee(cle[0], cle[1], APPELS))
    assert not disparues, f"Exclusions de routes qui n'existent plus : {disparues}"
    assert not appelees, f"Exclusions devenues inutiles (un écran appelle désormais la route) : {appelees}"


def test_chaque_exclusion_a_un_motif():
    assert all(len(motif.strip()) >= 15 for motif in EXCLUSIONS.values())
