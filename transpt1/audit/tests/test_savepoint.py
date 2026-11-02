"""Le journal d'audit n'empêche jamais l'action métier, même quand son propre enregistrement échoue en SQL."""

import pytest
from django.db import connection, transaction

from audit.models import JournalAudit
from reseau.models import Gare


@pytest.mark.django_db
def test_une_erreur_sql_du_journal_ne_casse_pas_la_transaction(monkeypatch, company_a):
    def echec_sql(*args, **kwargs):
        with connection.cursor() as curseur:
            curseur.execute("SELECT 1/0")

    monkeypatch.setattr(JournalAudit.objects, "create", echec_sql)

    with transaction.atomic():
        gare = Gare.objects.create(nom="Gare témoin", ville="Abidjan", company=company_a)
        # Sans savepoint, la transaction resterait « en échec » et cette requête lèverait InFailedSqlTransaction.
        assert Gare.objects.filter(pk=gare.pk).exists()
