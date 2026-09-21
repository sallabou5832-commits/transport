import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.demo_garde import refuser_hors_developpement
from core.models import Company, Role
from maintenance.models import OrdreReparation, StatutOrdreReparation
from personnel_roulant.models import (
    ChecklistDepart,
    EtatChecklist,
    FeuilleDeRoute,
    GraviteIncident,
    Incident,
    StatutIncident,
    TypeIncident,
)
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut
from supports.models import Assurance, DossierAgent, Sinistre, StatutDossierAgent, StatutSinistre

# Agents laissés volontairement sans dossier RH, pour montrer « agents sans dossier » au DRH.
SANS_DOSSIER = {"bagagiste_stc", "controleur_stc"}


class Command(BaseCommand):
    help = (
        "Génère des données réalistes pour essayer les tableaux de bord de chaque rôle : départs du jour "
        "(à l'heure, en retard, non partis), six jours d'historique, incidents, assurances, sinistres, "
        "dossiers RH. À lancer après seed_demo_users et seed_demo_reseau. Sans effet si déjà lancée."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        refuser_hors_developpement("seed_demo_tableaux")
        User = get_user_model()
        try:
            stc = Company.objects.get(name="STC Voyages")
            savane = Company.objects.get(name="Express Savane")
            adjame = Gare.objects.get(nom="Gare Adjamé", company=stc)
            ligne_bouake = Ligne.objects.get(nom="Abidjan-Bouaké", company=stc)
            v1 = Vehicule.objects.get(immatriculation="CI-1001-AB")
            v2 = Vehicule.objects.get(immatriculation="CI-1002-AB")
        except (Company.DoesNotExist, Gare.DoesNotExist, Ligne.DoesNotExist, Vehicule.DoesNotExist) as exc:
            raise CommandError(
                "Données de base introuvables. Lancez d'abord : python manage.py seed_demo_users "
                "puis python manage.py seed_demo_reseau"
            ) from exc

        if Gare.objects.filter(nom="Gare Yopougon", company=stc).exists():
            self.stdout.write("Données des tableaux de bord déjà générées : rien à faire.")
            return

        agents = {u.username: u for u in User.objects.filter(company=stc)}
        try:
            guichetier = agents["guichetier_stc"]
            chauffeur1, chauffeur2, chauffeur3 = agents["chauffeur_stc"], agents["chauffeur2_stc"], agents["chauffeur3_stc"]
            relais = agents["chauffeur_relais_stc"]
        except KeyError as exc:
            raise CommandError(
                f"Utilisateur de démo {exc} introuvable. Relancez : python manage.py seed_demo_users"
            ) from exc

        maintenant = timezone.now()

        def a(decalage_jours, heure, minute=0):
            debut = timezone.localtime(maintenant).replace(hour=0, minute=0, second=0, microsecond=0)
            return debut + datetime.timedelta(days=decalage_jours, hours=heure, minutes=minute)

        # Réseau supplémentaire
        yopougon = Gare.objects.create(nom="Gare Yopougon", ville="Abidjan", company=stc)
        yakro = Gare.objects.create(nom="Gare Yamoussoukro", ville="Yamoussoukro", company=stc)
        ligne_yakro = Ligne.objects.create(
            nom="Yopougon-Yamoussoukro", gare_depart=yopougon, gare_arrivee=yakro, company=stc
        )
        ligne_adjame_yakro = Ligne.objects.create(
            nom="Abidjan-Yamoussoukro", gare_depart=adjame, gare_arrivee=yakro, company=stc
        )

        def vehicule(immat, capacite, statut):
            return Vehicule.objects.get_or_create(
                immatriculation=immat, defaults={"capacite": capacite, "statut": statut, "company": stc}
            )[0]

        v_ok = vehicule("CI-1003-AB", 60, VehiculeStatut.DISPONIBLE)
        v_bloque = vehicule("CI-1004-AB", 50, VehiculeStatut.BLOQUE_SECURITE)
        v_maintenance = vehicule("CI-1005-AB", 45, VehiculeStatut.EN_MAINTENANCE)
        v_grand = vehicule("CI-1006-AB", 70, VehiculeStatut.DISPONIBLE)

        def vendre(depart, nombre, decalage_jours=0):
            for i in range(nombre):
                ticket = Ticket.objects.create(
                    depart=depart, company=depart.company, passager_nom=f"Passager {depart.id}-{i + 1}",
                    passager_telephone=f"+22507{depart.id:03d}{i:03d}"[:30],
                    prix=5000 + 500 * (i % 3),
                    mode_paiement=ModePaiement.MOBILE_MONEY if i % 3 == 0 else ModePaiement.ESPECES,
                    vendu_par=guichetier if depart.company_id == stc.id else agents_savane["guichetier_savane"],
                )
                if decalage_jours:
                    Ticket.objects.filter(pk=ticket.pk).update(
                        date_vente=a(decalage_jours, 8 + i % 9, (i * 7) % 60)
                    )

        def depart_et_feuille(company, ligne, vehicule_, chauffeur, prevue, vendues, statut, reelle=None, arrivee=None, jour=0):
            depart = Depart.objects.create(
                ligne=ligne, vehicule=vehicule_, chauffeur=chauffeur, company=company,
                date_heure=prevue, places_vendues=vendues, statut=statut,
            )
            vendre(depart, vendues, jour)
            feuille = FeuilleDeRoute.objects.create(
                depart=depart, chauffeur=chauffeur, company=company, heure_depart_prevue=prevue,
                heure_depart_reelle=reelle, heure_arrivee_reelle=arrivee,
            )
            return depart, feuille

        agents_savane = {u.username: u for u in User.objects.filter(company=savane)}

        # Aujourd'hui : un départ à l'heure et arrivé, un parti en retard, un pas encore parti alors
        # que l'heure est passée, un à venir sur un véhicule bloqué (à réaffecter).
        depart_et_feuille(
            stc, ligne_bouake, v_grand, chauffeur2, a(0, 6), 55, DepartStatut.TERMINE,
            reelle=a(0, 6, 4), arrivee=a(0, 10, 30),
        )
        depart_et_feuille(
            stc, ligne_yakro, v_ok, chauffeur3, a(0, 8, 30), 40, DepartStatut.EN_COURS, reelle=a(0, 9, 5)
        )
        depart_et_feuille(
            stc, ligne_adjame_yakro, v2, relais, maintenant - datetime.timedelta(minutes=45), 22,
            DepartStatut.PLANIFIE,
        )
        _, feuille_bloquee = depart_et_feuille(
            stc, ligne_yakro, v_bloque, chauffeur2, maintenant + datetime.timedelta(hours=5), 12,
            DepartStatut.PLANIFIE,
        )
        depart_et_feuille(stc, ligne_bouake, v_grand, chauffeur2, a(1, 7), 8, DepartStatut.PLANIFIE)

        # Défaut de sécurité saisi sur la feuille du car bloqué (donne du travail au QHSE).
        ChecklistDepart.objects.create(
            feuille_de_route=feuille_bloquee, company=stc, item="pneus", etat=EtatChecklist.DEFAUT,
            commentaire="Usure anormale du pneu avant droit.",
        )
        ChecklistDepart.objects.create(
            feuille_de_route=feuille_bloquee, company=stc, item="freins", etat=EtatChecklist.OK
        )

        # Six jours d'historique : recettes, ponctualité sur 7 jours.
        for jour in range(1, 7):
            depart_et_feuille(
                stc, ligne_bouake if jour % 2 else ligne_yakro, v_grand if jour % 2 else v_ok,
                chauffeur2 if jour % 2 else chauffeur3, a(-jour, 7), 4 + (jour % 4) * 2, DepartStatut.TERMINE,
                reelle=a(-jour, 7, 3 if jour % 3 else 24), arrivee=a(-jour, 11), jour=-jour,
            )

        # Incidents
        grave = Incident.objects.create(
            vehicule=v_bloque, chauffeur=chauffeur3, company=stc, type_incident=TypeIncident.ACCIDENT,
            description="Collision avec un poids lourd à la sortie de Bouaké.", gravite=GraviteIncident.GRAVE,
            statut=StatutIncident.OUVERT, date=maintenant - datetime.timedelta(hours=2),
        )
        Incident.objects.create(
            vehicule=v_maintenance, chauffeur=chauffeur2, company=stc, type_incident=TypeIncident.PANNE,
            description="Panne de boîte de vitesses.", gravite=GraviteIncident.MOYENNE,
            statut=StatutIncident.OUVERT, date=maintenant - datetime.timedelta(days=1),
        )
        Incident.objects.create(
            vehicule=v_ok, chauffeur=chauffeur3, company=stc, type_incident=TypeIncident.RETARD,
            description="Embouteillage à Yopougon.", gravite=GraviteIncident.FAIBLE,
            statut=StatutIncident.OUVERT, date=maintenant - datetime.timedelta(hours=3),
        )
        ancien = Incident.objects.create(
            vehicule=v_grand, chauffeur=chauffeur2, company=stc, type_incident=TypeIncident.ACCIDENT,
            description="Rétroviseur arraché au parking.", gravite=GraviteIncident.GRAVE,
            statut=StatutIncident.TRAITE, date=maintenant - datetime.timedelta(days=3),
        )

        # Juridique et technique
        aujourdhui = timezone.localdate(maintenant)
        for vehicule_, jours in ((v1, -10), (v2, 12), (v_ok, 25), (v_grand, 200), (v_bloque, 90)):
            Assurance.objects.create(
                vehicule=vehicule_, company=stc, compagnie_assurance="NSIA Assurances",
                numero_police=f"POL-{vehicule_.immatriculation}", date_echeance=aujourdhui + datetime.timedelta(days=jours),
            )
        Sinistre.objects.create(
            vehicule=v_bloque, incident=grave, company=stc, statut=StatutSinistre.OUVERT,
            description="Collision : constat amiable en cours, expertise demandée.",
        )
        Sinistre.objects.create(
            vehicule=v_grand, incident=ancien, company=stc, statut=StatutSinistre.CLOS,
            description="Rétroviseur : réparation remboursée.",
        )
        Sinistre.objects.create(
            vehicule=v_maintenance, company=stc, statut=StatutSinistre.EN_COURS,
            description="Dégât des eaux dans le dépôt.",
        )
        OrdreReparation.objects.create(
            vehicule=v_maintenance, company=stc, description="Remplacement de la boîte de vitesses.",
            statut=StatutOrdreReparation.EN_COURS, mecanicien=relais,
        )

        # Dossiers RH
        for i, agent in enumerate(a_ for a_ in agents.values() if a_.username not in SANS_DOSSIER):
            DossierAgent.objects.create(
                agent=agent, company=stc, poste=Role(agent.role).label,
                date_embauche=aujourdhui - datetime.timedelta(days=200 + 173 * i),
                statut=StatutDossierAgent.SUSPENDU if agent.username == "chauffeur3_stc" else StatutDossierAgent.ACTIF,
                notes_rh="Mise à pied de 3 jours (retard répété)." if agent.username == "chauffeur3_stc" else "",
            )

        # Une activité pour la deuxième compagnie : la vue plateforme en montre deux, et la
        # vérification d'isolation a quelque chose à ne pas laisser passer.
        if {"chauffeur_savane", "guichetier_savane"} <= set(agents_savane):
            ligne_savane = Ligne.objects.get(nom="Bouaké-Korhogo", company=savane)
            v_savane = Vehicule.objects.get_or_create(
                immatriculation="CI-2002-CD", defaults={"capacite": 40, "statut": VehiculeStatut.DISPONIBLE, "company": savane}
            )[0]
            depart_et_feuille(
                savane, ligne_savane, v_savane, agents_savane["chauffeur_savane"], a(0, 9), 18,
                DepartStatut.EN_COURS, reelle=a(0, 9, 3),
            )

        self.stdout.write(self.style.SUCCESS("Données des tableaux de bord générées pour STC Voyages et Express Savane."))
