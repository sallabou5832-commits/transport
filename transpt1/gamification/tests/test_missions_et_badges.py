"""Missions du jour (objectifs de travail) et badges (jalons), enregistrés une seule fois."""

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from configuration.models import ConfigurationPoste
from core.models import Role
from gamification.models import BadgeObtenu, MissionAccomplie
from gamification.tests.conftest import etat, trajet, vendre
from maintenance.models import OrdreReparation, StatutOrdreReparation


def mission(donnees, code):
    return next(m for m in donnees["missions"] if m["code"] == code)


@pytest.mark.django_db
class TestMissionsDuJour:
    def test_la_progression_suit_le_travail_de_la_journee(self, api_client, agents, monde):
        for _ in range(8):
            vendre(monde, agents["guichetier"])

        donnees = etat(api_client, agents["guichetier"])

        assert mission(donnees, "vendre_20")["progres"] == 8 and mission(donnees, "vendre_20")["objectif"] == 20
        assert mission(donnees, "vendre_20")["accomplie"] is False

    def test_une_mission_accomplie_est_enregistree_une_fois_et_rapporte_des_points(self, api_client, agents, monde):
        for _ in range(5):
            vendre(monde, agents["guichetier"])

        premiere = etat(api_client, agents["guichetier"])
        seconde = etat(api_client, agents["guichetier"])

        assert [m["code"] for m in premiere["nouvelles"]["missions"]] == ["zero_erreur"]
        assert seconde["nouvelles"]["missions"] == []  # la pop-up « mission accomplie » ne se répète pas
        assert MissionAccomplie.objects.filter(agent=agents["guichetier"]).count() == 1
        # 5 tickets + le bonus de la mission + le badge « première vente »
        assert seconde["points"] == 5 + 10 + 25
        assert mission(seconde, "zero_erreur")["accomplie"] is True

    def test_zero_erreur_est_perdu_des_qu_un_ticket_est_annule(self, api_client, agents, monde):
        for _ in range(6):
            vendre(monde, agents["guichetier"])
        vendre(monde, agents["guichetier"], statut="annule")

        donnees = etat(api_client, agents["guichetier"])

        assert mission(donnees, "zero_erreur")["progres"] == 0 and mission(donnees, "zero_erreur")["accomplie"] is False

    def test_le_chauffeur_sans_retard_accomplit_sa_mission(self, api_client, agents, monde):
        trajet(monde, agents["chauffeur_principal"], retard_minutes=3, checklist=True)

        donnees = etat(api_client, agents["chauffeur_principal"])

        assert mission(donnees, "zero_retard")["accomplie"] is True and mission(donnees, "checklist")["accomplie"] is True

    def test_un_retard_du_jour_fait_echouer_zero_retard(self, api_client, agents, monde):
        trajet(monde, agents["chauffeur_principal"], retard_minutes=3)
        trajet(monde, agents["chauffeur_principal"], retard_minutes=40)

        assert mission(etat(api_client, agents["chauffeur_principal"]), "zero_retard")["accomplie"] is False

    def test_le_mecanicien_doit_cloturer_trois_interventions(self, api_client, agents, monde, company_a):
        for numero in range(3):
            OrdreReparation.objects.create(
                vehicule=monde["vehicule"], company=company_a, description=f"Révision {numero}", mecanicien=agents["mecanicien"],
                statut=StatutOrdreReparation.TERMINE, date_cloture=timezone.now(),
            )

        assert mission(etat(api_client, agents["mecanicien"]), "cloturer_3")["accomplie"] is True

    def test_les_missions_d_hier_ne_comptent_pas_aujourd_hui(self, api_client, agents, monde):
        vieux = vendre(monde, agents["guichetier"])
        Ticket.objects.filter(pk=vieux.pk).update(date_vente=timezone.now() - datetime.timedelta(days=1, hours=1))

        assert mission(etat(api_client, agents["guichetier"]), "vendre_20")["progres"] == 0

    def test_zero_rupture_de_stock_pour_le_magasinier(self, api_client, agents, company_a):
        from maintenance.models import Piece

        assert mission(etat(api_client, agents["magasinier"]), "zero_rupture")["accomplie"] is True
        Piece.objects.create(nom="Filtre", reference="F1", quantite_stock=0, seuil_alerte=2, company=company_a)
        MissionAccomplie.objects.all().delete()

        assert mission(etat(api_client, agents["magasinier"]), "zero_rupture")["accomplie"] is False

    def test_zero_incident_non_traite_a_temps_pour_le_qhse(self, api_client, agents, monde, company_a):
        from personnel_roulant.models import Incident

        assert mission(etat(api_client, agents["qhse"]), "zero_incident_en_retard")["accomplie"] is True
        MissionAccomplie.objects.all().delete()
        incident = Incident.objects.create(
            vehicule=monde["vehicule"], chauffeur=agents["chauffeur_principal"], company=company_a,
            type_incident="retard", description="Retard", gravite="faible",
        )
        Incident.objects.filter(pk=incident.pk).update(date=timezone.now() - datetime.timedelta(hours=30))

        assert mission(etat(api_client, agents["qhse"]), "zero_incident_en_retard")["accomplie"] is False

    def test_les_postes_sans_mission_n_en_affichent_pas(self, api_client, agents):
        assert etat(api_client, agents["pdg"])["missions"] == []


@pytest.mark.django_db
class TestBadges:
    def badges(self, api_client, agent):
        return {b["code"]: b for b in etat(api_client, agent)["badges"]}

    def test_les_badges_du_poste_sont_proposes_avec_leur_description(self, api_client, agents):
        badges = self.badges(api_client, agents["guichetier"])

        assert set(badges) == {"premiere_vente", "centurion", "caisse_juste"}
        assert badges["premiere_vente"]["obtenu"] is False and "premier ticket" in badges["premiere_vente"]["description"].lower()

    def test_premiere_vente(self, api_client, agents, monde):
        vendre(monde, agents["guichetier"])

        premiere = etat(api_client, agents["guichetier"])

        assert [b["code"] for b in premiere["nouvelles"]["badges"]] == ["premiere_vente"]
        badges = {b["code"]: b for b in premiere["badges"]}
        assert badges["premiere_vente"]["obtenu"] is True and badges["centurion"]["obtenu"] is False

    def test_un_badge_n_est_gagne_qu_une_fois(self, api_client, agents, monde):
        vendre(monde, agents["guichetier"])
        etat(api_client, agents["guichetier"])

        seconde = etat(api_client, agents["guichetier"])

        assert seconde["nouvelles"]["badges"] == []
        assert BadgeObtenu.objects.filter(agent=agents["guichetier"], code="premiere_vente").count() == 1

    def test_un_badge_rapporte_des_points(self, api_client, agents, monde):
        vendre(monde, agents["guichetier"])

        assert etat(api_client, agents["guichetier"])["points"] == 1 + 25

    def test_centurion_apres_cent_tickets(self, api_client, agents, monde):
        Ticket.objects.bulk_create(
            [
                Ticket(depart=monde["depart"], company=agents["guichetier"].company, passager_nom="P", passager_telephone="+225",
                       prix=Decimal("1000"), mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"])
                for _ in range(100)
            ]
        )

        assert self.badges(api_client, agents["guichetier"])["centurion"]["obtenu"] is True

    def test_caisse_juste_trente_tickets_en_sept_jours_sans_annulation(self, api_client, agents, monde):
        Ticket.objects.bulk_create(
            [
                Ticket(depart=monde["depart"], company=agents["guichetier"].company, passager_nom="P", passager_telephone="+225",
                       prix=Decimal("1000"), mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"])
                for _ in range(30)
            ]
        )
        assert self.badges(api_client, agents["guichetier"])["caisse_juste"]["obtenu"] is True

    def test_routier_regulier_dix_trajets_sans_incident(self, api_client, agents, monde):
        for numero in range(10):
            trajet(monde, agents["chauffeur_principal"], il_y_a=datetime.timedelta(days=numero + 1))

        badges = self.badges(api_client, agents["chauffeur_principal"])

        assert badges["routier_regulier"]["obtenu"] is True and badges["routier_exemplaire"]["obtenu"] is False

    def test_six_mois_sans_retard(self, api_client, agents, monde):
        for numero in range(20):
            trajet(monde, agents["chauffeur_principal"], il_y_a=datetime.timedelta(days=5 + numero * 8))

        assert self.badges(api_client, agents["chauffeur_principal"])["six_mois_sans_retard"]["obtenu"] is True

    def test_un_seul_retard_dans_les_six_mois_prive_du_badge(self, api_client, agents, monde):
        for numero in range(20):
            trajet(monde, agents["chauffeur_principal"], il_y_a=datetime.timedelta(days=5 + numero * 8))
        trajet(monde, agents["chauffeur_principal"], retard_minutes=60, il_y_a=datetime.timedelta(days=20))

        assert self.badges(api_client, agents["chauffeur_principal"])["six_mois_sans_retard"]["obtenu"] is False

    def test_atelier_au_top_dix_interventions(self, api_client, agents, monde, company_a):
        for numero in range(10):
            OrdreReparation.objects.create(
                vehicule=monde["vehicule"], company=company_a, description=f"Révision {numero}", mecanicien=agents["mecanicien"],
                statut=StatutOrdreReparation.TERMINE, date_cloture=timezone.now(),
            )

        assert self.badges(api_client, agents["mecanicien"])["atelier_au_top"]["obtenu"] is True

    def test_les_postes_sans_badge_n_en_ont_pas(self, api_client, agents):
        assert etat(api_client, agents["pdg"])["badges"] == []

    def test_le_badge_ne_va_qu_a_celui_qui_le_merite(self, api_client, agents, monde):
        vendre(monde, agents["guichetier"])

        assert self.badges(api_client, agents["guichetier2"])["premiere_vente"]["obtenu"] is False


@pytest.mark.django_db
class TestGareDuMois:
    """« Meilleure gare du mois » : le badge du chef de la gare classée première le mois écoulé, regagnable chaque mois."""

    def mois_precedent(self, jour=10):
        maintenant = timezone.localtime(timezone.now())
        premier = maintenant.replace(day=1, hour=9, minute=0, second=0, microsecond=0)
        return (premier - datetime.timedelta(days=1)).replace(day=jour)

    def depart_le(self, monde, chauffeur, date, retard=0):
        depart = Depart.objects.create(
            ligne=monde["ligne"], vehicule=monde["vehicule"], chauffeur=chauffeur, company=chauffeur.company,
            date_heure=date, statut=DepartStatut.TERMINE, places_vendues=18,
        )
        from personnel_roulant.models import FeuilleDeRoute

        FeuilleDeRoute.objects.create(
            depart=depart, chauffeur=chauffeur, company=chauffeur.company, heure_depart_prevue=date,
            heure_depart_reelle=date + datetime.timedelta(minutes=retard), heure_arrivee_reelle=date + datetime.timedelta(hours=2),
        )

    def test_le_chef_de_la_premiere_gare_du_mois_ecoule_gagne_le_badge(self, api_client, agents, monde):
        date = self.mois_precedent()
        self.depart_le(monde, agents["chauffeur_principal"], date)
        self.depart_le(monde, agents["chauffeur2"], date + datetime.timedelta(hours=1))

        donnees = etat(api_client, agents["chef_gare"])

        assert [b["code"] for b in donnees["nouvelles"]["badges"]] == ["gare_du_mois"]
        badge = next(b for b in donnees["badges"] if b["code"] == "gare_du_mois")
        assert badge["derniere_periode"] == f"{date:%Y-%m}"

    def test_une_gare_sans_activite_ne_gagne_rien(self, api_client, agents, monde):
        assert etat(api_client, agents["chef_gare"])["nouvelles"]["badges"] == []

    def test_le_badge_ne_va_pas_au_chef_d_une_autre_gare(self, api_client, agents, monde, user_factory, company_a):
        from reseau.models import Gare

        autre_chef = user_factory("chef_gare_bis_jeu", Role.CHEF_GARE, company=company_a)
        Gare.objects.create(nom="Korhogo", ville="Korhogo", company=company_a, chef=autre_chef)
        self.depart_le(monde, agents["chauffeur_principal"], self.mois_precedent())

        assert etat(api_client, autre_chef)["nouvelles"]["badges"] == []

    def test_le_badge_se_regagne_pour_un_autre_mois(self, api_client, agents, monde):
        self.depart_le(monde, agents["chauffeur_principal"], self.mois_precedent())
        etat(api_client, agents["chef_gare"])
        BadgeObtenu.objects.create(agent=agents["chef_gare"], company=agents["chef_gare"].company, code="gare_du_mois", periode="2020-01")

        badges = [b for b in BadgeObtenu.objects.filter(agent=agents["chef_gare"], code="gare_du_mois")]

        assert len(badges) == 2


@pytest.mark.django_db
class TestPasDeBadgeEnModeSobre:
    def test_en_mode_sobre_on_ne_gagne_ni_ne_voit_de_badge(self, api_client, agents, monde, company_a):
        ConfigurationPoste.objects.create(company=company_a, role=Role.GUICHETIER, niveau_gamification="sobre")
        vendre(monde, agents["guichetier"])

        donnees = etat(api_client, agents["guichetier"])

        assert donnees["badges"] == [] and donnees["classements"] == []
        assert not BadgeObtenu.objects.exists()
        assert donnees["points"] == 1  # les points et les missions restent
