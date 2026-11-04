"""Numéros de téléphone saisis (voyageurs, destinataires, gares, service client) : un seul contrôle pour toute l'application."""

import re

from rest_framework import serializers

from notifications.providers import normaliser_numero

TELEPHONE_VALIDE = re.compile(r"^\+?\d{8,15}$")


def valider_telephone(valeur):
    """Le numéro sans espaces de bord ("" s'il est vide) ; erreur de validation s'il ne compte pas 8 à 15 chiffres."""
    valeur = (valeur or "").strip()
    if valeur and not TELEPHONE_VALIDE.match(normaliser_numero(valeur)):
        raise serializers.ValidationError("Numéro de téléphone invalide (8 à 15 chiffres, indicatif possible).")
    return valeur
