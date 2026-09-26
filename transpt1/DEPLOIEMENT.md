# Déploiement du pilote — checklist

Ce guide mène du serveur vide au premier lancement réel. Cochez chaque case dans l'ordre. L'API n'est servie
qu'en **HTTPS** : le TLS est terminé par un *reverse proxy* (Caddy ou nginx) qui relaie en HTTP vers Django.

```
téléphone / navigateur ──HTTPS──▶ proxy (Caddy, nginx) ──HTTP──▶ gunicorn / Django (127.0.0.1:8000) ──▶ PostgreSQL
                              └──WSS (carte temps réel)──▶ daphne / Django (même port, voir §1 et §5)
                                     └── sert aussi le site web (frontend/dist) et /static/ (administration)
```

## 1. Avant de commencer

- [ ] Un serveur avec **Python 3.12 ou plus** (Django 6.1), **PostgreSQL**, et un nom de domaine pointant dessus
      (ports 80 et 443 ouverts). Le port 8000 (Django) et le port PostgreSQL restent **fermés** au public.
- [ ] Le code sur le serveur, un environnement virtuel, puis `pip install -r requirements.txt`, qui installe déjà
      **daphne** (serveur ASGI : HTTP et WebSocket du même processus, voir §4 et §5) — ne lancez **jamais**
      `runserver` en production. Sans la carte temps réel, un serveur WSGI classique (`pip install gunicorn`
      sous Linux, `pip install waitress` sous Windows) reste possible : la carte retombe alors sur son
      rafraîchissement périodique (60 s) sans rien casser, voir `frontend/src/api/useFluxCarte.js`.
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
| `DJANGO_CHANNEL_LAYER_REDIS_URL` | Carte temps réel (§5) : vide par défaut (une seule instance suffit pour un pilote). Avec plusieurs workers `daphne` ou plusieurs machines, `pip install channels-redis` puis `redis://localhost:6379/0` — sans cela, un navigateur servi par le worker A ne reçoit pas les positions reçues par le worker B. |

**Sauvegardes** — voir §3 : `BACKUP_DIR` (défaut `transpt1/sauvegardes/`, à placer sur un autre disque),
`BACKUP_RETENTION_DAYS` (14), `BACKUP_MIN_KEEP` (3), `BACKUP_MAX_AGE_HOURS` (26), `BACKUP_POST_COMMAND` (envoi hors du serveur),
`SAUVEGARDE_ADMIN_USER` / `SAUVEGARDE_ADMIN_PASSWORD` (rôle `CREATEDB` du test de restauration, dans un fichier à part).

**Métier** (valeurs par défaut sensées) : `BILLETTERIE_QUOTA_HORS_LIGNE` (2 places réservées par guichetier et par
départ ; 0 désactive la vente hors ligne garantie), `BILLETTERIE_RESERVATION_TTL_HEURES` (12),
`BILLETTERIE_HORIZON_HORS_LIGNE_HEURES` (24).

**Réglages d'exploitation** (valeurs par défaut sensées, à ajuster au pilote) :

| Variable | Défaut | Rôle |
|---|---|---|
| `CONNEXION_LIMITE_COMPTE`, `CONNEXION_LIMITE_ADRESSE` | `10/min`, `30/min` | Limitation des essais de connexion (par couple adresse + identifiant, et par adresse) : 429 au-delà. **Chaque worker a ses compteurs** tant que le cache n'est pas partagé (ligne suivante). |
| `DJANGO_CACHE_BACKEND`, `DJANGO_CACHE_LOCATION` | mémoire du processus | Cache des compteurs. Avec plusieurs workers ou machines : `django.core.cache.backends.db.DatabaseCache` et `cache_table`, puis `python manage.py createcachetable` (une fois). |
| `SUIVI_SEUIL_FATIGUE_MINUTES` | `270` (4 h 30) | Conduite continue au-delà de laquelle l'alerte de fatigue propose un relais. |
| `NOTIFICATIONS_CANAUX_COLIS` | `sms,whatsapp` | Canaux du code de retrait et des étapes d'un colis. Le message WhatsApp part en texte libre : aucun modèle approuvé n'est prévu pour les colis. |
| `ENTRETIEN_PREAVIS_JOURS`, `ENTRETIEN_PREAVIS_KM` | `15`, `1000` | Un entretien préventif est « bientôt dû » à moins de N jours ou N km de son échéance : l'atelier est alerté et l'ordre de réparation s'ouvre. |
| `RENOUVELLEMENT_KM`, `RENOUVELLEMENT_ORDRES_12_MOIS`, `RENOUVELLEMENT_JOURS_IMMOBILISE_12_MOIS` | `600000`, `8`, `60` | Seuils d'usure du rapport de besoin de renouvellement de la flotte (deux seuils atteints = « à renouveler »). |
| `MEDIATION_SEUIL_LITIGE` | `grave` | Gravité (`faible`, `moyenne`, `grave`, `critique`) à partir de laquelle une doléance encore ouverte du canal de médiation prévient le responsable juridique d'un risque de litige social (le PDG aussi si elle est critique). |
| `DJANGO_MEDIA_ROOT` | `media/` du projet | **Où sont rangées les pièces jointes** (pièces des sinistres, fichiers des modèles de documents juridiques). À placer hors du dossier du code, sur un disque sauvegardé (§3). Le serveur web ne doit **pas** servir ce dossier : seule l'API rend les fichiers, après contrôle des droits. |
| `PIECES_JOINTES_TAILLE_MAX_MO` | `5` | Taille maximale d'une pièce jointe. Le proxy doit accepter au moins cette taille (§5 : `client_max_body_size`). |

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
- [ ] **Sauvegarder aussi les pièces jointes** : la sauvegarde de la base ne contient **pas** les fichiers (constats, photos, expertises,
      modèles de documents) rangés dans `DJANGO_MEDIA_ROOT`. Les copier avec la même fréquence et la même chaîne hors du serveur que la base
      (par exemple `rclone sync` ou `rsync` de ce dossier, chiffré), dans le `BACKUP_POST_COMMAND` ou une seconde tâche. Une restauration
      complète remet la base **et** ce dossier de la même date : sinon un dossier de sinistre pointerait vers un fichier absent.
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
      ExecStart=/srv/transport/venv/bin/daphne -b 127.0.0.1 -p 8000 transport_coord.asgi:application
      Restart=on-failure
      ```
      (Windows : pas d'équivalent Windows testé pour daphne ; `waitress-serve --listen=127.0.0.1:8000
      transport_coord.wsgi:application` sert le HTTP seul, sans la carte temps réel — voir §1.)
      Une seule instance `daphne` suffit pour un pilote (elle gère ses connexions WebSocket de façon
      asynchrone, pas par processus comme gunicorn) ; pour en faire tourner plusieurs derrière le proxy
      (plus de trafic), `DJANGO_CHANNEL_LAYER_REDIS_URL` devient nécessaire (§2) : sans lui, chacune ignore
      les positions reçues par les autres.

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
    reverse_proxy 127.0.0.1:8000   # daphne comprend le HTTP et le WebSocket (/ws/...) sur le même port : rien de
                                    # plus à déclarer ici, Caddy relaie une bascule WebSocket comme n'importe quelle requête.
}

app.votre-domaine.ci {
    root * /srv/transport/frontend/dist
    try_files {path} /index.html      # application à page unique : toute route retombe sur index.html
    file_server
}
```

Caddy obtient et renouvelle seul les certificats, redirige le HTTP vers HTTPS et pose `X-Forwarded-Proto`. Il ne limite pas la taille
des envois par défaut : le contrôle de `PIECES_JOINTES_TAILLE_MAX_MO` est fait par l'application (ajouter `request_body { max_size 6MB }` dans
le bloc `api.votre-domaine.ci` pour couper plus tôt).

### Alternative : nginx

```nginx
limit_req_zone $binary_remote_addr zone=connexion:10m rate=30r/m;

server {
    listen 443 ssl;
    server_name api.votre-domaine.ci;
    ssl_certificate     /etc/letsencrypt/live/api.votre-domaine.ci/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.votre-domaine.ci/privkey.pem;

    client_max_body_size 6m;                   # pièces jointes : PIECES_JOINTES_TAILLE_MAX_MO (5 Mo) + le corps du formulaire

    location /static/ { alias /srv/transport/transpt1/staticfiles/; }

    location = /api/auth/login/ {              # freine encore plus les essais de mots de passe, au niveau du proxy
                                                # (l'application limite déjà elle-même, voir « Limites connues avant le pilote » et `core/throttles.py`)
        limit_req zone=connexion burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
    location /ws/ {                             # carte temps réel (daphne, voir §4) : bascule WebSocket explicite,
                                                 # contrairement à Caddy qui la relaie sans configuration particulière
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 3600s;               # une connexion WebSocket reste ouverte : ne pas la couper comme une requête HTTP normale
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;   # toujours écrasé par le proxy
    }
}
server { listen 80; server_name api.votre-domaine.ci; return 301 https://$host$request_uri; }
```

- [ ] **Limiter encore plus les essais de connexion au niveau du proxy** (`/api/auth/login/`) : l'application limite déjà
      elle-même les tentatives par compte et par adresse (429, voir « Limites connues avant le pilote » et `core/throttles.py`), mais un cache non partagé
      entre plusieurs workers affaiblit cette limite d'autant (voir « Limites connues avant le pilote ») — une limitation côté proxy reste un filet de
      sécurité supplémentaire. Avec Caddy, prévoir un module de limitation ; avec nginx, le bloc ci-dessus. Gardez une
      limite généreuse : sur les réseaux mobiles, de nombreux agents partagent la même adresse IP publique.
- [ ] **Ne pas journaliser la chaîne de requête complète des WebSocket** (`/ws/...?token=...`) : le jeton d'accès y
      transite en clair (un navigateur ne peut pas poser d'en-tête `Authorization` sur un WebSocket, voir
      `dashboard/ws_auth.py`). Un journal d'accès qui inclut la chaîne de requête (comportement par défaut de
      beaucoup de configurations) l'enregistrerait donc en clair pendant sa durée de vie (30 minutes). Retirer la
      chaîne de requête du format de journal pour ce chemin, ou l'exclure du journal d'accès.

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

### Tâches planifiées — à installer **avant** d'ouvrir aux utilisateurs

Ces commandes font vivre les alertes, les clôtures et le jeu sans qu'un agent ait à ouvrir l'application. Toutes sont
**rejouables sans doublon** (chaque situation porte une clé) : mieux vaut les lancer trop souvent que pas assez.

| Commande | Fréquence conseillée | Ce qu'elle fait |
|---|---|---|
| `python manage.py generer_alertes` | toutes les 5 à 10 minutes | Alertes automatiques de chaque compagnie : seuils critiques du PDG (ponctualité, pannes, recettes), départs à risque de retard, échéances d'assurance (30 j, 7 j, expirée), conducteurs fatigués, **entretiens préventifs à échéance (ouvre l'ordre de réparation au mécanicien le moins chargé)**, véhicules à renouveler, **budget carburant à 80 % puis dépassé**, **factures à payer (rappels à 7 jours, 1 jour, en retard)**, **formations obligatoires à renouveler ou expirées (sécurité routière OSER, permis, visite médicale : DRH, QHSE et agent)**, **contrats à durée déterminée qui se terminent sous 30 jours**, **doléances au seuil de litige social non encore signalées au juridique**. |
| `python manage.py cloturer_caisses` | chaque soir (23 h 30) | Clôture les caisses des guichetiers en niveau d'automatisation « automatique » qui ont vendu sans clôturer, et prévient leur chef de gare. `--date AAAA-MM-JJ` rattrape un jour manqué. |
| `python manage.py evaluer_gamification` | chaque nuit | Enregistre les missions accomplies et les badges de tous les agents, même de ceux qui n'ont pas ouvert l'application (sinon l'évaluation se fait à la première consultation). |
| `python manage.py purger_positions_gps` | chaque nuit | Supprime les relevés GPS plus vieux que `POSITIONS_RETENTION_JOURS` (30 jours par défaut) : sans elle, la table des positions ne fait que grossir et ralentit la carte temps réel. `--jours N` remplace le réglage pour cet appel. |
| `python manage.py sauvegarde_base` | chaque nuit | Voir §3. |

Exemple `crontab` (compte du service, dans le dossier du projet, environnement chargé) :

```cron
*/10 * * * *  cd /srv/transport/transpt1 && ./venv/bin/python manage.py generer_alertes  >> /var/log/transport/alertes.log 2>&1
30 23 * * *   cd /srv/transport/transpt1 && ./venv/bin/python manage.py cloturer_caisses >> /var/log/transport/caisses.log 2>&1
15 2 * * *    cd /srv/transport/transpt1 && ./venv/bin/python manage.py evaluer_gamification >> /var/log/transport/jeu.log 2>&1
45 2 * * *    cd /srv/transport/transpt1 && ./venv/bin/python manage.py purger_positions_gps >> /var/log/transport/positions.log 2>&1
```

Sous Windows : Planificateur de tâches, une tâche par ligne. **Vérifier** après un jour de fonctionnement que les alertes se
créent (cloche d'alertes d'un compte de test) et que `cloturer_caisses` a clôturé les caisses attendues.

### Le reste

- **Mise à jour** : sauvegarde de la base → récupérer le code → `pip install -r requirements.txt` → `python manage.py
  migrate` → `python manage.py collectstatic --noinput` → redémarrer le service. Relire les migrations avant de les appliquer.
- **Sauvegardes** : `manage.py etat_sauvegarde` branché sur la supervision (alerte si échec ou trop ancienne) ; restauration
  de test chaque semaine (`verifier_sauvegarde`, §3) ; une répétition complète sur une autre machine avant le pilote.
- **Journal d'audit** : consulté depuis le site (Direction, secrétariat général, QHSE). Il grossit avec l'activité : prévoir
  d'en archiver les entrées de plus de 12 mois (export puis suppression par l'administrateur de la base — l'application
  elle-même ne supprime jamais).
- **Tickets** : un ticket vendu ne se modifie ni ne se supprime ; une erreur se corrige par **annulation motivée** (chef de
  gare ou direction), tracée dans le journal, et sort des recettes. Chaque ticket porte un **code** (10 caractères) : la
  migration `billetterie 0007` en a donné un, unique, aux tickets déjà vendus (relue et testée sur 50 tickets ; la relire sur
  une copie de la vraie base avant le pilote).
- **Compte d'un agent** : le PDG suspend un compte depuis « Pilotage » (motif obligatoire). Les sessions ouvertes sont coupées
  à la requête suivante ; rien n'est supprimé. Pour un départ définitif, suspendre plutôt que supprimer (l'historique des
  ventes, des contrôles et du journal d'audit garde l'auteur).
- **Ligne fermée** : le directeur des opérations ou le PDG ferme (jusqu'à un jour donné, ou jusqu'à réouverture) ; la ligne
  refuse alors planification et vente. Les départs déjà planifiés ne sont pas annulés d'office : l'alerte dit combien sont à
  réaffecter.
- **Kilométrage** : le technique relève le compteur des véhicules (page Technique) : sans relevé, seuls les entretiens en jours
  se déclenchent.
- **Secrets compromis** : changer `DJANGO_SECRET_KEY` (déconnecte tout le monde), les mots de passe de la base, les clés
  des fournisseurs de SMS ; désactiver les comptes concernés.
- **Pièces jointes** : elles vivent dans `DJANGO_MEDIA_ROOT` (voir §2 et §3). Le serveur n'accepte que PDF, PNG, JPEG, Word et Excel dont le
  contenu correspond à l'extension, sous un nom aléatoire, et ne les rend qu'à un utilisateur autorisé de la même compagnie ; **il n'analyse
  pas les fichiers à la recherche de virus** : les ouvrir depuis un poste protégé.
- **Données RH et médiation sociale** : dossiers du personnel, évaluations, mesures disciplinaires et doléances sont des données personnelles
  sensibles. L'accès suit la hiérarchie (`PERMISSIONS.md` §20) et chaque écriture figure au journal d'audit. Une doléance n'est lue que par son
  déposant et le DRH ; le juridique n'en voit que l'objet, le contenu et le poste de l'auteur. Prévoir, avec votre conseil juridique, la durée
  de conservation et l'information des agents.
- **Données personnelles** : la plateforme conserve nom et téléphone des voyageurs (tickets). Prévoir l'information
  des voyageurs et les formalités de protection des données applicables (à voir avec votre conseil juridique).

## Limites connues avant le pilote

- **Limitation des connexions** : l'application refuse (429) au-delà de `CONNEXION_LIMITE_COMPTE` / `_ADRESSE`, mais ses compteurs
  sont dans le cache : **par worker** tant que `DJANGO_CACHE_BACKEND` n'est pas un cache partagé (§2). Doubler par la
  limitation du proxy (§5) reste conseillé. Toujours pas d'authentification à deux facteurs ; les jetons de connexion du site
  web sont conservés dans le navigateur (`localStorage`).
- **Alertes internes seulement** : les alertes inter-pôles (blocage, panne, stock bas, fatigue, infraction…) s'affichent dans la
  cloche de chaque poste (rafraîchie toutes les minutes) mais ne déclenchent ni notification poussée, ni SMS, ni appel : un
  agent doit avoir l'application ouverte. Sans les tâches planifiées ci-dessus, les alertes automatiques ne se créent pas.
- **Suivi GPS** : la position est envoyée par le navigateur du chauffeur (page web) ; cette chaîne a été jouée dans un navigateur
  de test avec une position simulée, jamais sur un vrai téléphone en roulant. La carte du réseau est un schéma (gares reliées
  par des lignes), sans fond de carte.
- **Colis** : pas de reçu papier ; le code de retrait n'est envoyé que par SMS/WhatsApp (texte libre, sans modèle WhatsApp approuvé).
- **Pas de moteur vocal** : la préférence « vocal » d'un agent est enregistrée mais aucune commande ni lecture vocale n'est
  disponible (ni en français, ni en langues locales).
- **Mobile** : l'APK *release* se compile et se signe, mais il n'a **jamais été lancé sur un appareil** : le protocole
  d'essai (`mobile/TEST_TELEPHONES.md`) reste à exécuter sur de vrais téléphones. Le chauffeur ne peut pas encore démarrer ni
  terminer sa feuille de route depuis le mobile (web uniquement). **L'application mobile n'a pas été mise à jour** avec les
  nouveautés du serveur : elle envoie toujours un prix à la vente (elle n'utilise pas le tarif de la ligne, donc une vente
  au mauvais prix y serait refusée par le serveur), et n'a ni suivi GPS, ni contrôle des billets, ni colis, ni alertes.
  `flutter analyze` et `flutter test` n'ont pas été relancés depuis ces changements.
- **RH, finance et juridique** : ces modules ont été essayés dans un navigateur avec des données de démonstration, jamais avec de vrais
  agents ni de vraies factures. Ne sont **pas** couverts : le solde de congés (jours acquis et pris), la paie, la signature électronique des
  documents, un échange automatique avec un organisme de formation externe (la formation OSER est suivie par la compagnie elle-même, sans
  lien avec un système extérieur), l'anonymat d'une doléance (elle est nominative, confidentielle).
- **Listes non paginées** : les listes de l'API (tickets, départs, incidents…) renvoient tout ; à surveiller si une compagnie
  dépasse quelques milliers de tickets par mois (le journal d'audit, lui, est paginé).
