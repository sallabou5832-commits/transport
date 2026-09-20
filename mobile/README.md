# Transport Coord — application mobile

Application Flutter pour les rôles de terrain (chauffeurs, guichetiers, bagagistes, mécaniciens).
Elle utilise **la même API Django et les mêmes endpoints JWT que le frontend web**
(`/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`).

Ce qui est en place dans ce squelette :

- **Connexion** avec reprise de session au démarrage (même hors ligne).
- **Accueil selon le rôle** : le chauffeur voit sa feuille de route du jour ; le guichetier a un
  bouton « Vendre un ticket » ; les autres rôles voient un écran d'attente.
- **Mode hors ligne** : stockage local (Hive) et synchronisation automatique. Seule la
  **vente de ticket** est branchée pour l'instant ; les autres actions se greffent facilement
  (voir « Ajouter une action hors ligne »).

## Lancer l'application en local

### 1. Prérequis

- **Flutter 3.47 ou plus** ([installation](https://docs.flutter.dev/install)). Vérifiez avec `flutter doctor`.
  Sur cette machine, Flutter est installé dans `C:\src\flutter` (non ajouté au PATH) :
  `set PATH=C:\src\flutter\bin;%PATH%` (cmd) ou `$env:Path = "C:\src\flutter\bin;$env:Path"` (PowerShell).
- Pour Android : **Android Studio** (il installe le SDK Android) et soit un émulateur, soit un
  téléphone Android avec le « débogage USB » activé.

```bash
cd mobile
flutter pub get
```

### 2. Démarrer le backend

```bash
cd transpt1
python manage.py runserver 0.0.0.0:8000
```

`0.0.0.0` est indispensable pour qu'un émulateur ou un téléphone puisse joindre le serveur.
Django n'accepte que les noms d'hôte listés dans `DJANGO_ALLOWED_HOSTS` (fichier `transpt1/.env`) :
ajoutez `10.0.2.2` (émulateur Android) et, pour un vrai téléphone, l'adresse IP de votre PC :

```
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2,192.168.1.20
```

Comptes de démonstration (voir `transpt1/README.md` pour les créer) — mot de passe `Demo!2024` :
`guichetier_stc`, `chauffeur_stc`, `chauffeur_relais_stc`, `magasinier_stc`, `chef_atelier_stc`.

### 3. Lancer l'application

| Où | Commande | Adresse de l'API utilisée |
|---|---|---|
| **Émulateur Android** | `flutter run` | `http://10.0.2.2:8000/api` (automatique) |
| **Téléphone Android** (USB, même Wi-Fi que le PC) | `flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api` | celle que vous indiquez (IP de votre PC) |
| **Chrome** (essai rapide, sans Android) | `flutter run -d chrome --web-port 3000` | `http://localhost:8000/api` (automatique) |

- `flutter devices` liste les appareils disponibles ; `flutter emulators` les émulateurs
  (`flutter emulators --launch <id>` pour en démarrer un).
- Pour Chrome, gardez le port `3000` : il est déjà autorisé par `CORS_ALLOWED_ORIGINS`.
- Sur un vrai téléphone, le pare-feu Windows doit laisser passer le port 8000.
- En mode debug, l'écran de connexion affiche l'adresse du serveur utilisée (utile pour dépanner).

> **Émulateur Android sous Windows** : il exige la virtualisation (activée dans le BIOS, et
> « Plateforme de l'hyperviseur Windows » activée dans les fonctionnalités Windows). Sans elle,
> utilisez un téléphone réel ou Chrome.

### 4. Essayer le mode hors ligne

1. Connectez-vous en `guichetier_stc` et ouvrez « Vendre un ticket » une première fois **avec** le
   réseau (les départs sont alors mémorisés sur le téléphone).
2. Coupez le réseau (mode avion, ou arrêtez le serveur Django).
3. Vendez un ticket : il est enregistré sur le téléphone. Le bandeau du haut indique
   « Hors ligne : 1 action(s) en attente d'envoi ».
4. Rétablissez le réseau : le ticket est envoyé automatiquement et le bandeau repasse à
   « Tout est synchronisé ». Touchez le bandeau pour voir la liste et forcer l'envoi.

## Tests

```bash
flutter analyze        # analyse statique
flutter test           # tests unitaires et d'écrans (faux serveur, aucun réseau requis)
```

Test de bout en bout contre un **vrai** backend (il crée de vrais tickets : à lancer sur une base de
démonstration, jamais en production) :

```bash
# backend démarré sur http://localhost:8000 avec les comptes de démo
flutter test tool/e2e_smoke_test.dart
# autre serveur : --dart-define=API_BASE_URL=http://192.168.1.20:8000/api
```

## Architecture

```
lib/
├── main.dart, app.dart      Démarrage, choix de l'écran selon l'état de connexion
├── services.dart            Assemblage de toutes les briques (une seule instance)
├── config.dart              Adresse de l'API (--dart-define=API_BASE_URL=...)
├── api/                     Client HTTP : jeton JWT, renouvellement sur 401, erreurs réseau
├── auth/                    Connexion, profil, rôles, stockage sécurisé des jetons
├── storage/                 Base locale : file d'attente (outbox) et cache de lecture
├── sync/                    Actions hors ligne et synchronisation
├── data/                    Lecture des données (feuille de route, départs) avec repli sur le cache
└── ui/                      Écrans
```

### Comment fonctionne le hors ligne

- **Actions (écriture)** : une action est d'abord **écrite sur le téléphone** (`Outbox`, base Hive),
  puis envoyée. Sans réseau, elle reste en file ; `SyncService` la renvoie au retour de la connexion
  (déclenché par le réseau, le retour de l'app au premier plan, ou toutes les 60 s s'il reste des
  actions). L'ordre d'arrivée est respecté.
- **Résultat d'un envoi** : accepté → retirée de la file ; pas de réseau ou serveur en panne → reste en
  file, on réessaiera ; **refus du serveur** (par ex. car complet) → marquée « refusée » et signalée à
  l'utilisateur, qui la revoit depuis le bandeau (jamais renvoyée en boucle).
- **Comptes** : chaque action appartient à son utilisateur ; elle n'est jamais envoyée avec le compte
  d'un autre. À la déconnexion, les actions non envoyées restent sur le téléphone (l'app prévient).
- **Lecture** : les dernières données lues (feuille de route, départs) sont gardées en cache et
  affichées hors ligne, avec la mention « Hors ligne : données du … ».

### Ajouter une action hors ligne

1. Déclarer son type dans `lib/sync/action_handlers.dart` (`ActionTypes`) et l'associer à son appel API
   dans `buildActionHandlers`.
2. Depuis l'écran, appeler `context.read<SyncService>().submit(type: ..., payload: {...})` : il
   enregistre, tente l'envoi et renvoie `sent`, `queued` (gardée pour plus tard) ou `rejected`.
3. Ajouter son libellé dans `lib/ui/pending_actions_screen.dart`.

## Limites connues (à traiter avant la mise en production)

- **Doublons possibles.** Si le serveur enregistre une vente mais que la réponse se perd (coupure au
  mauvais moment), l'app la renverra et le ticket sera créé **deux fois**. Chaque action porte déjà un
  identifiant unique, envoyé dans l'en-tête `Idempotency-Key` ; le backend ne l'exploite pas encore. À
  faire côté Django : mémoriser cette clé (par utilisateur) et renvoyer le ticket existant.
- **Places non garanties hors ligne.** Le nombre de places affiché hors ligne date de la dernière
  lecture : deux guichetiers hors ligne peuvent vendre la même dernière place. Le serveur refuse la
  seconde vente à la synchronisation (elle apparaît alors « refusée », à traiter avec le client).
- **Données non chiffrées sur le téléphone.** La file d'attente et le cache (noms et téléphones des
  voyageurs) sont stockés en clair. Les jetons de connexion, eux, sont chiffrés (Keystore/Keychain).
  Envisager le chiffrement de la base locale (Hive le prévoit) avant la production.
- **HTTPS obligatoire en production.** Le HTTP en clair n'est autorisé que dans les versions debug/profile
  Android ; une version release exige une API en HTTPS.
- **Android et iOS non testés sur appareil** dans cet environnement (aucun émulateur ni téléphone
  disponibles). L'application a été vérifiée par les tests, contre le vrai backend, et lancée dans Chrome.
  iOS n'a reçu aucune configuration spécifique.
- Le chauffeur ne peut pas encore démarrer/terminer sa feuille de route, ni faire sa checklist depuis
  le mobile : ces actions du cahier des charges sont à ajouter (voir « Ajouter une action hors ligne »).
