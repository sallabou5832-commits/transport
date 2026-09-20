"""HTTPS : redirection, HSTS, cookies sécurisés et audit de déploiement de Django."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[2]
URL = "/api/auth/me/"  # répond 401 sans base de données : suffit pour observer la couche HTTPS
PROXY_HTTPS = {"HTTP_X_FORWARDED_PROTO": "https"}


@pytest.fixture
def https_active(settings):
    """Les réglages que `settings.py` applique quand DJANGO_FORCE_HTTPS est vrai."""
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    settings.SECURE_HSTS_SECONDS = 2592000
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = True


class TestRedirectionEtEntetes:
    def test_le_http_en_clair_est_redirige_vers_https(self, api_client, https_active):
        reponse = api_client.get(URL)

        assert reponse.status_code == 301
        assert reponse["Location"] == f"https://testserver{URL}"

    def test_la_redirection_ne_fait_pas_fuiter_un_jeton_en_clair_vers_le_corps(
        self, api_client, https_active
    ):
        reponse = api_client.post(
            "/api/auth/login/", {"username": "u", "password": "p"}, format="json"
        )

        # 301 : le client rejoue en HTTPS ; la requête n'a pas été traitée en clair.
        assert reponse.status_code == 301
        assert reponse["Location"].startswith("https://")

    def test_derriere_le_proxy_https_la_requete_passe_et_hsts_est_envoye(
        self, api_client, https_active
    ):
        reponse = api_client.get(URL, **PROXY_HTTPS)

        assert reponse.status_code == 401  # atteint l'API, pas de redirection
        assert reponse["Strict-Transport-Security"] == "max-age=2592000; includeSubDomains"

    def test_sans_https_actif_le_developpement_local_en_http_fonctionne(self, api_client):
        reponse = api_client.get(URL)

        assert reponse.status_code == 401
        assert "Strict-Transport-Security" not in reponse

    def test_un_proxy_http_n_est_pas_pris_pour_du_https(self, api_client, https_active):
        reponse = api_client.get(URL, HTTP_X_FORWARDED_PROTO="http")

        assert reponse.status_code == 301


def lancer_django(env_extra, *args):
    """Exécute manage.py dans un processus neuf, avec un environnement contrôlé."""
    env = {**os.environ, **env_extra}
    for cle in ("DJANGO_FORCE_HTTPS", "DJANGO_HSTS_SECONDS"):
        env.pop(cle, None) if cle not in env_extra else None
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


PRODUCTION = {
    "DJANGO_DEBUG": "False",
    "DJANGO_ALLOWED_HOSTS": "api.exemple.ci",
    # Valeur factice mais conforme à l'audit (longue, aléatoire, sans « django-insecure- »).
    "DJANGO_SECRET_KEY": "k9$Xq2#vL8@pR5!zT1&mN4^wB7*cF3(hJ6)dG0_sA2-eY9+uI5=oK8~bV3",
}


class TestReglagesSelonLEnvironnement:
    def test_la_production_passe_l_audit_de_deploiement_de_django(self):
        # Contrôles de sécurité uniquement : d'autres audits (ex. e-mail) sont hors sujet ici.
        resultat = lancer_django(
            PRODUCTION, "check", "--deploy", "--tag", "security", "--fail-level", "WARNING"
        )

        assert resultat.returncode == 0, resultat.stdout + resultat.stderr
        assert "no issues" in (resultat.stdout + resultat.stderr).lower()

    def test_la_production_active_les_reglages_https(self):
        resultat = lancer_django(
            PRODUCTION,
            "shell",
            "-c",
            "from django.conf import settings as s; "
            "print(s.SECURE_SSL_REDIRECT, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, "
            "s.SECURE_HSTS_SECONDS, s.SECURE_PROXY_SSL_HEADER)",
        )

        assert resultat.returncode == 0, resultat.stderr
        assert resultat.stdout.strip().splitlines()[-1] == (
            "True True True 2592000 ('HTTP_X_FORWARDED_PROTO', 'https')"
        )

    def test_le_developpement_reste_en_http(self):
        resultat = lancer_django(
            {"DJANGO_DEBUG": "True"},
            "shell",
            "-c",
            "from django.conf import settings as s; "
            "print(s.SECURE_SSL_REDIRECT, s.SESSION_COOKIE_SECURE, s.SECURE_HSTS_SECONDS)",
        )

        assert resultat.returncode == 0, resultat.stderr
        assert resultat.stdout.strip().splitlines()[-1] == "False False 0"

    def test_le_https_peut_etre_coupe_explicitement(self):
        resultat = lancer_django(
            {**PRODUCTION, "DJANGO_FORCE_HTTPS": "False"},
            "shell",
            "-c",
            "from django.conf import settings as s; print(s.SECURE_SSL_REDIRECT)",
        )

        assert resultat.stdout.strip().splitlines()[-1] == "False"
