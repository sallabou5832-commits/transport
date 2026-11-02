"""Robustesse du suivi : un réglage ou une panne de l'infrastructure ne fait jamais échouer l'envoi d'une position."""

import pytest
from django.test import override_settings

from personnel_roulant import suivi


class TestSeuilDeFatigue:
    @pytest.mark.parametrize("reglage, attendu", [(0, 1), (-5, 1), (1, 1), (270, 270)])
    def test_jamais_inferieur_a_une_minute(self, reglage, attendu):
        with override_settings(SUIVI_SEUIL_FATIGUE_MINUTES=reglage):
            assert suivi.seuil_fatigue_minutes() == attendu


class TestDiffusionDeLaPosition:
    def test_une_couche_de_canaux_en_panne_ne_leve_pas(self, monkeypatch, caplog):
        appels = []

        class CoucheEnPanne:
            async def group_send(self, groupe, message):
                appels.append(groupe)
                raise ConnectionError("Redis injoignable")

        monkeypatch.setattr("channels.layers.get_channel_layer", lambda *a, **k: CoucheEnPanne())
        monkeypatch.setattr(suivi, "_ligne_carte", lambda trajet, position, maintenant: {})

        class Trajet:
            company_id = 7

        suivi.diffuser_position(Trajet(), object())

        assert appels == ["carte_7"]
        assert "Diffusion de la position impossible" in caplog.text
