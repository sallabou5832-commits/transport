# Signer et tester l'application sur de vrais téléphones

> **État au moment de la rédaction** : la version *release* se compile et se signe (§1), mais **elle n'a jamais été
> installée ni lancée sur un téléphone** : la machine de développement n'a ni virtualisation (pas d'émulateur) ni
> téléphone branché. Tout ce qui suit le §2 est **un protocole à exécuter**, pas un résultat. Tant qu'il n'est pas
> rempli sur au moins deux téléphones, l'application mobile n'est pas validée pour le pilote.

## 1. La clé de signature

Android n'installe une mise à jour que si elle est signée par **la même clé** que la version installée. Perdre la
clé, c'est devoir faire désinstaller l'application (et donc perdre les ventes hors ligne en attente) sur chaque téléphone.

| Élément | Où |
|---|---|
| Le *keystore* (la clé) | `C:\Users\Lenovo\transport-coord-cles\transport-coord-release.jks` — **hors du dépôt** |
| Ses mots de passe, son alias | `mobile/android/key.properties` — ignoré par git, jamais commité |
| Alias de la clé | `transport-coord` (RSA 2048, valable 10 000 jours, format PKCS12) |

- [ ] **Sauvegarder maintenant les deux fichiers** (le `.jks` et `key.properties`) dans un endroit chiffré hors de cet ordinateur
      (gestionnaire de mots de passe, clé USB rangée à part). Un seul exemplaire = une panne de disque suffit à tout perdre.
- [ ] Ne jamais envoyer ces fichiers par courriel ni les coller dans une conversation.
- [ ] Sur une autre machine : recopier le `.jks`, créer `android/key.properties` (modèle ci-dessous) avec le bon chemin.

```properties
storeFile=C:/chemin/vers/transport-coord-release.jks
storePassword=…
keyAlias=transport-coord
keyPassword=…
```

**Sans `key.properties`, la compilation *release* échoue volontairement** (« Aucune clé de signature »), au lieu de
produire un APK signé avec la clé de débogage — publique, donc n'importe qui pourrait diffuser une fausse « mise à jour ».
`ALLOW_DEBUG_SIGNING=1` (variable d'environnement) permet un essai purement local ; cet APK ne doit jamais être distribué.

### Compiler et vérifier

```powershell
$env:Path = "C:\src\flutter\bin;$env:Path"; $env:JAVA_HOME = "C:\src\jdk-17"; $env:ANDROID_HOME = "C:\src\android-sdk"
cd mobile
flutter build apk --release --target-platform android-arm,android-arm64 --dart-define=API_BASE_URL=https://api.votre-domaine.ci/api
```

- **L'adresse de l'API est figée dans l'APK** : compilez avec l'adresse HTTPS **réelle** du pilote, sinon l'application
  ne joindra pas le serveur (et une adresse en `http://` est refusée au démarrage, voir `README.md`).
- **`android-arm` ET `android-arm64`, toujours** : beaucoup de téléphones d'entrée de gamme (Android Go, Tecno, Itel…) sont en
  **32 bits**. Un APK 64 bits seul s'y installe puis se ferme au lancement : le moteur Flutter n'y est pas. Cet APK pèse
  ~30 Mo. Ne pas utiliser le APK de débogage (150 Mo, lent, accepte le HTTP) pour les essais.

```powershell
# La signature est-elle valide, et est-ce bien NOTRE clé ? (l'empreinte SHA-256 du certificat doit être toujours la même)
C:\src\android-sdk\build-tools\36.0.0\apksigner.bat verify --verbose --print-certs build\app\outputs\flutter-apk\app-release.apk
Get-FileHash build\app\outputs\flutter-apk\app-release.apk -Algorithm SHA256
```

- [ ] `Verifies` s'affiche, le certificat est `CN=Transport Coord` (et **pas** `Android Debug`).
- [ ] Noter l'empreinte SHA-256 du certificat : elle doit être identique à chaque nouvelle version.
- [ ] Noter l'empreinte SHA-256 du fichier et la communiquer avec l'APK : chaque testeur peut ainsi vérifier qu'il installe le bon fichier.

## 2. Ce qu'il faut réunir

- [ ] **Un serveur de pilote en HTTPS** (certificat reconnu par Android, Let's Encrypt convient — voir `transpt1/DEPLOIEMENT.md`).
      Un serveur en `http://` ou un certificat auto-signé sera refusé par l'application, à raison.
- [ ] **Des comptes de test créés dans l'administration** (pas les comptes `seed_demo_*`, au mot de passe public) :
      2 guichetiers, 1 chauffeur, 1 chef de gare, dans la même compagnie ; 1 compte guichetier **d'une autre compagnie**.
- [ ] **Des données** : 2 départs à venir sur un véhicule à **3 places** (pour tester le manque de places), et une feuille de
      route du jour pour le chauffeur.
- [ ] **Au moins 2 téléphones différents** : idéalement un modeste (2 Go de RAM, Android ≤ 10, écran ~5") et un récent —
      c'est le modeste qui révèle les lenteurs et les fermetures d'application. Un téléphone de guichetier réel, si possible.
- [ ] Une **carte SIM avec données mobiles** (le Wi-Fi seul cache les vrais problèmes de réseau).

## 3. Installer

1. Copier `app-release.apk` sur le téléphone (câble USB, ou envoi à soi-même) et l'ouvrir ; autoriser « sources inconnues » pour
   l'application qui l'ouvre. Ou par câble : `adb install -r app-release.apk` (`C:\src\android-sdk\platform-tools\adb.exe`, débogage USB activé).
2. Noter le message d'Android : « application non reconnue » est normal hors Play Store ; un message de **signature invalide**
   ou **conflit avec une application existante** ne l'est pas (il trahit un APK signé avec une autre clé).
3. **Test de mise à jour** (à faire dès que vous avez une 2ᵉ version) : `adb install -r` de la nouvelle version **par-dessus**
   la première, sans désinstaller. Elle doit s'installer, garder la session et les ventes en attente. Sinon, la clé a changé.

## 4. Scénarios à jouer

Cocher, noter le téléphone, et pour chaque échec : capture d'écran + heure + compte utilisé (§6).

### A. Connexion et session

- [ ] Bon identifiant / bon mot de passe → arrive sur l'accueil du rôle (guichetier : « Vendre un ticket » ; chauffeur : feuille de route).
- [ ] Mauvais mot de passe → message clair, pas de plantage.
- [ ] Fermer l'application (retirer des tâches récentes) puis la rouvrir → **toujours connecté**.
- [ ] Idem **en mode avion** → toujours connecté, les dernières données s'affichent avec la mention « Hors ligne : données du … ».
- [ ] Désactiver le compte dans l'administration → l'application ne peut plus rien faire à la reconnexion / au prochain envoi (refus clair).
- [ ] Rôle sans écran mobile (ex. chef de gare) → écran d'attente compréhensible, pas d'erreur.

### B. Vente avec réseau (guichetier)

- [ ] Vendre un ticket (nom, téléphone, départ) → confirmation, le ticket apparaît sur le tableau de bord web du chef de gare.
- [ ] Le nombre de places restantes du départ diminue, sur le téléphone **et** sur le web.
- [ ] Deux guichetiers vendent la **dernière place** en même temps → un seul réussit, l'autre reçoit un refus clair (pas de surréservation).
- [ ] Vente d'un ticket sur un départ **complet** → refus clair.

### C. Vente hors ligne (le cœur de l'application)

- [ ] Avec réseau, ouvrir « Vendre un ticket » **une fois** (mémorise départs + réserve des places), puis passer en mode avion.
- [ ] Choisir un départ : « Places garanties hors ligne : 2 ». Vendre 2 tickets → bandeau « Hors ligne : 2 action(s) en attente d'envoi ».
- [ ] Une 3ᵉ vente est **refusée** (plus de place garantie).
- [ ] Rétablir le réseau → envoi automatique (< 1–2 min), bandeau « Tout est synchronisé », les 2 tickets sont sur le web, **sans doublon**.
- [ ] **Coupure au mauvais moment** : appuyer sur « Vendre » puis couper le réseau dans la seconde ; rétablir. Résultat : **un seul** ticket.
- [ ] **Application tuée avec des ventes en attente** (retirer des tâches récentes, ou redémarrer le téléphone) → rouvrir : les ventes sont toujours en file et partent au retour du réseau.
- [ ] **Batterie faible / économiseur d'énergie / « optimisation de la batterie »** activés sur les marques agressives
      (Xiaomi, Tecno, Infinix, Itel, Oppo, Huawei) : l'application ouverte se synchronise-t-elle ? Noter la marque si non.
- [ ] Une vente hors ligne **refusée par le serveur** à la synchronisation (ex. départ supprimé entre-temps) → marquée « refusée »,
      visible depuis le bandeau, jamais renvoyée en boucle.
- [ ] Attendre plus de 12 h hors ligne (ou baisser `BILLETTERIE_RESERVATION_TTL_HEURES` pour le test) → la garantie expire, comportement conforme au `README.md`.

### D. Comptes et déconnexion

- [ ] Se déconnecter avec des actions **non envoyées** → l'application prévient ; elles restent sur le téléphone.
- [ ] Se connecter avec un **autre** guichetier sur le même téléphone : il ne voit ni n'envoie les ventes de l'autre.
- [ ] Se déconnecter puis se reconnecter avec réseau → les places réservées sont rendues, puis redemandées.

### E. Chauffeur

- [ ] La feuille de route du jour s'affiche (véhicule, ligne, horaires) ; hors ligne, la dernière version s'affiche avec la mention de date.
- [ ] Un chauffeur sans feuille de route aujourd'hui → message clair.

### F. Conditions de terrain

- [ ] Réseau **très lent** (2G/EDGE, ou ville avec mauvaise couverture) : les écrans indiquent le chargement, pas de blocage définitif.
- [ ] Réseau qui **va et vient** (ascenseur, tunnel) pendant 5 minutes : aucun doublon, aucune vente perdue.
- [ ] **Heure du téléphone fausse** (réglage manuel décalé d'un jour) : pas de plantage, les départs affichés restent corrects ; noter tout écart.
- [ ] Rotation de l'écran, police agrandie dans les réglages Android, écran ~5" : rien n'est illisible ni coupé.
- [ ] Appel téléphonique reçu ou autre application au premier plan pendant une vente : au retour, l'écran est intact.
- [ ] Téléphone **redémarré** en plein milieu d'une saisie : rien d'incohérent au relancement.

### G. Sécurité

- [ ] Le trafic est chiffré : sur un point d'accès contrôlé, aucune requête `http://` (l'application refuse de toute façon de démarrer sans HTTPS).
- [ ] **Désinstaller puis réinstaller** l'application : elle prévient que des ventes en attente ont pu être perdues (clé de chiffrement perdue), sans planter.
- [ ] Téléphone verrouillé, application en arrière-plan : le contenu n'apparaît pas dans l'aperçu des applications récentes (si ce n'est pas le cas, le noter — c'est un choix à faire).
- [ ] Perte du téléphone : la procédure (désactiver le compte dans l'administration, qui coupe l'accès immédiatement) est connue des chefs de gare.

## 5. Un tableau par téléphone

| | Téléphone 1 | Téléphone 2 |
|---|---|---|
| Marque / modèle | | |
| Version d'Android | | |
| RAM | | |
| Taille de l'écran | | |
| Installation | | |
| A. Connexion | | |
| B. Vente en ligne | | |
| C. Vente hors ligne | | |
| D. Comptes | | |
| E. Chauffeur | | |
| F. Terrain | | |
| G. Sécurité | | |
| Anomalies (n°) | | |

## 6. Consigner les anomalies

Une ligne par anomalie : n°, téléphone, compte, **étapes exactes**, résultat obtenu, résultat attendu, capture d'écran, heure
(pour retrouver l'événement dans le **journal d'audit** du site web — Direction / QHSE — et dans `journalctl -u transport-coord`).

## 7. Décision

- **Bloquant (pas de pilote)** : ticket perdu ou en double, vente acceptée sans place, connexion impossible sur un téléphone testé,
  plantage au démarrage, mise à jour refusée par Android, donnée visible d'un autre guichetier.
- **À corriger avant la fin du pilote** : lenteur gênante, message peu clair, synchronisation retardée par l'économiseur d'énergie.
- **Acceptable, à noter** : détails d'affichage sans effet sur la vente.

Le pilote peut démarrer quand : les scénarios A à E passent sur les deux téléphones, aucune anomalie bloquante n'est ouverte,
la clé de signature est sauvegardée hors de l'ordinateur, et l'empreinte du certificat est consignée.
