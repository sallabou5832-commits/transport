"""Code de vérification et validation à bord des billets.

Le code est unique : un défaut appelé une seule fois par Django donnerait le même code à tous les billets déjà vendus.
On ajoute donc la colonne sans contrainte, on remplit chaque billet existant avec son propre code, puis on pose l'unicité.
"""

import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import billetterie.models

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def donner_un_code_aux_billets_existants(apps, schema_editor):
    Ticket = apps.get_model("billetterie", "Ticket")
    deja = set()
    for ticket in Ticket.objects.filter(code__isnull=True).iterator():
        code = "".join(secrets.choice(ALPHABET) for _ in range(10))
        while code in deja:
            code = "".join(secrets.choice(ALPHABET) for _ in range(10))
        deja.add(code)
        Ticket.objects.filter(pk=ticket.pk).update(code=code)


class Migration(migrations.Migration):

    dependencies = [
        ("billetterie", "0006_cloture_caisse"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="code",
            field=models.CharField(editable=False, max_length=12, null=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="utilise_le",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="utilise_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tickets_controles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(donner_un_code_aux_billets_existants, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ticket",
            name="code",
            field=models.CharField(
                default=billetterie.models.generer_code_billet, editable=False, max_length=12, unique=True
            ),
        ),
    ]
