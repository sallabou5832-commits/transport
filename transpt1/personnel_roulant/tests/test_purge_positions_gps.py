"""Purge des relevés GPS anciens (`manage.py purger_positions_gps`) : la table des positions ne doit pas grossir sans
fin, mais rien de récent ni d'une autre compagnie ne doit disparaître."""

import datetime

import pytest
from django.core.management import call_command
from django.utils import timezone

from personnel_roulant import suivi
from personnel_roulant.models import PositionVehicule
from personnel_roulant.tests.conftest_suivi import equipe, trajet  # noqa: F401

POSITION = {"latitude": "5.812345", "longitude": "-4.512345", "vitesse_kmh": 88}


def _position(trajet, releve_par, il_y_a):  # noqa: F811
    return PositionVehicule.objects.create(
        company=trajet["vehicule"].company,
        vehicule=trajet["vehicule"],
        feuille_de_route=trajet["feuille"],
        releve_par=releve_par,
        releve_le=timezone.now() - il_y_a,
        **POSITION,
    )


@pytest.mark.django_db
class TestPurgePositions:
    def test_supprime_seulement_ce_qui_depasse_la_retention(self, equipe, trajet):  # noqa: F811
        ancienne = _position(trajet, equipe["conducteur"], datetime.timedelta(days=31))
        recente = _position(trajet, equipe["conducteur"], datetime.timedelta(days=1))

        total = suivi.purger_positions(retention_jours=30)

        assert total == 1
        assert not PositionVehicule.objects.filter(pk=ancienne.pk).exists()
        assert PositionVehicule.objects.filter(pk=recente.pk).exists()

    def test_relancer_sans_rien_a_supprimer_ne_fait_rien(self, equipe, trajet):  # noqa: F811
        _position(trajet, equipe["conducteur"], datetime.timedelta(days=1))

        assert suivi.purger_positions(retention_jours=30) == 0
        assert PositionVehicule.objects.count() == 1

    def test_respecte_le_reglage_par_lots(self, equipe, trajet):  # noqa: F811
        for _ in range(7):
            _position(trajet, equipe["conducteur"], datetime.timedelta(days=31))

        total = suivi.purger_positions(retention_jours=30, taille_lot=2)

        assert total == 7
        assert not PositionVehicule.objects.exists()

    def test_reglage_par_defaut_lu_dans_les_settings(self, settings, equipe, trajet):  # noqa: F811
        settings.POSITIONS_RETENTION_JOURS = 5
        ancienne = _position(trajet, equipe["conducteur"], datetime.timedelta(days=6))
        recente = _position(trajet, equipe["conducteur"], datetime.timedelta(days=4))

        total = suivi.purger_positions()

        assert total == 1
        assert not PositionVehicule.objects.filter(pk=ancienne.pk).exists()
        assert PositionVehicule.objects.filter(pk=recente.pk).exists()

    def test_commande_de_gestion(self, capsys, equipe, trajet):  # noqa: F811
        _position(trajet, equipe["conducteur"], datetime.timedelta(days=31))
        _position(trajet, equipe["conducteur"], datetime.timedelta(days=1))

        call_command("purger_positions_gps", "--jours", "30")

        assert PositionVehicule.objects.count() == 1
        assert "1 relevé" in capsys.readouterr().out
