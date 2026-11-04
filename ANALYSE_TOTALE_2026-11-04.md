# Analyse totale du projet : manques et bugs (4 novembre 2026)

Demande : « fais l'analyse totale du projet et détermine les manques et les bugs ». Rien n'a été corrigé : ce rapport constate
et propose. Aucun lot ne commence sans votre accord.

## 1. En bref

> **Mise à jour du 4 novembre, après l'analyse** : T-08 et le lot A sont corrigés et vérifiés (§9). Parmi les quatre bugs
> graves, il ne reste que le côté site de T-02 (lot B).

- **La base est saine.** La suite serveur complète passe (5 158 tests), ainsi que le contrat site–serveur, l'inventaire des
  boutons et les tests du site et du mobile. Les parcours Chrome passent à **21 sur 22** : l'échec vient d'un défaut de la
  nouvelle barre du haut (T-08), §3.
- **20 bugs confirmés**, dont **4 graves** : trois font perdre une vente déjà payée par le voyageur, et le quatrième peut
  enregistrer « OK » sur un frein signalé défectueux. Tous les quatre touchent le **mobile**.
- **Douze de ces bugs étaient déjà relevés** : dix dans les lots 5 et 6 de l'audit du 2 novembre, jamais commencés, et deux
  (O-04, O-05) en attente de votre décision.
- **Trois risques hors code** : le dépôt GitHub est **public** ; deux jours de travail ne sont **pas commités** ; la base de
  développement a **53 migrations de retard**.
- **Manques principaux** :
  - les lots P2a à P9 du plan ;
  - les écrans mobiles du contrôleur, du bagagiste et du mécanicien ;
  - l'ouverture d'une compagnie, faite aujourd'hui depuis l'administration Django ;
  - les vrais SMS et le vrai lien avec la tutelle ;
  - un essai sur un vrai téléphone.

## 2. Méthode

| Volet | Ce qui a été fait |
|---|---|
| Serveur | Suite complète sur une base jetable (`DB_NAME=test_analyse_totale`, jamais la base de développement) ; `check`, `check --deploy`, `makemigrations --check` |
| Site | Tests unitaires, analyse statique stricte (oxlint), compilation, audit des dépendances, parcours Chrome complets |
| Mobile | Tests, `flutter analyze` |
| Revue de code | Revue « high » des changements en cours ; chaque constat relu dans le code avant d'être retenu |
| Audits précédents | Chaque point encore ouvert des rapports du 31 octobre et du 2 novembre relu dans le code actuel |
| Hors code | Visibilité du dépôt, secrets suivis par git, travail non commité, état de la base de développement |

## 3. Santé technique

| Vérification | Résultat |
|---|---|
| Suite serveur complète (pytest) | **5 158 réussis**, 1 ignoré, en 42 min |
| Migrations manquantes (`makemigrations --check`) | Aucune |
| `manage.py check` | Propre |
| `check --deploy` | 6 avertissements, tous propres au mode développement ; les réglages de production s'activent avec `DJANGO_DEBUG=False` |
| Contrat site–serveur | 353 réussis |
| Inventaire des boutons | 181 actions d'écriture : 152 appelées par un écran, 29 exclusions motivées |
| Guides | 53 réussis |
| Site : tests unitaires | 54 réussis |
| Site : analyse statique stricte | Aucun bug réel (avertissements d'accessibilité, effets « au montage » voulus) |
| Site : compilation | Réussie ; un seul fichier JS de **650 ko** (567 ko le 2 novembre) : pas de découpage par page (F-09) |
| Mobile | 249 tests réussis ; `flutter analyze` propre |
| Parcours Chrome (suite complète, nouvelle charte) | **21 réussis sur 22**. L'échec, « secrétariat », vient de T-08 : le panneau des alertes resté ouvert couvre le lien « Notes de service » |
| Dépendances serveur | **Django REST Framework 3.18.1 vulnérable** ; le correctif est la 3.18.2 |
| Dépendances site | 3 vulnérabilités, dans les outils de développement seulement (vite, vitest) : rien n'arrive en production |

## 4. Bugs confirmés, du plus grave au moins grave

Les identifiants T-xx sont nouveaux. Les autres viennent des rapports précédents et ont été relus aujourd'hui dans le code.

### Graves : vente payée perdue, ou sécurité

| # | Où | Ce qui se passe | Correction proposée |
|---|---|---|---|
| **T-01** | Mobile, synchronisation ([sync_service.dart:299-301](mobile/lib/sync/sync_service.dart#L299-L301)), et serveur ([authentification.py:12-19](transpt1/core/authentification.py#L12-L19)) | Un guichetier vend hors ligne. La direction réinitialise son mot de passe, puis il se reconnecte avec le mot de passe provisoire. La file part aussitôt, le serveur répond 403 « mot de passe provisoire », et le mobile classe chaque vente en **rejet définitif** : il la retire de la file alors que le voyageur a payé | Traiter ce 403 comme une session à reprendre (la file attend), et ne lancer la synchronisation qu'après le changement de mot de passe. Côté serveur, ajouter un code d'erreur explicite au lieu de compter sur le texte |
| **G-02** | Mobile, vente | Le mobile ignore le tarif de la ligne. Une vente hors ligne au mauvais prix est refusée à la synchronisation, alors que le voyageur a déjà payé. Reproduit en réel le 2 novembre | Lire et garder en cache le tarif de la ligne, comme le fait le site |
| **G-03** | Mobile, dictée de la checklist ([voice_text.dart](mobile/lib/voice/voice_text.dart)) | La négation n'est pas comprise. « Pas bon » ne contient aucun mot de défaut et contient « bon » : l'item est classé **OK**. Il en va de même pour « pas OK » et « c'est pas ok ». (Le pluriel « pas bons » n'était, lui, pas reconnu du tout.) La confirmation finale avait le même défaut : « je valide pas » valait « confirmer ». La relecture avant validation atténue le risque sans le supprimer, et la dictée démarre seule en mode vocal depuis P1e. L'inverse (« pas de problème » compris comme un défaut) est sans danger | Lire une négation (« pas », « plus », « jamais ») devant un mot d'accord : classer en défaut, ou demander de répéter |
| **T-02** | Site et mobile, guichet | En billetterie **externe**, l'écran du guichetier propose encore la vente, que le serveur refuse (403). Sur le site, l'erreur s'affiche aussitôt. Sur le mobile hors ligne, la vente est perdue à la synchronisation, comme en T-01 | Masquer la vente quand la compagnie est en billetterie externe (le réglage est déjà lu par la page Billetterie), sur le site comme sur le mobile |

### Moyens : session coupée, données effacées, page blanche, double vente

| # | Où | Ce qui se passe | Correction proposée |
|---|---|---|---|
| **G-01** | Mobile ([api_client.dart:137](mobile/lib/api/api_client.dart#L137)) | Une **erreur serveur** pendant le renouvellement du jeton est traitée comme un refus : la session est effacée, et le chauffeur est déconnecté en route | Ne fermer la session que sur 401 ; sur une erreur serveur ou une coupure, garder la session et réessayer |
| **O-04** | Serveur ([finance/models.py:48](transpt1/finance/models.py#L48), [reseau/models.py:181](transpt1/reseau/models.py#L181)) | Supprimer une ligne sans départ efface aussi ses **budgets carburant** et l'**historique de ses fermetures**. C'était possible par l'API seulement ; c'est désormais à portée du nouveau bouton « Supprimer la ligne » | **À décider** (règle d'intégrité) : refuser la suppression quand la ligne a un historique, en proposant de la fermer, ou en faire une règle du règlement intérieur |
| **F-05** | Site, suivi GPS du chauffeur ([SuiviTrajet.jsx:31-37](frontend/src/components/SuiviTrajet.jsx#L31-L37)) | Hors réseau, le tampon grossit sans limite et repart en bloc. Au-delà de 500 positions, environ 8 minutes de coupure, le serveur refuse le lot ([views.py:454](transpt1/personnel_roulant/views.py#L454)). Le lot est remis en tête, chaque essai échoue de nouveau, et **plus aucune position ne part** jusqu'à la fin du trajet | Envoyer par tranches de 500 au plus |
| **F-02** | Site, vente et colis | Envoyés sans `Idempotency-Key`. Un nouvel essai après une coupure **double la vente et le SMS** (le serveur sait dédoublonner, mais le site ne lui en donne pas les moyens) | Joindre une clé par vente et par colis, comme le mobile |
| **F-15** | Site, toutes les pages | Aucun filet d'erreur de rendu : une valeur inattendue venue de l'API donne une **page blanche** | Un filet par page, avec un message et un bouton « Recharger » |
| **F-16** | Site ([PlanificationDepart.jsx:19](frontend/src/components/PlanificationDepart.jsx#L19)) et autres champs de date | Une date mal tapée lève une erreur pendant le rendu : page blanche | Valider la date avant de la convertir |
| **G-04** | Mobile, GPS ([trip_gps_controller.dart:78-88](mobile/lib/gps/trip_gps_controller.dart#L78-L88)) | Deux vérifications peuvent se croiser pendant la demande d'autorisation de localisation. Deux abonnements GPS s'ouvrent alors, et le premier n'est jamais fermé | Empêcher deux vérifications en même temps |
| **T-03** | Serveur ([comptes.py:98-109](transpt1/core/comptes.py#L98-L109)) | Réinitialiser un mot de passe **ne prévient pas la direction**, alors que les autres gestes sur les comptes la préviennent | Appeler la même alerte que les autres gestes |

### Faibles : gêne, confidentialité, robustesse

| # | Où | Ce qui se passe | Correction proposée |
|---|---|---|---|
| **T-04** | Cloisonnement ([core/serializers.py:121](transpt1/core/serializers.py#L121)) | « Cet identifiant est déjà pris » révèle qu'un identifiant existe **dans une autre compagnie**. C'est une petite fuite, contraire au cloisonnement strict | **À décider** : un identifiant préfixé par le code de la compagnie, ou unique par compagnie |
| **O-05** | Cloisonnement, `/api/companies/<id>/` | La réponse est 403 pour une autre compagnie et 404 pour un identifiant inexistant : cela révèle qu'une compagnie existe | Répondre 404 dans les deux cas |
| **G-06** | Mobile, manifeste Android | `allowBackup` n'est pas réglé : les données de l'application peuvent partir dans la sauvegarde du téléphone | Le désactiver, ou exclure le stockage des jetons |
| **T-05** | Mobile, code court ([code_court_controller.dart:65](mobile/lib/auth/code_court_controller.dart#L65)) | Le compteur d'erreurs du code court survit à une connexion par mot de passe : l'agent a ensuite moins d'essais que prévu | Remettre le compteur à zéro après une connexion par mot de passe |
| **T-06** | Site, cloche des alertes ([AlertesCloche.jsx:11](frontend/src/components/AlertesCloche.jsx#L11)) | Chaque son ouvre un contexte audio jamais fermé. Sur une longue journée, les ressources s'accumulent et le son peut cesser | Un seul contexte réutilisé, ou le fermer après le son |
| **F-04** | Site ([ChauffeurDashboard.jsx:155](frontend/src/pages/ChauffeurDashboard.jsx#L155)) | Le message de démarrage est coupé au deuxième « : ». Par exemple, « car bloqué : visite technique » perd sa fin | Couper au premier « : » seulement |
| **T-08** | Site, cloche des alertes ([AlertesCloche.jsx:69-74](frontend/src/components/AlertesCloche.jsx#L69-L74)) | Depuis la barre du haut à deux étages (§8.9 de l'analyse métier), le panneau des alertes s'ouvre **sur la ligne de navigation** et en cache la partie droite. Il ne se ferme qu'en cliquant de nouveau sur la cloche, ni par un clic ailleurs ni par Échap : « Notes de service », par exemple, ne répond plus. C'est la cause du seul parcours Chrome en échec | Fermer le panneau par un clic à l'extérieur, par Échap et au changement de page |
| **T-07** | Serveur ([core/serializers.py:152-157](transpt1/core/serializers.py#L152-L157)) | Passer un membre de l'équipe d'une gare de guichetier à bagagiste est refusé : il faut le retirer de l'équipe, puis l'y remettre | **À décider** (règle d'intégrité) : autoriser le changement entre postes d'équipe, ou laisser tel quel |

### Dette technique (sans effet visible aujourd'hui)

- La liste des pages permises avec un mot de passe provisoire est écrite en dur
  ([authentification.py:12](transpt1/core/authentification.py#L12)). Un nouvel écran nécessaire à ce moment-là sera oublié,
  et la panne rejoindra T-01.
- `/configuration/moi/` fait quelques requêtes de trop à chaque chargement.
- Les sondes d'essai (`transpt1/zz_probe/`, `transpt1/sonde_*.json`) traînent dans l'arborescence et sont lancées avec la suite.
  Il faut les ranger dans `role_coverage_tests/` ou les retirer.

## 5. Risques hors code

| # | Constat | Effet | Proposition |
|---|---|---|---|
| **R1** | **152 entrées non commitées** (dont 61 nouveaux fichiers ou dossiers) depuis le dernier commit du 2 novembre : P1, guides, boutons, charte et rapports | Une seule copie, sur ce disque | Commiter par lot, quand vous le demandez |
| **R2** | Le dépôt `sallabou5832-commits/transport` est **public** (vérifié). Aucun secret n'y est suivi : `.env` et `key.properties` sont ignorés et n'ont jamais été commités. Le mot de passe de démonstration y est visible, mais sa commande refuse de tourner hors développement | Le code et la logique métier sont lisibles par tous | À vous de décider : passer le dépôt en privé, ou le laisser public |
| **R9** | La base de développement `transport_coord` a **53 migrations non appliquées** (alertes, audit, billetterie, colis…) | Le serveur de développement lancé sur elle échouera | Appliquer les migrations, avec votre accord, après une sauvegarde |
| **R3** | Le mobile n'a **jamais été essayé sur un vrai téléphone** | Le pilote repose sur lui ; les bugs graves ci-dessus touchent tous le mobile | Un essai sur un téléphone Android après le lot de corrections du mobile |

## 6. Manques

| Domaine | Ce qui manque |
|---|---|
| Plan du §6 de l'analyse métier | **P2a** (réglages métier), **P2b** (organisation), **P3** (billetterie du secteur), **P4** (caisse), **P5** (exploitation), **P6** (roulant et sécurité), **P7** (colis), **P8** (technique), **P9** (RH, finance, juridique, données). Aucun n'est commencé ; P1 est fait |
| Formation | Le parcours de formation par poste existe côté serveur, **sans écran** (O-13, lot P9) |
| Mobile | Aucun écran pour le **contrôleur**, le **bagagiste** ni le **mécanicien**. Côté chauffeur, il manque le signalement d'incident, le relais et le démarrage. Le reste se fait sur le site |
| Plateforme | Le superadmin ouvre une compagnie depuis l'**administration Django** : pas d'écran d'ouverture (lot P9) |
| Intégrations | SMS en **simulation** ; flux de la tutelle **générés, pas transmis** ; pas de notifications poussées (P9) |
| Montée en charge | Les écrans rechargent des listes entières chaque minute (F-03, R8) ; la gamification recalcule ses classements à chaque consultation (E-05) |
| Sécurité | Révocation des jetons (D-07), politique CSP, cache partagé pour la limitation des connexions, double authentification pour la direction et la finance |
| Langue | Français seulement (O-08, à traiter avec un besoin réel) |
| Décisions en attente | O-01 (deux gares du même nom), O-02 (places réduites sous les billets vendus), O-03 (chef de gare qui crée une gare par l'API), O-04 (ci-dessus), O-07 (comptes gérés par le DRH, coupé par défaut), D-06 (configuration non bornée à la gare), C-07 (fausses alertes d'assurance expirée), C-08 |

## 7. Ce qui est solide

- **Cloisonnement entre compagnies** : il est couvert par les sondes et par le contrat des rôles. Seules deux petites fuites de
  nom sont relevées (T-04, O-05), et aucune donnée d'une autre compagnie n'est lisible.
- **Contrat site–serveur et boutons** : chaque action d'écriture est appelée par un écran ou exclue avec un motif. Un test le
  vérifie, ce qui empêche d'oublier un bouton à l'avenir.
- **Erreurs serveur** : les erreurs métier répondent 400 ou 409, et non 500 (travail du 31 octobre).
- **Production** : les réglages de sécurité s'activent hors développement, et les commandes de démonstration y sont bloquées.
- **Règlement intérieur, guides par rôle et charte par pôle** : ils sont en place et testés, site et mobile concordants.

## 8. Ordre proposé

| Lot | Contenu | Pourquoi d'abord | Taille |
|---|---|---|---|
| **A : mobile, ventes et sécurité** | T-01, G-02, G-03, T-02 (côté mobile), G-01, G-04, G-06, T-05 | Ventes payées perdues et freins classés « OK » | M |
| **B : site, robustesse** | T-08, F-15, F-16, F-02, F-05, F-04, T-02 (côté site), T-06 | Pages blanches, double vente, GPS bloqué | M |
| **C : serveur** | DRF 3.18.2, T-03, liste du mot de passe provisoire | Faille connue d'une dépendance, traçabilité | S |
| **D : à décider avant de coder** | O-04, T-07, T-04, O-05, R2 | Règles d'intégrité et confidentialité : votre choix d'abord | S |
| **E : hygiène** | Commits par lot (R1), migrations de la base de développement (R9), sondes rangées, découpage du site par page (F-09), outils de développement à jour | Sécuriser le travail et l'environnement | S |
| **Ensuite** | Plan du §6 : P2a, puis P2b, etc. ; essai sur téléphone (R3) après le lot A | | |

## 9. Suivi des corrections

### 4 novembre : T-08 et lot A (accord du propriétaire : « go »)

| # | Correction | Vérification |
|---|---|---|
| **T-08** | Le panneau des alertes s'accroche sous toute la barre du haut, et la navigation reste cliquable. Il se ferme par la cloche, Échap, un clic ailleurs ou un changement de page ([AlertesCloche.jsx](frontend/src/components/AlertesCloche.jsx), [index.css](frontend/src/index.css)) | Parcours « secrétariat » réussi ; tests du site (54) et analyse propres |
| **T-01** | Le serveur donne un code à son refus « mot de passe provisoire » (`"code": "mot_de_passe_provisoire"`, [authentification.py](transpt1/core/authentification.py), [exceptions.py](transpt1/core/exceptions.py)). Le mobile n'envoie rien tant que le mot de passe est provisoire, et un tel refus laisse la vente en file au lieu de la marquer refusée ([sync_service.dart](mobile/lib/sync/sync_service.dart)) | Tests serveur (code dans la réponse) et mobile (file gardée, puis tout part après le changement) |
| **G-02** | Le mobile lit le tarif de la ligne et le garde pour le hors ligne. Le prix s'affiche et ne se modifie pas ; la vente part sans prix et le serveur applique le tarif, comme sur le site ; la dictée ne demande plus le prix ([depart_repository.dart](mobile/lib/data/depart_repository.dart), [vente_ticket_screen.dart](mobile/lib/ui/vente_ticket_screen.dart)) | Tests en ligne et hors ligne : la vente en file part sans prix et passe |
| **G-03** | La dictée lit la négation : un accord nié (« pas bon », « c'est pas ok ») donne un défaut. Un défaut nié seul (« pas de défaut ») ne vaut pas « OK » : l'agent reprend au clavier. Une confirmation niée (« je valide pas ») devient un refus. Pluriels et féminins reconnus ([voice_text.dart](mobile/lib/voice/voice_text.dart)) | 8 nouveaux tests (24 phrases), dont tous les cas dangereux |
| **T-02** (mobile) | `/api/configuration/moi/` dit si la vente au guichet est ouverte (`vente_au_guichet`). En billetterie externe, l'accueil du guichetier et l'écran de vente ne la proposent plus ; ce réglage est relu à chaque ouverture de l'écran et gardé hors ligne | Tests serveur (les trois modes, autre compagnie intacte) et mobile |
| **G-01** | Une erreur serveur (5xx, 408, 429) pendant le renouvellement du jeton ne ferme plus la session : l'appel échoue comme une erreur passagère ([api_client.dart](mobile/lib/api/api_client.dart)) | Test : jetons gardés, aucune déconnexion |
| **G-04** | Une seule vérification GPS à la fois ; un suivi ne démarre plus après une déconnexion survenue pendant la demande d'autorisation ([trip_gps_controller.dart](mobile/lib/gps/trip_gps_controller.dart)) | Deux tests : un seul abonnement, aucun après la déconnexion |
| **G-06** | Ni sauvegarde dans le cloud, ni transfert vers un autre appareil (`allowBackup="false"`, règles d'extraction pour Android 12 et plus) | APK de débogage compilé ; son manifeste porte `allowBackup=false`, `fullBackupContent=false` et les règles d'extraction (lu par `aapt2`) |
| **T-05** | Les erreurs de code court sont oubliées après une connexion par mot de passe ; une session reprise les garde | Deux tests |

**Vérification complète du lot** :

| Vérification | Résultat |
|---|---|
| Suite serveur complète | **5 159 réussis**, 1 ignoré |
| Mobile | **270 tests réussis** (21 nouveaux) ; `flutter analyze` propre ; APK de débogage compilé |
| Site | 54 tests unitaires ; analyse propre |
| Parcours Chrome | **22 sur 22** |

Le premier passage complet des parcours Chrome a montré une fragilité du **script d'essai** « guide », pas de l'application. Le script lisait le titre de la fiche juste après un clic, avant que la page ne se redessine. Il attend maintenant la fiche voulue ([scenarios.mjs](frontend/e2e/scenarios.mjs)).

Ce qui reste du lot A :

- **T-02, côté site** : le formulaire du guichetier reste affiché en billetterie externe. C'est au lot B ; la donnée `vente_au_guichet` est prête.
- **Une vente refusée ne peut pas être renvoyée**, seulement supprimée ([pending_actions_screen.dart](mobile/lib/ui/pending_actions_screen.dart)). Un bouton « Renvoyer » serait un filet de plus. C'est une proposition, non faite.
- **Changement de tarif pendant le hors ligne** : si le tarif change pendant qu'une vente attend en file, le serveur enregistre le nouveau tarif. C'est le comportement du site ; c'est plus rare que l'ancien refus et ne perd pas la vente.

## 10. Limites de l'analyse

- Aucun essai sur un vrai téléphone ni sous charge réelle : G-04, T-06 et la montée en charge sont lus dans le code, pas
  reproduits.
- La revue de code a porté sur les changements en cours. Le code plus ancien a été couvert par les audits précédents, relus
  point par point, et non par une nouvelle revue ligne à ligne.
- Les vulnérabilités sont celles que connaissent `pip` et `npm audit` aujourd'hui.
