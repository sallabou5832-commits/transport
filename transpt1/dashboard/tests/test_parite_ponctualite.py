"""La règle de ponctualité existe en deux exemplaires : ici (serveur) et dans frontend/src/lib/ponctualite.js. Les
mêmes cas (frontend/src/lib/ponctualite.cas.json) sont rejoués des deux côtés : un écart entre eux fait échouer l'un."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.utils.dateparse import parse_datetime

from dashboard.ponctualite import retard_minutes, statut_ponctualite

CAS = json.loads(
    (Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "ponctualite.cas.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("cas", CAS, ids=[c["cas"] for c in CAS])
def test_le_serveur_donne_le_meme_verdict_que_le_web(cas):
    feuille = SimpleNamespace(
        heure_depart_prevue=parse_datetime(cas["prevue"]),
        heure_depart_reelle=parse_datetime(cas["reelle"]) if cas["reelle"] else None,
    )
    maintenant = parse_datetime(cas["maintenant"])

    assert statut_ponctualite(feuille, maintenant) == cas["statut"]
    assert retard_minutes(feuille, maintenant) == cas["retard_minutes"]
