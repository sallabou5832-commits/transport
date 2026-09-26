"""Alertes automatiques : échéances d'assurance, départs à risque de retard, seuils critiques du PDG."""

import datetime
import io
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from alertes.generation import generer
from alertes.models import Alerte, TypeAlerte
from alertes.tests.conftest import alertes_de
from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from personnel_roulant.models import ChecklistDepart, Incident
from reseau.models import VehiculeStatut
from supports.models import Assurance


def titres(type_alerte):
    return sorted(Alerte.objects.filter(type=type_alerte).values_list("titre", flat=True))


@pytest.mark.django_db
class TestAssurances:
    def assurer(self, company, vehicule, jours):
        return Assurance.objects.create(
            vehicule=vehicule, company=company, compagnie_assurance="NSIA", numero_police="POL-1",
            date_echeance=timezone.localdate() + datetime.timedelta(days=jours),
        )

    def test_une_assurance_proche_previent_le_juridique_et_le_technique(self, api_client, agents, company_a, reseau_a):
        self.assurer(company_a, reseau_a["vehicule"], 20)

        generer(company_a)

        # Le jeu d'essai n'a pas d'agent juridique : on vérifie le technique, et que le juridique est bien visé.
        assert len(alertes_de(api_client, agents["directeur_technique"])) == 1
        assert Alerte.objects.get().roles_destinataires == ["directeur_technique", "responsable_juridique"]
        assert titres(TypeAlerte.ECHEANCE) == ["Assurance à renouveler : CI-4000-AA"]

    def test_une_assurance_lointaine_ne_declenche_rien(self, company_a, reseau_a):
        self.assurer(company_a, reseau_a["vehicule"], 90)

        assert generer(company_a) == []

    def test_relancer_ne_cree_pas_de_doublon(self, company_a, reseau_a):
        self.assurer(company_a, reseau_a["vehicule"], 20)

        assert len(generer(company_a)) == 1
        assert generer(company_a) == []

    def test_les_rappels_montent_en_gravite_a_7_jours_puis_a_l_expiration(self, company_a, reseau_a):
        assurance = self.assurer(company_a, reseau_a["vehicule"], 20)
        generer(company_a)
        assurance.date_echeance = timezone.localdate() + datetime.timedelta(days=5)
        assurance.save()
        generer(company_a)
        assurance.date_echeance = timezone.localdate() - datetime.timedelta(days=3)
        assurance.save()
        generer(company_a)

        alertes = list(Alerte.objects.order_by("id"))
        assert [a.gravite for a in alertes] == ["attention", "critique", "critique"]
        assert "expirée" in alertes[2].titre and "3 jour" in alertes[2].message


@pytest.mark.django_db
class TestDepartsARisque:
    def depart_dans(self, reseau_a, minutes):
        depart = reseau_a["depart"]
        depart.date_heure = timezone.now() + datetime.timedelta(minutes=minutes)
        depart.save()
        feuille = reseau_a["feuille"]
        feuille.heure_depart_prevue = depart.date_heure
        feuille.save()
        return depart

    def test_un_vehicule_immobilise_a_l_approche_du_depart_previent_la_regulation_et_la_gare(
        self, api_client, agents, company_a, reseau_a
    ):
        self.depart_dans(reseau_a, 40)
        reseau_a["vehicule"].statut = VehiculeStatut.EN_MAINTENANCE
        reseau_a["vehicule"].save()

        generer(company_a)

        for role in ("chef_ligne", "chef_gare"):
            visibles = alertes_de(api_client, agents[role])
            assert len(visibles) == 1, role
            assert visibles[0]["titre"].startswith("Risque de retard : Adjamé-Bouaké")
            assert "immobilisé" in visibles[0]["message"]

    def test_un_defaut_de_checklist_est_un_risque(self, company_a, reseau_a):
        self.depart_dans(reseau_a, 50)
        ChecklistDepart.objects.create(
            feuille_de_route=reseau_a["feuille"], company=company_a, item="carburant", etat="defaut"
        )

        generer(company_a)

        assert "défaut" in Alerte.objects.get().message.lower()

    def test_pas_de_checklist_a_45_minutes_n_est_pas_encore_un_risque(self, company_a, reseau_a):
        self.depart_dans(reseau_a, 45)

        assert generer(company_a) == []

    def test_pas_de_checklist_a_moins_de_30_minutes_est_un_risque(self, company_a, reseau_a):
        self.depart_dans(reseau_a, 20)

        creees = generer(company_a)

        assert len(creees) == 1
        assert "checklist" in creees[0].message.lower()

    def test_un_depart_qui_n_a_pas_eu_lieu_apres_la_tolerance_est_en_retard_et_critique(self, company_a, reseau_a):
        self.depart_dans(reseau_a, -25)

        generer(company_a)

        alerte = Alerte.objects.get()
        assert alerte.titre.startswith("Départ en retard") and alerte.gravite == "critique"

    def test_dans_la_tolerance_de_10_minutes_ce_n_est_pas_un_retard(self, company_a, reseau_a):
        self.depart_dans(reseau_a, -5)
        ChecklistDepart.objects.create(feuille_de_route=reseau_a["feuille"], company=company_a, item="pneus", etat="ok")

        assert generer(company_a) == []

    def test_un_depart_lointain_ou_deja_parti_ne_declenche_rien(self, company_a, reseau_a):
        self.depart_dans(reseau_a, 180)
        assert generer(company_a) == []

        depart = self.depart_dans(reseau_a, -20)
        reseau_a["feuille"].heure_depart_reelle = timezone.now()
        reseau_a["feuille"].save()
        depart.statut = DepartStatut.EN_COURS
        depart.save()
        assert generer(company_a) == []

    def test_un_depart_sans_feuille_de_route_est_ignore(self, company_a, reseau_a):
        self.depart_dans(reseau_a, -25)
        reseau_a["feuille"].delete()

        assert generer(company_a) == []

    def test_les_departs_d_une_autre_compagnie_ne_sont_pas_touches(self, company_b, reseau_a):
        self.depart_dans(reseau_a, -25)

        assert generer(company_b) == []


@pytest.mark.django_db
class TestSeuilsCritiques:
    def test_retards_recurrents(self, api_client, agents, company_a, reseau_a):
        hier = timezone.now() - datetime.timedelta(days=1)
        for numero in range(6):
            depart = Depart.objects.create(
                ligne=reseau_a["ligne"], vehicule=reseau_a["vehicule"], chauffeur=agents["chauffeur_principal"],
                company=company_a, date_heure=hier - datetime.timedelta(hours=numero), statut=DepartStatut.TERMINE,
            )
            from personnel_roulant.models import FeuilleDeRoute

            FeuilleDeRoute.objects.create(
                depart=depart, chauffeur=agents["chauffeur_principal"], company=company_a,
                heure_depart_prevue=depart.date_heure,
                heure_depart_reelle=depart.date_heure + datetime.timedelta(minutes=45),  # 6 départs sur 6 en retard
            )

        generer(company_a)

        visibles = alertes_de(api_client, agents["pdg"])
        assert [a["titre"] for a in visibles if a["type"] == TypeAlerte.SEUIL_CRITIQUE] == [
            "Retards récurrents : ponctualité de 0 % sur 7 jours"
        ]
        assert len(alertes_de(api_client, agents["directeur_exploitation"])) == 1

    def test_pas_assez_de_departs_pour_conclure_a_des_retards_recurrents(self, company_a, reseau_a, agents):
        from personnel_roulant.models import FeuilleDeRoute

        hier = timezone.now() - datetime.timedelta(days=1)
        for numero in range(4):  # 4 départs sur 4 en retard, mais sous le minimum de 5 départs mesurés
            depart = Depart.objects.create(
                ligne=reseau_a["ligne"], vehicule=reseau_a["vehicule"], chauffeur=agents["chauffeur_principal"],
                company=company_a, date_heure=hier - datetime.timedelta(hours=numero), statut=DepartStatut.TERMINE,
            )
            FeuilleDeRoute.objects.create(
                depart=depart, chauffeur=agents["chauffeur_principal"], company=company_a,
                heure_depart_prevue=depart.date_heure,
                heure_depart_reelle=depart.date_heure + datetime.timedelta(minutes=45),
            )

        assert titres(TypeAlerte.SEUIL_CRITIQUE) == []
        generer(company_a)
        assert titres(TypeAlerte.SEUIL_CRITIQUE) == []

    def test_pannes_en_hausse(self, api_client, agents, company_a, reseau_a):
        for _ in range(4):
            Incident.objects.create(
                vehicule=reseau_a["vehicule"], chauffeur=agents["chauffeur_principal"], company=company_a,
                type_incident="panne", description="Panne", gravite="faible",
            )

        generer(company_a)

        assert titres(TypeAlerte.SEUIL_CRITIQUE) == ["Pannes en hausse : 4 en 7 jours"]
        assert len(alertes_de(api_client, agents["pdg"])) == 1

    def test_quelques_pannes_stables_ne_declenchent_rien(self, company_a, reseau_a, agents):
        maintenant = timezone.now()
        for jours in (1, 2, 3, 9, 10, 11):
            Incident.objects.create(
                vehicule=reseau_a["vehicule"], chauffeur=agents["chauffeur_principal"], company=company_a,
                type_incident="panne", description="Panne", gravite="faible", date=maintenant - datetime.timedelta(days=jours),
            )

        assert generer(company_a) == []

    def test_recette_en_baisse(self, api_client, agents, company_a, reseau_a):
        maintenant = timezone.now()

        def vendre(jours_avant, prix):
            ticket = Ticket.objects.create(
                depart=reseau_a["depart"], company=company_a, passager_nom="P", passager_telephone="+225",
                prix=Decimal(prix), mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"],
            )
            Ticket.objects.filter(pk=ticket.pk).update(date_vente=maintenant - datetime.timedelta(days=jours_avant))

        vendre(10, "100000")  # semaine précédente : 100 000 FCFA
        vendre(3, "50000")  # semaine écoulée : 50 000 FCFA (-50 %)

        generer(company_a)

        assert titres(TypeAlerte.SEUIL_CRITIQUE) == ["Recette en baisse de 50 % sur 7 jours"]
        assert len(alertes_de(api_client, agents["pdg"])) == 1

    def test_une_recette_stable_ou_sans_historique_ne_declenche_rien(self, company_a, reseau_a, agents):
        Ticket.objects.create(
            depart=reseau_a["depart"], company=company_a, passager_nom="P", passager_telephone="+225",
            prix=Decimal("5000"), mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"],
        )

        assert generer(company_a) == []

    def test_un_ticket_annule_n_est_pas_une_recette(self, company_a, reseau_a, agents):
        maintenant = timezone.now()
        avant = Ticket.objects.create(
            depart=reseau_a["depart"], company=company_a, passager_nom="P", passager_telephone="+225",
            prix=Decimal("100000"), mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"],
        )
        Ticket.objects.filter(pk=avant.pk).update(date_vente=maintenant - datetime.timedelta(days=10))
        recent = Ticket.objects.create(
            depart=reseau_a["depart"], company=company_a, passager_nom="P", passager_telephone="+225",
            prix=Decimal("100000"), mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"],
        )
        Ticket.objects.filter(pk=recent.pk).update(
            date_vente=maintenant - datetime.timedelta(days=3), statut="annule"
        )

        generer(company_a)

        assert titres(TypeAlerte.SEUIL_CRITIQUE) == ["Recette en baisse de 100 % sur 7 jours"]


@pytest.mark.django_db
class TestCommande:
    def test_la_commande_genere_pour_chaque_compagnie_et_rejouer_ne_double_pas(self, company_a, reseau_a):
        depart = reseau_a["depart"]
        depart.date_heure = timezone.now() - datetime.timedelta(minutes=30)
        depart.save()
        sortie = io.StringIO()

        call_command("generer_alertes", stdout=sortie)
        assert "1 alerte(s) créée(s)" in sortie.getvalue()

        sortie = io.StringIO()
        call_command("generer_alertes", stdout=sortie)
        assert "0 alerte(s) créée(s)" in sortie.getvalue()
