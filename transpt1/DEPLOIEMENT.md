# Déploiement en production (HTTPS)

L'API ne doit être servie qu'en **HTTPS**. Le TLS est terminé par un *reverse proxy* (Caddy ou nginx) qui
relaie en HTTP vers Django, sur la même machine ou un réseau privé.

```
téléphone / navigateur ──HTTPS──▶ proxy (Caddy, nginx) ──HTTP──▶ Django (127.0.0.1:8000)
```

## 1. Variables d'environnement (`.env` de production)

```
DJANGO_DEBUG=False                       # active HTTPS forcé, cookies sécurisés et HSTS
DJANGO_SECRET_KEY=<longue valeur aléatoire, propre à la production>
DJANGO_ALLOWED_HOSTS=api.votre-domaine.ci
CSRF_TRUSTED_ORIGINS=https://api.votre-domaine.ci
CORS_ALLOWED_ORIGINS=https://app.votre-domaine.ci      # frontend web, en https
DJANGO_HSTS_SECONDS=2592000              # 30 jours ; allonger (jusqu'à 31536000) une fois le HTTPS validé
NOTIFICATIONS_SIMULATION_MODE=False      # seulement quand les clés SMS/WhatsApp sont configurées
```

Avec `DJANGO_DEBUG=False`, `settings.py` active : redirection HTTP → HTTPS, cookies de session et CSRF
« secure », en-tête HSTS et lecture de `X-Forwarded-Proto` (`DJANGO_FORCE_HTTPS=True|False` permet de forcer
ou de couper ce comportement explicitement).

## 2. Le proxy : Caddy (certificat Let's Encrypt automatique)

`/etc/caddy/Caddyfile` :

```
api.votre-domaine.ci {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtient et renouvelle seul le certificat, redirige le HTTP vers HTTPS et pose `X-Forwarded-Proto`.
Prérequis : le domaine pointe vers le serveur, et les ports 80 et 443 sont ouverts.

### Alternative : nginx

```
server {
    listen 443 ssl;
    server_name api.votre-domaine.ci;
    ssl_certificate     /etc/letsencrypt/live/api.votre-domaine.ci/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.votre-domaine.ci/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;   # toujours écrasé par le proxy
    }
}
server { listen 80; server_name api.votre-domaine.ci; return 301 https://$host$request_uri; }
```

## 3. Règle de sécurité essentielle

Django fait confiance à `X-Forwarded-Proto` pour savoir si la requête est en HTTPS. **Django ne doit donc être
joignable que par le proxy** : écoutez sur `127.0.0.1` (ou un réseau privé) et fermez le port 8000 au
pare-feu. Sinon, un client peut atteindre Django directement en HTTP et prétendre être en HTTPS.

Ne lancez pas `runserver` en production : utilisez un serveur WSGI (gunicorn sous Linux, waitress sous
Windows), par exemple `gunicorn transport_coord.wsgi --bind 127.0.0.1:8000`.

## 4. Vérifier

```bash
python manage.py check --deploy --tag security     # doit répondre « no issues »
curl -I http://api.votre-domaine.ci/api/auth/me/    # 301 vers https://
curl -I https://api.votre-domaine.ci/api/auth/me/   # 401 + Strict-Transport-Security
```

`check --deploy` (sans `--tag`) signale aussi que `MAILERS` utilise encore le backend d'e-mail de
développement (affichage console) : à remplacer par un vrai backend (SMTP) avant d'envoyer des e-mails.

## 5. Application mobile

La version *release* de l'application refuse toute adresse `http://` (voir `mobile/README.md`) : compilez-la
avec `--dart-define=API_BASE_URL=https://api.votre-domaine.ci/api`. Le certificat doit être émis par une
autorité reconnue par Android (Let's Encrypt convient) : un certificat auto-signé est refusé, à raison.
