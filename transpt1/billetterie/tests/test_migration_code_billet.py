"""La migration 0007 donne un code unique à chaque billet DÉJÀ vendu (un défaut appelé une fois les aurait tous confondus)."""

import datetime

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

AVANT = [("billetterie", "0006_cloture_caisse")]
APRES = [("billetterie", "0007_code_et_utilisation")]


def migrer(cibles):
    # Le test crée des lignes dans core et reseau : on garde leur état le plus récent, sinon leurs colonnes plus récentes
    # (NOT NULL, sans défaut en base) existeraient sans que le modèle historique les renseigne.
    executeur = MigrationExecutor(connection)
    executeur.loader.build_graph()
    cibles = cibles + [noeud for noeud in executeur.loader.graph.leaf_nodes() if noeud[0] in ("core", "reseau")]
    executeur.migrate(cibles)
    return executeur.loader.project_state(cibles).apps


@pytest.mark.django_db(transaction=True)
def test_chaque_billet_existant_recoit_son_propre_code():
    try:
        apps = migrer(AVANT)
        Company, User = apps.get_model("core", "Company"), apps.get_model("core", "User")
        Gare, Ligne, Vehicule = (apps.get_model("reseau", n) for n in ("Gare", "Ligne", "Vehicule"))
        Depart, Ticket = apps.get_model("billetterie", "Depart"), apps.get_model("billetterie", "Ticket")

        compagnie = Company.objects.create(name="STC", headquarters_city="Abidjan", created_at=datetime.date(2005, 1, 1))
        vendeur = User.objects.create(username="vendeur", role="guichetier", company=compagnie)
        depart_gare = Gare.objects.create(nom="A", ville="V", company=compagnie)
        arrivee_gare = Gare.objects.create(nom="B", ville="W", company=compagnie)
        ligne = Ligne.objects.create(nom="A-B", gare_depart=depart_gare, gare_arrivee=arrivee_gare, company=compagnie)
        vehicule = Vehicule.objects.create(immatriculation="CI-1-AA", capacite=30, company=compagnie)
        depart = Depart.objects.create(
            ligne=ligne, vehicule=vehicule, chauffeur=vendeur, company=compagnie,
            date_heure=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
        )
        for numero in range(50):
            Ticket.objects.create(
                depart=depart, company=compagnie, passager_nom=f"P{numero}", passager_telephone="+225", prix=1000,
                mode_paiement="especes", vendu_par=vendeur,
            )

        apres = migrer(APRES)
        codes = list(apres.get_model("billetterie", "Ticket").objects.values_list("code", flat=True))

        assert len(codes) == 50 and len(set(codes)) == 50
        assert all(code and len(code) == 10 and set(code) <= set("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for code in codes)
    finally:
        # On laisse la base de test dans son état définitif pour les tests suivants.
        executeur = MigrationExecutor(connection)
        executeur.loader.build_graph()
        executeur.migrate(executeur.loader.graph.leaf_nodes())
