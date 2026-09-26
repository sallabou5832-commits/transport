# Audit fonctionnel et sécurité — 24 septembre 2026

Analyse demandée sur **l'ensemble des fichiers existants du projet** (backend Django `transpt1/`, site web
`frontend/`, application mobile Flutter `mobile/`), à jour après les 5 derniers commits (sauvegardes automatiques,
signature mobile release, commande vocale, documentation, **app `tutelle`**) — postérieurs à `ANALYSE_PROJET.md`
(21 septembre, état *avant* le chantier de conformité) et à `RAPPORT_CONFORMITE.md` (21 septembre, état *après*, qui
reste la référence pour le détail des 99 fonctionnalités du cahier des charges, poste par poste).

**Ce document ne répète pas ce que ces deux rapports couvrent déjà bien** : il (1) résume l'état fonctionnel en
signalant ce qui a changé depuis, et (2) reprend intégralement la sécurité — app par app, y compris ce qui n'existait
pas encore le 21 septembre (`tutelle`, la commande vocale mobile, les sauvegardes automatisées) — avec, pour chaque
constat, la preuve dans le code (fichier et ligne).

## 1. Résumé

**Verdict : un code exceptionnellement discipliné pour sa sécurité — permissions par rôle systématiques et
testées, isolation multi-compagnie appliquée à la racine (`CompanyScopedQuerysetMixin`), journal d'audit complet,
pièces jointes traitées avec un soin rare (contenu vérifié par signature, nom aléatoire, jamais de lien public),
clé d'API tutelle hachée et cantonnée à sa seule route, sauvegardes sans injection de commande, mobile qui refuse de
se compiler en *release* sans vraie clé de signature.** Les failles ouvertes sont peu nombreuses, déjà pour la
plupart identifiées dans `ANALYSE_PROJET.md`, et aucune n'est critique dans le contexte d'un pilote restreint.

| # | Gravité | Constat | Statut |
|---|---|---|---|
| F1 | Moyenne | Jetons JWT dans `localStorage`, sans liste noire de révocation | **Toujours ouvert** |
| F2 | Moyenne | `Vehicule.immatriculation` unique **sur toute la plateforme** (fuite d'information entre compagnies) | **Toujours ouvert** (la même faille sur `Piece.reference` a été corrigée) |
| F3 | Faible | Aucune authentification à deux facteurs | **Toujours ouvert** |
| F4 | Faible | Pas de `Content-Security-Policy` (filet de sécurité si un XSS apparaissait un jour) | **Toujours ouvert** |
| F5 | Faible | Cache de limitation des connexions par défaut local au processus (`LocMemCache`) | **Connu, documenté**, à corriger au déploiement multi-worker |
| F6 | Info | Vulnérabilités des dépendances non vérifiées cette fois encore (réseau non sollicité, voir §6) | **Non vérifié** |
| F8 | Faible | Carte temps réel (WebSocket, ajoutée après ce rapport le même jour) : jeton d'accès dans l'URL, risque borné mais réel pour les journaux d'accès | **Nouveau, documenté** (voir `DEPLOIEMENT.md`) |
| — | — | Verrouillage des tickets, tarif imposé, unicité des pièces par compagnie, limitation des tentatives de connexion (429) | **Confirmés corrigés**, vérifiés dans le code aujourd'hui |
| — | — | Module `tutelle` (nouveau, échange avec le Ministère) | **Examiné pour la première fois : rien à signaler** |

> **Complément (même jour, après la rédaction de cet audit)** : suivi GPS natif ajouté à l'application mobile
> (arrière-plan, Android) et carte du réseau poussée en temps réel par WebSocket côté web (`dashboard/consumers.py`,
> `dashboard/ws_auth.py`) — authentification, permission et isolation entre compagnies testées (9 tests,
> `dashboard/tests/test_carte_consumer.py`). Le seul constat de sécurité nouveau est **F8** ci-dessus.

## 2. Ce qui a changé depuis `RAPPORT_CONFORMITE.md` (21 septembre)

| Ajout | Où | État constaté aujourd'hui |
|---|---|---|
| App `tutelle` : flux de données avec le Ministère des Transports / OSER / AMUGA / OFT | `transpt1/tutelle/` | Authentification par clé d'API séparée des comptes internes, jamais ajoutée à `DEFAULT_AUTHENTICATION_CLASSES` (`tutelle/authentication.py:1-4`) ; clé **hachée** (SHA-256), jamais stockée en clair, affichée une seule fois à la création (`tutelle/models.py:79-89`) ; un compte tutelle ne peut ni lire ni écrire les routes internes, et un jeton interne (même PDG) n'authentifie jamais un compte tutelle (`tutelle/permissions.py:19-27`, testé) |
| Commande vocale (français) — vente de ticket, checklist | `mobile/lib/voice/speech_services.dart` | S'appuie sur le moteur **natif** du téléphone (`speech_to_text` / `flutter_tts`), aucun envoi audio à un service tiers écrit par l'application ; à l'initialisation, un moteur indisponible fait retomber l'app sur la saisie tactile (pas de blocage) |
| Signature release avec une vraie clé | `mobile/android/app/build.gradle.kts` | La compilation *release* **échoue** sans `key.properties` (sauf `ALLOW_DEBUG_SIGNING=1` explicite) ; le fichier n'est **pas suivi par git** (`mobile/android/.gitignore:12`, vérifié : `git ls-files` et `git log --all` ne le retrouvent nulle part) — bon réflexe, mais toujours **sans copie du keystore hors de cet ordinateur** (perte du disque = plus jamais de mise à jour de l'app sur les téléphones déjà installés) |
| Sauvegardes automatiques (`sauvegarde_base`, `verifier_sauvegarde`, `etat_sauvegarde`) | `transpt1/core/sauvegarde.py` | Toutes les commandes externes (`pg_dump`, `pg_restore`, `BACKUP_POST_COMMAND`) passent par `subprocess.run` avec une **liste** d'arguments — jamais `shell=True` — donc pas d'injection de commande par un nom de fichier ou une variable ; empreinte SHA-256, rotation, restauration réellement testée dans une base temporaire |

La couverture fonctionnelle par poste (les 99 fonctionnalités du cahier) reste celle de `RAPPORT_CONFORMITE.md` §4
(**62 complètes, 19 partielles, 18 absentes**) : aucun des commits depuis n'ajoute ou ne retire de fonctionnalité de
ce tableau (`tutelle` et la commande vocale sont des briques techniques transverses, pas des lignes du cahier).

## 3. Sécurité, app par app

Méthode : lecture de `settings.py`, et pour chacune des 18 apps Django, de `models.py`, `permissions.py`,
`serializers.py`, `views.py` et `urls.py` quand ils existent ; grep systématique de motifs à risque
(`eval`, `exec`, `pickle`, `subprocess`, `os.system`, `mark_safe`, `csrf_exempt`, `shell=True`) sur tout le dépôt ;
lecture du frontend (`auth/`, `api/client.js`) et du mobile (manifeste Android, configuration de signature,
client HTTP) ; lecture du flux de CI.

### 3.1 Points forts confirmés (avec preuve)

- **Isolation multi-compagnie systématique** : `CompanyScopedQuerysetMixin.get_queryset()` filtre par
  `company_id` pour tout rôle non-superadmin (`core/mixins.py:23-28`), doublée par la permission d'objet
  `IsSameCompany` (`core/permissions.py:6-23`) sur les vues qui l'exposent.
- **Verrouillage des tickets (S1 de `ANALYSE_PROJET.md`) : confirmé corrigé.** `TicketViewSet.update/partial_update/destroy`
  renvoient inconditionnellement `405 MethodNotAllowed` (`billetterie/views.py:254-266`) ; seule l'action `annuler`
  (réservée à `IsDispatchManagerAlways`, motif ≥ 5 caractères, sous verrou `select_for_update`) rend la place et sort
  la vente des recettes (`billetterie/views.py:268-300`).
- **Tarif imposé (S4) : confirmé corrigé.** Le prix d'un ticket est le tarif de la ligne ; un prix différent exige un
  rôle de supervision et un motif obligatoire (`billetterie/serializers.py:218-239`).
- **Limitation des connexions (S3) : confirmé corrigée.** Deux compteurs (par compte+adresse, par adresse seule),
  429 avec message d'attente, connexion et échecs tracés dans le journal d'audit (`audit/views.py:78-100`,
  `core/throttles.py`).
- **Unicité par compagnie des pièces détachées (S6, partiel) : confirmé corrigée.** `UniqueConstraint(fields=["company",
  "reference"])` (`maintenance/models.py:23`). **Mais `Vehicule.immatriculation` reste unique sur toute la
  plateforme** (`reseau/models.py:76`) : une compagnie peut toujours déduire qu'une immatriculation est déjà prise
  par une autre compagnie via le message d'erreur — c'est la moitié non corrigée de S6, à traiter par la même
  méthode (`UniqueConstraint(company, immatriculation)`).
- **Journal d'audit** : avant/après sur les champs métier, mot de passe jamais écrit même comme diff
  (`audit/signals.py:77, 143-144`), remise à zéro du contexte à chaque requête pour qu'aucun acteur ne fuie d'un
  utilisateur au suivant (`audit/middleware.py`), échec d'écriture du journal isolé par un `try/except` qui ne bloque
  jamais l'action métier mais ne l'avale pas non plus en silence (log) (`audit/signals.py:142-166`).
- **Pièces jointes (sinistres, modèles juridiques) : traitement particulièrement soigné.** Extension **et** signature
  binaire vérifiées (un `.exe` renommé `.pdf` est refusé), taille bornée, nom d'origine réduit à un `basename` (donc
  aucun risque de traversée de répertoire), stockage sous un nom aléatoire (UUID) par compagnie, **jamais de lien
  public** (pas de `MEDIA_URL` routé), seul un téléchargement authentifié et permissionné répond, avec
  `X-Content-Type-Options: nosniff` et `Content-Disposition: attachment` (`core/fichiers.py`, complet). C'est un des
  points les plus robustes du projet.
- **Codes de retrait des colis** : hachés avec `django.contrib.auth.hashers.make_password` (PBKDF2 salé, pas un simple
  SHA), 5 essais avant verrouillage définitif du colis (`colis/models.py:70,128,132`, `colis/views.py:138-159`).
- **Clé d'API tutelle** : voir §2 — hachage, cantonnement, jamais dans `DEFAULT_AUTHENTICATION_CLASSES`.
- **Aucun motif de code dangereux** trouvé dans tout le dépôt (`eval`, `exec`, `pickle`, `mark_safe`, `csrf_exempt`,
  `shell=True`, `os.system`) — la seule occurrence de `subprocess` est le module de sauvegarde, déjà passé en revue.
- **Frontend** : aucun `dangerouslySetInnerHTML`, `innerHTML` ni `eval` dans `frontend/src` (grep exhaustif) ; le
  contrôle d'accès par rôle du site (`ProtectedRoute.jsx`) n'est qu'un confort d'affichage — la vérité est côté API,
  ce qui est la bonne architecture (vérifié : chaque permission ci-dessus s'applique côté serveur).
- **Mobile** : HTTPS obligatoire en mode release (`ApiClient` lève une erreur si l'URL ne commence pas par `https://`
  quand `kReleaseMode`, `mobile/lib/api/api_client.dart:22-23`), clé de signature hors du dépôt git (vérifié), pas de
  dépendance exotique (`http`, `flutter_secure_storage`, `connectivity_plus` — surface d'attaque tierce minimale).
- **CI** (`\.github/workflows/ci.yml`) : les seuls secrets présents sont des valeurs jetables explicitement
  documentées comme telles, jamais de vrai secret dans le dépôt.
- **Garde-fou sur le rôle par défaut** : le modèle `User` a `role` par défaut à `SUPERADMIN` (nécessaire pour que
  `createsuperuser` fonctionne sans question) — un point qui pourrait être dangereux si un formulaire créait un
  compte sans préciser le rôle. C'est explicitement neutralisé : le formulaire d'administration rend le rôle
  obligatoire et sans valeur par défaut (`core/admin.py:13-25`, commentaire du code lui-même très clair sur le
  risque et sa parade) ; aucune route DRF ne permet la création d'un compte (`ComptesViewSet` n'a que `ListModelMixin`).

### 3.2 Failles et faiblesses encore ouvertes

| # | Gravité | Constat | Preuve | Recommandation |
|---|---|---|---|---|
| F1 | Moyenne | Jetons d'accès et de rafraîchissement dans `localStorage` (lisibles par tout script injecté) ; `rest_framework_simplejwt.token_blacklist` n'est pas installé (`INSTALLED_APPS`, `transport_coord/settings.py:64-93`) : un jeton de rafraîchissement volé reste valable jusqu'à 24 h (`SIMPLE_JWT.REFRESH_TOKEN_LIFETIME`, `settings.py:245`) sans moyen de le révoquer individuellement — seule la suspension du compte entier le coupe | `frontend/src/api/client.js:5-17`, `frontend/src/auth/AuthContext.jsx:11` | Passer les jetons en cookies `HttpOnly` + `SameSite=Strict` (nécessite CSRF sur les routes API), ou a minima activer `token_blacklist` et une rotation courte des jetons de rafraîchissement |
| F2 | Moyenne | `Vehicule.immatriculation` unique sur toute la plateforme (pas par compagnie) : une compagnie apprend qu'une plaque existe déjà ailleurs | `reseau/models.py:76` | `UniqueConstraint(fields=["company", "immatriculation"])`, comme cela a déjà été fait pour `Piece.reference` |
| F3 | Faible | Pas de deuxième facteur d'authentification, y compris pour superadmin, PDG, finance, DRH (comptes à fort pouvoir) | `transport_coord/settings.py` (aucune dépendance 2FA dans `requirements.txt`) | 2FA (TOTP) au moins pour superadmin et PDG avant un déploiement multi-compagnies réel |
| F4 | Faible | Aucune `Content-Security-Policy` : si un XSS apparaissait un jour dans une page (aucun trouvé aujourd'hui), rien n'empêcherait l'exfiltration du jeton `localStorage` | Absent de `settings.py` et de `frontend/index.html` | Ajouter une CSP stricte (`django-csp` ou en-tête posé par le reverse proxy) en filet de sécurité pour F1 |
| F5 | Faible | Cache par défaut (`LocMemCache`) pour la limitation des connexions : propre à chaque worker, donc la limite réelle est multipliée par le nombre de workers en production | `transport_coord/settings.py:274-279` (déjà documenté dans le commentaire du fichier et dans `DEPLOIEMENT.md`) | Configurer un cache partagé (`DatabaseCache` ou Redis) dès qu'il y a plus d'un worker |
| F6 | Info | `pip-audit` / `npm audit` non relancés dans cette session (comme lors de l'analyse du 21 septembre : accès réseau non sollicité ici) ; `RAPPORT_CONFORMITE.md` rapportait 0 vulnérabilité connue à cette date sur les mêmes fichiers `requirements*.txt` / `package-lock.json` | — | Relancer `pip-audit -r requirements.txt` et `npm audit` avant tout déploiement, et à chaque mise à jour de dépendance (le flux CI le fait déjà, mais n'a jamais tourné sur GitHub — voir `RAPPORT_CONFORMITE.md` §6.2) |
| F7 | Info | `RECORD_AUDIO` désormais demandé par le mobile (commande vocale) : selon le téléphone, la reconnaissance vocale peut transiter par le service du fabricant (ex. Google) plutôt que rester locale | `mobile/android/app/src/main/AndroidManifest.xml` | Informer les agents (mention dans la notice d'utilisation / la formation QHSE) que la commande vocale peut passer par le service de reconnaissance du téléphone, dans la continuité du constat S7 de `ANALYSE_PROJET.md` (données personnelles) |
| F8 | Faible | Carte temps réel (nouveau, chantier GPS) : le jeton d'accès JWT transite en clair dans l'URL du WebSocket (`?token=...`), un navigateur ne pouvant pas poser d'en-tête `Authorization` sur une connexion WebSocket. Un journal d'accès qui inclut la chaîne de requête complète l'enregistrerait donc en clair pendant sa durée de vie (30 minutes) | `dashboard/ws_auth.py`, `frontend/src/api/useFluxCarte.js` | Documenté dans `DEPLOIEMENT.md` §5 (exclure `/ws/...` des journaux d'accès complets) ; risque déjà borné par la durée de vie courte du jeton d'accès et par HTTPS/WSS obligatoire (le jeton ne transite jamais en clair sur le réseau, seulement dans les journaux du serveur/proxy) |

Rien, dans ce nouveau passage, ne remet en cause les constats déjà résolus (S1 à S4, la moitié de S6) ni les
priorités déjà données par `ANALYSE_PROJET.md` §13 pour ce qui reste réellement bloquant (essai du mobile sur de
vrais téléphones, copie du keystore hors de cet ordinateur, pagination des listes de l'API).

## 4. Ce que cette analyse n'a pas vérifié

Les mêmes limites que `ANALYSE_PROJET.md` §2 s'appliquent, plus spécifiquement pour cette session : pas de nouvel
appel d'API réel (les constats de la §3.1 viennent de la lecture du code, pas de sondes comme au 21 septembre —
les comportements vérifiés alors, eux, ne changent pas puisque le code correspondant n'a pas bougé depuis) ; pas de
relance de `pip-audit`/`npm audit` (réseau non sollicité) ; pas de revue ligne à ligne des ~4 200 lignes de pages
React ni des ~3 000 lignes Dart (un grep exhaustif de motifs à risque n'y a rien trouvé, mais un grep n'est pas une
relecture) ; le module `tutelle` est neuf et n'a, par construction, jamais été mis en présence d'un vrai système du
Ministère.

## 5. Recommandations, par ordre de valeur

1. **F1** (jetons) et **F2** (immatriculation par compagnie) — les deux corrections les plus proches en coût/valeur
   de celles déjà faites pour S1–S6 ; F2 est un simple `UniqueConstraint` + migration, sur le modèle de ce qui a déjà
   été fait pour `Piece.reference`.
2. **F5** (cache partagé) avant tout déploiement avec plus d'un worker — sans quoi la limitation des tentatives de
   connexion (§3.1) est affaiblie proportionnellement.
3. **F6** : relancer les audits de dépendances dès que le réseau le permet, et faire tourner `.github/workflows/ci.yml`
   sur un vrai dépôt GitHub (jamais fait à ce jour).
4. **F3 / F4** : à traiter avant un déploiement ouvert à plusieurs compagnies réelles (moindre urgence pour un
   pilote restreint à une gare).
5. Ce qui reste bloquant pour le pilote est **inchangé** et déjà priorisé dans `ANALYSE_PROJET.md` §13 : essai du
   mobile sur de vrais téléphones, copie du keystore hors de cet ordinateur.
