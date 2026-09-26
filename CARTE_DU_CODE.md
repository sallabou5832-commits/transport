# Carte du code — rôle de chaque fichier

Inventaire de tous les fichiers du dépôt (hors fichiers générés : `frontend/dist*/`, `node_modules/`, `venv/`,
`__pycache__/`, plateformes mobiles `android/ios/linux/macos/windows/web` sous `mobile/`, verrous de dépendances).
Les `__init__.py`, `apps.py` et dossiers `migrations/` (schéma de base, un fichier par évolution) ne sont pas
détaillés un par un : leur rôle est toujours le même, rappelé une fois par app.

**Repère de suivi git** : 🔴 = fichier ou dossier actuellement **non suivi par git** (`??`, voir l'alerte ci-dessus) —
à corriger par un commit, pas un défaut du fichier lui-même.

## 1. Racine du dépôt

| Fichier | Rôle |
|---|---|
| `cahier.txt` | Le cahier des charges d'origine (5 pôles, 18 postes, 99 fonctionnalités) : la référence que tous les rapports de conformité découpent et vérifient. |
| `ANALYSE_PROJET.md` | Analyse fonctionnelle/sécurité/performance/qualité du 21 septembre, **avant** le chantier de mise en conformité — gardée pour sa méthode et ses chiffres de référence. |
| `RAPPORT_CONFORMITE.md` 🔴 | Les 99 fonctionnalités du cahier, une par une, état **après** le chantier (62 complètes, 20 partielles, 17 absentes) — référence à jour pour le fonctionnel. |
| `AUDIT_SECURITE_FONCTIONNEL_2026-09-24.md` 🔴 | Audit sécurité app par app du 24 septembre — référence à jour pour la sécurité. |
| `SCENARIO_PILOTE.md` | Scénario de bout en bout à rejouer à la main dans le navigateur (variantes A à J : vente, incident, atelier, PDG, colis, jeu, caisse, GPS, contrôle des billets, pouvoirs de direction). |
| `.gitignore` | Exclut `.claude/` (outils locaux de session) du suivi git à la racine. |
| `Disque local (C) - Raccourci.lnk` 🔴 | Raccourci Windows isolé à la racine, sans rapport avec le projet — probablement créé par erreur, à supprimer plutôt qu'à commiter. |

## 2. Backend Django (`transpt1/`)

### 2.0 Configuration du projet

| Fichier | Rôle |
|---|---|
| `manage.py` | Point d'entrée des commandes Django (`runserver`, `migrate`, `test`, commandes personnalisées). |
| `transport_coord/settings.py` | Réglages du projet : base de données, sécurité (HTTPS, JWT, CORS, limitation des connexions), apps installées, sauvegardes, notifications, seuils métier (fatigue, entretien, renouvellement). |
| `transport_coord/urls.py` | Branche l'admin Django et les `urls.py` de chaque app sous `/api/`. |
| `transport_coord/asgi.py` / `wsgi.py` | Points d'entrée serveur ASGI/WSGI (déploiement). |
| `requirements.txt` | Dépendances de production (Django, DRF, JWT, psycopg2, Twilio, etc.). |
| `requirements-dev.txt` 🔴 | Ajoute les outils de test et d'audit (`pytest`, `pip-audit`) par-dessus `requirements.txt`. |
| `pytest.ini` | Configuration de pytest-django (module de settings, options d'exécution). |
| `conftest.py` | Fixtures pytest globales (compagnies, utilisateurs de test par rôle, client API authentifié). |
| `.env.example` | Modèle des variables d'environnement (`DJANGO_SECRET_KEY`, base de données, notifications, sauvegardes…) ; `.env` réel non versionné. |
| `.gitignore` | Exclut `.env`, `venv/`, `__pycache__/`, `staticfiles/`. |
| `PERMISSIONS.md` | Qui peut voir et faire quoi, par rôle — fait foi, vérifié par `role_coverage_tests`. |
| `DEPLOIEMENT.md` | Checklist de mise en production : variables d'environnement, migrations, proxy, tâches planifiées, sauvegardes, limites connues. |
| `README.md` | Installation, structure des 18 apps, comptes de démonstration, endpoints clés. |
| `deploy/sauvegarde-windows.ps1` | Script Windows planifiable qui lance `sauvegarde_base` puis `etat_sauvegarde`. |
| `deploy/transport-coord-sauvegarde.{service,timer}` | Unités systemd (Linux) : sauvegarde nocturne planifiée. |
| `deploy/transport-coord-verif-sauvegarde.{service,timer}` | Unités systemd : test hebdomadaire de restauration planifié. |
| `scripts/base_e2e.py` 🔴 | Prépare une base jetable pour les essais de bout en bout du site (`npm run e2e`). |

### 2.1 `core/` — utilisateurs, compagnies, authentification, sauvegardes

| Fichier | Rôle |
|---|---|
| `models.py` | `Company` (compagnie), `Role` (18 rôles + superadmin), `User` (rôle + compagnie, suspension de compte). |
| `admin.py` | Admin Django du `User` : rôle **obligatoire et sans valeur par défaut** à la création (empêche qu'un compte créé à la hâte devienne superadmin). |
| `permissions.py` | `IsSameCompany` (isolation multi-compagnie), `IsPdg`. |
| `mixins.py` | `CompanyScopedQuerysetMixin` : filtre toute liste par la compagnie de l'utilisateur ; pose l'acteur du journal d'audit. |
| `serializers.py` 🔴 (`comptes.py`) | `serializers.py` : `Company`, `User`, `Compte`. `comptes.py` 🔴 : suspendre/réactiver un compte (motif obligatoire, alerte au DRH et au chef de gare). |
| `views.py` | `/api/auth/me/`, détail d'une compagnie, liste et suspension des comptes (PDG). |
| `throttles.py` 🔴 | Limitation des tentatives de connexion (par compte+adresse, et par adresse seule). |
| `fichiers.py` 🔴 | Pièces jointes : type de fichier vérifié par signature binaire, nom aléatoire, jamais de lien public, téléchargement sécurisé. |
| `sauvegarde.py` | `pg_dump`/`pg_restore` sans shell, empreinte SHA-256, rotation, envoi hors serveur, restauration testée. |
| `dates.py` 🔴 | Lit une date `AAAA-MM-JJ` d'un paramètre de requête sans lever d'exception sur une entrée invalide. |
| `demo_garde.py` 🔴 | Refuse les commandes de démonstration hors développement (`DJANGO_DEBUG=True` requis). |
| `urls.py` | `/api/auth/me/`, `/api/companies/<id>/`, `/api/comptes/`. |
| `management/commands/seed_demo_users.py` | Crée 2 compagnies et un utilisateur par rôle (mot de passe `Demo!2024`). |
| `management/commands/sauvegarde_base.py`, `verifier_sauvegarde.py`, `etat_sauvegarde.py` | Sauvegarde, test de restauration réel, vérification d'état (code de sortie pour supervision). |
| `tests/` (8 fichiers) | Modèles, permissions, authentification JWT, HTTPS, dates invalides, comptes (suspension), sauvegardes, données de démo. |

### 2.2 `audit/` — journal d'audit et connexions

| Fichier | Rôle |
|---|---|
| `models.py` | `JournalAudit` (compagnie, acteur, action, objet, avant/après, adresse IP), `ActionAudit`. |
| `signals.py` | Écoute la sauvegarde/suppression de 30+ modèles métier et écrit automatiquement l'entrée d'audit (mot de passe jamais tracé). |
| `contexte.py` | Qui agit et depuis où, porté par la requête en cours (`ContextVar`), lu par `signals.py`. |
| `middleware.py` | Pose l'adresse IP et l'utilisateur de session à chaque requête, réinitialise le contexte ensuite. |
| `views.py` | `ConnexionAuditee` (connexion JWT tracée, limitation des tentatives), `JournalAuditView` (consultation paginée et filtrable). |
| `permissions.py` | Consultation réservée à PDG, secrétaire général, QHSE, superadmin. |
| `serializers.py` | Sérialise une entrée du journal. |
| `admin.py` | Lecture seule dans l'admin (le journal ne se modifie ni ne se supprime). |
| `urls.py` | `/api/audit/`. |
| `tests/` (4 fichiers 🔴 dont `test_limitation.py`) | API du journal, connexions tracées, limitation des tentatives (429), consultation. |

### 2.3 `billetterie/` — départs, tickets, caisse

| Fichier | Rôle |
|---|---|
| `models.py` | `Depart`, `Ticket` (statut, code, annulation), `ReservationHorsLigne`, `ClotureCaisse`. |
| `permissions.py` | Rôles guichetier-et-au-dessus (ventes), rôles de planification (départs). |
| `planning.py` | Qui/quoi est libre à quelle heure : mêmes règles pour la création, la réaffectation et les suggestions de remplaçant. |
| `caisse.py` 🔴 | Calcul des totaux de caisse d'un guichetier et clôture (photo figée transmise au chef de gare). |
| `reservations.py` 🔴 | Réservation de places pour la vente hors ligne (quota, TTL, restitution). |
| `serializers.py` | Tarif imposé par la ligne (dérogation motivée réservée aux chefs), verrouillage du ticket après vente. |
| `views.py` | Vente idempotente, verrouillage (405 sur modif/suppression), annulation, planification, disponibilités, clôture de caisse. |
| `admin.py` | Departs/tickets en lecture, cohérents avec le verrouillage API. |
| `urls.py` | `/api/departs/`, `/api/tickets/`, `/api/cloture-caisse/`. |
| `management/commands/seed_demo_operations.py` | Données de démo : départ, ticket, feuille de route, pièce, ordre de réparation. |
| `management/commands/cloturer_caisses.py` 🔴 | Clôture automatique planifiée des caisses en fin de service. |
| `tests/` (9 fichiers, 3 🔴 dont `test_tarif.py`, `test_migration_code_billet.py`) | Idempotence, permissions, planification, réaffectation, réservations hors ligne, tarif imposé, clôture de caisse. |

### 2.4 `reseau/` — gares, lignes, véhicules

| Fichier | Rôle |
|---|---|
| `models.py` | `Gare`, `Ligne` (tarif), `Vehicule` (immatriculation **unique plateforme**, gare d'attache), `AffectationGare`, `ChangementLigne`. |
| `permissions.py` | Chef de gare limité à sa gare ; rôles de pilotage réseau ; décideurs/demandeurs de fermeture de ligne. |
| `lignes.py` 🔴 | Fermeture/réouverture de ligne : demande (chef de ligne/gare), décision (directeur exploitation/PDG), réouverture automatique. |
| `team.py` 🔴 | Équipe locale d'une gare : qui l'affecte (chef de sa gare, ou pilotage pour toute gare). |
| `serializers.py` | Refus des références croisées entre compagnies (gare/ligne/véhicule). |
| `views.py` | CRUD gares/lignes/véhicules, réaffectation de véhicule entre gares, gestion des affectations d'équipe, changements de ligne. |
| `admin.py` | Admin Django des gares/lignes/véhicules. |
| `urls.py` | `/api/gares/`, `/api/lignes/`, `/api/vehicules/`, `/api/affectations-gare/`, `/api/changements-ligne/`. |
| `management/commands/seed_demo_reseau.py` | Gares/lignes/véhicules de démonstration. |
| `tests/` (6 fichiers, 2 🔴 : `test_affectation_gare.py`, `test_fermeture_ligne.py`) | Permission du chef de gare, gares, lignes, véhicules, affectation d'équipe, fermeture de ligne. |

### 2.5 `personnel_roulant/` — feuilles de route, checklists, incidents, GPS, contrôle

| Fichier | Rôle |
|---|---|
| `models.py` | `FeuilleDeRoute`, `ChecklistDepart`, `Incident`, `BlocageSecurite`, `Relais`, `ChecklistReprise`, `ControleLigne`, `PausePrise`, `PositionVehicule`. |
| `permissions.py` | Chauffeur restreint à ses propres feuilles/checklists/incidents ; QHSE pour les blocages ; contrôleur pour les contrôles. |
| `suivi.py` 🔴 | Position en cours, temps de conduite continue (alerte fatigue à 4h30), relais entre conducteurs. |
| `controle.py` 🔴 | Contrôle à bord : vérification de billet, comparaison voyageurs/charge, génération du rapport. |
| `carnet.py` 🔴 | Carnet de route numérique : derniers trajets et documents du véhicule (assurance, contrôle technique). |
| `serializers.py` | Sérialisation des feuilles, checklists, incidents, positions, contrôles. |
| `views.py` | Feuilles de route, checklists, incidents, blocages de sécurité, positions GPS par lots, mon trajet, relais, contrôle de ligne. |
| `admin.py` | Admin Django des objets terrain. |
| `urls.py` | `/api/feuilles-de-route/`, `/api/checklists/`, `/api/incidents/`, `/api/blocages-securite/`, `/api/positions/`, `/api/controles/`, etc. |
| `tests/` (11 fichiers, 6 🔴) | Checklist/blocage, checklist unique, incidents graves, propagation du départ, restriction chauffeur, carnet de route, contrôle de ligne, fatigue/relais, positions GPS, reprise. |

### 2.6 `maintenance/` — pièces, ordres de réparation, atelier

| Fichier | Rôle |
|---|---|
| `models.py` | `Piece` (référence unique **par compagnie**), `OrdreReparation`, `SortiePiece`, `PlanEntretien`, `DemandePiece`. |
| `permissions.py` | Magasinier/chef d'atelier/directeur technique pour le stock ; mécanicien limité à ses propres ordres pour la modification. |
| `stock.py` 🔴 | Sortie de pièce : décrémente le stock, alerte sous le seuil. |
| `preventif.py` 🔴 | Entretien préventif : échéance en jours et/ou km, ordre ouvert automatiquement au mécanicien le moins chargé. |
| `analyses.py` 🔴 | Lecture seule : file des réparations par urgence, charge des mécaniciens, fiche véhicule, suggestions de commande, besoin de renouvellement. |
| `serializers.py` | Sérialisation pièces/ordres/sorties/plans/demandes. |
| `views.py` | Stock, ordres de réparation (file, réordonner, prioriser), demandes de pièces, fiche véhicule, charge, renouvellement. |
| `admin.py` | Admin Django atelier/stock. |
| `urls.py` | `/api/pieces/`, `/api/ordres-reparation/`, `/api/demandes-pieces/`, `/api/fiche-vehicule/`, `/api/maintenance/...`. |
| `tests/` (9 fichiers, 6 🔴) | Permissions, sortie de pièce, statut véhicule, analyses techniques, demandes de pièces, file d'attente, préventif, référence de pièce par compagnie, rôle mécanicien. |

### 2.7 `supports/` — dossiers RH (legacy), assurances, sinistres, juridique

| Fichier | Rôle |
|---|---|
| `models.py` | `DossierAgent`, `Assurance`, `Sinistre`, `PieceSinistre` (pièce jointe), `ModeleJuridique`. |
| `permissions.py` | DRH pour les dossiers ; juridique/technique pour assurances/sinistres/conformité ; finance pour la synthèse. |
| `conformite.py` 🔴 | Tableau de conformité réglementaire (assurance, contrôle technique, défauts ouverts, blocages) par véhicule — lecture seule. |
| `reporting_juridique.py` 🔴 | Reporting juridique pour la Direction Générale (assurances, sinistres, litiges comptés, sans donnée personnelle). |
| `services.py` 🔴 | Un incident grave déclaré ouvre automatiquement un dossier de sinistre. |
| `serializers.py` | Pièces jointes (validation de fichier), synthèse financière. |
| `views.py` | Dossiers agents, assurances, sinistres + pièces jointes (téléchargement authentifié), modèles juridiques, conformité, reporting. |
| `admin.py` | Admin Django RH/juridique. |
| `urls.py` | `/api/dossiers-agents/`, `/api/assurances/`, `/api/sinistres/`, `/api/modeles-juridiques/`, `/api/conformite/`, `/api/reporting-juridique/`. |
| `tests/` (5 fichiers, 3 🔴) | Permissions assurance/sinistre, permissions dossier agent, annuaire des dossiers, synthèse financière, conformité, juridique, synthèse fret. |

### 2.8 `dashboard/` — tableaux de bord

| Fichier | Rôle |
|---|---|
| `permissions.py` | Direction, exploitation, QHSE, superadmin (plateforme), carte, santé de gare. |
| `serializers.py` | Formes de réponse des tableaux de bord. |
| `ponctualite.py` 🔴 | Règle de ponctualité **partagée** avec le frontend (même seuil, tolérance 10 min) et avec les alertes automatiques. |
| `views.py` | `/api/dashboard/direction/`, `/exploitation/`, `/gare/`, `/carte/`, vue plateforme du superadmin. |
| `urls.py` | Routes des tableaux de bord. |
| `management/commands/seed_demo_tableaux.py` | Données réalistes pour les tableaux de bord (historique, incidents, assurances, sinistres). |
| `tests/` (5 fichiers, 3 🔴) | Dashboard direction/exploitation/plateforme/QHSE/gare, carte du réseau, parité de la règle de ponctualité avec le frontend. |

### 2.9 `notifications/` — SMS / WhatsApp

| Fichier | Rôle |
|---|---|
| `models.py` | `NotificationLog` (canal, contenu, fournisseur, statut, référence, erreur). |
| `providers.py` | Appels réels Orange SMS API et Twilio (SMS + WhatsApp) — jamais appelés en simulation. |
| `services.py` | Choix du fournisseur, mode simulation par défaut, échec isolé de la vente. |
| `admin.py` | Consultation du journal des notifications. |
| `urls.py` | (interne, pas de route publique dédiée — utilisé par `billetterie`/`colis`). |
| `tests/` (3 fichiers) | Fournisseurs, SMS de ticket, WhatsApp. |

### 2.10 `formation/` — parcours de formation simulés

| Fichier | Rôle |
|---|---|
| `models.py` | Parcours et étapes de formation par rôle. |
| `parcours_de_base.py` | Contenu par défaut des parcours (guichetier, chauffeur, magasinier). |
| `services.py` | Démarrer/reprendre un parcours, terminer une étape, calcul de progression — toujours simulé, isolé par compagnie. |
| `serializers.py` | Sérialisation parcours + progression. |
| `views.py` | Mon parcours, démarrer, terminer une étape. |
| `admin.py` | Édition du contenu des parcours. |
| `urls.py` | `/api/formation/mon-parcours/...`. |
| `management/commands/seed_formation.py` | Crée les parcours de base. |
| `tests/` (2 fichiers) | Isolation (aucune vraie donnée créée), progression. |

### 2.11 `role_coverage_tests/` — preuves transverses de conformité

| Fichier | Rôle |
|---|---|
| `test_matrice_conformite.py` | Chaque rôle × chaque endpoint restreint, comparé à `PERMISSIONS.md`. |
| `test_contrat_frontend.py` | Lit le code des pages web pour vérifier qu'aucune page n'appelle une route interdite à son rôle. |
| `test_role_coverage.py` | Couverture : tous les rôles ont un test qui les concerne. |
| `test_noms_affichage.py` | Cohérence des libellés de rôle affichés. |
| `test_scenario_pilote.py` | Rejoue par l'API le parcours nominal de `SCENARIO_PILOTE.md`. |
| `test_tickets_verrouilles.py` | Aucun rôle (superadmin compris, ni admin Django) ne peut modifier/supprimer un ticket vendu. |
| `test_e2e_comptes.py` 🔴 | Comptes utilisés par les essais de bout en bout du site. |

### 2.12 Apps ajoutées par le chantier de conformité (🔴 non suivies par git en intégralité)

| App | Fichiers clés | Rôle |
|---|---|---|
| `alertes/` 🔴 | `models.py` (`Alerte`, `LectureAlerte`, `TypeAlerte`), `services.py` (`alerter()` : jamais bloquant), `generation.py` (seuils critiques, départs à risque, échéances — idempotent), `serializers.py`, `views.py`/`urls.py` (`/api/alertes/`, lecture individuelle) | Alertes inter-pôles : cloche sur toutes les pages, génération automatique, blocage de sécurité QHSE. |
| `colis/` 🔴 | `models.py` (code de retrait haché, `make_password`/`check_password`), `serializers.py`, `services.py` (notifications, plan de chargement), `admin.py` (lecture seule), `views.py`/`urls.py` (`/api/colis/`) | Colis et bagages : enregistrement → chargement → arrivée → retrait par code (5 essais puis verrouillage). |
| `communication/` 🔴 | `models.py` (`NoteService`, `EvenementAgenda`, `MessageDirect`, `DocumentArchive`), `serializers.py`, `views.py`/`urls.py` (`/api/notes-service/`, `/api/agenda/`, `/api/messages-directs/`, `/api/archives/`) | Secrétariat général : notes de service, agenda de direction, messages directs du chef de gare, archives. |
| `configuration/` 🔴 | `models.py`, `regles.py` (qui configure qui, valeurs par défaut), `services.py` (configuration effective d'un agent, dans le cadre de la compagnie), `serializers.py`, `views.py`/`urls.py` (`/api/configuration/...`) | Configuration hiérarchique compagnie → poste → agent (automatisation, gamification), appliquée par le serveur. |
| `finance/` 🔴 | `models.py` (`Depense`, `BudgetCarburant`, `Fournisseur`, `Facture`, `ConfigurationFinance`), `serializers.py`, `views.py` (export CSV), `urls.py` (`/api/finance/...`) | Dépenses, budget carburant, fournisseurs/factures, export de reporting financier. |
| `gamification/` 🔴 | `models.py` (`MissionAccomplie`), `moteur.py` (points/niveaux/missions/badges recalculés à chaque fois), `views.py`/`urls.py` (`/api/gamification/moi/`, `/classement/`, `/agents/`) — pas de `serializers.py` (réponses construites en dict par `moteur.py`) | Points, niveaux, missions du jour, badges, classements, réglable par poste via `configuration`. |
| `investissements/` 🔴 | `models.py` (`Investissement`), `serializers.py`, `views.py`/`urls.py` (`/api/investissements/`) | Demandes d'investissement (technique/exploitation/finance), décision du PDG seul. |
| `rh/` 🔴 | `models.py` (obligations de formation, contrats, évaluations, mesures disciplinaires, congés, fiches de poste, recrutement, doléances), `serializers.py`, `views.py`/`urls.py` (`/api/rh/...`) | RH au-delà du dossier agent : formations obligatoires, congés, recrutement, médiation sociale. |

Chacune de ces 8 apps suit le même squelette que les apps « historiques » : `apps.py`, `admin.py`, `migrations/`,
`tests/` (couverture équivalente, un fichier par règle métier ou permission).

### 2.13 `tutelle/` — échange avec le Ministère des Transports / OSER / AMUGA / OFT

| Fichier | Rôle |
|---|---|
| `models.py` | `FluxTutelle` (échange, par type et direction), `CompteTutelle` (clé d'API **hachée** SHA-256, jamais en clair). |
| `authentication.py` | Authentification par clé d'API, séparée des JWT internes, jamais dans `DEFAULT_AUTHENTICATION_CLASSES`. |
| `permissions.py` | `EstCompteTutelle` (réservé à la tutelle), `PeutSuivreLesFluxTutelle` (QHSE, responsable juridique). |
| `generation.py` | Génère automatiquement les flux (incident grave, assurance proche échéance) — idempotent. |
| `signals.py` | Un incident grave prévient la tutelle tout seul, sans coupler `personnel_roulant` à `tutelle`. |
| `serializers.py` | Flux (lecture) et flux entrant (ce que la tutelle envoie). |
| `views.py` | Consultation/traitement des flux, réception d'un flux entrant, rattrapage à la demande. |
| `admin.py` | Gestion des comptes tutelle. |
| `urls.py` | `/api/tutelle/entrant/`, `/api/tutelle/generer/`, `/api/flux-tutelle/`. |
| `management/commands/creer_compte_tutelle.py` | Crée un compte tutelle, affiche la clé en clair **une seule fois**. |
| `management/commands/generer_flux_tutelle.py` | Rattrapage quotidien planifié des flux automatiques. |
| `tests/test_tutelle.py` | Authentification, permissions, génération, réception d'un flux. |

## 3. Frontend web (`frontend/`)

### 3.1 Configuration

| Fichier | Rôle |
|---|---|
| `index.html` | Page hôte de l'application React (Vite). |
| `vite.config.js` | Configuration du bundler (build, dev server). |
| `package.json` | Dépendances (React 19, React Router 7), scripts (`dev`, `build`, `lint`, `test`, `e2e`). |
| `.oxlintrc.json` | Règles du linter `oxlint`. |
| `.env.example` | `VITE_API_BASE_URL` (adresse de l'API). |
| `.gitignore` | Exclut `node_modules/`, `dist/`. |
| `README.md` | Installation, comptes de démonstration. |
| `public/favicon.svg`, `public/icons.svg` | Icône de l'onglet, sprite d'icônes utilisé par les pages. |
| `src/main.jsx` | Point d'entrée React (monte `<App/>`). |
| `src/index.css` | Styles globaux (thème, mise en page commune à toutes les pages). |
| `src/App.jsx` | Table de routage : associe chaque chemin (`/dashboard/direction`, `/secretariat`…) à sa page et à `ProtectedRoute`. |

### 3.2 `src/auth/` et `src/api/`

| Fichier | Rôle |
|---|---|
| `auth/AuthContext.jsx` | État de connexion React (utilisateur courant, `login`/`logout`), reprise de session au démarrage. |
| `auth/ProtectedRoute.jsx` | Redirige vers `/login` si non connecté, vers le tableau de bord du rôle si la page ne lui est pas ouverte (confort d'affichage — le vrai contrôle est côté API). |
| `auth/roles.js` | Libellés des rôles, table rôle → page, table page → rôles autorisés. |
| `api/client.js` | Client HTTP : jetons JWT (`localStorage`), renouvellement automatique sur 401, téléchargement de fichier authentifié. |
| `api/useChargement.js` | Hook commun : charge une liste, l'actualise automatiquement à intervalle régulier. |
| `api/useActions.js` 🔴 | Hook commun : exécute une action (bouton/formulaire), affiche confirmation/erreur, recharge ensuite. |

### 3.3 `src/lib/` — règles partagées avec le serveur et données de référence

| Fichier | Rôle |
|---|---|
| `format.js` | Formatage de dates/montants/téléphones à l'affichage. |
| `format.test.js` 🔴 | Tests unitaires de `format.js`. |
| `ponctualite.js` | **Même règle que le serveur** (`dashboard/ponctualite.py`) pour qu'affichage web et calcul serveur ne divergent jamais. |
| `ponctualite.test.js` 🔴 | Tests unitaires, rejoués contre les cas de `ponctualite.cas.json`. |
| `ponctualite.cas.json` 🔴 | Fichier de cas **partagé** (source unique de vérité pour les deux tests, web et serveur). |
| `finance.js` 🔴 | Libellés/catégories des dépenses, budgets carburant, factures. |
| `finance.test.js` 🔴 | Tests unitaires de `finance.js`. |
| `rh.js` 🔴 | Libellés et tons des statuts RH/juridiques (congés, litiges) tels que nommés par le serveur. |

### 3.4 `src/components/` — briques réutilisables et blocs métier

| Fichier | Rôle |
|---|---|
| `Layout.jsx` | Ossature commune de toutes les pages (en-tête, nom du rôle, déconnexion). |
| `Alert.jsx` | Bandeau de confirmation/erreur après une action. |
| `Badge.jsx` | Étiquette colorée (statut). |
| `Barres.jsx` | Barres de progression/comparaison (jauges de tableaux de bord). |
| `Jauge.jsx` | Jauge de remplissage d'un départ. |
| `Kpi.jsx` | Tuile chiffre-clé d'un tableau de bord. |
| `Onglets.jsx` | Onglets génériques pour une page dense. |
| `PlanificationDepart.jsx` | Écran de planification : véhicules/chauffeurs réellement libres, création départ + feuille de route. |
| `ReaffectationDepart.jsx` 🔴 | Réaffecter le véhicule ou le chauffeur d'un départ planifié. |
| `TuilesGares.jsx` | Tuiles par gare du tableau de bord direction. |
| `SanteGare.jsx` 🔴 | Bloc « santé de la gare » (ponctualité, remplissage, incidents, équipe). |
| `EquipeGare.jsx` 🔴 | Composition de l'équipe locale (guichetiers, bagagistes) par le chef de gare. |
| `MessagesGare.jsx` 🔴 | Message direct du chef de gare à son équipe / aux chauffeurs en approche. |
| `TensionGares.jsx` 🔴 | « Gares en tension » : départs à venir vs véhicules disponibles rattachés. |
| `DemandeLigne.jsx` 🔴 / `DemandesLigne.jsx` 🔴 | Demander une fermeture/réouverture de ligne / lister les demandes en cours. |
| `LignesFermeture.jsx` 🔴 | Décision (directeur exploitation/PDG) sur les demandes de fermeture de ligne. |
| `CarteReseau.jsx` 🔴 | Carte SVG du réseau, positions GPS des cars en route. |
| `SuiviTrajet.jsx` 🔴 | Suivi GPS du trajet en cours, alerte fatigue, relais suggérés. |
| `ControleBillets.jsx` 🔴 | Ouvrir un contrôle, vérifier des billets, clôturer avec rapport. |
| `CarnetDeRoute.jsx` 🔴 | Carnet de route et documents du véhicule (chauffeur). |
| `ChecklistReprise.jsx` 🔴 | Constat d'état du véhicule par le conducteur relais. |
| `AlertesCloche.jsx` 🔴 | Cloche d'alertes commune à toutes les pages (lecture individuelle). |
| `GamificationBandeau.jsx` 🔴 | Bandeau points/niveau/missions du jour, son coupable en `localStorage` (préférence par appareil). |
| `VehiculesAtelier.jsx` 🔴 | Véhicules actuellement à l'atelier (vu du chef de ligne / directeur exploitation). |
| `FileReparations.jsx` 🔴 | File des réparations réordonnable par urgence. |
| `DemandePieceAtelier.jsx` 🔴 / `DemandesPiecesMagasin.jsx` 🔴 | Demander une pièce (atelier) / servir les demandes (magasinier). |
| `SuggestionsCommande.jsx` 🔴 | Réapprovisionnement suggéré selon la consommation. |
| `PlansEntretien.jsx` 🔴 | Plans d'entretien préventif (échéances jours/km). |
| `FicheVehicule.jsx` 🔴 | Historique d'un véhicule (pannes récurrentes, pièces montées). |
| `BesoinRenouvellement.jsx` 🔴 | Rapport de renouvellement de flotte pour la Direction Générale. |
| `FicheAgent.jsx` 🔴 | Dossier agent (statut, poste, embauche, notes). |
| `CongesDrh.jsx` 🔴 / `MesConges.jsx` 🔴 | Gestion des congés (DRH) / mes propres congés (agent). |
| `FormationsObligatoires.jsx` 🔴 / `MesFormations.jsx` 🔴 | Suivi des formations obligatoires (DRH/QHSE) / les miennes (agent). |
| `FichesDePoste.jsx` 🔴 / `OffresRecrutement.jsx` 🔴 | Fiches de poste par rôle / offres de recrutement (DRH). |
| `MediationDrh.jsx` 🔴 / `MaMediation.jsx` 🔴 | Traiter les doléances (DRH) / déposer/suivre la mienne (agent). |
| `LitigesSociaux.jsx` 🔴 | Doléances ayant atteint le seuil de litige (juridique/DRH/PDG). |
| `SyntheseRh.jsx` 🔴 | Chiffres consolidés de la gestion RH (pour la Direction Générale). |
| `DossierSinistre.jsx` 🔴 / `PiecesSinistre.jsx` 🔴 | Sinistre lié à un incident, avec ses pièces jointes. |
| `TableauConformite.jsx` 🔴 | Tableau de conformité réglementaire (QHSE + juridique). |
| `ModelesJuridiquesGestion.jsx` 🔴 / `BibliothequeModeles.jsx` 🔴 | Tenir la bibliothèque de modèles juridiques (juridique) / la consulter (tous pôles). |
| `ReportingJuridique.jsx` 🔴 | Reporting juridique remonté à la Direction Générale. |
| `DepensesFinance.jsx` 🔴 / `SuiviBudgetCarburant.jsx` 🔴 / `BudgetsCarburant.jsx` 🔴 | Saisie des dépenses / suivi et alerte de dépassement du budget carburant. |
| `FacturesFournisseurs.jsx` 🔴 / `EcheancierFactures.jsx` 🔴 | Fournisseurs/factures et leur échéancier de paiement. |
| `Rentabilite.jsx` 🔴 / `Tresorerie.jsx` 🔴 | Rentabilité par ligne/gare / trésorerie en temps réel. |
| `SoldeInitial.jsx` 🔴 | Solde d'ouverture de la comptabilité finance. |
| `CaissesDuJour.jsx` 🔴 | Clôtures de caisse du jour (chef de gare). |

### 3.5 `src/pages/` — un écran par rôle ou par fonction transverse

| Fichier | Rôle |
|---|---|
| `LoginPage.jsx` | Connexion. |
| `GenericDashboard.jsx` | Page de repli pour un rôle sans tableau de bord dédié. |
| `DirectionDashboard.jsx` | PDG : santé de l'entreprise, alertes, pilotage. |
| `PilotagePage.jsx` 🔴 | Pouvoirs directs du PDG : geler une ligne, réaffecter, suspendre un compte, investissements. |
| `ExploitationDashboard.jsx` | Directeur des opérations : vue temps réel gares/lignes, tension, fermetures. |
| `ChefGareDashboard.jsx` | Chef de gare : santé de la gare, équipe locale, messages. |
| `ChefLigneDashboard.jsx` | Chef de ligne : santé de la ligne, planification, réaffectation. |
| `GuichetierDashboard.jsx` | Vente de ticket, jauge, clôture de caisse. |
| `BagagisteDashboard.jsx` | Colis : enregistrement, chargement, plan, retrait. |
| `ChauffeurDashboard.jsx` | Feuille de route, checklist, incident, suivi GPS/fatigue, relais. |
| `ControleurDashboard.jsx` | Contrôle à bord, historique par ligne/chauffeur. |
| `TechniqueDashboard.jsx` | Directeur technique : flotte, file de réparations, plans d'entretien, renouvellement. |
| `MagasinierDashboard.jsx` | Stock, alertes de rupture, suggestions de commande. |
| `ChefAtelierDashboard.jsx` | Ordres de réparation, fiche véhicule, répartition de charge. |
| `MecanicienDashboard.jsx` 🔴 | Ses ordres de réparation, ses sorties de pièces, ses demandes. |
| `RhDashboard.jsx` | Dossiers agents, gamification par agent. |
| `EspacePage.jsx` 🔴 | Espace personnel de tout agent : mes congés, mes formations, ma médiation. |
| `FinanceDashboard.jsx` | Consolidation des recettes en temps réel. |
| `ComptabilitePage.jsx` 🔴 | Dépenses, budget carburant, factures fournisseurs, rentabilité. |
| `FinancesPage.jsx` 🔴 | Trésorerie et export de reporting financier. |
| `JuridiqueDashboard.jsx` | Registre des assurances, sinistres, conformité. |
| `ModelesPage.jsx` 🔴 | Bibliothèque de modèles juridiques (ouverte à tous les pôles). |
| `SynthesePage.jsx` 🔴 | Reporting juridique + synthèse RH pour la Direction Générale. |
| `QhseDashboard.jsx` | Checklist sécurité, incidents, blocages, conformité réglementaire. |
| `SecretariatPage.jsx` 🔴 | Agenda, notes de service, archives (secrétaire général). |
| `NotesPage.jsx` 🔴 | Notes de service reçues par le poste connecté. |
| `CadrePage.jsx` 🔴 | Cadre de configuration hiérarchique de la compagnie (automatisation, gamification). |
| `ConfigurationPage.jsx` 🔴 | Configuration du poste/agent, dans le cadre fixé par la compagnie. |
| `InvestissementsPage.jsx` 🔴 | Demandes et décisions d'investissement. |
| `AuditPage.jsx` | Journal d'audit filtrable et paginé. |
| `PlateformeDashboard.jsx` | Vue superadmin toutes compagnies confondues. |

### 3.6 `frontend/e2e/` — essais de bout en bout

| Fichier | Rôle |
|---|---|
| `run.mjs` 🔴 | Lance les scénarios dans Chrome (Playwright) contre une base jetable. |
| `scenarios.mjs` 🔴 | Les 10 scénarios rejoués (vente, incident, atelier, PDG, colis, jeu, configuration, caisse, GPS, contrôle). |
| `lib.mjs` 🔴 | Fonctions communes aux scénarios (connexion, attente, capture). |
| `comptes.json` 🔴 | Comptes de démonstration utilisés par les essais. |

## 4. Application mobile (`mobile/`)

### 4.1 Configuration et racine

| Fichier | Rôle |
|---|---|
| `pubspec.yaml` | Dépendances Flutter (`http`, `flutter_secure_storage`, `hive_ce`, `speech_to_text`, `flutter_tts`, `connectivity_plus`). |
| `analysis_options.yaml` | Règles d'analyse statique (`flutter analyze`). |
| `.metadata` | Métadonnées du projet Flutter (généré par l'outil). |
| `.gitignore` | Exclut le build, `.dart_tool/`. |
| `README.md` | Installation, architecture, mode hors ligne, commande vocale, limites connues. |
| `TEST_TELEPHONES.md` | Protocole d'essai sur téléphones réels (jamais exécuté dans cet environnement). |
| `android/app/build.gradle.kts` | Signature release : refuse de compiler sans `key.properties` (sauf dérogation explicite). |
| `android/key.properties` (non commité, volontairement) | Chemin/mots de passe du keystore de signature — hors du dépôt. |
| `android/app/src/main/AndroidManifest.xml` | Permissions `INTERNET`, `RECORD_AUDIO` (commande vocale), déclaration du service de reconnaissance vocale. |

### 4.2 `lib/` — cœur de l'application

| Fichier | Rôle |
|---|---|
| `main.dart` | Point d'entrée : assemble les services puis lance `app.dart`. |
| `app.dart` | Racine du widget tree, fournit les services (Provider) aux écrans. |
| `config.dart` | Adresse de l'API ; **exige HTTPS en version release**. |
| `services.dart` | Assemble toutes les briques (client API, auth, stockage, sync) en une seule instance. |
| `api/api_client.dart` | Client HTTP : jeton JWT, renouvellement sur 401, HTTPS obligatoire en release. |
| `api/api_exception.dart` | Exception typée pour une réponse d'erreur du serveur. |
| `auth/app_user.dart` | Modèle de l'utilisateur connecté (réponse de `/auth/me/`). |
| `auth/auth_controller.dart` | Connexion, reprise de session, déconnexion. |
| `auth/roles.dart` | Constantes des rôles de l'API et leurs libellés. |
| `auth/token_storage.dart` | Jetons JWT dans le coffre sécurisé du système (`flutter_secure_storage`). |
| `storage/local_store.dart` | Base locale chiffrée (Hive) : point d'accès du stockage sur l'appareil. |
| `storage/encryption_key.dart` | Génère/retrouve la clé AES-256 dans le coffre sécurisé (Keystore/Keychain). |
| `storage/string_box.dart` | Petite abstraction clé → valeur au-dessus de Hive (testable sans vrai Hive). |
| `storage/cache_store.dart` | Cache de lecture (dernières données vues), avec provenance et horodatage. |
| `storage/outbox.dart` | File d'attente des actions non envoyées (écriture hors ligne). |
| `sync/pending_action.dart` | Une action en attente (type, charge utile, statut, identifiant d'idempotence). |
| `sync/action_handlers.dart` | Associe un type d'action à son appel API réel. |
| `sync/sync_service.dart` | Envoie la file dans l'ordre, gère accepté/en attente/refusé. |
| `sync/sync_triggers.dart` | Déclenche une synchronisation (retour réseau, retour au premier plan, toutes les 60 s). |
| `sync/connectivity_monitor.dart` | Surveille la présence d'une connexion réseau. |
| `data/loaded.dart` | Enveloppe générique : donnée + provenance (serveur/cache) + date. |
| `data/depart_repository.dart` / `feuille_repository.dart` | Lecture des départs / feuilles de route (réseau ou cache hors ligne). |
| `data/quota_service.dart` | Places garanties hors ligne du guichetier (`reserver-hors-ligne`). |
| `ui/login_screen.dart` | Écran de connexion (affiche l'adresse du serveur en debug). |
| `ui/home_screen.dart` | Aiguille vers l'écran d'accueil du rôle connecté. |
| `ui/guichetier_home.dart` / `vente_ticket_screen.dart` | Accueil guichetier / écran de vente (avec dictée vocale). |
| `ui/chauffeur_home.dart` / `checklist_depart_screen.dart` | Accueil chauffeur / checklist avant-départ (avec dictée vocale). |
| `ui/generic_home.dart` | Écran d'attente pour un rôle sans action mobile dédiée. |
| `ui/user_header.dart` | En-tête (nom, rôle) commun aux écrans. |
| `ui/sync_status_bar.dart` | Bandeau « hors ligne : n action(s) en attente » / « tout est synchronisé ». |
| `ui/pending_actions_screen.dart` | Liste des actions en attente ou refusées. |
| `ui/config_error_app.dart` | Écran « Application mal configurée » (adresse API absente/HTTP en release). |
| `ui/voice_dictation_panel.dart` | Panneau de dictée vocale réutilisable (question, écoute, récapitulatif). |
| `ui/formatters.dart` | Formatage heure/date à l'affichage mobile. |
| `voice/speech_services.dart` | Reconnaissance/synthèse vocale du téléphone (`speech_to_text`, `flutter_tts`), jamais un service cloud. |
| `voice/voice_form_session.dart` | Parcours vocal générique : une question à la fois, récapitulatif, confirmation. |
| `voice/voice_text.dart` | Compréhension du texte reconnu (fonctions pures : paiement, état, nombre, confirmation). |

### 4.3 `test/` et `tool/`

| Fichier | Rôle |
|---|---|
| `api_client_test.dart`, `config_test.dart`, `auth_controller_test.dart` | Client API, configuration, authentification. |
| `encryption_test.dart` | Chiffrement de la base locale. |
| `outbox_test.dart`, `sync_service_test.dart`, `sync_hooks_test.dart` | File d'attente et synchronisation. |
| `quota_service_test.dart`, `offline_guarantee_test.dart` | Places garanties hors ligne. |
| `voice_text_test.dart`, `voice_form_session_test.dart`, `voice_ui_test.dart` | Compréhension du texte dicté, parcours vocal (faux moteur), écrans avec commande vocale. |
| `app_flow_test.dart` | Parcours d'écran de bout en bout (faux serveur). |
| `support/harness.dart`, `support/app_helpers.dart` | Utilitaires communs aux tests d'écran. |
| `tool/e2e_smoke_test.dart` | Essai de bout en bout contre un **vrai** backend (crée de vrais tickets — jamais en production). |
