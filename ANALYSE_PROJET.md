# Analyse complète du projet Transport Coord

Analyse réalisée le 21 septembre 2026 sur l'état du dépôt après l'étape 13 (dernier commit : préparation du pilote).
Elle repose sur des **mesures et des sondes exécutées sur le code**, pas sur des impressions : chaque chiffre de ce
document a été relevé, et les constats de sécurité ont été vérifiés par des appels réels à l'API.

## 1. Synthèse

**Verdict : un socle solide et bien testé, prêt pour un pilote restreint sous conditions, mais qui ne couvre qu'environ
un quart du cahier des charges.**

- **Ce qui est solide** : l'isolation entre compagnies, les permissions par rôle (vérifiées pour les 18 rôles sur chaque
  endpoint restreint), la vente de tickets (idempotente, verrouillée, avec places garanties hors ligne), la chaîne
  chauffeur → checklist → blocage de sécurité → atelier → direction, et une base de tests dense (939 cas backend, 142
  côté mobile, ≈ 96 % des lignes du backend exercées, tests écrits > code applicatif).
- **Ce qui empêche un pilote « ouvert »** : quatre défauts majeurs (les deux premiers prouvés par appel d'API).
  1. Un guichetier peut **modifier le prix d'un ticket vendu par un autre et le supprimer**, sans aucune trace ni
     libération de la place (fraude de caisse possible).
  2. Il n'existe **aucun journal d'audit**, alors que le cahier des charges l'exige.
  3. **Aucun écran ne permet de planifier** les départs et feuilles de route (administration Django seulement).
  4. Le **mobile n'a jamais été lancé sur un téléphone** et sa version release est signée avec la clé de débogage.
- **Couverture fonctionnelle du cahier** : sur 99 fonctionnalités par poste, **10 sont complètes, 30 partielles, 59 absentes**
  (≈ 25 % en pondérant une partielle à moitié). Les blocs entièrement absents : gamification, colis et bagages, vocal
  multilingue, GPS et carte, modules RH / finance / juridique / secrétariat au-delà d'un premier écran.
- **Recommandation** : lancer un pilote limité (1 gare, 1 ligne, guichetiers + chauffeurs + chef de ligne + direction)
  **après** les cinq actions « avant le pilote » du §13 (de l'ordre de trois à six semaines pour un développeur, dont
  l'écran de planification est la part la plus lourde ; sans lui, un opérateur saisit le planning dans l'administration).

### Suivi après l'analyse (21 septembre 2026)

Les cinq actions « avant le pilote » du §13 ont été traitées le jour même ; ce qui suit décrit l'état **après** ces
corrections (les §2 à §12 décrivent l'état au moment de l'analyse).

| # | Action | État | Preuve |
|---|---|---|---|
| 1 | Tickets verrouillés | **Fait** : plus de modification ni de suppression pour aucun des 18 rôles, superadmin compris (405, ou 403 pour un rôle sans droit d'écriture), ni depuis l'administration Django ; annulation motivée (5 caractères min.) par le chef de gare ou la direction, qui libère la place et sort la vente des recettes ; index sur les dates | Tests API (rôles × actions), essai dans le navigateur : annulation, jauge, recettes |
| 2 | Journal d'audit | **Fait** : création, modification (avant → après), suppression, annulation, connexions réussies et échecs, sur 16 types d'objets ; ajout seulement (l'application ne peut ni modifier ni supprimer une entrée) ; mots de passe jamais enregistrés ; page web filtrable et paginée (PDG, secrétaire général, QHSE, superadmin) | 67 tests, essai dans le navigateur (filtres, pagination, accès par rôle) |
| 3 | Écran de planification | **Fait** : départ + feuille de route créés d'un coup ; seuls les véhicules et chauffeurs réellement libres sont proposés (fenêtre de 8 h, véhicule ni bloqué ni en maintenance), mêmes règles imposées par le serveur ; réaffecter, décaler, supprimer un départ sans ticket | 64 tests, essai dans le navigateur |
| 4 | APK signé + téléphones | **Signature faite, essai sur téléphones NON fait** : APK *release* 32 et 64 bits (32 Mo) signé avec une clé propre, vérifié par `apksigner` ; la compilation échoue désormais sans clé au lieu de signer avec la clé de débogage. **L'application n'a toujours jamais été lancée sur un appareil** (aucun téléphone ni émulateur ici) : protocole d'essai dans `mobile/TEST_TELEPHONES.md` | `apksigner verify`, contenu de l'APK, compilation refusée sans clé |
| 5 | Sauvegardes automatiques | **Fait** : `sauvegarde_base` (archive relue, empreinte SHA-256, rotation, envoi hors du serveur), `verifier_sauvegarde` (restauration réelle dans une base temporaire), `etat_sauvegarde` (alerte) ; planification systemd et Windows. **Non fait** : limitation des connexions au proxy et essai réel de SMS/WhatsApp (dépendent de l'infrastructure et de comptes fournisseur) | Tests avec vrais `pg_dump` / `pg_restore`, exécution du script Windows sur une base jetable |

Autres corrections : dates impossibles (`2030-13-45`) qui provoquaient une erreur 500 sur l'audit, la synthèse et la clôture
de caisse ; index sur les dates des tickets, départs, feuilles de route et incidents ; APK compilé pour les deux
architectures ARM (un APK 64 bits seul se serait fermé au lancement sur les téléphones 32 bits d'entrée de gamme).
Suite backend : **1 206 tests passent** (1 ignoré : le cas du superadmin, sans compagnie, d'un test paramétré, couvert à part), contre 939 à l'analyse ; le rendu web a été
revérifié dans un navigateur sur les 21 comptes de démonstration, sans erreur JavaScript ni requête refusée.

**Reste à faire, par ordre d'importance** : essai sur de vrais téléphones (bloquant pour le mobile) ; sauvegarde du
keystore hors de l'ordinateur ; limitation des connexions au proxy ; essai réel de SMS/WhatsApp ; pagination des listes
de l'API ; unicité des pièces par compagnie ; intégration continue ; prévenir automatiquement les voyageurs quand
l'heure d'un départ vendu est décalée (aujourd'hui : simple avertissement à l'écran du chef de ligne).

## 2. Périmètre et méthode

| Mesure | Comment |
|---|---|
| Taille du code | `git ls-files` + comptage de lignes, par composant |
| Surface d'API et modèle de données | introspection Django (routes, modèles) |
| Conformité au cahier | les 99 fonctionnalités du cahier découpées poste par poste, chacune classée sur le code réel |
| Sécurité | recherche de motifs à risque, revue des permissions, **sondes** par appels d'API (voir §7) |
| Performance | comptage de requêtes SQL à 5 puis 60 lignes ; chronométrage avec 5 000 tickets |
| Tests | 939 cas pytest, 142 tests Flutter, lint et build du frontend, `check --deploy` |
| Couverture de code | lignes exécutées par les 939 tests, mesurées par un traceur `sys.monitoring` (le paquet `coverage` n'a pas pu être installé : réseau indisponible) ; approximative, à quelques points de `coverage.py`, et couverture de **lignes**, pas de branches |

**Ce que cette analyse n'a pas pu vérifier** : l'exécution sur un appareil Android ou iOS (aucune virtualisation
disponible), un envoi réel de SMS ou WhatsApp, un déploiement sur un vrai serveur, les vulnérabilités connues des
dépendances (`pip-audit` et `npm audit` non exécutés : le réseau était instable pendant l'analyse, des installations ont échoué), l'accessibilité, un test de charge
concurrent, la conformité légale sur les données personnelles.

## 3. Le projet en chiffres

| Composant | Contenu | Taille |
|---|---|---|
| Backend (Django 6.1, DRF, PostgreSQL) | 9 applications, **21 modèles métier, 52 routes d'API** | 4 830 lignes (+ 563 de migrations) |
| Tests backend | 939 cas (338 fonctions, dont 34 d'audit des rôles) | 6 137 lignes (1,27 × le code) |
| Frontend web (React 19, Vite 8) | 16 tableaux de bord, connexion, page de repli | 4 167 lignes ; bundle 329 ko (98 ko compressé) |
| Mobile (Flutter) | vente de ticket hors ligne, feuille de route en lecture | 3 039 lignes + 2 477 de tests (142 tests) |
| Documentation | README ×3, PERMISSIONS, DEPLOIEMENT, SCENARIO_PILOTE, cahier | 1 163 lignes |
| Historique | 29 commits, du 19 au 21 septembre 2026 | — |

## 4. Architecture

```
Web (React)  ──┐                                  ┌── notifications SMS/WhatsApp (Orange, Twilio), simulées par défaut
Mobile (Flutter, hors ligne) ──┼──HTTPS/JWT──▶ API Django REST ──▶ PostgreSQL
Administration Django (superadmin) ──┘   (multi-compagnie, permissions par rôle)
```

- **Multi-compagnie** : chaque objet porte sa compagnie ; un mixin filtre toutes les listes, une permission d'objet
  contrôle les accès directs, et les sérialiseurs refusent les références croisées. Les endpoints à calcul manuel
  (tableaux de bord, synthèse financière, clôture de caisse) filtrent explicitement par compagnie ; la seule exception
  voulue est la vue « plateforme » du superadmin. L'isolation est testée pour chaque ressource.
- **Rôles** : 17 rôles métier + superadmin, droits **fixes dans le code** (`PERMISSIONS.md` fait foi). Aucune
  configuration par compagnie ou par échelon hiérarchique, alors que le cahier la demande.
- **Applications** : `core` (comptes, compagnies), `reseau` (gares, lignes, véhicules), `billetterie` (départs, tickets,
  réservations hors ligne), `personnel_roulant` (feuilles de route, checklists, incidents), `maintenance` (pièces,
  ordres de réparation, sorties), `supports` (dossiers RH, assurances, sinistres, synthèse financière), `dashboard`,
  `notifications`, `formation` (parcours simulés et isolés).
- **Flux clé** : vente → compteur de places sous verrou → notifications ; checklist en défaut de sécurité → véhicule
  bloqué → ordre de réparation → véhicule libéré ; départ démarré/arrivé → statut du départ et du véhicule.

## 5. Conformité au cahier des charges

Règle de classement : **F** = utilisable dans une interface (web ou mobile) sans contournement ; **P** = partielle, ou
disponible seulement par l'API ou l'administration ; **A** = absente. Total : 99 fonctionnalités (les lignes du secrétaire
général et du QHSE, écrites sans « ; », sont découpées en 3 et 4).

| Pôle | Fonctionnalités | F | P | A |
|---|---|---|---|---|
| Direction Générale (PDG, secrétaire général, QHSE) | 13 | 2 | 3 | 8 |
| Exploitation & Réseau (dir. des opérations, chef de gare, chef de ligne, guichetier, bagagiste) | 31 | 4 | 8 | 19 |
| Personnel roulant (chauffeur, relais, contrôleur) | 19 | 0 | 8 | 11 |
| Technique & Maintenance (dir. technique, magasinier, atelier) | 18 | 2 | 8 | 8 |
| Fonctions supports (DRH, finance, juridique) | 18 | 2 | 3 | 13 |
| **Total** | **99** | **10** | **30** | **59** |

**Complètes** : tableau de bord d'exploitation temps réel, checklist avant départ liée au blocage de sécurité, suivi des
incidents (QHSE), réaffectation en un geste avec suggestions (chef de ligne), santé de la ligne, jauge de remplissage en
direct, stock avec alerte de rupture et sortie décrémentant le stock, consolidation des recettes (finance), registre des
assurances avec alerte de renouvellement.

**Partielles typiques** : des données présentes mais sans écran (clôture de caisse, sortie de pièce, recettes du jour d'une
gare, formation), un sous-ensemble seulement (dossier RH sans contrat ni évaluations ; flotte sans kilométrage), ou une
alerte affichée sur un tableau de bord sans envoi automatique.

**Blocs entièrement absents** (chacun regroupe plusieurs fonctionnalités) :

| Bloc | Fonctionnalités concernées |
|---|---|
| Gamification (scores, classements, missions, points, badges) | ≈ 11 fonctionnalités par poste + toute la section « mécaniques » du cahier |
| Colis et bagages (enregistrement, fret, suivi, code de retrait) | 8 (poste du bagagiste entier) |
| Vocal multilingue | absent partout ; manque aussi comme modalité dans ≈ 8 fonctionnalités partielles |
| GPS, carte temps réel, alerte fatigue | 3 |
| RH au-delà du dossier (congés, formations obligatoires, recrutement, médiation) | 5 |
| Finance au-delà des recettes (carburant, rentabilité, échéancier, trésorerie) | 4 |
| Juridique au-delà du registre (conformité, litiges, bibliothèque, reporting) | 4 |
| Secrétariat général (agenda, notes de service, archivage) | 3 |
| Maintenance préventive, validation de tickets, scan | 4 |

**Exigences transverses du cahier**

| Exigence | État |
|---|---|
| Backend API + web + mobile sur la même API | Faite |
| Authentification par poste, droits limités au périmètre du rôle | Faite (et testée) |
| Journal d'audit de toutes les actions | **Absent** |
| Mode hors ligne du mobile des chauffeurs | Partiel : fait pour la vente du guichetier ; le chauffeur n'a que la lecture |
| Notifications client par SMS/WhatsApp | Faite pour les tickets (simulation par défaut, jamais testée en réel) ; absente pour les colis |
| Mobile money (Orange, MTN, Wave) | Le mode de paiement est enregistré ; aucune intégration de paiement |
| GPS des véhicules | Absent |
| Moteur vocal multilingue | Absent (hors périmètre de la phase 1) |
| Lien Ministère / OSER | Absent (hors périmètre de la phase 1) |
| Configuration par entreprise et par échelon, niveau d'automatisation modulable | Absente |

## 6. Qualité du code et des tests

**Points forts**
- Des tests **écrits contre la spécification** : la matrice `test_matrice_conformite.py` teste 18 rôles × 12 endpoints
  restreints contre `PERMISSIONS.md`, et un test de contrat lit le code des pages web pour vérifier qu'aucune page
  n'appelle une route interdite à l'un de ses rôles.
- Des tests **qui détectent vraiment** les erreurs : 7 casses volontaires (fuite entre compagnies, permission élargie,
  contrôle supprimé…) ont toutes fait échouer au moins un test.
- Du code lisible : aucun motif à risque (SQL brut, `eval`, `pickle`, `mark_safe`, `csrf_exempt`, `innerHTML`…), noms
  parlants, commentaires qui expliquent le « pourquoi », règles métier centralisées.
- Une couverture fonctionnelle vérifiée de bout en bout par un scénario rejoué dans un navigateur (8 étapes sur 8).

**Points faibles**
- **Aucune intégration continue** ni conteneur : les tests ne tournent que sur la machine de développement.
- **Frontend sans test unitaire** : sa seule protection est le test de contrat côté backend et les passages manuels.
- **Logique dupliquée entre web et serveur** (règle de ponctualité, seuils, calculs de remplissage) : elle est alignée
  à la main, sans test qui vérifie l'égalité.
- **Deux styles de code** côté web : les pages anciennes (chef de gare, guichetier, chauffeur, magasinier) chargent leurs
  données à la main, les nouvelles utilisent un hook commun ; 4 avertissements de lint subsistent sur les pages anciennes.
- `requirements.txt` mêle dépendances de production et de test ; `psycopg2-binary` est déconseillé en production par
  ses auteurs.

**Couverture de code : ≈ 96 % des lignes** (2 953 sur 3 079, dans 92 fichiers), de 87 % (configuration du projet) à 99,5 %
(notifications) selon l'application ; 62 fichiers sur 92 sont entièrement couverts. Les lignes non couvertes sont surtout
les **refus d'écriture entre compagnies** des sérialiseurs (`validate_*` du réseau, des assurances, sinistres, dossiers RH,
ordres de réparation). Une sonde montre qu'ils **fonctionnent** (HTTP 400 dans les 9 cas essayés : assurance, sinistre,
dossier, gare, ordre et sortie de pièce d'une compagnie visant les données d'une autre), mais **aucun test ne les protège**
d'une régression : à ajouter (voir §13).

## 7. Sécurité

**Ce qui est bien fait** : secrets uniquement dans l'environnement (aucun dans le code ni dans l'historique), HTTPS forcé
avec HSTS et cookies sécurisés, clé secrète sans valeur par défaut, `DEBUG` faux par défaut, isolation entre compagnies
testée, un compte désactivé est coupé **immédiatement** (401 sur l'accès comme sur le rafraîchissement, vérifié), création
d'utilisateur dans l'administration sans superadmin par défaut, commandes de démonstration refusées en production,
`check --deploy` propre.

**Failles et faiblesses trouvées** (les 5 premières prouvées par appel d'API) :

| # | Gravité | Constat | Recommandation |
|---|---|---|---|
| S1 | **Élevée** | Un guichetier modifie le prix d'un ticket vendu **par un autre** (PATCH → 200, prix ramené de 5 000 à 1) et le **supprime** (DELETE → 204). La suppression **ne libère pas la place** (le compteur reste à 1). Cela fausse aussi la clôture de caisse. | Interdire la modification et la suppression après vente ; passer par une annulation explicite (motif, auteur, remboursement) qui rend la place. |
| S2 | **Élevée** | **Aucun journal d'audit** (exigence du cahier). Un chauffeur peut supprimer **son propre incident** (204) sans trace ; aucun champ « créé par / modifié par / date ». | Historisation des tickets, incidents, ordres de réparation, dossiers et comptes (qui, quoi, quand, avant/après). |
| S3 | Moyenne | **Aucune limitation des essais de connexion** : 40 mots de passe faux d'affilée sont tous traités (401, jamais 429). Pas d'authentification à deux facteurs. | Limiter au proxy (voir `DEPLOIEMENT.md`) ; blocage progressif par compte ; 2FA pour les rôles sensibles (superadmin, finance, DRH). |
| S4 | Moyenne | Le prix d'un ticket est **saisi librement** par le guichetier (pas de tarif) : sous-facturation possible, indétectable. | Modèle de tarif par ligne, prix imposé, dérogation tracée. |
| S5 | Moyenne | Jetons de connexion du site web stockés dans `localStorage` : lisibles par tout script injecté. Pas de rotation ni de liste noire des jetons de rafraîchissement. | Cookies `HttpOnly` ou, à défaut, politique de contenu stricte (CSP) ; rotation des jetons. |
| S6 | Faible | Unicité **globale** de `Piece.reference` et de `Vehicule.immatriculation` : une compagnie apprend qu'une référence ou une plaque existe chez une autre (message d'erreur explicite). | Voir §8 : unicité par compagnie pour les pièces. |
| S7 | Faible | Numéros de téléphone et noms des voyageurs conservés en clair (tickets, journal des notifications). | Information des voyageurs, durée de conservation, formalités de protection des données (avis juridique). |
| S8 | À faire | Vulnérabilités des dépendances non vérifiées. | `pip-audit`, `npm audit` et mises à jour automatiques dans l'intégration continue. |

## 8. Modèle de données et intégrité

- **Contraintes sérieuses** : suppression protégée (`PROTECT`) sur les liens principaux, index d'unicité pour
  l'idempotence des ventes et pour les réservations hors ligne, invariant « vendues + réservées ≤ capacité » tenu sous verrou.
- **Bug de conception multi-compagnie** : `Piece.reference` est **unique sur toute la plateforme**. Deux compagnies ne
  peuvent donc pas avoir la même référence de pièce (cas fréquent : références constructeur). À corriger par une
  unicité (compagnie, référence) avant l'arrivée d'une seconde compagnie réelle.
- **Compteur dénormalisé** : `Depart.places_vendues` est un compteur, pas un calcul. Toute suppression ou modification
  de ticket hors du flux normal le désynchronise (voir S1). À recalculer ou à dériver des tickets.
- **Cycle de vie du ticket absent** : pas d'état « utilisé », « annulé » ou « remboursé » : impossible de valider un
  ticket à bord ou de tracer une annulation.
- **Deux sources pour le chauffeur** : `Depart.chauffeur` et `FeuilleDeRoute.chauffeur` ; la réaffectation les
  synchronise, mais rien ne l'impose en base.
- **Un véhicule n'est rattaché à aucune gare**, ce qui interdit l'arbitrage de véhicules entre gares du cahier.
- **Pas de tarif, pas de kilométrage, pas de colis, pas de position GPS** : autant de données que les fonctions absentes du
  §5 supposent.
- **Pas de champs d'audit** (`créé par`, `modifié le`) sur les modèles.
- **Formation** : un seul parcours par rôle pour toute la plateforme (pas de personnalisation par compagnie).

## 9. Performance et passage à l'échelle

| Mesure | Résultat |
|---|---|
| Requêtes SQL d'une liste (départs, tickets, feuilles, incidents, véhicules) | **1**, identique avec 5 et avec 60 lignes : **aucun N+1** |
| Tableaux de bord d'exploitation / direction | 9 et 5 requêtes, constantes |
| `GET /api/tickets/` avec **5 000 tickets** | **1,4 Mo et 1,7 s** pour un seul appel |

**Le risque** n'est pas le nombre de requêtes mais le **volume** : l'API ne pagine aucune liste. Plusieurs pages web
(contrôleur, chef de ligne, bagagiste, technique) rechargent des listes complètes **chaque minute**, et les autres
(dont le QHSE) à chaque visite. Au rythme de 500 tickets par
jour et par compagnie, la page du contrôleur atteint ces 5 000 tickets en dix jours et dépasse la dizaine de secondes en
quelques mois, pour chaque utilisateur connecté.
Aucun index n'est déclaré sur les colonnes de date filtrées par les tableaux de bord (`Depart.date_heure`,
`Ticket.date_vente`, `FeuilleDeRoute.heure_depart_prevue`, `Incident.date`).
**À faire** : pagination et filtres serveur (`?depart=`, `?date=`), index sur ces colonnes, agrégats côté serveur plutôt
que listes complètes côté navigateur. Rien de bloquant pour un pilote d'une gare pendant quelques semaines.

## 10. Fiabilité et exploitation

- **Sauvegardes** : documentées, non automatisées ; restauration jamais éprouvée.
- **Journalisation** : ajoutée à l'étape 13 (sans elle, les erreurs 500 n'étaient écrites nulle part avec `DEBUG=False`).
  Pas de suivi d'erreurs (type Sentry), pas de tableau de bord technique, pas de point de santé dédié.
- **Déploiement manuel** : ni Docker, ni script, ni intégration/livraison continue. La procédure de `DEPLOIEMENT.md` n'a
  pas été déroulée sur un vrai serveur.
- **Instance unique** : le cache par défaut est local au processus ; à revoir avant plusieurs machines.
- **Migrations** : pas de plan de retour arrière documenté.
- **Points positifs** : ventes idempotentes (rejouables sans doublon), verrous sur les compteurs, transactions sur les
  changements d'état, échecs de notification isolés de la vente.

## 11. Frontend web

Forces : une page par poste, table rôle → page unique (`roles.js`), composants communs (badges, indicateurs, barres),
hook de chargement avec rafraîchissement automatique, aucune erreur JavaScript ni requête refusée sur 21 comptes,
bundle léger. Faiblesses : aucun test unitaire ; pas de TypeScript ; tout le texte est codé en français dans les pages
(pas d'internationalisation, alors que les langues locales sont un objectif du cahier) ; chargement par listes complètes
(§9) ; deux styles de code cohabitent ; pas d'audit d'accessibilité ; création de départs et de feuilles de route
impossible depuis l'interface (§13).

## 12. Application mobile

Forces : conception « hors ligne d'abord » (file d'actions, synchronisation, places garanties par réservation), base
locale **chiffrée** (AES-256, clé dans le coffre sécurisé), HTTPS obligatoire en release, 142 tests dont un test de bout
en bout contre le vrai serveur. Faiblesses : **jamais lancée sur un appareil** (un APK de débogage de 153 Mo se compile) ;
signature release avec la clé de débogage ; le chauffeur n'y a que la lecture (ni checklist, ni départ, ni incident) alors
que le cahier en fait la cible principale du hors ligne ; aucune configuration iOS ; pas de notifications poussées.

## 13. Recommandations priorisées

Tailles indicatives pour un développeur : **S** ≤ 1 jour, **M** 2 à 5 jours, **L** 1 à 3 semaines, **XL** au-delà.

**Avant le pilote (bloquants)**

| # | Action | Taille | Pourquoi |
|---|---|---|---|
| 1 | Verrouiller les tickets après vente : plus de modification ni suppression, annulation explicite avec motif qui rend la place | M | S1 : fraude de caisse |
| 2 | Journal d'audit sur tickets, incidents, ordres, dossiers, comptes | M | S2 : exigence du cahier, traçabilité |
| 3 | Écran de planification des départs et feuilles de route pour le chef de ligne (l'API et la liste de chauffeurs libres existent presque) | M–L | Sans lui, tout passe par un opérateur dans l'administration |
| 4 | APK signé avec une vraie clé, essai sur 2 ou 3 téléphones réels avec réseau dégradé | M | Risque terrain le plus élevé, jamais éprouvé |
| 5 | Limitation des connexions au proxy, sauvegardes automatiques avec restauration testée, essai réel de SMS/WhatsApp | S chacune | S3, exploitation, notifications |

**Pendant le pilote (1 à 2 mois)** : tests des refus d'écriture entre compagnies (§6) — S ; pagination, filtres et index (§9) — M ; unicité des pièces par compagnie — S ;
modèle de tarif et prix imposé — M ; intégration continue (tests backend, lint et build web, tests et analyse Flutter,
`pip-audit`, `npm audit`) — S à M ; tests frontend et scénario navigateur versionné — M ; écrans manquants dont l'API
existe (clôture de caisse, sortie de pièce) — S chacun ; notifications internes (un incident grave prévient
l'exploitation et le QHSE) — M ; état du ticket (utilisé, annulé) et validation à bord — M à L ; chauffeur mobile
(checklist, départ, incident, hors ligne) — L.

**Phase suivante** : colis et bagages — L à XL ; gamification — XL ; GPS et carte — XL ; vocal multilingue — XL ; mobile
money réel — L ; modules RH, finance, juridique complets — XL ; configuration par compagnie et par échelon — L ; lien
Ministère / OSER — hors périmètre de la phase 1.

## 14. Risques

| Risque | Probabilité | Impact | Réponse |
|---|---|---|---|
| Perte de recettes par modification ou suppression de tickets (S1, S2, S4) | Moyenne | Élevé | Actions 1 et 2 avant le pilote |
| Saisie du planning par un opérateur : erreurs, retards, dépendance à une personne | Élevée | Moyen | Action 3, ou opérateur formé et checklist de saisie |
| Défauts du mobile sur le terrain (hors ligne, réseau, appareils) | Élevée | Moyen à élevé | Action 4 |
| Lenteur des tableaux de bord avec la croissance des données | Moyenne (semaines) | Moyen | Pagination et index |
| Faible adoption par le personnel de terrain (numérique, langues locales, vocal absent) | Élevée | Élevé | Formation, pilote sur peu de personnes, écrans simples ; le vocal viendra après |
| Notifications réelles jamais éprouvées (coût, refus du fournisseur, modèle WhatsApp non approuvé) | Moyenne | Moyen | Essai réel avant le pilote |
| Perte de données (sauvegardes manuelles) | Faible à moyenne | Très élevé | Sauvegardes automatiques et restauration testée |
| Compromission de compte (aucune limitation, pas de 2FA, jetons en `localStorage`) | Moyenne | Élevé | S3 et S5 |
| Régressions non détectées (pas d'intégration continue, frontend sans test) | Élevée à terme | Moyen | Intégration continue, tests frontend |
| Données personnelles des voyageurs (conformité) | À évaluer | Moyen | Avis juridique avant le pilote |

## 15. Annexe : méthode et limites

- **Sondes de sécurité** : tests jetables (supprimés après usage) qui appellent l'API réelle avec les comptes de chaque rôle
  et affichent le résultat : modification et suppression d'un ticket d'un autre guichetier, suppression d'un incident par
  son chauffeur, collisions d'unicité entre compagnies, 40 connexions échouées, compte désactivé, 9 écritures visant les données d'une autre
  compagnie (toutes refusées).
- **Mesure des requêtes** : `CaptureQueriesContext` sur sept endpoints avec 5 puis 60 lignes de chaque type.
- **Volume** : 5 000 tickets insérés en masse, un appel `GET /api/tickets/` chronométré (machine de développement, base
  locale) : l'ordre de grandeur compte plus que la valeur exacte.
- **Conformité** : le classement F / P / A est un jugement fait sur le code au 21 septembre 2026 ; deux lecteurs
  pourraient classer différemment quelques fonctionnalités limites, mais pas l'ordre de grandeur (25 % en pondéré).
- **Vérifications déjà en place** : voir `SCENARIO_PILOTE.md` (parcours de bout en bout), `PERMISSIONS.md` (référence des
  droits) et `DEPLOIEMENT.md` (mise en production).
