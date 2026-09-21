# Transport Coord

Logiciel web de coordination du personnel pour une compagnie de transport routier
(type UTB, AVS, GTI) en Côte d'Ivoire.

**Stack** : Django + Django REST Framework + PostgreSQL, tests avec pytest-django.

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
   pip install -r requirements.txt
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

   Le serveur est accessible sur http://127.0.0.1:8000/

## Tests

Les tests utilisent `pytest-django` :

```bash
pytest
```

## Notifications SMS et WhatsApp

Le client final n'a pas accès au logiciel : à la vente d'un ticket, une confirmation
est envoyée au passager par SMS et par WhatsApp. Chaque tentative est tracée dans
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

```
transpt1/
├── transport_coord/       # Configuration du projet Django (settings, urls, wsgi/asgi)
├── core/                   # Utilisateurs, rôles, compagnies (multi-tenant), auth JWT
├── reseau/                 # Gares, lignes, véhicules
├── manage.py
├── requirements.txt
├── .env.example
├── .env                    # non versionné
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

Crée deux compagnies et des utilisateurs (un par rôle : les 17 rôles du cahier des
charges et un superadmin) avec le mot de passe `Demo!2024`, des gares/lignes/véhicules
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

## Endpoints d'authentification

- `POST /api/auth/login/` — obtenir un couple de tokens JWT (`access`/`refresh`)
- `POST /api/auth/refresh/` — renouveler un token `access`
- `GET /api/auth/me/` — infos de l'utilisateur connecté (rôle, compagnie)

## Endpoints réseau

CRUD complet, isolé par compagnie (`IsSameCompany`) :

- `/api/gares/` — un chef de gare (`role=chef_gare`) ne peut modifier/supprimer que
  la gare dont il est `chef`, pas les autres gares de sa compagnie
- `/api/lignes/` — `gare_depart`/`gare_arrivee` doivent appartenir à la même compagnie
- `/api/vehicules/`

## Pilote

- `../SCENARIO_PILOTE.md` : scénario de test de bout en bout (guichetier, chauffeur, incident, atelier, PDG), à jouer
  à la main dans le navigateur ; rejouable par l'API avec `pytest role_coverage_tests/test_scenario_pilote.py`.
- `DEPLOIEMENT.md` : checklist de déploiement (variables d'environnement, migrations, premier lancement, proxy,
  sauvegardes, notifications) et limites connues avant le pilote.
- `PERMISSIONS.md` : qui peut voir et faire quoi, par rôle (fait foi).
