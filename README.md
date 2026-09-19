# Transport Coord

Logiciel web de coordination du personnel pour une compagnie de transport routier
(type UTB, AVS, GTI) en Côte d'Ivoire.

**Stack** : Django + Django REST Framework + PostgreSQL, tests avec pytest-django.

## Prérequis

- Python 3.11+
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

## Structure du projet

```
transpt1/
├── transport_coord/       # Configuration du projet Django (settings, urls, wsgi/asgi)
├── manage.py
├── requirements.txt
├── .env.example
├── .env                    # non versionné
└── README.md
```

Aucune application métier n'est encore créée à ce stade (étape 0 : socle technique uniquement).
