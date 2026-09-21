"""Sauvegarde et restauration de la base PostgreSQL, avec les garanties qu'une simple copie n'offre pas :
fichier contrôlé (lisible par `pg_restore`), empreinte SHA-256, rotation, envoi hors du serveur, et test de
restauration réel dans une base temporaire (« une sauvegarde qu'on n'a jamais restaurée n'est pas une sauvegarde »).

Aucune commande n'est lancée par un shell : les arguments sont passés en liste.
"""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from django.db import connections
from django.utils import timezone

PREFIXE = "transport_coord"
FICHIER_STATUT = "dernier_statut.json"
DELAI_OUTIL_SECONDES = 3600
RACINES_POSTGRESQL = (r"C:\Program Files\PostgreSQL", "/usr/lib/postgresql")


class SauvegardeErreur(Exception):
    """Une sauvegarde ou une vérification a échoué : le message dit pourquoi, la commande sort en erreur."""


def trouver_outil(nom):
    """`pg_dump` ou `pg_restore` : variable PG_DUMP / PG_RESTORE, sinon le PATH, sinon l'installation standard."""
    variable = nom.upper()
    force = os.environ.get(variable)
    if force and Path(force).exists():
        return force
    sur_le_path = shutil.which(nom)
    if sur_le_path:
        return sur_le_path
    for racine in map(Path, RACINES_POSTGRESQL):
        if racine.exists():
            for chemin in sorted([*racine.glob(f"*/bin/{nom}.exe"), *racine.glob(f"*/bin/{nom}")], reverse=True):
                return str(chemin)
    raise SauvegardeErreur(
        f"{nom} est introuvable : installez les outils client de PostgreSQL ou renseignez la variable {variable}."
    )


def connexion():
    """Paramètres de la base de l'application (la base de test pendant les tests)."""
    return connections["default"].settings_dict


def _arguments(cfg):
    arguments = []
    if cfg.get("HOST"):
        arguments += ["-h", str(cfg["HOST"])]
    if cfg.get("PORT"):
        arguments += ["-p", str(cfg["PORT"])]
    if cfg.get("USER"):
        arguments += ["-U", str(cfg["USER"])]
    return arguments


def _environnement(mot_de_passe):
    env = os.environ.copy()
    if mot_de_passe:
        env["PGPASSWORD"] = str(mot_de_passe)
    return env


def _executer(commande, env, **kwargs):
    try:
        return subprocess.run(commande, env=env, capture_output=True, text=True, check=True, timeout=DELAI_OUTIL_SECONDES, **kwargs)
    except subprocess.CalledProcessError as exc:
        raise SauvegardeErreur(f"{Path(commande[0]).name} a échoué : {(exc.stderr or exc.stdout or '').strip()[:500]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SauvegardeErreur(f"{Path(commande[0]).name} a dépassé {DELAI_OUTIL_SECONDES} s.") from exc


def empreinte(chemin):
    condensat = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            condensat.update(bloc)
    return condensat.hexdigest()


def controler(chemin):
    """Le fichier est une archive PostgreSQL lisible et non vide (`pg_restore --list`)."""
    listing = _executer([trouver_outil("pg_restore"), "--list", str(chemin)], os.environ.copy())
    if not listing.stdout.strip():
        raise SauvegardeErreur("Archive vide ou illisible.")
    return listing.stdout


def ecrire_statut(dossier, **champs):
    champs["date"] = timezone.now().isoformat()
    Path(dossier, FICHIER_STATUT).write_text(json.dumps(champs, ensure_ascii=False, indent=2), encoding="utf-8")


def lire_statut(dossier):
    chemin = Path(dossier, FICHIER_STATUT)
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None


def sauvegardes(dossier):
    """Les sauvegardes du dossier, de la plus récente à la plus ancienne."""
    return sorted(Path(dossier).glob(f"{PREFIXE}_*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)


def faire_tourner(dossier, garder_jours, garder_minimum=3):
    """Supprime les sauvegardes plus vieilles que `garder_jours`, sans jamais descendre sous `garder_minimum`
    (une panne du serveur de planification ne doit pas vider le dossier). Renvoie les fichiers supprimés."""
    limite = time.time() - garder_jours * 86400
    supprimees = []
    for chemin in sauvegardes(dossier)[garder_minimum:]:
        if chemin.stat().st_mtime < limite:
            chemin.unlink()
            Path(f"{chemin}.sha256").unlink(missing_ok=True)
            supprimees.append(chemin.name)
    return supprimees


def sauvegarder(dossier, *, garder_jours=14, garder_minimum=3, commande_apres=""):
    debut = time.monotonic()
    cfg = connexion()
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    final = dossier / f"{PREFIXE}_{datetime.now():%Y%m%d_%H%M%S}.dump"
    temporaire = Path(f"{final}.tmp")
    try:
        _executer(
            [trouver_outil("pg_dump"), "-Fc", *_arguments(cfg), "-f", str(temporaire), cfg["NAME"]],
            _environnement(cfg.get("PASSWORD")),
        )
        controler(temporaire)
        temporaire.replace(final)
    except SauvegardeErreur as exc:
        temporaire.unlink(missing_ok=True)
        ecrire_statut(dossier, ok=False, erreur=str(exc))
        raise

    somme = empreinte(final)
    Path(f"{final}.sha256").write_text(f"{somme}  {final.name}\n", encoding="utf-8")
    try:
        os.chmod(final, 0o600)  # sans effet sous Windows
    except OSError:
        pass
    supprimees = faire_tourner(dossier, garder_jours, garder_minimum)
    statut = {
        "ok": True,
        "fichier": final.name,
        "taille_octets": final.stat().st_size,
        "sha256": somme,
        "duree_secondes": round(time.monotonic() - debut, 1),
        "supprimees": supprimees,
    }
    ecrire_statut(dossier, **statut)
    if commande_apres:
        # Envoi hors du serveur (rclone, scp, chiffrement…) : la sauvegarde est faite quoi qu'il arrive ; si l'envoi
        # échoue, la commande sort en erreur pour que la surveillance le voie.
        try:
            _executer([*shlex.split(commande_apres, posix=os.name != "nt"), str(final)], os.environ.copy())
        except SauvegardeErreur as exc:
            ecrire_statut(dossier, **{**statut, "ok": False, "erreur": f"Envoi : {exc}"})
            raise SauvegardeErreur(f"Sauvegarde faite ({final.name}) mais l'envoi a échoué. {exc}") from exc
    return statut


@contextmanager
def _base(cfg, nom, *, utilisateur=None, mot_de_passe=None, autocommit=False):
    """Un curseur sur la base `nom`. La connexion est fermée en sortant (le `with` de psycopg2 ne la ferme pas) ;
    `autocommit` est obligatoire pour CREATE / DROP DATABASE."""
    conn = psycopg2.connect(
        dbname=nom,
        user=utilisateur or cfg.get("USER"),
        password=mot_de_passe or cfg.get("PASSWORD"),
        host=cfg.get("HOST") or None,
        port=cfg.get("PORT") or None,
    )
    conn.autocommit = autocommit
    try:
        with conn.cursor() as curseur:
            yield curseur
    finally:
        conn.close()


def _compter(cfg, nom, requete, **identifiants):
    with _base(cfg, nom, **identifiants) as curseur:
        curseur.execute(requete)
        return curseur.fetchone()[0]


# pg_tables (et non information_schema, qui masque les tables sur lesquelles le rôle n'a aucun droit) : le rôle qui
# fait la vérification n'a pas besoin de lire les données de l'application.
TABLES_PUBLIQUES = "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'"


def verifier(fichier, *, admin_utilisateur=None, admin_mot_de_passe=None):
    """Restaure la sauvegarde dans une base temporaire (supprimée ensuite) et compare : mêmes tables que la base
    vivante, migrations présentes. L'utilisateur doit pouvoir créer une base (`CREATEDB`) ; sinon renseignez
    SAUVEGARDE_ADMIN_USER / SAUVEGARDE_ADMIN_PASSWORD (un rôle réservé à cette vérification)."""
    fichier = Path(fichier)
    attendu = Path(f"{fichier}.sha256")
    if attendu.exists() and attendu.read_text(encoding="utf-8").split()[0] != empreinte(fichier):
        raise SauvegardeErreur(f"L'empreinte de {fichier.name} ne correspond plus : le fichier est altéré.")
    controler(fichier)

    cfg = dict(connexion())
    identifiants = {
        "utilisateur": admin_utilisateur or cfg.get("USER"),
        "mot_de_passe": admin_mot_de_passe or cfg.get("PASSWORD"),
    }
    temporaire = f"restauration_test_{datetime.now():%Y%m%d%H%M%S}"
    try:
        with _base(cfg, "postgres", autocommit=True, **identifiants) as curseur:
            curseur.execute(f'CREATE DATABASE "{temporaire}"')
    except psycopg2.Error as exc:
        raison = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        raise SauvegardeErreur(
            f"Impossible de créer la base temporaire : {raison}. L'utilisateur doit avoir le droit CREATEDB, "
            "ou renseignez SAUVEGARDE_ADMIN_USER et SAUVEGARDE_ADMIN_PASSWORD."
        ) from exc
    try:
        _executer(
            [
                trouver_outil("pg_restore"),
                "--no-owner",
                "--exit-on-error",
                *_arguments({**cfg, "USER": identifiants["utilisateur"]}),
                "-d",
                temporaire,
                str(fichier),
            ],
            _environnement(identifiants["mot_de_passe"]),
        )
        tables_restaurees = _compter(cfg, temporaire, TABLES_PUBLIQUES, **identifiants)
        tables_vivantes = _compter(cfg, cfg["NAME"], TABLES_PUBLIQUES, **identifiants)
        migrations = _compter(cfg, temporaire, "SELECT count(*) FROM django_migrations", **identifiants)
        if tables_restaurees != tables_vivantes:
            raise SauvegardeErreur(f"Restauration incomplète : {tables_restaurees} tables au lieu de {tables_vivantes}.")
        if migrations == 0:
            raise SauvegardeErreur("Restauration vide : aucune migration enregistrée.")
        return {"fichier": fichier.name, "tables": tables_restaurees, "migrations": migrations}
    finally:
        try:
            with _base(cfg, "postgres", autocommit=True, **identifiants) as curseur:
                curseur.execute(f'DROP DATABASE IF EXISTS "{temporaire}"')
        except psycopg2.Error:
            pass  # la base temporaire restera : son nom (restauration_test_…) permet de la supprimer à la main


def etat(dossier, max_heures=26):
    """(ok, message) : la dernière sauvegarde a réussi et n'est pas trop ancienne (surveillance)."""
    statut = lire_statut(dossier)
    if statut is None:
        return False, "Aucune sauvegarde n'a jamais été faite."
    if not statut.get("ok"):
        return False, f"La dernière sauvegarde a échoué : {statut.get('erreur', 'motif inconnu')}"
    age = timezone.now() - datetime.fromisoformat(statut["date"])
    if age > timedelta(hours=max_heures):
        return False, f"La dernière sauvegarde réussie date de {age.total_seconds() / 3600:.0f} h (limite : {max_heures} h)."
    return True, f"Dernière sauvegarde : {statut['fichier']}, il y a {age.total_seconds() / 3600:.1f} h."
