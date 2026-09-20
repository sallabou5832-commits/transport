"""Matrice de conformité : chaque rôle × chaque endpoint que les tableaux de bord utilisent.

Les ensembles de rôles ci-dessous recopient PERMISSIONS.md (qui fait foi). Un écart entre ce
tableau et le code est un bug : l'un des deux est à corriger, pas ce test à assouplir.
"""

import pytest
from django.utils import timezone

from core.models import Role

TOUS_LES_ROLES = [r.value for r in Role]
PERIODE = "date_debut={0}&date_fin={0}"

# endpoint -> rôles autorisés (tout autre rôle doit recevoir 403)
RESTREINTS = {
    "/api/dashboard/direction/": {"pdg", "secretaire_general", "qhse"},
    "/api/dashboard/qhse/": {"qhse"},
    "/api/dashboard/exploitation/": {"directeur_exploitation", "pdg", "secretaire_general"},
    "/api/dashboard/plateforme/": {"superadmin"},
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
    "/api/sorties-pieces/",
    "/api/dossiers-agents/",
]


def _url(gabarit, monde_a):
    aujourdhui = timezone.localdate().isoformat()
    return gabarit.replace("{0}", aujourdhui).replace("{depart}", str(monde_a["depart"].id))


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
        """Exception à la transparence : données RH. Seul le DRH voit les dossiers des autres."""
        api_client.force_authenticate(user=tous_les_roles["drh"])
        assert [d["id"] for d in api_client.get("/api/dossiers-agents/").data] == [monde_a["dossier"].id]

        for role in TOUS_LES_ROLES:
            if role in ("drh", "superadmin"):
                continue
            api_client.force_authenticate(user=tous_les_roles[role])
            assert api_client.get("/api/dossiers-agents/").data == [], role


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
