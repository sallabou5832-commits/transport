"""Matrice de conformité : chaque rôle × chaque endpoint que les tableaux de bord utilisent.

Les ensembles de rôles ci-dessous recopient PERMISSIONS.md (qui fait foi). Un écart entre ce
tableau et le code est un bug : l'un des deux est à corriger, pas ce test à assouplir.
"""

import pytest
from django.utils import timezone

from core.models import Role

TOUS_LES_ROLES = [r.value for r in Role]
PERIODE = "date_debut={0}&date_fin={0}"
# La comptabilité : tenue par la finance, lue par le PDG et son secrétaire général (pas par le superadmin : données de compagnie).
FINANCE = {"directeur_financier", "pdg", "secretaire_general"}
# Ressources humaines : la direction lit, le DRH tient ; le libre-service (congés, doléances, formations) est ouvert à tout poste de
# compagnie, chacun n'y voyant que ce qui le concerne (le superadmin, sans compagnie, n'y a pas accès).
DIRECTION_RH = {"drh", "pdg", "secretaire_general"}
COMPAGNIE = {r for r in TOUS_LES_ROLES if r != "superadmin"}

# endpoint -> rôles autorisés (tout autre rôle doit recevoir 403)
RESTREINTS = {
    "/api/dashboard/direction/": {"pdg", "secretaire_general", "qhse"},
    "/api/dashboard/qhse/": {"qhse"},
    "/api/dashboard/exploitation/": {"directeur_exploitation", "pdg", "secretaire_general"},
    "/api/dashboard/plateforme/": {"superadmin"},
    "/api/audit/": {"pdg", "secretaire_general", "qhse", "superadmin"},
    "/api/synthese-financiere/?" + PERIODE: {"directeur_financier", "pdg", "secretaire_general", "superadmin"},
    "/api/dossiers-agents/agents-sans-dossier/": {"drh"},
    "/api/assurances/": {"responsable_juridique", "directeur_technique"},
    "/api/assurances/echeance-proche/": {"responsable_juridique", "directeur_technique"},
    "/api/sinistres/": {"responsable_juridique", "directeur_technique"},
    "/api/incidents/graves/": {"qhse", "directeur_exploitation", "superadmin"},
    "/api/tickets/cloture-caisse/?" + PERIODE: {
        "superadmin", "pdg", "secretaire_general", "qhse", "directeur_exploitation",
        "chef_gare", "chef_ligne", "guichetier",
    },
    "/api/departs/{depart}/remplacants-possibles/": {
        "superadmin", "pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne",
    },
    # Colis : noms et téléphones des clients, donc pas de transparence par défaut (voir PERMISSIONS.md §8).
    "/api/colis/": {
        "superadmin", "pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne", "bagagiste",
        "guichetier", "controleur_ligne", "chauffeur_principal", "chauffeur_relais", "qhse",
    },
    "/api/departs/{depart}/plan-chargement/": {
        "superadmin", "pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne", "bagagiste",
        "guichetier", "controleur_ligne", "chauffeur_principal", "chauffeur_relais", "qhse",
    },
    # Où sont les cars, qui conduit depuis combien de temps : régulation, direction, QHSE, technique (pas le superadmin :
    # ces données sont celles d'une compagnie).
    "/api/positions/dernieres/": {
        "pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne", "qhse", "directeur_technique",
    },
    "/api/dashboard/carte/": {
        "pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne", "qhse", "directeur_technique",
    },
    # Contrôles à bord : billets, fraudes, infractions. Le contrôleur voit les siens, la supervision ceux de la compagnie.
    "/api/controles/": {
        "controleur_ligne", "qhse", "directeur_exploitation", "pdg", "secretaire_general", "chef_ligne", "chef_gare",
        "superadmin",
    },
    # Pouvoirs d'exploitation et de direction : fermer une ligne, suspendre un compte, valider un investissement.
    "/api/changements-ligne/": {"chef_ligne", "chef_gare", "directeur_exploitation", "pdg"},
    "/api/comptes/": {"pdg"},
    "/api/investissements/": {
        "pdg", "secretaire_general", "directeur_financier", "directeur_technique", "directeur_exploitation",
    },
    # Maintenance avancée : charge de l'atelier, demandes de pièces, suggestions de commande, fiche véhicule, rapport de
    # renouvellement. Données d'atelier : pas de transparence par défaut (voir PERMISSIONS.md §4).
    "/api/maintenance/charge-mecaniciens/": {"directeur_technique", "chef_atelier"},
    "/api/maintenance/besoin-renouvellement/": {
        "directeur_technique", "pdg", "secretaire_general", "directeur_exploitation", "directeur_financier",
    },
    "/api/pieces/suggestions-commande/": {"magasinier", "directeur_technique", "chef_atelier"},
    "/api/demandes-pieces/": {"magasinier", "mecanicien", "chef_atelier", "directeur_technique"},
    "/api/fiche-vehicule/{vehicule}/": {
        "directeur_technique", "chef_atelier", "mecanicien", "magasinier", "directeur_exploitation", "pdg",
        "secretaire_general", "qhse",
    },
    # « Santé de la gare » : le chef de gare pour la sienne, le pilotage de l'exploitation pour la gare de son choix (?gare=).
    "/api/dashboard/gare/?gare={gare}": {"chef_gare", "directeur_exploitation", "pdg", "secretaire_general"},
    # Secrétariat de la direction : archives réservées au secrétariat, agenda partagé de la direction, notes de service qui
    # ne visent que les postes concernés (le superadmin, sans compagnie, n'en lit aucune), messages directs des gares.
    "/api/archives/": {"secretaire_general", "pdg"},
    "/api/agenda/": {
        "pdg", "secretaire_general", "qhse", "directeur_exploitation", "directeur_technique", "directeur_financier", "drh",
        "responsable_juridique",
    },
    "/api/messages-directs/": {"chef_gare", "directeur_exploitation", "pdg", "secretaire_general"},
    "/api/notes-service/": {r for r in TOUS_LES_ROLES if r != "superadmin"},
    # Conformité réglementaire de la flotte : partagée par le QHSE et le juridique, lue par le technique, l'exploitation, la direction.
    "/api/conformite/": {
        "qhse", "responsable_juridique", "directeur_technique", "directeur_exploitation", "pdg", "secretaire_general",
    },
    # Carnet de route numérique : celui du conducteur connecté (les autres postes n'en ont pas).
    "/api/carnet-de-route/": {"chauffeur_principal", "chauffeur_relais"},
    # Finance : dépenses, budgets carburant, fournisseurs et factures, rentabilité, trésorerie, exports.
    "/api/depenses/": FINANCE,
    "/api/budgets-carburant/": FINANCE,
    "/api/fournisseurs/": FINANCE,
    "/api/factures/": FINANCE,
    "/api/finance/rentabilite/": FINANCE,
    "/api/finance/budget-carburant/": FINANCE,
    "/api/finance/tresorerie/": FINANCE,
    "/api/finance/configuration/": FINANCE,
    "/api/finance/export/?type=rentabilite": FINANCE,
    # RH : catalogue des formations (le QHSE y participe), synthèse, fiches de poste et recrutement (le DRH tient, la direction lit).
    "/api/obligations-formation/": {"drh", "qhse", "pdg", "secretaire_general"},
    "/api/rh/synthese/": DIRECTION_RH,
    "/api/fiches-poste/": DIRECTION_RH,
    "/api/offres-recrutement/": DIRECTION_RH,
    "/api/candidatures/": DIRECTION_RH,
    # Libre-service RH : chacun voit ses formations, congés, doléances, contrats, évaluations et mesures (et l'échelon ceux de ses postes).
    "/api/formations-obligatoires/suivi/": COMPAGNIE,
    "/api/formations-suivies/": COMPAGNIE,
    "/api/conges/": COMPAGNIE,
    "/api/doleances/": COMPAGNIE,
    "/api/contrats/": COMPAGNIE,
    "/api/evaluations/": COMPAGNIE,
    "/api/mesures-disciplinaires/": COMPAGNIE,
    # Juridique : litiges sociaux signalés, pièces de sinistre, reporting pour la direction, bibliothèque de modèles ouverte à tous les pôles.
    "/api/litiges-sociaux/": {"responsable_juridique", "drh", "pdg"},
    "/api/pieces-sinistre/": {"responsable_juridique", "directeur_technique"},
    "/api/juridique/reporting/": {"responsable_juridique", "pdg", "secretaire_general"},
    "/api/modeles-juridiques/": COMPAGNIE,
    "/api/gamification/agents/": {"drh", "pdg"},  # scores de tous les agents : aide à l'évaluation, pas de transparence
    "/api/clotures-caisse/": {
        "superadmin", "pdg", "secretaire_general", "qhse", "directeur_exploitation", "chef_gare", "chef_ligne",
        "guichetier",
    },
    "/api/affectations-gare/agents-affectables/": {
        "superadmin", "pdg", "secretaire_general", "directeur_exploitation", "chef_gare",
    },
}

# Lecture ouverte à tout utilisateur authentifié de la compagnie (règle générale de PERMISSIONS.md).
LECTURE_GENERALE = [
    "/api/auth/me/",
    "/api/gares/",
    "/api/lignes/",
    "/api/vehicules/",
    "/api/departs/",
    "/api/tickets/",
    "/api/feuilles-de-route/",
    "/api/checklists/",
    "/api/incidents/",
    "/api/pieces/",
    "/api/pieces/sous-seuil/",
    "/api/ordres-reparation/",
    "/api/ordres-reparation/file-attente/",  # la file de l'atelier, avec les retours estimés, remonte à la régulation
    "/api/plans-entretien/",
    "/api/plans-entretien/echeances/",
    "/api/sorties-pieces/",
    "/api/dossiers-agents/",
    "/api/alertes/",
    "/api/blocages-securite/",
    "/api/affectations-gare/",  # chacun n'y voit que son propre rattachement
    "/api/configuration/moi/",
    "/api/configuration/catalogue/",
    "/api/configuration/compagnie/",  # tous voient le cadre de leur compagnie ; seul le PDG le modifie
    "/api/configuration/postes/",  # liste vide pour qui ne règle personne
    "/api/configuration/agents/",
    "/api/suivi/moi/",  # « en_cours: false » pour qui ne conduit pas
    "/api/relais/",  # un conducteur y voit ses relais, la régulation tous ; liste vide pour les autres
    "/api/communication/catalogue/",  # les pôles et leurs postes
    "/api/gamification/moi/",
    "/api/gamification/classement/",  # « visible: false » pour qui n'a pas la gamification complète
]


def _url(gabarit, monde_a):
    aujourdhui = timezone.localdate().isoformat()
    return (
        gabarit.replace("{0}", aujourdhui)
        .replace("{depart}", str(monde_a["depart"].id))
        .replace("{vehicule}", str(monde_a["vehicule"].id))
        .replace("{gare}", str(monde_a["gare_depart"].id))
    )


@pytest.mark.django_db
class TestMatriceEndpointsRestreints:
    @pytest.mark.parametrize("role", TOUS_LES_ROLES)
    @pytest.mark.parametrize("gabarit", list(RESTREINTS))
    def test_seuls_les_roles_prevus_y_accedent(self, api_client, tous_les_roles, monde_a, gabarit, role):
        api_client.force_authenticate(user=tous_les_roles[role])

        statut = api_client.get(_url(gabarit, monde_a)).status_code

        attendu = 200 if role in RESTREINTS[gabarit] else 403
        assert statut == attendu, f"{role} sur {gabarit} : {statut} au lieu de {attendu}"

    @pytest.mark.parametrize("gabarit", list(RESTREINTS))
    def test_refuse_sans_authentification(self, api_client, monde_a, gabarit):
        assert api_client.get(_url(gabarit, monde_a)).status_code == 401


@pytest.mark.django_db
class TestLectureGenerale:
    @pytest.mark.parametrize("role", TOUS_LES_ROLES)
    @pytest.mark.parametrize("url", LECTURE_GENERALE)
    def test_tout_role_authentifie_peut_lire(self, api_client, tous_les_roles, monde_a, url, role):
        api_client.force_authenticate(user=tous_les_roles[role])

        assert api_client.get(url).status_code == 200

    def test_le_dossier_agent_reste_cloisonne(self, api_client, tous_les_roles, monde_a):
        """Exception à la transparence : données RH. Le DRH voit tous les dossiers ; les autres, seulement le leur et ceux des postes
        placés sous leur autorité (configuration hiérarchique) : ici, le dossier d'un contrôleur de ligne, que règlent le directeur de
        l'exploitation et le PDG. Sans les notes internes du DRH."""
        api_client.force_authenticate(user=tous_les_roles["drh"])
        assert [d["id"] for d in api_client.get("/api/dossiers-agents/").data] == [monde_a["dossier"].id]

        for role in TOUS_LES_ROLES:
            if role in ("drh", "superadmin"):
                continue
            api_client.force_authenticate(user=tous_les_roles[role])
            donnees = api_client.get("/api/dossiers-agents/").data
            if role in ("pdg", "directeur_exploitation"):
                assert [d["id"] for d in donnees] == [monde_a["dossier"].id], role
                assert "notes_rh" not in donnees[0], role
            else:
                assert donnees == [], role


@pytest.mark.django_db
class TestIsolationEntreCompagnies:
    """Aucune liste utilisée par un tableau de bord ne laisse passer la compagnie voisine."""

    LISTES = {
        "pdg": {
            "/api/gares/": "gare_depart",
            "/api/lignes/": "ligne",
            "/api/vehicules/": "vehicule",
            "/api/departs/": "depart",
            "/api/tickets/": "ticket",
            "/api/feuilles-de-route/": "feuille",
            "/api/incidents/": "incident",
            "/api/pieces/": "piece",
            "/api/ordres-reparation/": "ordre",
        },
        "responsable_juridique": {"/api/assurances/": "assurance", "/api/sinistres/": "sinistre"},
        "drh": {"/api/dossiers-agents/": "dossier"},
    }

    @pytest.mark.parametrize("role", list(LISTES))
    def test_les_listes_ne_contiennent_que_la_compagnie_de_l_utilisateur(
        self, api_client, tous_les_roles, monde_a, monde_b, role
    ):
        api_client.force_authenticate(user=tous_les_roles[role])

        for url, cle in self.LISTES[role].items():
            ids = {ligne["id"] for ligne in api_client.get(url).data}
            assert monde_a[cle].id in ids, f"{role} ne voit pas sa propre donnée sur {url}"
            assert monde_b[cle].id not in ids, f"{role} voit une donnée étrangère sur {url}"

    @pytest.mark.parametrize("role", list(LISTES))
    def test_l_acces_direct_a_une_donnee_etrangere_est_introuvable(
        self, api_client, tous_les_roles, monde_a, monde_b, role
    ):
        api_client.force_authenticate(user=tous_les_roles[role])

        for url, cle in self.LISTES[role].items():
            assert api_client.get(f"{url}{monde_b[cle].id}/").status_code == 404, url

    def test_les_annuaires_ne_fuient_pas(self, api_client, tous_les_roles, monde_a, monde_b, user_factory, company_b):
        etranger = user_factory("chauffeur_annuaire_b", Role.CHAUFFEUR_PRINCIPAL, company=company_b)
        api_client.force_authenticate(user=tous_les_roles["chef_ligne"])
        remplacants = api_client.get(f"/api/departs/{monde_a['depart'].id}/remplacants-possibles/").data
        assert etranger.id not in [c["id"] for c in remplacants["chauffeurs"]]
        assert monde_b["vehicule"].id not in [v["id"] for v in remplacants["vehicules"]]

        api_client.force_authenticate(user=tous_les_roles["drh"])
        sans_dossier = api_client.get("/api/dossiers-agents/agents-sans-dossier/").data
        assert etranger.id not in [a["id"] for a in sans_dossier]
