# Rapport d'anomalies — revue complète du dépôt (31 octobre 2026)

Revue demandée : étudier le projet en profondeur, vérifier chaque ligne de code, corriger, puis rendre compte. Ce document est la
**première partie** : ce qui a été détecté. Rien n'a encore été corrigé dans le code : chaque correction « importante » attend
l'accord du propriétaire (voir §6). Les statuts seront mis à jour au fur et à mesure.

Légende de gravité : **HAUT** = casse un garde-fou métier ou de sécurité documenté, expose des données confidentielles, ou
bloque la CI · **MOYEN** = bug réel et reproductible à impact limité, écart avec `PERMISSIONS.md`, robustesse ·
**BAS** = amélioration, cosmétique, risque théorique · **INFO** = constat sans action immédiate.
Preuve : **[reproduit]** = rejoué par un test jetable (échec observé) · **[lu]** = relevé à la lecture du code, non rejoué ·
**[outil]** = relevé par un outil automatique.

## 1. Périmètre et méthode

| Zone | Lignes | Lecture |
|---|---|---|
| Backend Django (`transpt1/`, hors tests et migrations) | ≈ 18 200 | **Tout le code de production lu**, sauf les données statiques (`rh/fiches_types.py`, `formation/parcours_de_base.py`, `seed_demo_tableaux.py`) parcourues par échantillon |
| Tests backend + `role_coverage_tests` | ≈ 19 900 | Exécutés (4 439) ; lus par échantillon (pas ligne à ligne) |
| Migrations | ≈ 2 400 | Vérifiées par `makemigrations --check` (aucune dérive) |
| Frontend React (`frontend/src`, hors CSS) | ≈ 13 800 | Socle, hooks, 30 pages et ≈ 40 composants lus en entier ; une vingtaine de composants d'affichage passés à l'analyse automatique (oxlint règles React, accessibilité, motifs à risque) |
| Appels API du frontend | 264 | **Tous recoupés avec les vraies routes Django** (script) : 0 route inexistante, 0 méthode interdite |
| Mobile Flutter (`mobile/lib`, Android) | ≈ 4 200 | Tout lu |
| Intégration continue, `e2e/`, scripts, déploiement, docs | — | Lus |

Moyens complémentaires : `manage.py check`, `check --deploy`, `makemigrations --check`, suite pytest complète, vitest, `npm run build`,
`oxlint` (règles React, accessibilité, code suspect), `npm audit`, `flutter analyze`, `flutter test`, une vingtaine de **sondes jetables**
(tests écrits pour reproduire chaque soupçon ; supprimés ensuite, rien n'est resté dans le dépôt).

## 2. État de référence (avant toute modification)

| Contrôle | Résultat |
|---|---|
| `manage.py check` / `check --deploy` / `makemigrations --check` | OK / OK / aucune migration manquante |
| pytest (backend) | **4 434 réussis, 4 échecs, 1 ignoré** en 34 min — les 4 échecs sont dans `dashboard/tests/test_carte_consumer.py` (voir A-04) |
| vitest (frontend) | 42 tests réussis mais **1 suite en échec** (`e2e/example.spec.ts`, voir A-02) |
| `npm run build` / `oxlint` | OK (bundle unique de 567 ko) / 1 avertissement (`AuthContext.jsx:52`) |
| `flutter analyze` / `flutter test` | 0 problème / **209 tests réussis** |
| `npm audit` | 3 vulnérabilités dans l'outillage de développement (vite, vitest) — voir A-05 |
| `pip-audit` (`requirements.txt`) | 5 vulnérabilités dans 2 paquets (`djangorestframework` 3.18.1, `pyjwt` 2.14.0) — voir A-10 |

## 3. Synthèse

| Domaine | HAUT | MOYEN | BAS | INFO |
|---|---:|---:|---:|---:|
| A. Dépôt, CI, environnement | 3 | 3 | 2 | 2 |
| B. Backend — réponses 500 (robustesse) | 1 | 6 | 3 | 0 |
| C. Backend — intégrité métier | 2 | 5 | 6 | 0 |
| D. Backend — sécurité, confidentialité, permissions | 2 | 6 | 4 | 1 |
| E. Backend — qualité, performance, sauvegardes | 0 | 0 | 7 | 1 |
| F. Frontend | 0 | 8 | 6 | 2 |
| G. Mobile | 2 | 2 | 2 | 1 |
| H. Documentation | 0 | 0 | 4 | 0 |
| **Total (81 constats)** | **10** | **30** | **34** | **7** |

**Les 10 points à traiter en premier** : A-01 (environnement entier indexé dans git), A-02 (CI frontend rouge), A-04 (tests WebSocket
instables), C-01 (sorties de pièces modifiables sans recalcul du stock), C-02 (la clôture d'un ordre de réparation lève de fait
un blocage du QHSE), D-01 (le journal d'audit expose les doléances), D-02 (code de retrait de colis en clair dans la base),
B-03 (suppressions qui renvoient une erreur 500), G-01 (le mobile déconnecte l'utilisateur sur une erreur serveur), G-02 (le mobile
ignore le tarif de la ligne).

## 4. Anomalies détectées

### A. Dépôt, CI et environnement

| # | Gravité | Constat | Preuve |
|---|---|---|---|
| A-01 | HAUT | `venv/` (racine) est **entièrement dans l'index git** (11 721 fichiers : paquets Python et `.pyc`) ; le `.gitignore` racine ne contient que `.claude/`. Un `git commit` embarquerait l'environnement entier. Seul `transpt1/venv/` est ignoré, par `transpt1/.gitignore`. | [outil] `git ls-files venv` = 11 721 |
| A-02 | HAUT | `npm test` **échoue** : Vitest ramasse `frontend/e2e/example.spec.ts` (fichier Playwright) → « Playwright Test did not expect test() to be called here ». Le job `frontend` de la CI est donc rouge. | [reproduit] `1 failed \| 5 passed` |
| A-03 | MOYEN | L'échafaudage Playwright ajouté (indexé, non commité) est cassé et redondant : `example.spec.ts` vise `input[name="username"]` qui n'existe pas dans la page de connexion ; `playwright.config.ts` déclare 3 navigateurs à télécharger alors que le projet a choisi de n'en télécharger aucun ; `@playwright/test` et `@types/node` doublonnent `playwright-core` ; rien ne les relie aux scripts npm ni à la CI. | [lu] |
| A-04 | HAUT | **Tests WebSocket instables** (`test_carte_consumer.py`) : 2 à 4 échecs sur 14, différents à chaque exécution (`TimeoutError` sur `communicator.connect()`, délai par défaut de 1 s trop court pour ouvrir une connexion PostgreSQL neuve), 205 s pour 14 tests. La CI rouge au hasard fait perdre toute confiance dans les vrais échecs. | [reproduit] 4 échecs en suite complète, 2 autres en isolation |
| A-05 | MOYEN | Dépendances de développement vulnérables : `vite` 8.3.0–8.3.2 (sévérité haute : serveur de développement) et `vitest` 5.0.0–5.0.2 ; `npm audit fix` disponible. N'affecte pas le site compilé. | [outil] `npm audit` |
| A-06 | BAS | Deux modifications **non indexées** parasites : `mobile/lib/data/loaded.dart` (un espace en fin de fichier, sans retour à la ligne) et `mobile/lib/data/feuille_repository.dart` (le filtre de sécurité `f['chauffeur'] == user.id`, que le commentaire juste au-dessus déclare conservé, a été supprimé ; il reste une ligne blanche avec espaces). | [lu] `git diff` |
| A-07 | BAS | `transpt1/deploy/sauvegarde-windows.ps1` est supprimé (dans l'index) mais toujours cité par `DEPLOIEMENT.md` §3 et `CARTE_DU_CODE.md`. | [lu] |
| A-08 | INFO | 41 fichiers (≈ 1 200 lignes) sont indexés mais **non commités** : pagination, filtres de feuilles de route, tests WebSocket, Playwright, migration `reseau 0007`, etc. | [outil] `git status` |
| A-09 | INFO | Deux environnements virtuels coexistent : `transpt1/venv/` (utilisé par les essais de bout en bout) et `venv/` à la racine (sans `pytest` au départ). | [outil] |
| A-10 | MOYEN | **`djangorestframework` 3.18.1 est vulnérable** (correctif en 3.18.2) : CVE-2026-114138 — un en-tête `Accept` de ≈ 780 ko garde un processus occupé ≈ 19 s, sans authentification ; CVE-2026-114136 — un `charset` de compression dans `Content-Type` fait allouer ≈ 97 Mio de mémoire à partir d'une requête de 108 octets, sans authentification, sur tout point d'entrée JSON (dont la connexion). La troisième faille (CVE-2026-114137, `TokenProxy.delete`) ne concerne pas le projet (`rest_framework.authtoken` non installé). `pyjwt` 2.14.0 → 2.15.0 corrige deux failles qui ne concernent pas ce projet (`PyJWKClient` et import de clés JWK privées, non utilisés ; un en-tête de jeton imbriqué est bien rejeté en `DecodeError`). | [outil] `pip-audit` ; [reproduit] PyJWT |

### B. Backend — réponses 500 (robustesse)

Le serveur doit répondre 400/404/409 avec un message clair, jamais 500.

| # | Gravité | Constat | Preuve |
|---|---|---|---|
| B-01 | MOYEN | `POST /api/auth/login/` avec un corps JSON qui n'est pas un objet (`[1,2]`) → **500** (`'list' object has no attribute 'get'` dans `core/throttles.py:37`), sans authentification. | [reproduit] |
| B-02 | MOYEN | `core.dates.lire_date` ne tolère pas une valeur non textuelle venue d'un corps JSON : `POST /clotures-caisse/ {"date": 123}` et `POST /factures/{id}/payer/ {"date": 20260101}` → **500** (`TypeError`). | [reproduit] ×2 |
| B-03 | HAUT | Aucune gestion de `ProtectedError` : `DELETE /gares/{id}/` d'une gare utilisée par une ligne, `DELETE /departs/{id}/` dont la feuille a un contrôle, `DELETE /incidents/{id}/` lié à un sinistre, `DELETE /obligations-formation/{id}/` dès qu'une session est enregistrée → **500**. | [reproduit] ×3 |
| B-04 | MOYEN | `parse_date` appelé directement (date bien formée mais impossible, `2030-13-45`) → **500** : `lignes/{id}/changement/`, `agenda/?du=`, et `plans-entretien/{id}/realise/` (même motif, à la lecture). Le correctif existe déjà (`lire_date`) mais n'est pas utilisé là. | [reproduit] ×2, [lu] ×1 |
| B-05 | BAS | Une vingtaine de filtres font `.isdigit()` puis `int()` : le caractère « ² » passe le premier test et fait échouer le second → 500 (reseau ×2, colis, personnel_roulant ×4, billetterie, supports, maintenance ×3, rh ×2, finance, dashboard). | [reproduit] ×2 |
| B-06 | MOYEN | Contrôle à bord : un code de billet de plus de 32 caractères, un nombre de voyageurs hors limites, une charge `NaN` ou trop grande → **500** (`DataError`, `InvalidOperation`) : les nombres sont lus à la main, hors du sérialiseur. | [reproduit] ×4 |
| B-07 | BAS | Validations JSON par `set(valeur)` : `modeles-juridiques` avec `poles=[[1]]`, `configuration/postes` avec `fonctions_desactivees=5` → **500**. | [reproduit] ×2 |
| B-08 | MOYEN | `suivi.diffuser_position` : si la couche de canaux (Redis) est en panne, la requête renvoie 500 **après** avoir enregistré les positions ; le client rejoue le lot → doublons. | [lu] |
| B-09 | BAS | `SUIVI_SEUIL_FATIGUE_MINUTES=0` provoque une division par zéro dans `generer_alertes` (toutes les règles suivantes sautent). | [lu] |
| B-10 | MOYEN | `audit/signals.py` : l'écriture du journal est entourée d'un `except Exception` mais sans savepoint ; une erreur SQL (valeur trop longue, caractère nul dans un texte) dans un bloc `atomic` laisse la transaction cassée, et les requêtes suivantes échouent. | [lu] |

### C. Backend — intégrité métier

| # | Gravité | Constat | Preuve |
|---|---|---|---|
| C-01 | HAUT | `PATCH` et `DELETE /sorties-pieces/{id}/` réussissent (200/204) pour le magasinier, le chef d'atelier et le directeur technique **sans recalculer le stock** (stock 7 avant et après). `PERMISSIONS.md` §4 : « ni modification ni suppression après coup ». Le test existant ne vérifie que le refus (403) du mécanicien. | [reproduit] |
| C-02 | HAUT | Clôturer un ordre de réparation remet **toujours** le véhicule « disponible », même quand un blocage du QHSE reste actif : le pouvoir de blocage est contournable par l'atelier. Ensuite, le QHSE ne peut plus rebloquer le véhicule : **500** (`un_blocage_actif_par_vehicule`). | [reproduit] |
| C-03 | MOYEN | Porte de sécurité sensible à la casse : `FeuilleDeRoute.peut_demarrer` teste `item__in=ITEMS_SECURITE` (exact) alors que `est_item_securite` ignore casse et espaces. Un défaut « Freins » bloque le véhicule, mais une fois celui-ci débloqué, `peut_demarrer` redevient vrai (« freins » : faux comme attendu). | [reproduit] |
| C-04 | MOYEN | Un mécanicien peut, par `PATCH` sur son propre ordre, changer le **véhicule** et (selon `reaffecter` réservé) le **mécanicien**, et supprimer l'ordre (204). | [reproduit] véhicule et suppression ; mécanicien : voir D-bis ci-dessous |
| C-05 | MOYEN | Un chauffeur peut supprimer sa propre feuille de route (204, cascade sur checklists, pauses, positions, relais) et son incident (500 s'il a un sinistre). Perte de traçabilité. | [reproduit] |
| C-06 | MOYEN | `FactureViewSet.payer` sans verrou : deux requêtes simultanées créent deux dépenses pour la même facture. | [lu] |
| C-07 | MOYEN | Assurances : `alertes.generation.assurances_proches`, le compteur du tableau de bord de la direction et `/assurances/echeance-proche/` comptent comme expirées les polices **remplacées** par une plus récente, alors que le tableau de conformité ne retient que la plus récente → fausses alertes critiques (« expirée depuis 400 jours »). | [lu] |
| C-08 | BAS | `Sinistre.incident` est une clé étrangère non unique : « un seul sinistre par incident » n'est garanti que par le sérialiseur (`get_or_create` peut dupliquer sous concurrence). | [lu] |
| C-09 | BAS | Supprimer un sinistre supprime ses pièces en base mais laisse leurs fichiers sur disque. | [lu] |
| C-10 | BAS | Le kilométrage d'un véhicule peut être diminué (PATCH), ce qui fausse les échéances d'entretien. | [lu] |
| C-11 | BAS | `DepartSerializer.validate_chauffeur` accepte un chauffeur désactivé, alors que `disponibilites()` l'exclut. | [lu] |
| C-12 | BAS | `OrdreReparation.save` : condition redondante (`in (A, B) and != B`, soit `== A`). | [lu] |
| C-13 | BAS | Latitude/longitude des gares et des incidents sans bornes (−90/90, −180/180) ; seules les positions GPS sont validées. | [lu] |

### D. Backend — sécurité, confidentialité, permissions

| # | Gravité | Constat | Preuve |
|---|---|---|---|
| D-01 | HAUT | Le **journal d'audit** copie les champs des objets tracés dans `changements` et se lit par le QHSE, le secrétaire général et le PDG. Il expose donc le texte complet d'une doléance **et l'identité de son déposant**, ainsi que les motifs disciplinaires et notes RH — alors que `PERMISSIONS.md` §20 et l'écran « Médiation sociale » affirment que « même la hiérarchie et le PDG ne les lisent pas ». | [reproduit] |
| D-02 | HAUT | Le **code de retrait d'un colis** est stocké en clair dans `NotificationLog.contenu` (« Code de retrait : JTSK2C »), alors que le modèle et la documentation affirment qu'il n'existe qu'en empreinte. Lisible dans l'administration, dans les sauvegardes. | [reproduit] |
| D-03 | MOYEN | `GET /clotures-caisse/` (liste) : le chef de gare voit les clôtures de **toutes** les équipes (l'action `etat`, elle, filtre correctement). `PERMISSIONS.md` : « le chef de gare, celles de son équipe ». Non couvert par les tests. | [reproduit] |
| D-04 | BAS | Un chef de gare peut **créer** une gare (201), y compris sans en être le chef (`chef` vide ou un autre chef de gare) : `CanManageOwnGare` ne contrôle que la modification et la suppression. Le comportement est fixé par `test_role_coverage.py:125`, alors que `PERMISSIONS.md` §1 écrit « créer / modifier / supprimer … uniquement la gare qu'il dirige » : décision métier, aucun correctif sans votre accord. | [reproduit] |
| D-05 | MOYEN | Export CSV : les libellés, noms de ligne et de fournisseur sont écrits tels quels ; une valeur commençant par `=`, `+`, `-` ou `@` s'exécute comme formule dans Excel (injection de formule). Un chef de ligne peut ainsi piéger l'export du directeur financier. Même défaut dans l'export fabriqué côté navigateur (`FinanceDashboard`). | [reproduit] serveur |
| D-06 | MOYEN | Configuration hiérarchique non bornée à la gare : un chef de gare règle les guichetiers et bagagistes de **toutes** les gares (peut désactiver `vente_ticket` partout). À trancher avec le métier. | [lu] |
| D-07 | MOYEN | Le jeton de renouvellement n'est jamais révoqué : la déconnexion n'efface que les jetons du navigateur, pas de rotation ni de liste noire (valable 1 jour). | [lu] |
| D-08 | MOYEN | L'adresse du client est la dernière entrée de `X-Forwarded-For` : falsifiable si Django est joignable sans passer par le proxy, ce qui contourne la limitation des connexions et fausse le journal. Documenté dans `DEPLOIEMENT.md` §6. | [lu] |
| D-09 | BAS | Le jeton d'accès voyage dans l'URL du WebSocket ; le journal d'accès **de Daphne** (activé par défaut) l'écrit, ce que `DEPLOIEMENT.md` n'évoque que pour le proxy. | [lu] |
| D-10 | BAS | `tutelle.CompteTutelle` (clés d'API des organismes) n'est pas dans le registre d'audit. | [lu] |
| D-11 | INFO | La description libre d'un incident grave est transmise telle quelle à la tutelle (données personnelles possibles). | [lu] |
| D-12 | BAS | Le téléphone d'un ticket n'est pas validé (contrairement aux colis) : la confirmation SMS d'un numéro invalide se perd silencieusement. | [lu] |
| D-bis | MOYEN | Un mécanicien peut réassigner son ordre à un collègue par `PATCH {"mecanicien": …}` (200, contourne `reaffecter` réservé au directeur technique et au chef d'atelier). | [reproduit] |

### E. Backend — qualité, performance, sauvegardes

| # | Gravité | Constat |
|---|---|---|
| E-01 | BAS | `core/sauvegarde.trouver_outil` classe les versions de PostgreSQL comme du texte (« 9.6 » > « 17 »). |
| E-02 | BAS | `sauvegarde_base --verifier` ignore `SAUVEGARDE_ADMIN_USER/PASSWORD`, contrairement à `verifier_sauvegarde`. |
| E-03 | BAS | `verifier()` compare le nombre de tables à la base vivante : faux échec si une migration a été appliquée depuis la sauvegarde. |
| E-04 | BAS | `finance.analyses.tresorerie` : une centaine de requêtes (3 par jour sur 30 jours). |
| E-05 | BAS | `GET /gamification/moi/` écrit en base et, pour un chef de gare, recalcule le classement de toutes les gares du mois — appelé toutes les 60 s par chaque utilisateur connecté ; `vue_des_agents` et `classement` coûtent ≈ 15 requêtes par agent. |
| E-06 | BAS | Missions « passives » (`zero_rupture`, `zero_incident_en_retard`) accomplies sans aucune activité ; les points d'« incident traité » se gagnent par va-et-vient ouvert/traité. |
| E-07 | BAS | `notifier_vente_ticket` formate l'heure sans conversion de fuseau (exact aujourd'hui car Abidjan = UTC+0 ; fragile). |
| E-08 | INFO | Pas de `CONN_MAX_AGE` : chaque appel `database_sync_to_async` (WebSocket) ouvre une connexion PostgreSQL. |

### F. Frontend

| # | Gravité | Constat |
|---|---|---|
| F-01 | MOYEN | `useChargement` : aucune annulation, une réponse tardive d'une ancienne clé (période, recherche, classement) écrase la plus récente. |
| F-02 | MOYEN | Vente de ticket (guichetier) et enregistrement de colis (bagagiste) sans `Idempotency-Key`, alors que le serveur la gère : un nouvel essai après coupure double la vente et le SMS. |
| F-03 | MOYEN | Les tableaux de bord téléchargent **toute** la table (tickets, départs, feuilles de route, colis) à chaque chargement, certains chaque minute : ne tient pas la charge (le serveur sait paginer, aucun écran ne s'en sert). |
| F-04 | MOYEN | `ChauffeurDashboard.jsx:136` : `split(':', 2)` tronque tout message d'erreur contenant « : » (ex. « …raison de sécurité : la feuille de route ne peut pas démarrer. » perd sa suite). |
| F-05 | MOYEN | Suivi GPS web (`SuiviTrajet`) : le tampon est renvoyé en bloc ; au-delà de 500 positions (≈ 8 min hors réseau) ou avec un seul relevé invalide, le serveur répond 400 à chaque essai et **plus aucune position ne part**. Le mobile, lui, abandonne le lot refusé. |
| F-06 | MOYEN | 11 suppressions sur 12 (factures, dépenses, budgets, contrats, mesures disciplinaires, évaluations, modèles juridiques, pièces de sinistre, équipes, formations, notes) se font sans confirmation. |
| F-07 | BAS | `AuditPage` : « Charger plus » applique des filtres non validés ; 16 types d'objets filtrables sur 60 tracés ; les valeurs-objets s'affichent « [object Object] ». |
| F-08 | BAS | `apiTelecharger` et l'export de `FinanceDashboard` révoquent l'URL du fichier juste après le clic (peut interrompre le téléchargement). |
| F-09 | BAS | Bundle JS unique de 567 ko (aucun découpage par route). |
| F-10 | BAS | Accessibilité : ≈ 20 `<th />` vides, `role` à la place de balises sémantiques, `autoFocus`. |
| F-11 | BAS | `AuthContext` : avertissement `only-export-components`, valeur de contexte recréée à chaque rendu, jetons posés avant le succès de `/auth/me/`. |
| F-12 | BAS | Dates `min` calculées en UTC (`DemandeLigne`, `LignesFermeture`) ; `AudioContext` jamais fermé ; liste des 18 postes dupliquée 3 fois ; logique « agir » dupliquée dans ≈ 25 composants. |
| F-13 | INFO | `QhseDashboard` ne se rafraîchit pas seul (les autres tableaux de bord oui). |
| F-14 | INFO | Jetons en `localStorage` et aucune politique CSP : un défaut XSS leur donnerait accès. |
| F-15 | MOYEN | **Aucun filet d'erreur de rendu** (pas de `ErrorBoundary`) alors que ≈ 40 composants lisent un dictionnaire par une valeur venue de l'API (`DEGRES[s.degre].ton`, `ETATS_FORMATION[ligne.etat].ton`, `GRAVITES_DOLEANCE[l.gravite].ton`…). Une valeur inattendue (nouvel état ajouté côté serveur, donnée ancienne) fait lever une exception au rendu : React démonte alors **toute** l'application, page blanche, sans message ni bouton de déconnexion. |
| F-16 | MOYEN | Une date-heure mal tapée fait lever `RangeError: Invalid time value` : le champ `datetime-local` accepte une année à 5 chiffres (`20266-10-31T10:00`) que `new Date(x).toISOString()` refuse. Dans `PlanificationDepart` l'appel est fait **pendant le rendu** → page blanche (voir F-15) ; dans l'agenda du secrétariat (`SecretariatPage.jsx:148`) et la réaffectation du chef de ligne (`ChefLigneDashboard.jsx:81`) il est fait avant le `try` → rejet non géré, l'utilisateur ne voit aucun message. | [reproduit] `node` (V8) |

### G. Application mobile

| # | Gravité | Constat |
|---|---|---|
| G-01 | HAUT | Une erreur serveur (5xx) pendant le renouvellement du jeton (`ApiClient._doRefresh`) ou au démarrage (`AuthController.restore`) **efface la session** et déconnecte l'utilisateur ; le site web, lui, garde ses jetons. Un chauffeur en zone instable est expulsé et ne peut pas se reconnecter si le serveur est en panne. |
| G-02 | HAUT | Le mobile ignore le **tarif de la ligne** (aucune occurrence de « tarif » dans `lib/`). Le guichetier saisit un prix ; une vente hors ligne à un autre prix est acceptée sur le téléphone puis **refusée à la synchronisation**, voyageur déjà payé. Le cahier des charges demande un « tarif automatique ». |
| G-03 | MOYEN | Commande vocale : les négations ne sont pas comprises. « Freins pas bons » / « pas OK » → état **OK** (item de sécurité) ; « ne confirme pas » → vente **confirmée** ; si « confirmer » et « annuler » sont dits ensemble, « confirmer » l'emporte. |
| G-04 | MOYEN | `TripGpsController` : deux vérifications rapprochées (retour de la fenêtre d'autorisation) peuvent lancer deux abonnements GPS (fuite, relevés en double). |
| G-05 | BAS | Les dépôts de données téléchargent l'historique complet des départs et font 3 appels de détail alors que la feuille de route porte déjà ligne et véhicule. |
| G-06 | BAS | `AndroidManifest` : `allowBackup` laissé à sa valeur par défaut (la base chiffrée entre dans les sauvegardes Android). |
| G-07 | INFO | `gradle.properties` : `-Xmx8G` sur une machine de 7,9 Go de mémoire. |

### H. Documentation

| # | Gravité | Constat |
|---|---|---|
| H-01 | BAS | `PERMISSIONS.md` §11 : « trois essais erronés » ; le code (et `CARTE_DU_CODE.md`) : cinq. |
| H-02 | BAS | `DEPLOIEMENT.md` périmé : « pas de moteur vocal », « suivi GPS par le navigateur seulement », « mobile sans GPS », « flutter test non relancé » alors que le mobile a la voix et le GPS en arrière-plan et que les 209 tests passent. |
| H-03 | BAS | Références au fichier supprimé `sauvegarde-windows.ps1` (voir A-07). |
| H-04 | BAS | `CARTE_DU_CODE.md` §3.6 : « les 10 scénarios » (il y en a 14) et `lib.mjs` décrit comme « connexion, attente, capture » (il contient les outils de processus et de navigateur ; la connexion est dans `scenarios.mjs`). |

## 5. Ce qui est sain (constaté)

- Les 264 appels API du site correspondent à des routes et méthodes réelles ; aucun `dangerouslySetInnerHTML`, `eval`, `console.log`.
- Cloisonnement par compagnie, verrouillage des tickets, idempotence des ventes, réservation de places hors ligne, clôture de caisse,
  chiffrement de la base mobile, HTTPS obligatoire en version release : conformes à ce qui est documenté et couverts par des tests.
- `manage.py check --deploy`, migrations, `flutter analyze` : propres.

## 6. Suite

Chaque lot de corrections ci-dessous sera soumis pour accord avant d'être appliqué, puis vérifié (tests ciblés, suite complète à la fin)
avant de passer au suivant :

1. **Hygiène** : A-01, A-02, A-03, A-06, A-07 (git, CI).
2. **Robustesse des réponses** : B-01 à B-10.
3. **Intégrité métier** : C-01 à C-05, D-bis.
4. **Confidentialité et permissions** : D-01 à D-05.
5. **Frontend** : F-01 à F-12, F-15 et F-16.
6. **Mobile** : G-01 à G-06.
7. **Tests, dépendances, documentation** : A-04, A-05, A-10, H-01 à H-03.
8. **À arbitrer plus tard** (hors correctif immédiat) : D-06, D-07, F-03/E-05 (filtres serveur), C-07, C-08.

## 7. Avancement (mis à jour le 31 octobre 2026)

### Lot 2 — Robustesse des réponses : **appliqué et vérifié**

Le serveur répond 400 ou 409 avec un message clair, jamais 500, sur tous les cas relevés. Les garde-fous sont centralisés dans
`transpt1/core/` (voir « Entrées invalides et erreurs » dans `transpt1/README.md`) au lieu d'être refaits vue par vue.

| # | Statut | Correction |
|---|---|---|
| B-01 | corrigé | Corps de connexion qui n'est pas un objet : refusé en 400 par `core/parsers.py` (et `champ_du_corps` côté limitation). |
| B-02 | corrigé | `lire_date` / `lire_date_heure` refusent proprement toute valeur qui n'est pas un texte. |
| B-03 | corrigé | `core/exceptions.py` : `ProtectedError` et `RestrictedError` donnent 409 « Suppression impossible : cet élément est encore utilisé ». |
| B-04 | corrigé | Agenda (`?du=`, `?au=`), `lignes/{id}/changement/`, `plans-entretien/{id}/realise/` passent par `lire_date`. |
| B-05 | corrigé | Les 17 filtres `isdigit()` + `int()` passent par `core.entiers.lire_entier` ; plus aucun `isdigit()` en production. |
| B-06 | corrigé | Contrôle à bord : code de billet > 32 caractères traité comme billet inconnu ; clôture refuse `NaN`, `Infinity` et les nombres hors colonne (400). |
| B-07 | corrigé | `modeles-juridiques` (`poles`), `fiches-poste` (`role`, `roles`), `configuration` (`fonctions_desactivees`) : un élément non textuel donne 400. |
| B-08 | corrigé | `diffuser_position` : une couche de canaux en panne est journalisée, la requête ne répond plus 500 après avoir enregistré les positions. |
| B-09 | corrigé | `seuil_fatigue_minutes()` ne descend jamais sous 1 minute. |
| B-10 | corrigé | L'écriture du journal d'audit est isolée par un savepoint. |
| (nouveau) | corrigé | Relevé par la sonde, absent du premier rapport : un délai estimé démesuré (`prioriser`) ou un kilométrage hors colonne (`realise`) donnait une erreur de base ; le délai est plafonné à 100 000 h (au-delà, le retour estimé dépasse l'an 9999 et fait échouer la file d'attente), le kilométrage à 2 147 483 647. |

Vérifications :

- Suite backend complète (sans la sonde et sans `test_carte_consumer.py`, instable, voir A-04) : **4 497 réussis, 1 ignoré, 0 échec**
  (avant : 4 434 + 4 échecs WebSocket). Les tests ajoutés depuis (contrôle à bord, suivi, savepoint, modèles juridiques) : 165 réussis.
- Nouveaux tests : `core/tests/test_entrees_hostiles.py`, `personnel_roulant/tests/test_robustesse_suivi.py`,
  `audit/tests/test_savepoint.py`, cas ajoutés à `test_controle_ligne.py` et `test_juridique.py`.
- Sonde de fuzz (entrées hostiles sur chaque route et chaque méthode, avec un rôle autorisé trouvé automatiquement) :
  **105 emplacements en 500 avant, 0 après** (45 312 requêtes, 193 routes). Limite : 52 routes de détail n'ont pas pu être
  sondées parce qu'aucun objet d'identifiant 1 n'existe dans les données de démonstration (404 pour tous les rôles) ; elles
  passent par les mêmes analyseur, gestionnaire d'exceptions et aides, mais ne sont pas couvertes directement.

### Lot 1 — Hygiène : **appliqué et vérifié** (1er novembre 2026)

| # | Statut | Constat |
|---|---|---|
| A-01 | corrigé | `venv/` est ignoré par le `.gitignore` racine ; `git ls-files venv` = 0. |
| A-02 | corrigé | Vitest exclut `e2e/` : `npm test` = 5 fichiers, 42 tests réussis. |
| A-03 | corrigé, vérifié | Configuration Playwright réécrite (Chrome installé, aucun navigateur téléchargé), `connexion.spec.ts` et `pile.setup.mjs` ajoutés, script `e2e:pw` et étape de CI ajoutés. `npm run e2e:pw` : **4 essais réussis** en 4,4 min sur la vraie pile (base jetable migrée et garnie, API, site compilé), base supprimée et ports libérés ensuite. Rapport et traces (`playwright-report/`, `test-results/`, `dist-e2e/`) ignorés par git. |
| A-06 | corrigé | Constaté le 1er novembre : la copie de travail ne diffère plus du dépôt pour `loaded.dart` ; `feuille_repository.dart` ne garde que la modification indexée (filtre côté serveur `?chauffeur=&date=`), le filtre local `f['chauffeur'] == user.id` est bien conservé. |
| A-07 / H-03 | corrigé | `transpt1/deploy/sauvegarde-windows.ps1` est de nouveau présent et identique au dépôt : les références de `DEPLOIEMENT.md` §3 et `CARTE_DU_CODE.md` sont justes. |

### Lot 3 — Intégrité métier : **règlement intérieur appliqué ; corrections du socle refusées** (1er novembre 2026)

Décisions du propriétaire (1er novembre) : les quatre corrections du socle proposées (lot 3a) ne sont **pas** appliquées ; les
règles métier deviennent un **règlement intérieur par compagnie** dont chaque défaut est le comportement actuel (rien ne change
tant qu'une compagnie ne règle rien), réglé par le PDG (toutes les règles) et par le directeur du pôle (les siennes) ; API
seulement pour l'instant, l'écran viendra avec le lot 5.

| # | Statut | Décision ou correction |
|---|---|---|
| C-01 | réglable ; **stock non recalculé** | Règle `sorties_pieces_corrigeables` (défaut : permis). La correction proposée (le stock suit une correction ou une annulation) est refusée : tant qu'une compagnie permet les corrections, une sortie corrigée ou annulée laisse le stock inchangé. Écrit dans `PERMISSIONS.md` §4. |
| C-02 | **non corrigé** (refusé) | Clore un ordre de réparation remet toujours le véhicule « disponible », même sous blocage actif du QHSE ; le QHSE qui veut ensuite rebloquer ce véhicule obtient une erreur 500. |
| C-03 | **non corrigé** (refusé) | `peut_demarrer` reste sensible à la casse (« Freins » en défaut n'empêche plus le départ une fois le véhicule libéré). |
| C-04 | réglable | Règle `mecanicien_supprime_ses_ordres` (défaut : permis). Le changement de véhicule d'un ordre ouvert (C-04a) reste possible : correction refusée. |
| C-05 | réglable | Règles `chauffeur_supprime_ses_feuilles` et `chauffeur_supprime_ses_incidents` (défaut : permis). La régulation garde ses droits. |
| D-bis | réglable | Règle `mecanicien_confie_ses_ordres` (défaut : permis) ; interdite, le mécanicien passe par `reaffecter` (directeur technique, chef d'atelier). Renvoyer son propre nom dans un formulaire complet n'est pas refusé. |

Réalisation : `configuration/regles.py` (`REGLEMENT` : libellé, message de refus, postes concernés, pôle, défaut),
modèle `ReglementInterieur` (migration `configuration 0002`, seules les règles réglées sont enregistrées, tracé dans le journal
d'audit), `services.exiger_regle` appelé là où la règle s'applique (sorties de pièces : modification et suppression ; ordres de
réparation : changement d'intervenant et suppression ; feuilles de route et incidents : suppression), point d'entrée
`/api/configuration/reglement/` (GET pour tous ; PATCH pour le PDG et le directeur du pôle, une demande qui déborde du pôle est
refusée en entier). `PERMISSIONS.md` §3, §4, §12 et la synthèse par rôle sont à jour.

Vérifications :

- Nouveaux tests : `configuration/tests/test_reglement.py` (lecture, qui règle quoi, refus hors pôle, valeurs invalides,
  cloisonnement entre compagnies, journal d'audit), `maintenance/tests/test_reglement_atelier.py`,
  `personnel_roulant/tests/test_reglement_chauffeur.py` (défaut inchangé, interdiction, postes non concernés) : **52 réussis**.
  Contre-épreuve : le refus neutralisé dans `exiger_regle`, les 7 tests d'interdiction échouent.
- Suites des apps touchées (`configuration`, `maintenance`, `personnel_roulant`, `audit`, matrice de conformité, contrat du
  frontend) : **2 799 réussis, 0 échec** en 9 min. `manage.py check` et `makemigrations --check` : propres.
- Suite backend complète : prévue en fin de série (après les lots 4 à 7).

### Lot 4 — Confidentialité et permissions : **D-03 et D-05 appliqués ; D-01, D-02, D-04 laissés tels quels** (1er novembre 2026)

| # | Statut | Décision ou correction |
|---|---|---|
| D-01 | **non corrigé** (décision du propriétaire) | Le journal d'audit continue d'exposer à ses lecteurs (PDG, secrétaire général, QHSE) le texte des doléances, l'identité de leur déposant et les contenus RH (motifs disciplinaires, évaluations, notes, motifs de congé). L'écart avec `PERMISSIONS.md` §20 (« même la hiérarchie et le PDG ne les lisent pas ») demeure. |
| D-02 | **non corrigé** (décision du propriétaire) | Le code de retrait d'un colis reste en clair dans le journal des SMS (`NotificationLog.contenu`). |
| D-03 | corrigé | Consigne du propriétaire : « le chef de gare peut voir et clôturer la caisse du guichet de sa gare seulement ». Partout où il voit ou clôture une caisse : `GET /clotures-caisse/` (liste et détail : les clôtures faites à **sa gare**, `ClotureCaisse.gare` étant figée à la clôture ; une autre est introuvable, 404), `POST /clotures-caisse/` et `GET /tickets/cloture-caisse/?guichetier=` (403 pour un guichetier d'une autre gare ou sans gare), `etat` (déjà filtré). Sa propre caisse reste visible. Les autres rôles de supervision (directeur des opérations, chef de ligne, secrétaire général, PDG, QHSE) voient et clôturent toutes les caisses de **leur propre compagnie uniquement**, précision du propriétaire : c'était déjà le cas (filtre par compagnie, et contrainte en base qui oblige tout compte autre que le super-administrateur à avoir une compagnie), c'est désormais couvert par un test. Le site n'utilise que `etat` et la clôture de son équipe : aucun écran touché. |
| D-04 | **non traité** | Pas de consigne sur la création de gares par un chef de gare : comportement inchangé. |
| D-05 | corrigé (serveur) | `/finance/export/` : un texte qui commence par `=`, `+`, `-`, `@`, une tabulation ou un retour chariot est précédé d'une apostrophe ; un montant, même négatif (« -1600,50 »), reste un nombre. L'export des recettes fabriqué par le navigateur (`FinanceDashboard`) n'est **pas** protégé (choix « serveur seulement ») : à revoir au lot 5. |

Vérifications :

- `billetterie/tests/test_cloture_caisse_transmise.py` et `test_cloture_caisse.py` : le test qui fixait l'ancien comportement (« le chef
  voit toutes celles de la compagnie ») est remplacé par la règle voulue (sa gare seulement : liste, filtre et détail en 404 ; clôture
  et consultation en direct d'un guichetier d'une autre gare ou sans gare en 403 ; le directeur des opérations voit et clôture tout).
  Contre-épreuve : vérification retirée, les tests de clôture et de consultation échouent. Après ce dernier changement, suites
  `billetterie`, `role_coverage_tests` et `lien_billetterie` : **2 497 réussis, 1 ignoré, 0 échec**.
- Isolement entre compagnies de la supervision (`test_la_supervision_ne_voit_et_ne_cloture_que_sa_propre_compagnie`, un cas par
  rôle : directeur des opérations, chef de ligne, secrétaire général, PDG, QHSE) : ce rôle dans une autre compagnie a une liste
  vide, le détail en 404, l'état du jour vide, la caisse en direct à zéro et la clôture refusée (400). Dans sa compagnie, il voit et
  clôture. Contre-épreuves : le filtre par compagnie retiré du calcul de la caisse, puis de la clôture, et les 5 cas échouent
  chaque fois. Les deux fichiers de tests de caisse : **41 réussis, 0 échec**.
- `finance` : nouveau test d'export (libellé `=2+5`, libellé `-Remise…`, fournisseur `@SOMME(A1:A9)`, référence `+225…`, montant net
  négatif) ; **91 réussis**. Contre-épreuve : apostrophe retirée, le test échoue. Le parcours e2e « comptabilité » lit l'export
  (en-tête, `Abidjan-Bouaké;`, `TOTAL;`) : non concerné.
- Suites `billetterie` et `role_coverage_tests` : **2 363 réussis, 1 ignoré, 0 échec** en 9 min 20 s.

### Demande nouvelle (1er novembre 2026) — billetterie : garder le logiciel de la compagnie ou s'y relier

Demande : « au niveau de la billetterie, la capacité d'utiliser le logiciel ou de créer un lien avec un logiciel déjà utilisé par
l'entreprise ». Décisions du propriétaire : trois modes par compagnie, lien par API **et** par import de fichier, réglé par le PDG et
le directeur des opérations (import ouvert au chef de gare pour sa gare), lien générique (le logiciel utilisé n'est pas encore connu).

| Élément | Réalisation |
|---|---|
| Mode de billetterie | `integre` (défaut : rien ne change), `externe` (vente au guichet fermée en 403, plus de places mises de côté pour le hors ligne), `mixte` (les deux, places communes). `GET/PATCH /api/lien-billetterie/reglage/`. |
| API du logiciel | Clé d'API par compagnie (hachée, montrée une fois, révocable ; n'ouvre que ses 3 routes) : planning avec les places vendables, envoi de ventes par lot de 500 au plus, annulations. Chaque vente traitée à part, compte rendu par vente. |
| Import de fichier | CSV (`;`, `,`, tabulation ; UTF-8 ou Windows) ou Excel `.xlsx`, 5 Mo et 5 000 ventes au plus ; noms de colonnes courants reconnus, montants (« 5 000 FCFA ») et moyens de paiement (Orange Money, Wave, cash…) normalisés ; compte rendu ligne par ligne conservé. |
| Billet reçu | Un vrai `Ticket` (`source` = `lien` ou `import`, `logiciel`, `reference_externe`) : place prise sous verrou sans toucher aux places réservées des guichets, anti-doublon par référence (rejouer un lot ou réimporter un fichier est sans effet), prix du logiciel gardé (écart au tarif signalé), date de vente du logiciel ; hors caisse des guichetiers, aucun SMS ; contrôlé à bord par le code imprimé par le logiciel. |
| Code partagé | `billetterie.reservations.consommer_une_place` et `billetterie.ventes.annuler_ticket` servent au guichet comme au lien (extraits de `TicketViewSet`, sans changement de règle) ; `cloturer_caisses` ignore les billets sans vendeur. |
| Dépendances | `openpyxl` 3.1.5 (lecture Excel), `et_xmlfile` 2.0.0 (dépendance), `defusedxml` 0.7.1 (protège la lecture d'un fichier Excel piégé), ajoutées à `requirements.txt` : **`pip install -r requirements.txt` à refaire sur le serveur**. |
| Documentation | `PERMISSIONS.md` §2 et §22, synthèse par rôle ; `transpt1/LIEN_BILLETTERIE.md` (guide pour l'éditeur du logiciel) ; `README.md`, `CARTE_DU_CODE.md`. |

Vérifications :

- `lien_billetterie/tests/` : **72 réussis** (mode et guichet, clés et authentification, planning, ventes, annulations, import CSV
  et Excel, chef de gare, contrôle à bord). Contre-épreuves : fermeture du guichet, restriction du chef de gare et code externe à
  bord retirés tour à tour, chaque fois un test échoue.
- Matrice de conformité, 3 nouvelles routes × 20 rôles : **60 réussis**.
- Suite backend complète (sans la sonde ni `test_carte_consumer.py`, instable, voir A-04), lots 3 et 4 compris : **4 658 réussis,
  1 ignoré, 0 échec** en 13 min. `manage.py check` et `makemigrations --check` : propres.

Pas encore fait (à proposer) : les écrans (choix du mode, clés, dépôt du fichier et compte rendu) ; sur le site et le mobile, le
formulaire de vente reste affiché en billetterie externe (le serveur refuse avec un message clair) ; un mobile qui synchronise
des ventes faites hors ligne avant le passage en externe se les voit refuser.

### Consigne du 1er novembre 2026 — cloisonnement entre compagnies : **vérifié, rien à corriger dans les données**

Consigne du propriétaire : « les membres d'une compagnie de transport n'ont aucune vue des activités d'une autre compagnie ».
Vérification de tout le backend, sans modifier le code de l'application (sondes temporaires dans `zz_probe/`) :

| Contrôle | Méthode | Résultat |
|---|---|---|
| Lectures | Un compte de chaque rôle (18) d'Express Savane interroge en GET les 150 routes de l'API (8 496 requêtes), sans paramètre, avec l'identifiant d'un objet STC dans le chemin et dans chaque paramètre de filtre (`?gare=`, `?ligne=`, `?chauffeur=`…). Recherche, dans chaque réponse, des 881 textes propres à STC (noms, plaques, codes, identifiants de connexion) et de `"company": <STC>` ; comparaison champ par champ avec la réponse pour un identifiant inexistant. | **Aucune donnée STC.** Les seuls textes trouvés sont communs à toutes les compagnies (fiche de poste type, code de mission) ; les écarts, l'âge d'une position GPS qui avance d'une seconde. |
| Requêtes | Pour les 57 vues qui lisent une table, le SQL construit pour un compte de chaque rôle filtre-t-il sur sa compagnie ? Couvre les 30 modèles sans données de démonstration STC (colis, messages, notes, clôtures de caisse, contrôles en ligne…). | **Toutes filtrent**, sauf la fiche d'une compagnie (`/api/companies/<id>/`), protégée autrement (voir ci-dessous). |
| Écritures | Les comptes STC (18 rôles) désignent un objet d'Express Savane dans 108 routes d'écriture (1 756 requêtes) : champ relationnel d'une modification ou d'une création, champ d'une action (réaffecter, planifier…). | **Toutes refusées** (400, ou 403 pour un rôle non autorisé) ; les 4 réponses acceptées ignoraient le champ. Les messages de refus ne citent pas l'objet. |
| Hors API | Lecture : carte en temps réel (un canal par compagnie), service d'alertes (écarte tout destinataire d'une autre compagnie), lien billetterie (la clé ne voit que sa compagnie, testé), classements de gamification (par compagnie), vue plateforme (super-administrateur seulement), fichiers (servis par l'API seulement). | Conforme. |

Deux points mineurs, **non corrigés** (accord attendu) : ils ne montrent aucune activité, seulement qu'un identifiant existe.
- `GET /api/companies/<id>/` d'une autre compagnie : 403 (une compagnie inexistante : 404). Révèle qu'une compagnie porte ce numéro.
- Désigner l'objet d'une autre compagnie en écriture : « N'appartient pas à votre compagnie » (un identifiant inexistant :
  « l'objet n'existe pas »). Révèle qu'un objet porte ce numéro ailleurs.

Le super-administrateur, opérateur de la plateforme et membre d'aucune compagnie, garde la lecture de toutes les compagnies
(sauf la finance), comme le dit `PERMISSIONS.md`. Dans la supervision de la caisse, « toute la compagnie » s'entend de **sa propre
compagnie** (précisé dans `PERMISSIONS.md` §2, et un test par rôle).

### À venir

Lots 5 à 7 du §6 : rien n'est appliqué. Les points qui touchent aux règles métier (D-04, D-06) seront proposés comme
**réglages par compagnie**, jamais durcis en dur.
La sonde `transpt1/zz_probe/` est conservée le temps de la revue (non versionnée) ; elle sera supprimée à la fin.
