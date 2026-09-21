# Déploiement du pilote — checklist

Ce guide mène du serveur vide au premier lancement réel. Cochez chaque case dans l'ordre. L'API n'est servie
qu'en **HTTPS** : le TLS est terminé par un *reverse proxy* (Caddy ou nginx) qui relaie en HTTP vers Django.

```
téléphone / navigateur ──HTTPS──▶ proxy (Caddy, nginx) ──HTTP──▶ gunicorn / Django (127.0.0.1:8000) ──▶ PostgreSQL
                                     └── sert aussi le site web (frontend/dist) et /static/ (administration)
```

## 1. Avant de commencer

- [ ] Un serveur avec **Python 3.12 ou plus** (Django 6.1), **PostgreSQL**, et un nom de domaine pointant dessus
      (ports 80 et 443 ouverts). Le port 8000 (Django) et le port PostgreSQL restent **fermés** au public.
- [ ] Le code sur le serveur, un environnement virtuel, puis :
      `pip install -r requirements.txt` et un serveur WSGI : `pip install gunicorn` (Linux) ou `pip install waitress`
      (Windows). Il n'est pas dans `requirements.txt` : ne lancez **jamais** `runserver` en production.
- [ ] Sur la machine de build : Node.js 18+ (site web) et Flutter (application mobile).

## 2. Variables d'environnement

À fournir par l'environnement du service (`EnvironmentFile` de systemd, variables du service Windows…) ou, à défaut,
un fichier `.env` **lisible par le seul compte du service** (`chmod 600`). Ne commitez jamais ce fichier
(`.env` est ignoré par git ; seul `.env.example` est suivi, avec des valeurs fictives).

**Obligatoires** — sans elles, Django ne démarre pas ou refuse toutes les requêtes :

| Variable | Valeur en production |
|---|---|
| `DJANGO_SECRET_KEY` | Valeur aléatoire propre à la production : `python -c "import secrets; print(secrets.token_urlsafe(60))"`. Jamais la valeur de développement. |
| `DJANGO_DEBUG` | `False` : active HTTPS forcé, cookies sécurisés, HSTS. |
| `DJANGO_ALLOWED_HOSTS` | `api.votre-domaine.ci` (vide = toutes les requêtes refusées). |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | La base créée au §3. Mot de passe fort et unique. |
| `CORS_ALLOWED_ORIGINS` | `https://app.votre-domaine.ci` : l'adresse du site web, en https, sans `/` final. |
| `CSRF_TRUSTED_ORIGINS` | `https://api.votre-domaine.ci` : sans cela, l'administration Django refuse les formulaires. |

**Recommandées**

| Variable | Rôle |
|---|---|
| `DJANGO_HSTS_SECONDS` | `2592000` (30 jours) au début ; allonger jusqu'à `31536000` une fois le HTTPS validé. Ne pas mettre 0. |
| `DJANGO_STATIC_ROOT` | Où `collectstatic` rassemble les fichiers de l'administration (défaut : `staticfiles/` du projet). |
| `DJANGO_LOG_LEVEL` | `WARNING` par défaut ; `INFO` pour plus de détails. Les erreurs 500 sont écrites sur la sortie d'erreur. |

**Sauvegardes** — voir §3 : `BACKUP_DIR` (défaut `transpt1/sauvegardes/`, à placer sur un autre disque),
`BACKUP_RETENTION_DAYS` (14), `BACKUP_MIN_KEEP` (3), `BACKUP_MAX_AGE_HOURS` (26), `BACKUP_POST_COMMAND` (envoi hors du serveur),
`SAUVEGARDE_ADMIN_USER` / `SAUVEGARDE_ADMIN_PASSWORD` (rôle `CREATEDB` du test de restauration, dans un fichier à part).

**Métier** (valeurs par défaut sensées) : `BILLETTERIE_QUOTA_HORS_LIGNE` (2 places réservées par guichetier et par
départ ; 0 désactive la vente hors ligne garantie), `BILLETTERIE_RESERVATION_TTL_HEURES` (12),
`BILLETTERIE_HORIZON_HORS_LIGNE_HEURES` (24).

**Notifications aux voyageurs** — voir le §8. `NOTIFICATIONS_SIMULATION_MODE` vaut `True` par défaut : **aucun message
réel n'est envoyé** tant que vous ne le passez pas explicitement à `False`.

## 3. Base de données

- [ ] Créer l'utilisateur et la base (en tant que `postgres`) :
      ```sql
      CREATE USER transport_coord_user WITH PASSWORD '<mot de passe fort>';
      CREATE DATABASE transport_coord OWNER transport_coord_user ENCODING 'UTF8';
      ```
      En production, cet utilisateur n'a pas besoin du droit `CREATEDB` (il ne sert qu'aux tests).

### Sauvegardes automatiques — à installer **avant** d'ouvrir aux utilisateurs

`python manage.py sauvegarde_base` fait une sauvegarde complète (`pg_dump -Fc`) dans `BACKUP_DIR`, **relit l'archive**
(`pg_restore --list`) avant de la garder, écrit son empreinte SHA-256, supprime les sauvegardes de plus de
`BACKUP_RETENTION_DAYS` jours (sans jamais descendre sous `BACKUP_MIN_KEEP` fichiers) et, si `BACKUP_POST_COMMAND` est
renseignée, l'envoie hors du serveur. Les outils `pg_dump` / `pg_restore` doivent être installés (paquet
`postgresql-client`), sinon indiquer leur chemin par `PG_DUMP` / `PG_RESTORE`. Le mot de passe passe par l'environnement
(`PGPASSWORD`), jamais par la ligne de commande.

- [ ] **Planifier la sauvegarde nocturne**
      - Linux : copier `deploy/transport-coord-sauvegarde.service` et `.timer` dans `/etc/systemd/system/`, adapter les
        chemins et l'utilisateur, puis `systemctl daemon-reload && systemctl enable --now transport-coord-sauvegarde.timer`.
        `Persistent=true` rattrape une sauvegarde manquée pendant une extinction ; `systemctl list-timers` montre la prochaine.
      - Windows : `schtasks /Create /TN "Transport Coord - sauvegarde" /SC DAILY /ST 02:30 /RU SYSTEM /TR "powershell
        -NoProfile -ExecutionPolicy Bypass -File C:\transport\transpt1\deploy\sauvegarde-windows.ps1"`.
- [ ] **Copie hors du serveur** (`BACKUP_POST_COMMAND`, ex. `rclone copy` vers un stockage distant, ou `scp`) : la commande
      reçoit le chemin du fichier en dernier argument. Une sauvegarde sur le même disque que la base ne protège pas d'une panne
      de ce disque, d'un vol ou d'un rançongiciel. **Chiffrer avant l'envoi** (les sauvegardes contiennent noms et numéros de
      téléphone des voyageurs) : par exemple `rclone` avec un remote `crypt`, ou `age`/`gpg` dans un petit script.
- [ ] **Surveiller** : `python manage.py etat_sauvegarde` sort en erreur (code 1) si la dernière sauvegarde a échoué ou date
      de plus de `BACKUP_MAX_AGE_HOURS` heures (26 par défaut). À brancher sur votre supervision (Uptime Kuma, cron + mail…) :
      une sauvegarde qui échoue en silence est pire qu'aucune, on ne s'en aperçoit qu'au moment d'en avoir besoin.
- [ ] **Tester la restauration chaque semaine** : `python manage.py verifier_sauvegarde` restaure la dernière sauvegarde dans
      une base temporaire, compare le nombre de tables avec la base vivante, vérifie les migrations, puis supprime la base.
      Il faut un rôle PostgreSQL avec `CREATEDB` (celui de l'application ne l'a pas en production) : créez-en un réservé à
      cet usage et donnez-le par `SAUVEGARDE_ADMIN_USER` / `SAUVEGARDE_ADMIN_PASSWORD` (voir
      `deploy/transport-coord-verif-sauvegarde.service` et son `.timer` hebdomadaire).
- [ ] **Faire une vraie répétition de restauration** une fois avant le pilote, sur une autre machine : installer le code,
      `createdb`, `pg_restore --no-owner -d <base> sauvegarde.dump`, `manage.py check`, se connecter. Noter le temps qu'elle prend.

**Restaurer après un incident** : arrêter le service applicatif ; `pg_restore --clean --if-exists --no-owner -d transport_coord
<fichier>.dump` (ou créer une base neuve, restaurer dedans, puis changer `DB_NAME`) ; `manage.py migrate` (sans effet si le code est
à la même version) ; relancer. Les données saisies depuis la dernière sauvegarde sont perdues : d'où une sauvegarde chaque nuit et, si
l'activité le justifie, une seconde à midi (dupliquer le timer).

## 4. Premier lancement — dans cet ordre

```bash
cd transpt1
python manage.py check --deploy          # doit répondre « no issues » (1 vérification écartée volontairement : HSTS preload)
python manage.py migrate                 # crée les tables
python manage.py collectstatic --noinput # fichiers de l'administration, servis par le proxy (§5)
python manage.py seed_formation          # parcours de formation de base (guichetier, chauffeur, magasinier) : du contenu, pas des données de démo
python manage.py createsuperuser         # le premier compte : rôle « superadmin », sans compagnie
```

- [ ] **Ne lancez jamais les commandes `seed_demo_*`** : elles créent des comptes au mot de passe public (dont un
      superadmin). Elles refusent d'ailleurs de s'exécuter quand `DJANGO_DEBUG=False`.
- [ ] Démarrer le service applicatif, par exemple avec systemd (`/etc/systemd/system/transport-coord.service`) :
      ```ini
      [Service]
      User=transport
      WorkingDirectory=/srv/transport/transpt1
      EnvironmentFile=/srv/transport/transpt1/.env
      ExecStart=/srv/transport/venv/bin/gunicorn transport_coord.wsgi --bind 127.0.0.1:8000 --workers 3
      Restart=on-failure
      ```
      (Windows : `waitress-serve --listen=127.0.0.1:8000 transport_coord.wsgi:application`.)

### Créer les vraies données, dans l'administration (`https://api.votre-domaine.ci/admin/`)

Il n'existe pas d'écran métier pour ces saisies : l'administration Django est le seul moyen, réservé au superadmin.

- [ ] **Compagnie** (« Compagnies ») puis **gares**, **lignes**, **véhicules**, **pièces** de la compagnie.
- [ ] **Un compte nominatif par agent** (« Utilisateurs »). Le **rôle est un choix obligatoire** dans le formulaire
      (il n'est jamais prérempli) et la compagnie est obligatoire pour tout rôle sauf « superadmin ». Mot de passe fort
      (le formulaire refuse les mots de passe trop simples). Pas de compte partagé : les journaux et les scores sont par agent.
- [ ] Rattacher chaque **chef de gare** à sa gare (champ « Chef » de la gare : un chef par gare).
- [ ] **Planning du jour** : les **départs** (ligne, véhicule, chauffeur principal ou relais, date et heure) et leur
      **feuille de route** se planifient **depuis le site**, par le chef de ligne ou la direction de l'exploitation
      (« Planifier un départ » : le formulaire ne propose que les véhicules et chauffeurs réellement libres à cette heure,
      et refuse un véhicule ou un chauffeur déjà affecté à un autre départ dans les 8 h). L'administration Django reste
      possible mais ne fait pas ces vérifications. Le chauffeur ne voit que les feuilles de route **datées d'aujourd'hui**.
- [ ] Départ d'un agent : décocher « Actif » dans son compte (ne le supprimez pas : ses actions passées restent
      rattachées à lui). L'accès est coupé **immédiatement** : le serveur relit le compte à chaque requête, un jeton
      déjà émis (accès comme rafraîchissement) est refusé dès la requête suivante. Il en va de même d'un changement de rôle.

## 5. Le proxy : Caddy (certificat Let's Encrypt automatique)

`/etc/caddy/Caddyfile` :

```
api.votre-domaine.ci {
    handle_path /static/* {
        root * /srv/transport/transpt1/staticfiles
        file_server
    }
    reverse_proxy 127.0.0.1:8000
}

app.votre-domaine.ci {
    root * /srv/transport/frontend/dist
    try_files {path} /index.html      # application à page unique : toute route retombe sur index.html
    file_server
}
```

Caddy obtient et renouvelle seul les certificats, redirige le HTTP vers HTTPS et pose `X-Forwarded-Proto`.

### Alternative : nginx

```nginx
limit_req_zone $binary_remote_addr zone=connexion:10m rate=30r/m;

server {
    listen 443 ssl;
    server_name api.votre-domaine.ci;
    ssl_certificate     /etc/letsencrypt/live/api.votre-domaine.ci/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.votre-domaine.ci/privkey.pem;

    location /static/ { alias /srv/transport/transpt1/staticfiles/; }

    location = /api/auth/login/ {              # freine les essais de mots de passe
        limit_req zone=connexion burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;   # toujours écrasé par le proxy
    }
}
server { listen 80; server_name api.votre-domaine.ci; return 301 https://$host$request_uri; }
```

- [ ] **Limiter les essais de connexion** : l'application n'a pas de limitation intégrée (`/api/auth/login/`). Avec
      Caddy, prévoir un module de limitation ; avec nginx, le bloc ci-dessus. Gardez une limite généreuse : sur
      les réseaux mobiles, de nombreux agents partagent la même adresse IP publique.

## 6. Règle de sécurité essentielle

Django fait confiance à `X-Forwarded-Proto` pour savoir si la requête est en HTTPS. **Django ne doit donc être
joignable que par le proxy** : écoutez sur `127.0.0.1` (ou un réseau privé) et fermez le port 8000 au pare-feu.
Sinon, un client peut atteindre Django directement en HTTP et prétendre être en HTTPS.

**Le journal d'audit** enregistre l'adresse du client : la **dernière** entrée de `X-Forwarded-For`, c'est-à-dire celle
qu'ajoute votre proxy (Caddy et nginx avec `$proxy_add_x_forwarded_for` le font ; les entrées précédentes viennent du
client et sont falsifiables). Même règle que ci-dessus : si Django est joignable sans passer par le proxy, l'adresse
enregistrée peut être inventée. Pour un pilote, vérifier dans « Journal d'audit » que les adresses affichées sont celles
des agents et non celle du proxy (`127.0.0.1`).

Le journal est en **ajout seulement** pour l'application (ni modification ni suppression, même depuis l'administration).
Un administrateur de la base garde toutefois la main dessus : ne donnez pas à l'utilisateur PostgreSQL de l'application
d'autres droits que ceux nécessaires, et gardez les sauvegardes hors du serveur (§3) pour pouvoir prouver l'historique.

## 7. Site web et application mobile

**Site web**

- [ ] `cd frontend && VITE_API_BASE_URL=https://api.votre-domaine.ci/api npm run build`, puis copier `dist/` sur le
      serveur (`/srv/transport/frontend/dist`). L'adresse de l'API est figée à la compilation.
- [ ] Vérifier que `CORS_ALLOWED_ORIGINS` contient exactement l'adresse du site (§2).

**Application mobile** (Android)

- [ ] Compiler avec l'adresse de production : `flutter build apk --release --target-platform android-arm64 --dart-define=API_BASE_URL=https://api.votre-domaine.ci/api`.
      La version *release* refuse toute adresse `http://` (voir `mobile/README.md`).
- [ ] **La signature *release* est configurée** (`mobile/android/app/build.gradle.kts` lit `mobile/android/key.properties`,
      ignoré par git, ainsi que le keystore `.jks`). Sans ce fichier, la compilation *release* **échoue volontairement** plutôt
      que de signer avec la clé de débogage (publique). **Sauvegarder le keystore et `key.properties` hors de l'ordinateur** :
      Android n'accepte une mise à jour que si elle est signée par la même clé, et sa perte oblige à faire désinstaller
      l'application partout (avec les ventes hors ligne en attente). Vérifier chaque APK : `apksigner verify --print-certs`.
      Détails, création de la clé sur une autre machine et protocole d'essai sur téléphones : `mobile/TEST_TELEPHONES.md`.
- [ ] **Essayer l'APK sur au moins deux vrais téléphones** avant de le distribuer (`mobile/TEST_TELEPHONES.md`) : il n'a
      **jamais été installé sur un appareil** à ce jour.
- [ ] Le certificat HTTPS doit être émis par une autorité reconnue par Android (Let's Encrypt convient) : un
      certificat auto-signé est refusé, à raison.

## 8. Notifications aux voyageurs (SMS / WhatsApp)

Par défaut tout est **simulé** : chaque vente journalise la notification (« Simulé ») sans rien envoyer. Pour passer en réel :

- [ ] Ouvrir un compte fournisseur : **Orange SMS API** (numéros +225 ; `ORANGE_SMS_CLIENT_ID`, `ORANGE_SMS_CLIENT_SECRET`,
      `ORANGE_SMS_SENDER`) et/ou **Twilio** (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`). Pour WhatsApp :
      `TWILIO_WHATSAPP_FROM` et un modèle de message **approuvé** (`TWILIO_WHATSAPP_CONTENT_SID`).
- [ ] Choisir les canaux (`NOTIFICATIONS_CANAUX_TICKET=sms,whatsapp`) et le fournisseur (`NOTIFICATIONS_SMS_PROVIDER=auto`).
- [ ] Tester avec **votre propre numéro** en mettant `NOTIFICATIONS_SIMULATION_MODE=False`, vendre un ticket, vérifier la
      réception **et** le statut « Envoyé » dans « Notification logs » de l'administration. Chaque message est facturé.
- [ ] Ces clés sont des secrets : uniquement dans l'environnement du service, jamais dans le dépôt.

## 9. Vérifier le déploiement

```bash
curl -I http://api.votre-domaine.ci/api/auth/me/     # 301 vers https://
curl -I https://api.votre-domaine.ci/api/auth/me/    # 401 + Strict-Transport-Security
curl -I https://api.votre-domaine.ci/static/admin/css/base.css   # 200 : les fichiers statiques sont servis
curl -I https://app.votre-domaine.ci/dashboard/finance           # 200 : le site rend index.html sur toute route
```

- [ ] Se connecter à `/admin/` avec le superadmin, puis créer un compte de test pour chaque rôle utile.
- [ ] Rejouer le scénario `SCENARIO_PILOTE.md` (à la racine du dépôt) sur la vraie plateforme avec ces comptes de test
      (sans les commandes `seed_demo_*`), puis **supprimer les comptes et données de test**.
- [ ] Provoquer une erreur volontaire et vérifier qu'elle apparaît dans les journaux du service
      (`journalctl -u transport-coord`) : sans cela, on ne saurait pas pourquoi une requête échoue.

## 10. Exploitation courante

- **Mise à jour** : sauvegarde de la base → récupérer le code → `pip install -r requirements.txt` → `python manage.py
  migrate` → `python manage.py collectstatic --noinput` → redémarrer le service. Relire les migrations avant de les appliquer.
- **Sauvegardes** : `manage.py etat_sauvegarde` branché sur la supervision (alerte si échec ou trop ancienne) ; restauration
  de test chaque semaine (`verifier_sauvegarde`, §3) ; une répétition complète sur une autre machine avant le pilote.
- **Journal d'audit** : consulté depuis le site (Direction, secrétariat général, QHSE). Il grossit avec l'activité : prévoir
  d'en archiver les entrées de plus de 12 mois (export puis suppression par l'administrateur de la base — l'application
  elle-même ne supprime jamais).
- **Tickets** : un ticket vendu ne se modifie ni ne se supprime ; une erreur se corrige par **annulation motivée** (chef de
  gare ou direction), tracée dans le journal, et sort des recettes.
- **Secrets compromis** : changer `DJANGO_SECRET_KEY` (déconnecte tout le monde), les mots de passe de la base, les clés
  des fournisseurs de SMS ; désactiver les comptes concernés.
- **Données personnelles** : la plateforme conserve nom et téléphone des voyageurs (tickets). Prévoir l'information
  des voyageurs et les formalités de protection des données applicables (à voir avec votre conseil juridique).

## Limites connues avant le pilote

- **Pas de limitation des essais de connexion dans l'application** (à faire au niveau du proxy, §5) ni d'authentification
  à deux facteurs ; les jetons de connexion du site web sont conservés dans le navigateur (`localStorage`).
- **Un seul processus de cache** par instance : ne pas compter sur un cache partagé entre plusieurs machines.
- **Aucune alerte en temps réel** : un incident déclaré apparaît sur les tableaux de bord (qui se rafraîchissent chaque
  minute) mais ne déclenche ni notification ni appel.
- **Mobile** : l'APK *release* se compile et se signe, mais il n'a **jamais été lancé sur un appareil** : le protocole
  d'essai (`mobile/TEST_TELEPHONES.md`) reste à exécuter sur de vrais téléphones. Le chauffeur ne peut pas encore démarrer ni
  terminer sa feuille de route depuis le mobile (web uniquement).
- **Listes non paginées** : les listes de l'API (tickets, départs, incidents…) renvoient tout ; à surveiller si une compagnie
  dépasse quelques milliers de tickets par mois (le journal d'audit, lui, est paginé).
