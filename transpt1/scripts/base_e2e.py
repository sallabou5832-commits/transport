"""Crée (ou détruit) la base jetable des essais de bout en bout dans le navigateur (frontend/e2e).

    python scripts/base_e2e.py creer     # supprime puis recrée une base vide
    python scripts/base_e2e.py detruire  # supprime la base

Le nom est E2E_DB_NAME (« transport_coord_e2e » par défaut) : jamais la base de développement. On se connecte avec le
compte de l'application, qui doit pouvoir créer des bases (c'est déjà ce que fait pytest-django pour ses tests).
"""

import sys

import psycopg2
from decouple import config
from psycopg2 import sql

NOM = config("E2E_DB_NAME", default="transport_coord_e2e")

if NOM == config("DB_NAME"):
    sys.exit("E2E_DB_NAME doit différer de DB_NAME : la base de développement ne se réinitialise jamais ici.")


def main(action):
    connexion = psycopg2.connect(
        dbname=config("DB_NAME"),
        user=config("DB_USER"),
        password=config("DB_PASSWORD"),
        host=config("DB_HOST", default="localhost"),
        port=config("DB_PORT", default="5432"),
    )
    connexion.autocommit = True
    with connexion.cursor() as curseur:
        curseur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (NOM,),
        )
        curseur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(NOM)))
        if action == "creer":
            curseur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(NOM)))
    connexion.close()
    print(f"Base {NOM} : {'créée' if action == 'creer' else 'supprimée'}.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("creer", "detruire"):
        sys.exit(__doc__)
    main(sys.argv[1])
