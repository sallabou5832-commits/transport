# Transport Coord

Serveur (API) du logiciel de coordination gamifié pour compagnie de transport routier
(type UTB, AVS, GTI) en Côte d'Ivoire : il sert le site web (`../frontend`) et l'application mobile (`../mobile`).
Cahier des charges : `../cahier.txt` ; état d'avancement : `../AUDIT_AVANCEMENT_2026-11-02.md`.

**Stack** : Django 6.1 + Django REST Framework + PostgreSQL, jetons JWT, Channels et Daphne pour la carte du réseau en
temps réel (WebSocket), tests avec pytest-django.

## Prérequis

- Python 3.12+ (exigé par Django 6.1)
- PostgreSQL 14+ installé et démarré
- pip

## Installation locale

1. **Cloner le dépôt et se placer dans le dossier du projet**

   ```bash
   git clone <url-du-depot>
   cd transpt1
   ```

2. **Créer et activer un environnement virtuel**

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```

3. **Installer les dépendances**

   ```bash
   pip install -r requirements.txt       # exécution
   pip install -r requirements-dev.txt   # en plus, pour lancer les tests et l'audit des dépendances
   ```

4. **Configurer les variables d'environnement**

   Copier `.env.example` en `.env` puis renseigner vos propres valeurs
   (clé secrète Django, identifiants PostgreSQL, etc.) :

   ```bash
   cp .env.example .env
   ```

5. **Créer la base de données PostgreSQL**

   ```sql
   CREATE USER transport_coord_user WITH PASSWORD 'votre_mot_de_passe';
   CREATE DATABASE transport_coord OWNER transport_coord_user;
   ```

   (Adapter les noms/valeurs à ceux définis dans votre `.env`. Le rôle doit être
   propriétaire de la base pour pouvoir créer des tables via les migrations
   Django — sur PostgreSQL 15+, un simple `GRANT ALL PRIVILEGES` ne suffit pas
   car le schéma `public` reste restreint au propriétaire.)

6. **Appliquer les migrations**

   ```bash
   python manage.py migrate
   ```

7. **Créer un superutilisateur (optionnel)**

   ```bash
   python manage.py createsuperuser
   ```

8. **Lancer le serveur de développement**

   ```bash
   python manage.py runserver
   ```

   Le serveur est accessible sur http://127.0.0.1:8000/ (HTTP et WebSocket de la carte, servis par Daphne).

## Tests

Les tests utilisent `pytest-django` (dépendances : `requirements-dev.txt`) ; la base de test est créée puis supprimée
par pytest.

```bash
pytest                                   # toute la suite (≈ 15 à 40 min selon la charge de la machine)
pytest billetterie                       # une app
pytest role_coverage_tests               # matrice rôle × endpoint, contrat pages web ↔ API
```

- Dernier relevé (2 novembre 2026) : **4 725 réussis, 1 ignoré, 0 échec**, hors `dashboard/tests/test_carte_consumer.py`.
- `dashboard/tests/test_carte_consumer.py` (WebSocket de la carte) passe seul (14 tests, ≈ 50 s) mais peut se bloquer quand
  la machine est chargée : le lancer à part (`--ignore=dashboard/tests/test_carte_consumer.py` pour le reste).
- Deux `pytest` en même temps se disputent la base de test : lancer le second avec un autre nom de base
  (`DB_NAME=transport_coord_autre pytest …`, base de test distincte créée et supprimée par pytest).

## Tâches planifiées

Sans elles, les alertes automatiques, l'entretien préventif, la clôture automatique des caisses et l'évaluation du jeu ne
se déclenchent pas. Toutes sont rejouables sans doublon ; fréquences et exemple `crontab` : `DEPLOIEMENT.md` §10.

| Commande | Fréquence conseillée |
|---|---|
| `generer_alertes` | toutes les 5 à 10 minutes |
| `cloturer_caisses` | chaque soir |
| `evaluer_gamification`, `purger_positions_gps`, `sauvegarde_base` | chaque nuit |
| `generer_flux_tutelle` | chaque jour (rattrapage des flux vers la tutelle) |
| `verifier_sauvegarde` | chaque semaine (restauration réelle) |

## Notifications SMS et WhatsApp

Le client final n'a pas accès au logiciel : à la vente d'un ticket, une confirmation
est envoyée au passager par SMS et par WhatsApp ; l'expéditeur et le destinataire d'un colis sont prévenus à chaque
étape (le code de retrait part à l'enregistrement). Chaque tentative est tracée dans
`NotificationLog` (destinataire, canal, contenu, fournisseur, statut, référence, erreur, date).

- **Mode simulation (défaut)** : `NOTIFICATIONS_SIMULATION_MODE=True` n'appelle aucun
  fournisseur, écrit seulement dans les logs et dans `NotificationLog` (statut `simulé`).
  Ne le passer à `False` qu'en production, avec les identifiants du fournisseur.
- **Canaux** : `NOTIFICATIONS_CANAUX_TICKET=sms,whatsapp` (défaut). Les canaux sont
  indépendants : l'échec de l'un n'empêche pas l'autre ni la vente.
- **SMS** : Orange SMS API (Côte d'Ivoire) et Twilio (international).
  `NOTIFICATIONS_SMS_PROVIDER=auto` envoie les numéros `+225` par Orange (s'il est
  configuré) et tous les autres par Twilio ; `orange` ou `twilio` force un fournisseur.
- **WhatsApp** : via Twilio (`TWILIO_WHATSAPP_FROM`). WhatsApp n'autorise un message
  libre que dans les 24 h suivant un message du client (ou dans le bac à sable Twilio,
  après opt-in). Pour écrire à un client qui ne nous a pas contactés, il faut un
  **modèle de message approuvé** : créez-le dans Twilio (variables `{{1}}` nom,
  `{{2}}` ligne, `{{3}}` date et heure, `{{4}}` prix) et renseignez
  `TWILIO_WHATSAPP_CONTENT_SID`.
- **Identifiants** : uniquement par variables d'environnement (voir `.env.example`),
  jamais dans le code.
- Un échec d'envoi n'annule jamais la vente : il est tracé avec le statut `échec`.

## Formation par poste

Chaque poste dispose d'un parcours de formation « jeu » **entièrement simulé** : les actions
(vendre un ticket, faire la checklist avant-départ, traiter une demande de pièce...) ne créent
jamais de vraies données. Voir `PERMISSIONS.md` §7 pour les garanties d'isolation.

```bash
python manage.py seed_formation          # crée les parcours de base (guichetier, chauffeur principal, magasinier)
python manage.py seed_formation --force  # réécrit leur contenu (écrase les modifications faites dans l'admin)
```

- `GET  /api/formation/mon-parcours/` : le parcours du rôle de l'utilisateur, avec sa progression
- `POST /api/formation/mon-parcours/demarrer/` : démarre (ou reprend) le parcours
- `POST /api/formation/mon-parcours/etapes/{id}/terminer/` : termine l'étape courante (dans l'ordre)

Le contenu des parcours (étapes, consignes, données fictives) s'édite dans l'admin Django.

## Structure du projet

20 applications Django, chacune avec ses `models.py` / `permissions.py` / `serializers.py` / `views.py` / `urls.py` /
`tests/` :

```
transpt1/
├── transport_coord/    # Configuration du projet (settings, urls racine, wsgi/asgi)
├── core/               # Utilisateurs, rôles, compagnies (multi-tenant), auth JWT, sauvegardes, suspension de compte,
│                       # lecture sûre des entrées (entiers, textes, dates), analyseur JSON, gestionnaire d'erreurs, pagination
├── audit/              # Journal d'audit (créations/modifications/suppressions, connexions), limitation des connexions
├── reseau/             # Gares, lignes, véhicules, gare d'attache, fermeture/réouverture de ligne
├── billetterie/        # Départs, tickets (tarif imposé, verrouillage, annulation), ventes hors ligne, clôture de caisse
├── personnel_roulant/  # Feuilles de route, checklists, incidents, positions GPS, fatigue, relais, contrôle à bord
├── maintenance/        # Pièces, stock, ordres de réparation, plans d'entretien préventif, fiche véhicule
├── colis/               # Enregistrement, chargement et retrait des colis/bagages (code de retrait haché)
├── supports/           # Dossiers agents, assurances, sinistres et pièces jointes, modèles juridiques, conformité,
│                       # reporting juridique, synthèse financière des recettes
├── rh/                  # Congés, formations obligatoires, contrats, évaluations, recrutement, médiation sociale
├── finance/             # Dépenses, budget carburant, fournisseurs/factures, rentabilité, trésorerie, export CSV
├── investissements/    # Demandes et décisions d'investissement (achat de cars, ouverture de ligne)
├── configuration/      # Configuration hiérarchique compagnie → poste → agent (automatisation, gamification), règlement intérieur
├── gamification/       # Points, niveaux, badges, missions, classements par poste
├── alertes/             # Alertes inter-pôles, génération automatique, blocages de sécurité QHSE
├── communication/      # Notes de service, agenda de direction, messages directs, archives
├── notifications/      # Envoi SMS/WhatsApp (Orange, Twilio), journal des notifications
├── formation/           # Parcours de formation simulés par poste
├── tutelle/             # Échange de données avec le Ministère des Transports / OSER / AMUGA / OFT (clé d'API)
├── lien_billetterie/    # Mode de billetterie, ventes du logiciel de la compagnie par API (clé) ou fichier (voir LIEN_BILLETTERIE.md)
├── dashboard/           # Tableaux de bord (direction, exploitation, gare, carte du réseau)
├── role_coverage_tests/ # Matrice de conformité rôle × endpoint, contrat pages web ↔ API
├── manage.py
├── requirements.txt
├── .env.example
├── .env                 # non versionné
└── README.md
```

## Utilisateurs de démonstration

Ces commandes créent des comptes au **mot de passe public** (dont un superadmin) : elles ne tournent que si
`DJANGO_DEBUG=True` et sont refusées en production.

```bash
python manage.py seed_demo_users
python manage.py seed_demo_reseau        # nécessite seed_demo_users au préalable
python manage.py seed_demo_operations    # nécessite seed_demo_users + seed_demo_reseau
python manage.py seed_demo_tableaux      # données réalistes pour les tableaux de bord ; nécessite les trois précédentes
```

Crée deux compagnies et des utilisateurs (un par rôle : les 18 rôles du cahier des
charges, mécanicien compris, et un superadmin) avec le mot de passe `Demo!2024`, des gares/lignes/véhicules
de démonstration, puis un départ, un ticket, une feuille de route, des pièces et un
ordre de réparation, et enfin des données réalistes pour les tableaux de bord (départs
du jour à l'heure ou en retard, six jours d'historique, incidents, assurances,
sinistres, dossiers RH) — utiles pour tester manuellement l'API et le frontend (voir
`core/management/commands/seed_demo_users.py`,
`reseau/management/commands/seed_demo_reseau.py`,
`billetterie/management/commands/seed_demo_operations.py` et
`dashboard/management/commands/seed_demo_tableaux.py`). `seed_demo_tableaux` est sans
effet s'il a déjà été lancé.

## Frontend

Une interface web (React + Vite) consommant cette API se trouve dans `../frontend`.
Voir `frontend/README.md` pour l'installation et les comptes de démonstration.

## Application mobile

Une application Flutter (hors ligne d'abord, commande vocale) consommant la même API se trouve dans `../mobile`.
Voir `mobile/README.md` pour l'installation, les comptes de démonstration et le protocole d'essai sur téléphone
(`mobile/TEST_TELEPHONES.md`).

## Endpoints d'authentification

- `POST /api/auth/login/` — obtenir un couple de tokens JWT (`access`/`refresh`), tentative tracée dans le journal d'audit
- `POST /api/auth/refresh/` — renouveler un token `access`
- `GET /api/auth/me/` — infos de l'utilisateur connecté (rôle, compagnie)

## Endpoints réseau

CRUD complet, isolé par compagnie (`IsSameCompany`) :

- `/api/gares/` — un chef de gare (`role=chef_gare`) ne peut modifier/supprimer que
  la gare dont il est `chef`, pas les autres gares de sa compagnie
- `/api/lignes/` — `gare_depart`/`gare_arrivee` doivent appartenir à la même compagnie
- `/api/vehicules/`

## Entrées invalides et erreurs

Une valeur fantaisiste envoyée à l'API (identifiant illisible, date impossible, corps qui n'est pas un objet, nombre
démesuré, caractère nul) donne une erreur **400** claire, une suppression d'un élément encore utilisé donne une **409** :
jamais une erreur serveur (500). Les garde-fous sont centralisés dans `core/` ; une nouvelle vue les réutilise au lieu de
refaire ses propres conversions :

| Besoin | À utiliser | À éviter |
|---|---|---|
| Identifiant venu de l'URL ou du JSON | `core.entiers.lire_entier` (renvoie `None` si invalide) | `x.isdigit()` puis `int(x)` (« ² » passe le premier test, pas le second) |
| Date ou date-heure | `core.dates.lire_date` / `lire_date_heure` (`None` si invalide, y compris un nombre ou une liste) | `parse_date` appelé directement (lève sur `2030-13-45`) |
| Texte d'un corps de requête | `core.textes.lire_texte` / `champ_du_corps` (retire espaces et caractères nuls) | `(valeur or "").strip()` (plante sur un nombre ou une liste) |
| Corps JSON | `core.parsers.AnalyseurJSON` (réglage global) : un corps qui n'est pas un objet est refusé en 400 ; une vue qui accepte une liste le déclare par `corps_json_liste = True` (positions GPS par lot) | `request.data.get(...)` sans filet dans une vue qui n'est pas passée par l'analyseur |
| Suppression d'un élément référencé | `core.exceptions.gestionnaire_exceptions` (réglage global) : `ProtectedError` → 409 ; nombre démesuré et caractère nul → 400 | `try/except` à refaire dans chaque vue |

Les tests de ces garde-fous sont dans `core/tests/test_entrees_hostiles.py` et `core/tests/test_dates_invalides.py`.

## Pagination facultative

Sans paramètre, une liste est renvoyée entière, comme toujours. Avec `?limit=50` (et `?offset=`), la réponse devient
`{count, next, previous, results}` (`core/pagination.py`, maximum 500 par page). Le journal d'audit garde sa propre
pagination, obligatoire.

## Journal d'audit, tickets verrouillés, sauvegardes

- **Journal d'audit** (`audit/`, `GET /api/audit/`) : qui a fait quoi, quand, d'où, avec « avant → après » ; connexions
  réussies et échecs comprises ; ajout seulement (aucune entrée ne se modifie ni ne se supprime, même depuis
  l'administration). Son écriture est isolée par un savepoint : une erreur du journal n'annule pas l'action métier ni
  les requêtes qui suivent. Voir `PERMISSIONS.md` §8.
- **Tickets** : un ticket vendu ne se modifie ni ne se supprime ; une erreur se corrige par
  `POST /api/tickets/<id>/annuler/` avec un motif (chef de gare, chef de ligne, direction).
- **Planification** : `GET /api/departs/disponibilites/?date_heure=…` (véhicules et chauffeurs libres) puis
  `POST /api/departs/planifier/` (départ + feuille de route d'un coup).
- **Sauvegardes** : `python manage.py sauvegarde_base` (à planifier chaque nuit), `verifier_sauvegarde` (restauration réelle
  dans une base temporaire, chaque semaine), `etat_sauvegarde` (code de sortie 1 si échec ou trop ancienne : à brancher sur la
  supervision). Réglages `BACKUP_*` dans `.env.example`, modèles de planification dans `deploy/`, procédure complète dans
  `DEPLOIEMENT.md` §3.

## Pilote

- `../SCENARIO_PILOTE.md` : scénario de test de bout en bout (guichetier, chauffeur, incident, atelier, PDG, puis annulation,
  planification et journal d'audit), à jouer à la main dans le navigateur ; le parcours nominal est rejouable par l'API avec
  `pytest role_coverage_tests/test_scenario_pilote.py`.
- `DEPLOIEMENT.md` : checklist de déploiement (variables d'environnement, migrations, premier lancement, proxy,
  sauvegardes, notifications) et limites connues avant le pilote.
- `PERMISSIONS.md` : qui peut voir et faire quoi, par rôle (fait foi).

## Règlement intérieur et lien billetterie

- **Règlement intérieur** (`GET/PATCH /api/configuration/reglement/`) : ce qu'une compagnie permet ou non à certains postes
  (corriger une sortie de pièce, supprimer sa feuille de route…). Chaque règle a pour défaut le comportement actuel ; le PDG
  règle tout, chaque directeur de pôle les siennes. Liste des règles : `configuration/regles.py` ; droits : `PERMISSIONS.md`.
- **Lien billetterie** (`/api/lien-billetterie/…`) : garder le logiciel de billetterie de la compagnie (mode `externe` ou
  `mixte`) et en recevoir les ventes par API (clé par compagnie) ou par import CSV/Excel. Guide pour l'éditeur du logiciel :
  `LIEN_BILLETTERIE.md`.
- Les deux s'utilisent par l'API seulement : leurs écrans ne sont pas encore faits.

## Analyses du projet

- `../AUDIT_AVANCEMENT_2026-11-02.md` : état d'avancement le plus récent (**2 novembre**) — 99 fonctionnalités du cahier
  (77 complètes, 19 partielles, 3 absentes), vérifications relancées (serveur, site, mobile), risques et reste à construire.
- `../RAPPORT_ANOMALIES_2026-10-31.md` : revue complète du dépôt du **31 octobre** (81 constats classés par gravité, avec
  la preuve de chacun) et plan de correction par lots ; les statuts y sont mis à jour au fil des corrections.
- `../ANALYSE_PROJET.md` : analyse fonctionnelle, sécurité, performance et qualité complète, état du **21 septembre**
  avant le chantier de mise en conformité (chiffres de conformité obsolètes, garder pour le détail méthode/risques).
- `../RAPPORT_CONFORMITE.md` : les 99 fonctionnalités du cahier des charges, une par une, avec la preuve de chacune ;
  ses totaux (62 complètes, 20 partielles, 17 absentes) datent d'avant les modules finance, RH et juridique — les
  reclassements sont au §4.2 de l'audit du 2 novembre.
- `../AUDIT_SECURITE_FONCTIONNEL_2026-09-24.md` : audit sécurité **app par app** du 24 septembre (le plus récent),
  couvrant aussi ce qui n'existait pas encore le 21 septembre (`tutelle`, la commande vocale mobile, les sauvegardes
  automatisées) — référence à jour pour la sécurité.
