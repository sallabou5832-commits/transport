import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.demo_garde import refuser_hors_developpement
from core.models import Company
from maintenance.models import OrdreReparation, Piece, StatutOrdreReparation
from personnel_roulant.models import ChecklistDepart, EtatChecklist, FeuilleDeRoute
from reseau.models import AffectationGare, Ligne, Vehicule


class Command(BaseCommand):
    help = (
        "Crée un départ, un ticket, une feuille de route, des pièces et un ordre de "
        "réparation de démonstration pour STC Voyages — à lancer après seed_demo_users "
        "et seed_demo_reseau. Sert à avoir des données visibles dans le frontend."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        refuser_hors_developpement("seed_demo_operations")
        User = get_user_model()

        try:
            stc = Company.objects.get(name="STC Voyages")
            ligne = Ligne.objects.get(nom="Abidjan-Bouaké", company=stc)
            vehicule = Vehicule.objects.get(immatriculation="CI-1001-AB")
            vehicule_atelier = Vehicule.objects.get(immatriculation="CI-1002-AB")
        except (Company.DoesNotExist, Ligne.DoesNotExist, Vehicule.DoesNotExist) as exc:
            raise CommandError(
                "Données de base introuvables. Lancez d'abord : "
                "python manage.py seed_demo_users puis python manage.py seed_demo_reseau"
            ) from exc

        try:
            chauffeur = User.objects.get(username="chauffeur_stc")
            mecanicien = User.objects.get(username="mecanicien_stc")
            guichetier = User.objects.get(username="guichetier_stc")
        except User.DoesNotExist as exc:
            raise CommandError(
                "Utilisateurs de démo introuvables. Lancez d'abord : python manage.py seed_demo_users"
            ) from exc

        # Dans 3 h, mais toujours AUJOURD'HUI : la page du chauffeur ne liste que les feuilles de route
        # du jour, un départ qui passerait à demain (commande lancée le soir) n'y apparaîtrait pas.
        maintenant = timezone.now()
        fin_de_journee = timezone.localtime(maintenant).replace(hour=23, minute=55, second=0, microsecond=0)
        depart, _ = Depart.objects.update_or_create(
            ligne=ligne,
            vehicule=vehicule,
            chauffeur=chauffeur,
            company=stc,
            defaults={
                "date_heure": min(maintenant + datetime.timedelta(hours=3), fin_de_journee),
                "statut": DepartStatut.PLANIFIE,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Départ prêt : {depart}"))

        ticket, ticket_cree = Ticket.objects.get_or_create(
            depart=depart,
            passager_nom="Passager Démo",
            defaults={
                "company": stc,
                "passager_telephone": "+2250700000000",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.ESPECES,
                "vendu_par": guichetier,
            },
        )
        if ticket_cree:
            depart.places_vendues += 1
            depart.save(update_fields=["places_vendues"])
        self.stdout.write(self.style.SUCCESS(f"{'Créé' if ticket_cree else 'Existe déjà'} : {ticket}"))

        feuille, _ = FeuilleDeRoute.objects.get_or_create(
            depart=depart,
            defaults={
                "chauffeur": chauffeur,
                "company": stc,
                "heure_depart_prevue": depart.date_heure,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Feuille de route prête : {feuille}"))

        checklist, _ = ChecklistDepart.objects.get_or_create(
            feuille_de_route=feuille,
            item="pneus",
            defaults={"etat": EtatChecklist.OK, "company": stc, "commentaire": "RAS"},
        )
        self.stdout.write(self.style.SUCCESS(f"Item checklist prêt : {checklist}"))

        piece_basse, _ = Piece.objects.get_or_create(
            reference="REF-DEMO-HUILE",
            company=stc,
            defaults={"nom": "Filtre à huile", "quantite_stock": 2, "seuil_alerte": 5},
        )
        piece_ok, _ = Piece.objects.get_or_create(
            reference="REF-DEMO-PNEU",
            company=stc,
            defaults={"nom": "Pneu 22.5", "quantite_stock": 20, "seuil_alerte": 4},
        )
        self.stdout.write(self.style.SUCCESS(f"Pièces prêtes : {piece_basse}, {piece_ok}"))

        ordre, _ = OrdreReparation.objects.get_or_create(
            vehicule=vehicule_atelier,
            company=stc,
            description="Révision moteur programmée.",
            defaults={"statut": StatutOrdreReparation.OUVERT, "mecanicien": mecanicien},
        )
        self.stdout.write(self.style.SUCCESS(f"Ordre de réparation prêt : {ordre}"))

        # L'équipe locale de la gare de départ, telle que le chef de gare la composerait (guichetier et bagagiste).
        for username in ("guichetier_stc", "bagagiste_stc"):
            agent = User.objects.get(username=username)
            AffectationGare.objects.get_or_create(
                agent=agent, defaults={"gare": ligne.gare_depart, "company": stc}
            )
        self.stdout.write(self.style.SUCCESS(f"Équipe de la gare {ligne.gare_depart.nom} prête."))
