# Transport Coord — application mobile

Application Flutter pour les rôles de terrain (chauffeurs, guichetiers, bagagistes, mécaniciens).
Elle utilise **la même API Django et les mêmes endpoints JWT que le frontend web**
(`/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`).

Ce qui est en place :

- **Connexion** avec reprise de session au démarrage (même hors ligne).
- **Accueil selon le rôle** : le chauffeur voit sa feuille de route du jour, avec sa checklist
  avant-départ ; le guichetier a un bouton « Vendre un ticket » ; les autres rôles voient un écran
  d'attente.
- **Commande vocale (français)** sur la vente de ticket et la checklist avant-départ : parler pour
  remplir le formulaire, entendre un récapitulatif avant validation, avec repli sur la saisie
  tactile si la reconnaissance échoue ou est indisponible (voir « Commande vocale »).
- **Mode hors ligne** : stockage local **chiffré** (Hive, AES-256) et synchronisation automatique.
  La **vente de ticket** et la **checklist avant-départ** sont branchées ; les autres actions se
  greffent facilement (voir « Ajouter une action hors ligne »).
- **Ventes hors ligne garanties** : le serveur réserve des places au guichetier tant qu'il a du réseau.
- **Pas de doublon** : chaque vente porte une clé d'idempotence que le serveur reconnaît.
- **HTTPS obligatoire** dans les versions release.

## Lancer l'application en local

### 1. Prérequis

- **Flutter 3.47 ou plus** ([installation](https://docs.flutter.dev/install)). Vérifiez avec `flutter doctor`.
- Pour Android : le **SDK Android** et un **JDK 17**, puis un émulateur ou un téléphone Android avec le
  « débogage USB » activé.

Sur cette machine, tout est installé dans `C:\src` (rien n'est ajouté au PATH) :
`C:\src\flutter` (Flutter), `C:\src\android-sdk` (SDK Android 36 + build-tools 36), `C:\src\jdk-17`.
Flutter est déjà configuré pour les utiliser (`flutter config`). Pour ouvrir un terminal prêt à l'emploi :

```powershell
$env:Path = "C:\src\flutter\bin;C:\src\android-sdk\platform-tools;$env:Path"
```

> **Antivirus qui inspecte le HTTPS (Avast, etc.)** : il présente ses propres certificats, que Windows
> accepte mais que Java refuse (`PKIX path building failed`) : Gradle ne peut alors rien télécharger.
> Le fichier `~/.gradle/gradle.properties` de cette machine indique donc à Gradle d'utiliser le magasin
> de certificats de Windows (`systemProp.javax.net.ssl.trustStoreType=Windows-ROOT`). À reproduire sur
> tout poste dans le même cas.

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

### 4. Installer l'application sur un téléphone sans câble de développement

```bash
flutter build apk --debug          # -> build/app/outputs/flutter-apk/app-debug.apk
adb install build/app/outputs/flutter-apk/app-debug.apk     # (téléphone branché, débogage USB activé)
```

Ou copiez l'APK sur le téléphone et ouvrez-le (autoriser les sources inconnues). Une version debug utilise
l'adresse de développement : pour joindre un serveur, compilez avec `--dart-define=API_BASE_URL=...`.

### 5. Version de production (release) : HTTPS obligatoire

```bash
flutter build apk --release --target-platform android-arm,android-arm64 --dart-define=API_BASE_URL=https://api.votre-domaine.ci/api
```

Une version release **refuse** de démarrer (écran « Application mal configurée ») si l'adresse de l'API
est absente ou en `http://`. Android et iOS bloquent de toute façon le HTTP en clair hors développement.
La mise en place du HTTPS côté serveur est décrite dans `transpt1/DEPLOIEMENT.md`.

- **Toujours `android-arm` ET `android-arm64`** : de nombreux téléphones d'entrée de gamme sont en 32 bits. Un APK compilé
  pour `android-arm64` seul s'installe sur eux puis se ferme au lancement (le moteur Flutter 32 bits n'y est pas).
- **Signature** : la version release est signée par la clé décrite dans `android/key.properties` (ignoré par git, comme le
  keystore). **Sans ce fichier la compilation échoue** (volontairement : pas de signature silencieuse avec la clé de
  débogage). Création, sauvegarde et vérification de la clé, puis essai sur téléphones : [`TEST_TELEPHONES.md`](TEST_TELEPHONES.md).

### 6. Essayer le mode hors ligne

1. Connectez-vous en `guichetier_stc` et ouvrez « Vendre un ticket » une première fois **avec** le
   réseau (les départs sont mémorisés, et des places sont réservées à ce guichetier).
2. Coupez le réseau (mode avion, ou arrêtez le serveur Django).
3. Choisissez un départ : l'écran indique « Places garanties hors ligne : 2 ». Vendez un ticket : il est
   enregistré sur le téléphone, le bandeau du haut indique « Hors ligne : 1 action(s) en attente d'envoi ».
   Après 2 ventes, une troisième est refusée : plus aucune place garantie sans réseau.
4. Rétablissez le réseau : les tickets sont envoyés automatiquement, les places garanties sont
   reconstituées et le bandeau repasse à « Tout est synchronisé ».

## Tests

```bash
flutter analyze        # analyse statique
flutter test           # tests unitaires et d'écrans (faux serveur, aucun réseau requis)
```

Test de bout en bout contre un **vrai** backend (il crée de vrais tickets : à lancer sur une base de
démonstration, jamais en production). Il a besoin des comptes de démo, d'un second guichetier
`guichetier2_stc` et d'un départ « E2E-Garantie » sur un véhicule de 3 places (voir l'en-tête du fichier) :

```bash
# backend démarré sur http://localhost:8000
flutter test tool/e2e_smoke_test.dart
# autre serveur : --dart-define=API_BASE_URL=http://192.168.1.20:8000/api
```

## Architecture

```
lib/
├── main.dart, app.dart      Démarrage (écran d'erreur si configuration invalide), choix de l'écran
├── services.dart            Assemblage de toutes les briques (une seule instance)
├── config.dart              Adresse de l'API, HTTPS obligatoire en release
├── api/                     Client HTTP : jeton JWT, renouvellement sur 401, erreurs réseau
├── auth/                    Connexion, profil, rôles, stockage sécurisé des jetons
├── storage/                 Base locale chiffrée : file d'attente (outbox) et cache de lecture
├── sync/                    Actions hors ligne et synchronisation
├── data/                    Lecture des données (feuille de route, départs) et places garanties
├── voice/                   Commande vocale : compréhension du texte reconnu, moteurs, conversation
└── ui/                      Écrans
```

### Comment fonctionne le hors ligne

- **Actions (écriture)** : une action est d'abord **écrite sur le téléphone** (`Outbox`, base Hive),
  puis envoyée. Sans réseau, elle reste en file ; `SyncService` la renvoie au retour de la connexion
  (déclenché par le réseau, le retour de l'app au premier plan, ou toutes les 60 s). L'ordre d'arrivée
  est respecté.
- **Résultat d'un envoi** : accepté → retirée de la file ; pas de réseau ou serveur en panne → reste en
  file, on réessaiera ; **refus du serveur** → marquée « refusée » et signalée à l'utilisateur, qui la
  revoit depuis le bandeau (jamais renvoyée en boucle).
- **Pas de doublon** : chaque action porte un identifiant unique, envoyé dans l'en-tête `Idempotency-Key`.
  Si le serveur a enregistré une vente mais que la réponse s'est perdue, le renvoi rend le ticket
  existant au lieu d'en créer un second (voir `PERMISSIONS.md`, §2).
- **Comptes** : chaque action appartient à son utilisateur ; elle n'est jamais envoyée avec le compte
  d'un autre. À la déconnexion, les actions non envoyées restent sur le téléphone (l'app prévient).
- **Lecture** : les dernières données lues (feuille de route, départs) sont gardées en cache et
  affichées hors ligne, avec la mention « Hors ligne : données du … ».

### Places garanties pour la vente hors ligne

Sans réseau, un guichetier ignore les ventes des autres : il pourrait vendre une place déjà prise, et le
serveur refuserait la vente à la synchronisation alors que le voyageur a **déjà payé**. Le serveur réserve
donc des places au guichetier tant qu'il a du réseau (`POST /api/tickets/reserver-hors-ligne/`) :

- l'application n'autorise, **hors ligne, que des ventes couvertes par ces places** (l'écran indique combien
  il en reste) ; avec le réseau, la vente reste toujours possible ;
- ses ventes consomment d'abord ces places, qui lui sont garanties : un autre guichet ne peut pas les
  prendre ; la réserve est complétée à chaque synchronisation et renouvelée régulièrement ;
- elle est **rendue** à la déconnexion (sauf s'il reste des ventes à envoyer, qui en ont besoin) et expire
  d'elle-même au départ ou après 12 h.

Réglages côté serveur (`transpt1/.env`) : `BILLETTERIE_QUOTA_HORS_LIGNE` (2 par défaut, `0` désactive),
`BILLETTERIE_RESERVATION_TTL_HEURES` (12), `BILLETTERIE_HORIZON_HORS_LIGNE_HEURES` (24).

### Données chiffrées sur le téléphone

La file d'attente et le cache (noms et téléphones des voyageurs) sont chiffrés en **AES-256**. La clé,
générée au premier lancement, est gardée dans le coffre du système (Keystore Android / Keychain iOS), jamais
à côté des données. Si la clé est perdue (réinstallation, sauvegarde restaurée sur un autre téléphone),
les données deviennent illisibles : elles sont effacées et l'application **prévient l'utilisateur** que des
ventes en attente ont pu être perdues.

### Ajouter une action hors ligne

1. Déclarer son type dans `lib/sync/action_handlers.dart` (`ActionTypes`) et l'associer à son appel API
   dans `buildActionHandlers`.
2. Depuis l'écran, appeler `context.read<SyncService>().submit(type: ..., payload: {...})` : il
   enregistre, tente l'envoi et renvoie `sent`, `queued` (gardée pour plus tard) ou `rejected`.
3. Ajouter son libellé dans `lib/ui/pending_actions_screen.dart`.
4. Côté serveur, rendre l'endpoint idempotent (clé `Idempotency-Key`) s'il crée des données, et se demander
   si l'action a besoin d'une ressource garantie hors ligne (comme les places).

## Commande vocale

Une première couche d'accessibilité vocale, **en français uniquement**, sur deux écrans pour
commencer : la vente d'un ticket (guichetier) et la checklist avant-départ (chauffeur).

**Moteurs** : les API natives du téléphone — `speech_to_text` (reconnaissance : Android
`SpeechRecognizer`, iOS `SFSpeechRecognizer`) et `flutter_tts` (synthèse), pas un service cloud
(type Google Speech-to-Text). Trois raisons : (1) elles fonctionnent sans dépendre du réseau de la
même façon que le reste de l'application (voir « Mode hors ligne » — un service cloud ajouterait un
appel réseau, un coût par requête et une clé d'API à gérer, à l'opposé de ce choix) ; (2) la voix du
voyageur (nom, téléphone) ne quitte jamais l'appareil vers un tiers, cohérent avec le chiffrement
local déjà en place ; (3) le français est déjà pris en charge nativement sur Android et iOS, sans
configuration supplémentaire.

**Parcours** (`lib/voice/`, `VoiceFormSession`) : une question à la fois — énoncée, puis écoutée
jusqu'au silence. Une fois tous les champs comprises, un récapitulatif est énoncé et demande
« confirmer » ou « modifier » ; la validation elle-même passe par **exactement le même code** que le
bouton tactile (`_submit`), avec la même validation — la voix ne fait que remplir les mêmes champs.

**Mode secours**, jamais bloquant :
- moteur absent ou permission refusée : `VoiceFormSession.init()` renvoie faux, un message invite à
  continuer au clavier, formulaire inchangé ;
- incompréhension, erreur en cours de dictée, ou réponse « modifier » : la dictée s'arrête, les champs
  déjà compris restent remplis, à corriger ou compléter à la main ;
- un bouton « Annuler » interrompt la dictée à tout moment (`VoiceFormSession.cancel`).

**Compréhension du texte reconnu** (`lib/voice/voice_text.dart`) : fonctions pures (accents/casse
normalisés, mots-clés français pour le mode de paiement et l'état « OK »/« Défaut », nombre dicté
extrait pour le prix, intention « confirmer »/« modifier ») — c'est ce qui est testé
(`test/voice_text_test.dart`, `test/voice_form_session_test.dart` avec un faux moteur). La
reconnaissance et la synthèse elles-mêmes dépendent du service du téléphone : non testées (mais leur
échec l'est, via le mode secours).

**Pour ajouter la voix à un autre écran** : construire un `VoiceFormSession`, l'initialiser
(`init()`), enchaîner des `ask(question)` en écrivant chaque réponse comprise dans le même état que
la saisie tactile, terminer par un récapitulatif (`ask(recap)`) interprété avec
`parseConfirmationIntent`, puis appeler la méthode de soumission existante seulement si l'utilisateur
confirme. Toujours envelopper dans `try`/`finally` (`session.dispose()`) pour ne jamais laisser
l'écran bloqué sur un micro resté ouvert.

**Permissions natives** : `RECORD_AUDIO` + une entrée `<queries>` pour le service de reconnaissance
(Android, `AndroidManifest.xml`) ; `NSMicrophoneUsageDescription` et
`NSSpeechRecognitionUsageDescription` (iOS, `Info.plist`).

## Limites connues (à traiter avant la mise en production)

- **Places réservées = places immobilisées.** Tant qu'elles sont réservées, les autres guichets ne peuvent
  pas les vendre. Le quota (2 par guichetier et par départ) est un compromis à ajuster selon la taille des
  cars et le nombre de guichets ; il est le même pour toutes les compagnies.
- **Au-delà de la durée de réservation** (12 h par défaut) sans réseau, la garantie n'existe plus : une
  vente pourrait être refusée à la synchronisation (elle apparaît alors « refusée », avec la consigne de
  rembourser le voyageur ou de lui proposer un autre départ).
- **Deux téléphones pour le même guichetier** se partagent les mêmes places réservées.
- **Le chiffrement protège les fichiers** (téléphone perdu, copie de sauvegarde), pas un téléphone
  déverrouillé entre de mauvaises mains.
- **Android et iOS** : l'application est vérifiée par les tests, contre le vrai backend et dans Chrome, mais
  elle n'a pas été lancée sur un émulateur ni un téléphone dans cet environnement (aucune virtualisation
  disponible). Les APK de débogage et **release signé** se compilent, mais aucun n'a jamais été installé sur un appareil :
  le protocole d'essai sur de vrais téléphones est dans [`TEST_TELEPHONES.md`](TEST_TELEPHONES.md), **il reste à exécuter**.
  iOS n'a reçu aucune configuration spécifique.
- **Signature de la version release** : configurée (clé propre, hors du dépôt, dans `android/key.properties`) et vérifiée
  par `apksigner`. **À sauvegarder hors de l'ordinateur** : sa perte interdit toute mise à jour des téléphones installés.
- Le chauffeur ne peut pas encore démarrer/terminer sa feuille de route depuis le mobile (la checklist
  avant-départ, elle, est en place) : cette action du cahier des charges est à ajouter (voir « Ajouter
  une action hors ligne »).
- **Commande vocale** : première couche, en français uniquement, sur deux actions (voir « Commande
  vocale »). La compréhension du texte dicté est volontairement simple (mots-clés, pas de négation) :
  à étendre si l'usage sur le terrain le montre nécessaire. Non essayée sur un vrai téléphone dans cet
  environnement, pour la même raison que le reste de l'application (voir plus haut, « Android et iOS »).
