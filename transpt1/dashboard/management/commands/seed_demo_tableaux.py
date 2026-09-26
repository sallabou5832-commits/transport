import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.demo_garde import refuser_hors_developpement
from core.models import Company, Role
from finance.models import (
    BudgetCarburant,
    CategorieDepense,
    ConfigurationFinance,
    Depense,
    Facture,
    Fournisseur,
    StatutFacture,
    TypeFacture,
)
from investissements.models import Investissement, TypeInvestissement
from rh.services import ajouter_mois
from rh.models import (
    Candidature,
    ContratAgent,
    DemandeConge,
    Doleance,
    EvaluationAgent,
    FormationSuivie,
    MesureDisciplinaire,
    ObligationFormation,
    OffreRecrutement,
)
from maintenance.models import OrdreReparation, PlanEntretien, StatutOrdreReparation, UrgenceReparation
from personnel_roulant.models import (
    ChecklistDepart,
    EtatChecklist,
    FeuilleDeRoute,
    GraviteIncident,
    Incident,
    PositionVehicule,
    StatutIncident,
    TypeIncident,
)
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut
from supports.models import Assurance, CategorieModele, DossierAgent, ModeleJuridique, Sinistre, StatutDossierAgent, StatutSinistre

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

        def vehicule(immat, capacite, statut, gare):
            return Vehicule.objects.get_or_create(
                immatriculation=immat, defaults={"capacite": capacite, "statut": statut, "company": stc, "gare": gare}
            )[0]

        # Le parc est réparti entre les gares : Adjamé et Yopougon ont plus de départs que de véhicules disponibles (gares en
        # tension), Bouaké a de quoi prêter un car.
        v_ok = vehicule("CI-1003-AB", 60, VehiculeStatut.DISPONIBLE, adjame)
        v_bloque = vehicule("CI-1004-AB", 50, VehiculeStatut.BLOQUE_SECURITE, yopougon)
        v_maintenance = vehicule("CI-1005-AB", 45, VehiculeStatut.EN_MAINTENANCE, yakro)
        v_grand = vehicule("CI-1006-AB", 70, VehiculeStatut.DISPONIBLE, Gare.objects.get(nom="Gare Bouaké", company=stc))

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
            statut=StatutOrdreReparation.EN_COURS, mecanicien=agents["mecanicien_stc"],
            urgence=UrgenceReparation.HAUTE, delai_estime_heures=48,
        )

        # Compteurs kilométriques (relevés par le technique) et un entretien préventif à jour : de quoi montrer le rapport de
        # renouvellement (un véhicule a dépassé les 600 000 km) et le planning d'entretien.
        for vehicule_, km in ((v1, 182000), (v2, 415000), (v_ok, 96000), (v_bloque, 640000), (v_maintenance, 388000), (v_grand, 121000)):
            Vehicule.objects.filter(pk=vehicule_.pk).update(kilometrage=km)
        # Obligations réglementaires : une visite technique à jour, une en retard (le tableau de conformité du QHSE et du juridique).
        for vehicule_, fait_il_y_a in ((v1, 200), (v2, 400)):
            PlanEntretien.objects.get_or_create(
                vehicule=vehicule_, company=stc, libelle="Visite technique périodique",
                defaults={
                    "periodicite_jours": 365, "derniere_date": timezone.localdate() - datetime.timedelta(days=fait_il_y_a),
                    "reglementaire": True, "declenche_ordre": False,
                },
            )
        PlanEntretien.objects.get_or_create(
            vehicule=v1, company=stc, libelle="Vidange",
            defaults={
                "periodicite_km": 10000, "periodicite_jours": 180, "derniere_date": timezone.localdate() - datetime.timedelta(days=60),
                "dernier_km": 176000, "duree_estimee_heures": 4,
            },
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
                immatriculation="CI-2002-CD",
                defaults={
                    "capacite": 40, "statut": VehiculeStatut.DISPONIBLE, "company": savane,
                    "gare": Gare.objects.filter(nom="Gare Bouaké Nord", company=savane).first(),
                },
            )[0]
            depart_et_feuille(
                savane, ligne_savane, v_savane, agents_savane["chauffeur_savane"], a(0, 9), 18,
                DepartStatut.EN_COURS, reelle=a(0, 9, 3),
            )

        # Une demande d'investissement du technique attend la décision du PDG.
        if "directeur_technique_stc" in agents:
            Investissement.objects.get_or_create(
                company=stc, libelle="Achat de 3 autocars",
                defaults={
                    "type": TypeInvestissement.ACHAT_VEHICULE, "montant": 210000000, "quantite": 3,
                    "demandeur": agents["directeur_technique_stc"],
                    "justification": "Trois autocars ont dépassé 900 000 km et immobilisent la flotte.",
                },
            )

        if "directeur_financier_stc" in agents:
            self._tenir_les_comptes(stc, agents["directeur_financier_stc"], (ligne_bouake, ligne_yakro, ligne_adjame_yakro), adjame, v1)

        if {"drh_stc", "chauffeur_stc", "guichetier_stc"} <= set(agents):
            self._animer_les_rh(stc, agents)
        if "responsable_juridique_stc" in agents:
            self._garnir_la_bibliotheque(stc, agents["responsable_juridique_stc"])

        self._localiser_le_reseau(maintenant)
        self.stdout.write(self.style.SUCCESS("Données des tableaux de bord générées pour STC Voyages et Express Savane."))

    def _animer_les_rh(self, company, agents):
        """La vie RH : formations obligatoires à des états variés, contrats, une évaluation, une mesure, des congés (dont un dont l'impact est
        critique), une offre de recrutement et deux doléances (dont une assez grave pour prévenir le juridique au prochain passage des alertes)."""
        aujourdhui = timezone.localdate()
        drh = agents["drh_stc"]

        def jour(decalage):
            return aujourdhui + datetime.timedelta(days=decalage)

        oser = ObligationFormation.objects.create(
            company=company, nom="Sécurité routière OSER", roles=["chauffeur_principal", "chauffeur_relais"], validite_mois=24, preavis_jours=60,
            description="Formation annuelle de sécurité routière, suivie avec le QHSE.",
        )
        visite = ObligationFormation.objects.create(
            company=company, nom="Visite médicale d'aptitude", roles=["chauffeur_principal", "chauffeur_relais", "controleur_ligne"],
            validite_mois=12, preavis_jours=30,
        )
        # Un conducteur à jour, un dont l'échéance approche, un expiré, un qui n'a rien suivi.
        for username, obligation, il_y_a in (
            ("chauffeur_relais_stc", oser, 100), ("chauffeur_stc", oser, 700), ("chauffeur2_stc", oser, 800),
            ("chauffeur_stc", visite, 180), ("chauffeur_relais_stc", visite, 90),
        ):
            if username in agents:
                obtention = jour(-il_y_a)
                FormationSuivie.objects.create(
                    company=company, agent=agents[username], obligation=obligation, date_obtention=obtention,
                    date_expiration=ajouter_mois(obtention, obligation.validite_mois), saisi_par=drh, organisme="Centre agréé",
                )

        contrats = (("guichetier_stc", "cdd", jour(-160), jour(20)), ("chauffeur_stc", "cdi", jour(-900), None), ("chef_gare_stc", "cdi", jour(-1500), None))
        for username, type_, debut, fin in contrats:
            if username in agents:
                ContratAgent.objects.create(company=company, agent=agents[username], type=type_, date_debut=debut, date_fin=fin)
        if "chef_gare_stc" in agents:
            EvaluationAgent.objects.create(
                company=company, agent=agents["guichetier_stc"], date=jour(-20), note=4, evaluateur=agents["chef_gare_stc"],
                commentaire="Rigoureux à la caisse, à encourager sur l'accueil.",
            )
        if "chauffeur3_stc" in agents:
            MesureDisciplinaire.objects.create(
                company=company, agent=agents["chauffeur3_stc"], date=jour(-30), type="mise_a_pied", duree_jours=3,
                motif="Retards répétés au départ.", decidee_par=drh,
            )

        # Congés : le guichetier est seul à son poste (impact critique) ; le chauffeur a un départ demain (à réaffecter).
        DemandeConge.objects.create(company=company, agent=agents["guichetier_stc"], type="annuel", debut=jour(10), fin=jour(14), motif="Mariage d'un proche")
        if "chauffeur2_stc" in agents:
            DemandeConge.objects.create(company=company, agent=agents["chauffeur2_stc"], type="annuel", debut=jour(1), fin=jour(3), motif="Voyage familial")

        offre = OffreRecrutement.objects.create(
            company=company, role="chauffeur_principal", intitule="Chauffeur d'autocar", nombre_postes=2, date_limite=jour(30), cree_par=drh,
            description="Missions\n- Conduire en sécurité selon la feuille de route\n\nProfil recherché\n- Permis D et visite médicale à jour",
        )
        Candidature.objects.create(company=company, offre=offre, nom="Yao Kouadio", telephone="0708091011", source="Annonce")
        Candidature.objects.create(company=company, offre=offre, nom="Awa Traoré", telephone="0501020304", statut="entretien", source="Recommandation")

        Doleance.objects.create(
            company=company, auteur=agents["guichetier_stc"], objet="Primes de caisse non versées",
            description="Les primes de caisse du dernier trimestre n'ont pas été versées.", gravite="moyenne",
        )
        Doleance.objects.create(
            company=company, origine="syndicat", syndicat="Délégués du personnel roulant", objet="Temps de repos entre deux trajets",
            description="Les conducteurs signalent des repos inférieurs aux durées prévues sur la ligne Abidjan-Bouaké.", gravite="grave",
        )

    def _garnir_la_bibliotheque(self, company, juriste):
        """Des modèles de documents que les autres pôles peuvent reprendre, dont un réservé au pôle technique."""
        for titre, categorie, contenu, poles in (
            ("Attestation de travail", CategorieModele.TRAVAIL, "Je soussigné [nom], [fonction] de [compagnie], atteste que [agent] est employé(e) depuis le [date d'embauche].", []),
            (
                "Constat amiable d'accident", CategorieModele.SINISTRE,
                "1. Date, heure et lieu\n2. Véhicules impliqués (immatriculation, assureur, police)\n3. Circonstances\n4. Témoins\n5. Signatures", [],
            ),
            ("Charte de sécurité de l'atelier", CategorieModele.REGLEMENT, "Port obligatoire du gilet et des chaussures de sécurité, consignation avant intervention…", ["technique"]),
        ):
            ModeleJuridique.objects.create(company=company, titre=titre, categorie=categorie, contenu=contenu, poles=poles, auteur=juriste)

    def _tenir_les_comptes(self, company, saisisseur, lignes, gare, vehicule):
        """La comptabilité du mois : un solde de départ, du carburant dépensé contre des budgets (une ligne à 92 %, une qui dépasse),
        des charges communes, et des factures à des échéances variées (une en retard, une à cinq jours, une déjà payée)."""
        ligne_bouake, ligne_yakro, ligne_adjame_yakro = lignes
        aujourdhui = timezone.localdate()
        debut_mois = aujourdhui.replace(day=1)

        def le(jours_avant):
            return max(debut_mois, aujourdhui - datetime.timedelta(days=jours_avant))  # toujours dans le mois en cours

        ConfigurationFinance.objects.get_or_create(company=company, defaults={"solde_initial": 2000000})
        for ligne, budget in ((ligne_bouake, 250000), (ligne_yakro, 120000), (ligne_adjame_yakro, 80000)):
            BudgetCarburant.objects.get_or_create(company=company, ligne=ligne, mois=debut_mois, defaults={"montant": budget})

        def depense(jours_avant, categorie, libelle, montant, **rattachement):
            return Depense.objects.create(
                company=company, date=le(jours_avant), categorie=categorie, libelle=libelle, montant=montant, saisi_par=saisisseur,
                **rattachement,
            )

        depense(9, CategorieDepense.CARBURANT, "Plein Abidjan-Bouaké", 75000, ligne=ligne_bouake)
        depense(3, CategorieDepense.CARBURANT, "Plein Abidjan-Bouaké", 75000, ligne=ligne_bouake)
        depense(8, CategorieDepense.CARBURANT, "Plein Yopougon-Yamoussoukro", 55000, ligne=ligne_yakro)
        depense(2, CategorieDepense.CARBURANT, "Plein Yopougon-Yamoussoukro", 55000, ligne=ligne_yakro)
        depense(4, CategorieDepense.CARBURANT, "Plein Abidjan-Yamoussoukro", 95000, ligne=ligne_adjame_yakro)
        depense(6, CategorieDepense.MAINTENANCE, "Vidange et filtres", 180000, vehicule=vehicule)
        depense(5, CategorieDepense.AUTRE, "Loyer de la gare d'Adjamé", 150000, gare=gare)
        depense(1, CategorieDepense.SALAIRES, "Salaires du personnel administratif", 600000)

        fournisseurs = {
            nom: Fournisseur.objects.get_or_create(company=company, nom=nom, defaults={"categorie": categorie})[0]
            for nom, categorie in (("Total Énergies CI", "Carburant"), ("Garage Auto Plus", "Pièces détachées"), ("NSIA Assurances", "Assurance"))
        }

        def facture(fournisseur, type_, libelle, montant, echeance_dans, **plus):
            return Facture.objects.create(
                company=company, fournisseur=fournisseurs[fournisseur], type=type_, libelle=libelle, montant=montant,
                date_emission=aujourdhui - datetime.timedelta(days=30), echeance=aujourdhui + datetime.timedelta(days=echeance_dans),
                saisi_par=saisisseur, **plus,
            )

        facture("NSIA Assurances", TypeFacture.ASSURANCE, "Prime d'assurance de la flotte", 480000, 5, reference="PRIME-2026-09")
        facture("Garage Auto Plus", TypeFacture.FOURNISSEUR, "Plaquettes de frein et filtres", 95000, -4, reference="GAP-0418")
        facture("Total Énergies CI", TypeFacture.FOURNISSEUR, "Carburant du mois", 320000, 20)
        reglement = Depense.objects.create(
            company=company, date=aujourdhui - datetime.timedelta(days=3), categorie=CategorieDepense.FOURNISSEUR,
            libelle="Garage Auto Plus — Pneus avant", montant=210000, saisi_par=saisisseur,
        )
        facture(
            "Garage Auto Plus", TypeFacture.FOURNISSEUR, "Pneus avant", 210000, -3, statut=StatutFacture.PAYEE,
            payee_le=reglement.date, mode_paiement="virement", depense=reglement,
        )

    # Coordonnées approximatives des gares de démonstration (pour la carte du réseau).
    COORDONNEES = {
        "Gare Adjamé": (5.3600, -4.0083), "Gare Yopougon": (5.3400, -4.0900), "Gare Bouaké": (7.6906, -5.0300),
        "Gare Yamoussoukro": (6.8276, -5.2893), "Gare Bouaké Nord": (7.7100, -5.0300), "Gare Korhogo": (9.4580, -5.6297),
    }

    def _localiser_le_reseau(self, maintenant):
        """Donne des coordonnées aux gares, et une position (proportionnelle au temps écoulé) aux cars en route."""
        for gare in Gare.objects.all():
            coordonnees = self.COORDONNEES.get(gare.nom)
            if coordonnees and gare.latitude is None:
                gare.latitude, gare.longitude = coordonnees
                gare.save(update_fields=["latitude", "longitude"])
        en_route = FeuilleDeRoute.objects.filter(
            heure_depart_reelle__isnull=False, heure_arrivee_reelle__isnull=True
        ).select_related("depart__ligne__gare_depart", "depart__ligne__gare_arrivee", "depart__vehicule")
        for feuille in en_route:
            ligne = feuille.depart.ligne
            depart_, arrivee_ = ligne.gare_depart, ligne.gare_arrivee
            if depart_.latitude is None or arrivee_.latitude is None or feuille.positions.exists():
                continue
            ecoule = (maintenant - feuille.heure_depart_reelle).total_seconds() / 3600
            progression = min(0.9, max(0.1, ecoule / 4))  # un trajet dure environ 4 h
            for reculons in (2, 1, 0):  # trois relevés, le dernier est « maintenant »
                part = max(0.05, progression - 0.04 * reculons)
                PositionVehicule.objects.create(
                    company=feuille.company, vehicule=feuille.depart.vehicule, feuille_de_route=feuille,
                    latitude=round(float(depart_.latitude) + (float(arrivee_.latitude) - float(depart_.latitude)) * part, 6),
                    longitude=round(float(depart_.longitude) + (float(arrivee_.longitude) - float(depart_.longitude)) * part, 6),
                    vitesse_kmh=82 + reculons, releve_le=maintenant - datetime.timedelta(minutes=2 * reculons),
                    releve_par=feuille.chauffeur,
                )
