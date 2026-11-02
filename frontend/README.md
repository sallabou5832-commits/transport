# Transport Coord — site web

Site web (React 19 + Vite + React Router 7) du logiciel Transport Coord : un tableau de bord par poste du cahier des
charges, plus des pages transverses (pilotage, secrétariat, comptabilité, RH, journal d'audit…). Il consomme l'API Django
(`../transpt1`) exposée sous `/api/`, et la carte du réseau en temps réel par WebSocket.

L'interface est sobre et fonctionnelle : pas de charte graphique finale.

## Prérequis

- Node.js **20.19+ ou 22.12+** (exigé par Vite 8 ; l'intégration continue utilise Node 24)
- Le backend Django doit tourner sur `http://localhost:8000` (voir `../transpt1/README.md`)

## Installation

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, par défaut http://localhost:8000/api
npm run dev
```

L'application est servie sur `http://localhost:5173`.

Le backend doit autoriser cette origine en CORS — `CORS_ALLOWED_ORIGINS` dans `transpt1/.env` doit inclure
`http://localhost:5173` (déjà le cas dans `.env.example` du backend).

## Comptes de démonstration

Le backend crée un utilisateur par rôle (les 18 rôles du cahier des charges, plus un superadmin) et des données réalistes,
avec le mot de passe `Demo!2024` :

```bash
cd ../transpt1
python manage.py migrate
python manage.py seed_demo_users
python manage.py seed_demo_reseau       # gares, lignes, véhicules
python manage.py seed_demo_operations   # départ, ticket, feuille de route, pièces, ordre de réparation
python manage.py seed_demo_tableaux     # historique, incidents, assurances, sinistres, RH, finance
python manage.py generer_alertes        # facultatif : remplit les cloches d'alertes
```

`seed_demo_tableaux` n'a aucun effet s'il a déjà été lancé. Les comptes se créent lentement (le hachage de mot de passe
de production coûte quelques secondes par utilisateur, ≈ 3 min au total).

| Identifiant | Poste | Tableau de bord (`/dashboard/…`) |
|---|---|---|
| `pdg_stc`, `secretaire_general_stc` | PDG, secrétaire général | `direction` : santé de l'entreprise (recettes, ponctualité, flotte, incidents), tuiles par gare, carte du réseau en temps réel, trésorerie, besoin de renouvellement de flotte |
| `qhse_stc` | QHSE | `qhse` : incidents, blocages de sécurité (bloquer / lever un départ), défauts de checklist, tableau de conformité, formations obligatoires |
| `directeur_exploitation_stc` | directeur des opérations | `exploitation` : gares et lignes en temps réel, gares en tension, fermetures de ligne à décider, véhicules à l'atelier, carte, planification |
| `chef_gare_stc` | chef de gare | `gare` : santé de la gare, recettes du jour, caisses du jour, équipe locale, messages à l'équipe et aux chauffeurs, demande de fermeture de ligne, annulation motivée d'un ticket |
| `chef_ligne_stc` | chef de ligne | `ligne` : santé de la ligne, planification, réaffectation (véhicule, chauffeur, heure), véhicules à l'atelier, demande de fermeture |
| `guichetier_stc` | guichetier | `guichetier` : vente au tarif de la ligne, jauge de remplissage, clôture de caisse |
| `bagagiste_stc` | bagagiste | `bagagiste` : colis (enregistrement, chargement, arrivée, retrait par code), plan de chargement |
| `chauffeur_stc`, `chauffeur2_stc`, `chauffeur3_stc`, `chauffeur_relais_stc`, `chauffeur_libre_stc` | chauffeurs | `chauffeur` : feuille de route, checklist avant-départ, incident géolocalisé, suivi GPS et fatigue, relais et checklist de reprise, carnet de route |
| `controleur_stc` | contrôleur de ligne | `controle` : contrôle à bord (vérification des billets, constats, rapport), historique par ligne et par chauffeur |
| `directeur_technique_stc` | directeur technique | `technique` : santé de la flotte, file des réparations par urgence, plans d'entretien préventif, fiche véhicule, renouvellement, suggestions de commande |
| `magasinier_stc` | magasinier | `magasinier` : stock et alertes de rupture, demandes de pièces à servir, suggestions de commande |
| `chef_atelier_stc` | chef d'atelier | `atelier` : ordres de réparation, file, répartition entre mécaniciens, demandes de pièces, fiche véhicule |
| `mecanicien_stc` | mécanicien | `mecanicien` : ses ordres de réparation, ses sorties et demandes de pièces |
| `drh_stc` | DRH | `rh` : fiche agent (contrat, évaluations, discipline), congés avec impact, formations obligatoires, fiches de poste et recrutement, médiation sociale, synthèse RH |
| `directeur_financier_stc` | directeur financier | `finance` : recettes consolidées par gare, mode de paiement et jour, trésorerie ; page Comptabilité pour le reste |
| `responsable_juridique_stc` | responsable juridique | `juridique` : assurances, sinistres liés aux incidents avec pièces jointes, litiges sociaux, tableau de conformité, modèles juridiques, reporting |
| `superadmin_demo` | superadmin | `plateforme` : une ligne par compagnie cliente |

Les comptes `*_stc` appartiennent à la compagnie **STC Voyages**. `pdg_savane`, `chef_gare_savane`, `chauffeur_savane` et
`guichetier_savane` (compagnie **Express Savane**) servent à vérifier le cloisonnement entre compagnies et alimentent la vue
plateforme.

Chaque rôle a exactement un tableau de bord (`src/auth/roles.js`). La page générique (`/dashboard/generique`) ne sert que de
repli pour un rôle inconnu du site. Sur toutes les pages : la **cloche d'alertes** (alertes inter-pôles, lecture
individuelle) et le **bandeau de jeu** (points, niveau, missions du jour, selon le niveau de gamification réglé pour le poste).

### Pages annexes

En plus du tableau de bord (`PAGES_ANNEXES` dans `roles.js`) ; leurs liens n'apparaissent que pour les postes autorisés.

| Page | Pour qui | Contenu |
|---|---|---|
| `/pilotage` | PDG | Geler ou rouvrir une ligne, réaffecter un véhicule ou un chauffeur, suspendre un compte, décider des investissements |
| `/investissements` | directeurs technique, des opérations, financier | Demander un investissement (le PDG décide) |
| `/cadre`, `/configuration` | PDG ; chaque échelon pour ses subordonnés | Cadre de la compagnie, puis réglage par poste et par agent (automatisation, gamification, fonctions, préférence vocale) |
| `/secretariat` | secrétaire général, PDG | Agenda de la direction, notes de service, archives |
| `/comptabilite` | directeur financier | Dépenses, budgets carburant, fournisseurs et factures, rentabilité, solde de départ, export |
| `/finances` | PDG, secrétaire général | Trésorerie, budget carburant, rentabilité, échéancier (lecture) |
| `/synthese` | PDG, secrétaire général | Reporting juridique et synthèse RH |
| `/espace` | tous les postes | Mes congés, mes formations obligatoires, ma médiation |
| `/notes` | tous les postes | Notes de service reçues |
| `/modeles` | tous les postes | Bibliothèque de modèles juridiques |
| `/audit` | PDG, secrétaire général, QHSE, superadmin | Journal d'audit filtrable, pagination « Charger plus » |

### Règles appliquées par le serveur, visibles à l'écran

- **Planifier un départ** (`components/PlanificationDepart.jsx`) : une fois la date et l'heure choisies, le formulaire ne
  propose que les véhicules et chauffeurs **libres** à cette heure (pas d'autre départ dans les 8 h, véhicule ni bloqué ni en
  maintenance) ; le serveur applique les mêmes règles et crée le départ **et** la feuille de route d'un seul coup.
- **Tickets** : vendus au tarif de la ligne (un autre prix est réservé aux chefs, avec un motif). Un ticket vendu ne se modifie
  ni ne se supprime : le chef de gare (ou la direction) l'**annule avec un motif** ; la place est libérée et la vente sort des
  recettes.
- **Blocage QHSE** : un défaut sur un item de sécurité de la checklist bloque le véhicule ; « Démarrer » est alors refusé.

## Ce que le site ne fait pas encore

État vérifié le 2 novembre 2026 (détail : `../AUDIT_AVANCEMENT_2026-11-02.md`).

- **Voix** : aucune commande ni lecture vocale sur le site (la dictée en français n'existe que sur deux écrans du mobile).
- **Écrans manquants** : règlement intérieur de la compagnie et lien avec un logiciel de billetterie (mode, clés, import de
  fichier) — disponibles par l'API seulement. En billetterie externe, le formulaire de vente reste affiché (le serveur refuse).
- **Fonctions** : rotation des quais, lecture du QR code d'un billet par la caméra, impression d'un ticket papier, carte avec
  fond de carte (la carte est un schéma), paiement Mobile Money réel.
- **Défauts connus, non corrigés** (`../RAPPORT_ANOMALIES_2026-10-31.md`, lot 5) : aucun filet d'erreur de rendu (une valeur
  inattendue de l'API donne une page blanche, F-15) ; une date-heure mal tapée peut faire de même (F-16) ; vente et colis
  envoyés sans clé d'idempotence (un nouvel essai après coupure double la vente, F-02) ; après ≈ 8 min sans réseau, le suivi
  GPS ne renvoie plus rien (F-05) ; la plupart des suppressions sans confirmation (F-06) ; listes téléchargées en entier à
  chaque rafraîchissement (F-03).
- **Technique** : un seul fichier JavaScript de 567 ko (pas de découpage par page) ; jetons de connexion dans `localStorage`,
  sans politique CSP.

## Comment tester manuellement

1. Lancer le backend (`python manage.py runserver`) puis le site (`npm run dev`).
2. Ouvrir `http://localhost:5173` — redirige vers `/login`.
3. Se connecter avec chacun des identifiants ci-dessus (mot de passe `Demo!2024`) et vérifier que le tableau de bord affiché
   correspond à la colonne « Tableau de bord ».
4. Vérifier la restriction par rôle : connecté en `guichetier_stc`, ouvrir directement
   `http://localhost:5173/dashboard/direction` — l'application doit revenir au tableau de bord du guichetier.
5. Sur `guichetier_stc`, vendre un ticket : la jauge de remplissage se met à jour.
6. Sur `chauffeur_stc`, remplir la checklist avant-départ avec « freins » en défaut : un message de défaut s'affiche, puis
   « Démarrer » est refusé par le serveur (véhicule bloqué pour raison de sécurité).
7. Se déconnecter (bouton en haut à droite) et vérifier le retour à `/login`.

Le scénario complet, poste par poste, est dans `../SCENARIO_PILOTE.md`.

## Vérifications automatiques

| Commande | Ce qu'elle vérifie | Dernier résultat (2 nov. 2026) |
|---|---|---|
| `npm test` | Tests unitaires (Vitest) : client API, format, ponctualité (cas partagés avec le serveur), finance, carte | 42 réussis |
| `npm run lint` | Analyse statique (oxlint) | 0 erreur, 1 avertissement connu (`AuthContext.jsx`) |
| `npm run build` | Compilation | Réussie |
| `npm run e2e` | 14 parcours dans un vrai Chrome, contre une vraie API et une base jetable (créée puis supprimée) : chaque poste se connecte, coordination QHSE, colis, jeu, configuration, caisse, GPS et relais, contrôle à bord, pouvoirs de direction, atelier, secrétariat, comptabilité, RH, juridique | 14/14 (≈ 10 min) |
| `npm run e2e -- caisse` | Un seul parcours (filtre sur le nom ; plusieurs : `jeu,caisse`) ; `--garder` laisse la pile en marche | — |
| `npm run e2e:pw` | 4 essais Playwright Test sur la même pile (connexion, mauvais mot de passe, page réservée) | 4/4 (1er nov.) |

Les essais de bout en bout utilisent le Chrome (ou Edge) déjà installé, sans rien télécharger, et le Python du backend
(`E2E_PYTHON` pour en indiquer un autre). Les captures d'écran vont dans `e2e/captures/` (non suivi par git).

Côté backend (`cd ../transpt1 && pytest`), deux suites protègent le site :

- `role_coverage_tests/test_matrice_conformite.py` teste **chaque rôle sur chaque endpoint restreint** contre `PERMISSIONS.md` ;
- `role_coverage_tests/test_contrat_frontend.py` **lit le code des pages**, en extrait chaque appel à l'API et vérifie que tous
  les rôles auxquels la page est proposée (`src/auth/roles.js`) y ont droit.

## Structure

```
src/
├── api/          client.js (fetch authentifié, JWT + renouvellement), useChargement.js (chargement et rafraîchissement),
│                 useActions.js (boutons et formulaires), useFluxCarte.js (carte en temps réel par WebSocket)
├── auth/         contexte d'authentification, garde de route par rôle, roles.js (rôle → tableau de bord, pages annexes)
├── components/   ≈ 60 composants : briques d'affichage (Layout, Kpi, Jauge…) et blocs métier réutilisés par plusieurs pages
│                 (planification, carte, suivi de trajet, contrôle des billets, file des réparations, congés, factures…)
├── lib/          format.js, ponctualite.js (même règle que le serveur), carte.js, finance.js, rh.js, et leurs tests
└── pages/        un tableau de bord par poste, les pages annexes, la connexion
e2e/              parcours de bout en bout (run.mjs, scenarios.mjs, lib.mjs) et essais Playwright (connexion.spec.ts)
```

Le rôle de chaque fichier est décrit dans `../CARTE_DU_CODE.md` §3.
