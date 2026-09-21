"""Sauvegarde de la base : rotation, contrôle, surveillance, et — quand les outils PostgreSQL sont présents —
une vraie sauvegarde suivie d'une vraie restauration dans une base temporaire."""

import json
import os
import subprocess
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from core import sauvegarde


def _fichier(dossier, nom, age_jours=0, contenu=b"x"):
    chemin = Path(dossier, nom)
    chemin.write_bytes(contenu)
    date = time.time() - age_jours * 86400
    os.utime(chemin, (date, date))
    return chemin


class TestRotation:
    def test_supprime_les_anciennes_et_leur_empreinte(self, tmp_path):
        vieille = _fichier(tmp_path, "transport_coord_20200101_000000.dump", age_jours=40)
        _fichier(tmp_path, "transport_coord_20200101_000000.dump.sha256", age_jours=40)
        for i in range(3):
            _fichier(tmp_path, f"transport_coord_2026090{i}_000000.dump", age_jours=i)

        supprimees = sauvegarde.faire_tourner(tmp_path, garder_jours=14)

        assert supprimees == [vieille.name]
        assert not vieille.exists()
        assert not Path(f"{vieille}.sha256").exists()
        assert len(sauvegarde.sauvegardes(tmp_path)) == 3

    def test_ne_descend_jamais_sous_le_minimum(self, tmp_path):
        # Serveur de planification en panne pendant des semaines : tout est « vieux », on garde quand même 3 fichiers.
        for i in range(5):
            _fichier(tmp_path, f"transport_coord_2026010{i}_000000.dump", age_jours=100 + i)

        supprimees = sauvegarde.faire_tourner(tmp_path, garder_jours=14, garder_minimum=3)

        assert len(supprimees) == 2
        assert len(sauvegarde.sauvegardes(tmp_path)) == 3

    def test_garde_les_plus_recentes_et_ne_touche_pas_aux_autres_fichiers(self, tmp_path):
        recentes = [_fichier(tmp_path, f"transport_coord_2026090{i}_000000.dump", age_jours=100 - i) for i in range(3)]
        _fichier(tmp_path, "transport_coord_20200101_000000.dump", age_jours=500)
        etranger = _fichier(tmp_path, "notes.txt", age_jours=500)

        sauvegarde.faire_tourner(tmp_path, garder_jours=14, garder_minimum=3)

        assert etranger.exists()
        assert all(f.exists() for f in recentes)


class TestSurveillance:
    def test_aucune_sauvegarde(self, tmp_path):
        ok, message = sauvegarde.etat(tmp_path)
        assert not ok and "jamais" in message

    def test_derniere_sauvegarde_echouee(self, tmp_path):
        sauvegarde.ecrire_statut(tmp_path, ok=False, erreur="disque plein")
        ok, message = sauvegarde.etat(tmp_path)
        assert not ok and "disque plein" in message

    def test_sauvegarde_trop_ancienne(self, tmp_path):
        sauvegarde.ecrire_statut(tmp_path, ok=True, fichier="a.dump")
        statut = sauvegarde.lire_statut(tmp_path)
        statut["date"] = (timezone.now() - timedelta(hours=40)).isoformat()
        Path(tmp_path, sauvegarde.FICHIER_STATUT).write_text(json.dumps(statut), encoding="utf-8")

        ok, message = sauvegarde.etat(tmp_path, max_heures=26)

        assert not ok and "40 h" in message

    def test_sauvegarde_recente(self, tmp_path):
        sauvegarde.ecrire_statut(tmp_path, ok=True, fichier="a.dump")
        ok, message = sauvegarde.etat(tmp_path)
        assert ok and "a.dump" in message

    def test_la_commande_sort_en_erreur_quand_rien_n_a_ete_sauvegarde(self, tmp_path):
        with pytest.raises(CommandError, match="jamais"):
            call_command("etat_sauvegarde", dossier=str(tmp_path))


class FauxOutils:
    """Remplace `subprocess.run` : pg_dump écrit un fichier, pg_restore --list répond, le reste est enregistré."""

    def __init__(self, echec_dump=False, echec_liste=False):
        self.appels = []
        self.echec_dump = echec_dump
        self.echec_liste = echec_liste

    def __call__(self, commande, env=None, **kwargs):
        self.appels.append((commande, env))
        nom = Path(commande[0]).name
        if nom == "pg_dump":
            if self.echec_dump:
                raise subprocess.CalledProcessError(1, commande, stderr="FATAL: connexion refusée")
            Path(commande[commande.index("-f") + 1]).write_bytes(b"PGDMP-contenu")
        elif nom == "pg_restore" and self.echec_liste:
            raise subprocess.CalledProcessError(1, commande, stderr="archive corrompue")
        return SimpleNamespace(stdout="; Archive\n1; table public core_user\n", stderr="")


@pytest.fixture
def faux(monkeypatch):
    outils = FauxOutils()
    monkeypatch.setattr(sauvegarde, "trouver_outil", lambda nom: nom)
    monkeypatch.setattr(sauvegarde.subprocess, "run", outils)
    return outils


class TestSauvegarderSansPostgres:
    def test_ecrit_le_fichier_l_empreinte_et_le_statut(self, tmp_path, faux):
        statut = sauvegarde.sauvegarder(tmp_path)

        fichier = tmp_path / statut["fichier"]
        assert fichier.exists() and not list(tmp_path.glob("*.tmp"))
        assert Path(f"{fichier}.sha256").read_text(encoding="utf-8").split()[0] == sauvegarde.empreinte(fichier) == statut["sha256"]
        assert sauvegarde.etat(tmp_path)[0] is True

    def test_le_mot_de_passe_passe_par_l_environnement_jamais_par_la_ligne_de_commande(self, tmp_path, faux):
        mot_de_passe = sauvegarde.connexion()["PASSWORD"]

        sauvegarde.sauvegarder(tmp_path)

        commande, env = faux.appels[0]
        assert mot_de_passe and mot_de_passe not in " ".join(commande)
        assert env["PGPASSWORD"] == mot_de_passe

    def test_un_echec_de_pg_dump_est_signale_et_ne_laisse_aucun_fichier(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sauvegarde, "trouver_outil", lambda nom: nom)
        monkeypatch.setattr(sauvegarde.subprocess, "run", FauxOutils(echec_dump=True))

        with pytest.raises(sauvegarde.SauvegardeErreur, match="connexion refusée"):
            sauvegarde.sauvegarder(tmp_path)

        assert sauvegarde.sauvegardes(tmp_path) == [] and not list(tmp_path.glob("*.tmp"))
        ok, message = sauvegarde.etat(tmp_path)
        assert not ok and "connexion refusée" in message

    def test_une_archive_illisible_n_est_pas_gardee(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sauvegarde, "trouver_outil", lambda nom: nom)
        monkeypatch.setattr(sauvegarde.subprocess, "run", FauxOutils(echec_liste=True))

        with pytest.raises(sauvegarde.SauvegardeErreur, match="corrompue"):
            sauvegarde.sauvegarder(tmp_path)

        assert sauvegarde.sauvegardes(tmp_path) == []

    def test_la_commande_d_envoi_recoit_le_fichier(self, tmp_path, faux):
        statut = sauvegarde.sauvegarder(tmp_path, commande_apres="envoyer --vers coffre")

        derniere, _ = faux.appels[-1]
        assert derniere[:3] == ["envoyer", "--vers", "coffre"]
        assert Path(derniere[-1]).name == statut["fichier"]

    def test_un_echec_d_envoi_fait_echouer_la_commande_et_la_surveillance(self, tmp_path, monkeypatch):
        outils = FauxOutils()
        original = outils.__call__

        def envoi_en_echec(commande, env=None, **kwargs):
            if Path(commande[0]).name == "envoyer":
                raise subprocess.CalledProcessError(1, commande, stderr="coffre injoignable")
            return original(commande, env, **kwargs)

        monkeypatch.setattr(sauvegarde, "trouver_outil", lambda nom: nom)
        monkeypatch.setattr(sauvegarde.subprocess, "run", envoi_en_echec)

        with pytest.raises(sauvegarde.SauvegardeErreur, match="envoi a échoué"):
            sauvegarde.sauvegarder(tmp_path, commande_apres="envoyer")

        assert len(sauvegarde.sauvegardes(tmp_path)) == 1  # la sauvegarde locale, elle, existe
        ok, message = sauvegarde.etat(tmp_path)
        assert not ok and "coffre injoignable" in message

    def test_la_rotation_est_appliquee(self, tmp_path, faux):
        for i in range(4):
            _fichier(tmp_path, f"transport_coord_2020010{i}_000000.dump", age_jours=400 + i)

        statut = sauvegarde.sauvegarder(tmp_path, garder_jours=14, garder_minimum=3)

        assert len(statut["supprimees"]) == 2
        assert len(sauvegarde.sauvegardes(tmp_path)) == 3

    def test_outil_introuvable_dit_quoi_faire(self, monkeypatch):
        monkeypatch.delenv("PG_DUMP", raising=False)
        monkeypatch.setattr(sauvegarde.shutil, "which", lambda nom: None)
        monkeypatch.setattr(sauvegarde, "RACINES_POSTGRESQL", ())

        with pytest.raises(sauvegarde.SauvegardeErreur, match="PG_DUMP"):
            sauvegarde.trouver_outil("pg_dump")


class TestVerifierSansPostgres:
    def test_un_fichier_altere_est_refuse(self, tmp_path, faux):
        statut = sauvegarde.sauvegarder(tmp_path)
        fichier = tmp_path / statut["fichier"]
        fichier.write_bytes(b"PGDMP-contenu-modifie")

        with pytest.raises(sauvegarde.SauvegardeErreur, match="altéré"):
            sauvegarde.verifier(fichier)


def _outils_postgres():
    try:
        return sauvegarde.trouver_outil("pg_dump"), sauvegarde.trouver_outil("pg_restore")
    except sauvegarde.SauvegardeErreur:
        return None


sans_postgres = pytest.mark.skipif(_outils_postgres() is None, reason="pg_dump / pg_restore absents")


def _bases_de_test_restantes():
    with sauvegarde._base(sauvegarde.connexion(), "postgres") as curseur:
        curseur.execute("SELECT datname FROM pg_database WHERE datname LIKE 'restauration_test_%'")
        return [ligne[0] for ligne in curseur.fetchall()]


@sans_postgres
@pytest.mark.django_db
class TestAvecPostgres:
    """Vrais pg_dump et pg_restore, sur la base de test."""

    def test_sauvegarde_puis_restauration_reelle(self, tmp_path):
        avant = _bases_de_test_restantes()

        statut = sauvegarde.sauvegarder(tmp_path)
        resultat = sauvegarde.verifier(tmp_path / statut["fichier"])

        assert statut["taille_octets"] > 1000
        assert resultat["tables"] > 20 and resultat["migrations"] > 20
        assert _bases_de_test_restantes() == avant, "la base temporaire de restauration doit être supprimée"

    def test_une_archive_tronquee_est_detectee(self, tmp_path):
        statut = sauvegarde.sauvegarder(tmp_path)
        fichier = tmp_path / statut["fichier"]
        Path(f"{fichier}.sha256").unlink()  # sans empreinte : c'est pg_restore qui doit s'en apercevoir
        fichier.write_bytes(fichier.read_bytes()[:200])

        with pytest.raises(sauvegarde.SauvegardeErreur):
            sauvegarde.verifier(fichier)
        assert _bases_de_test_restantes() == []

    def test_les_commandes_de_bout_en_bout(self, tmp_path):
        call_command("sauvegarde_base", dossier=str(tmp_path), verifier=True)
        call_command("etat_sauvegarde", dossier=str(tmp_path))
        call_command("verifier_sauvegarde", dossier=str(tmp_path))

        assert len(sauvegarde.sauvegardes(tmp_path)) == 1

    def test_verifier_sans_sauvegarde_est_une_erreur_claire(self, tmp_path):
        with pytest.raises(CommandError, match="Aucune sauvegarde"):
            call_command("verifier_sauvegarde", dossier=str(tmp_path / "vide"))
