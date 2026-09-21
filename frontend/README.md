# Transport Coord — Frontend

Interface web minimale (React + Vite) pour le logiciel Transport Coord. Consomme
l'API Django (`../transpt1`) exposée sous `/api/`.

Aucun design final n'est implémenté à ce stade : l'objectif est une interface simple
et fonctionnelle, un rôle par tableau de bord.

## Prérequis

- Node.js 18+
- Le backend Django doit tourner sur `http://localhost:8000` (voir `../transpt1/README.md`)

## Installation

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, par défaut http://localhost:8000/api
npm run dev
```

L'application est servie sur `http://localhost:5173`.

Le backend doit autoriser cette origine en CORS — `CORS_ALLOWED_ORIGINS` dans
`transpt1/.env` doit inclure `http://localhost:5173` (déjà le cas dans
`.env.example` du backend).

## Comptes de démonstration

Le backend fournit des commandes de seed pour créer un utilisateur par rôle (les 17 rôles du cahier
des charges, plus un superadmin) et des données réalistes, avec le mot de passe `Demo!2024` :

```bash
cd ../transpt1
python manage.py migrate
python manage.py seed_demo_users
python manage.py seed_demo_reseau       # gares/lignes/véhicules
python manage.py seed_demo_operations   # départ, ticket, feuille de route, pièces, ordre de réparation
python manage.py seed_demo_tableaux     # départs du jour (à l'heure, en retard), 6 jours d'historique,
                                        # incidents, assurances, sinistres, dossiers RH
```

`seed_demo_tableaux` n'a aucun effet s'il a déjà été lancé. Les comptes se créent lentement (le
hachage de mot de passe de production coûte quelques secondes par utilisateur).

| Identifiant | Rôle | Tableau de bord (`/dashboard/…`) |
|---|---|---|
| `pdg_stc`, `secretaire_general_stc` | pdg, secrétaire général | `direction` : recettes, ponctualité, statut des gares, courbe de recettes |
| `qhse_stc` | qhse | `qhse` : incidents ouverts (action « marquer traité »), véhicules bloqués, défauts de checklist |
| `directeur_exploitation_stc` | directeur d'exploitation | `exploitation` : gares, lignes, ponctualité, départs en retard, flotte, incidents graves ; **planifier un départ** |
| `chef_gare_stc` | chef de gare | `gare` : départs de sa gare, tickets de chaque départ, **annulation motivée d'un ticket** |
| `chef_ligne_stc` | chef de ligne | `ligne` : santé de la ligne, départs, **planifier un départ**, réaffecter (véhicule, chauffeur, heure), supprimer un départ planifié |
| `guichetier_stc` | guichetier | `guichetier` : vente de ticket |
| `bagagiste_stc` | bagagiste | `bagagiste` : départs à charger (pas de module colis côté serveur) |
| `chauffeur_stc`, `chauffeur2_stc`, `chauffeur3_stc`, `chauffeur_relais_stc` | chauffeurs | `chauffeur` : feuille de route du jour |
| `controleur_stc` | contrôleur de ligne | `controle` : passagers d'un départ, vérification de charge, signalement d'incident |
| `directeur_technique_stc` | directeur technique | `technique` : disponibilité de la flotte, file de réparations par urgence, pièces, assurances |
| `magasinier_stc` | magasinier | `magasinier` : pièces / alerte de rupture |
| `chef_atelier_stc` | chef d'atelier | `atelier` : ordres de réparation en cours |
| `drh_stc` | DRH | `rh` : dossiers des agents, statuts, notes, ouverture de dossier |
| `directeur_financier_stc` | directeur financier | `finance` : recettes par période, gare, mode de paiement, jour ; export CSV |
| `responsable_juridique_stc` | responsable juridique | `juridique` : assurances (échéances, renouvellement), sinistres |
| `superadmin_demo` | superadmin | `plateforme` : une ligne par compagnie cliente |

Les comptes `*_stc` appartiennent à la compagnie **STC Voyages**. `pdg_savane`, `chef_gare_savane`,
`chauffeur_savane` et `guichetier_savane` (compagnie **Express Savane**) servent à vérifier l'isolation
multi-compagnie et alimentent la vue plateforme.

Chaque rôle a exactement un tableau de bord (`src/auth/roles.js`). La page générique
(`/dashboard/generique`) ne sert plus que de repli pour un rôle inconnu du frontend.

**Pages annexes** (`PAGES_ANNEXES` dans `roles.js`, en plus du tableau de bord) : `/audit`, le **journal d'audit**
(qui a fait quoi, quand, d'où ; filtres par objet, action et dates ; pagination « Charger plus »), réservé au PDG, au
secrétaire général, au QHSE et au superadmin. Son lien apparaît dans la barre du haut pour ces rôles seulement.

**Planifier un départ** (`components/PlanificationDepart.jsx`, chef de ligne et directeur d'exploitation) : une fois la
date et l'heure choisies, le formulaire ne propose que les véhicules et chauffeurs **libres** à cette heure (pas d'autre
départ dans les 8 h, véhicule ni bloqué ni en maintenance) ; le serveur applique les mêmes règles à l'envoi et crée le
départ **et** la feuille de route du chauffeur d'un seul coup.

**Tickets** : un ticket vendu ne se modifie ni ne se supprime. Le chef de gare (ou la direction) l'**annule avec un
motif** (5 caractères minimum) : la place est libérée, la vente sort des recettes et l'annulation est tracée.

## Ce que les tableaux de bord ne font pas encore

Le cahier des charges demande plus que ce que le serveur enregistre aujourd'hui. Chaque page l'indique quand
c'est le cas, plutôt que d'afficher de fausses données :

- **Colis et bagages** (enregistrement, code de retrait par SMS/WhatsApp, suivi de statut) : pas de modèle côté serveur.
- **Validation des tickets** (détection d'un ticket déjà utilisé) : les tickets n'ont pas d'état « utilisé ».
- **Gamification** (missions, points, badges, classements), **carte temps réel des véhicules**, **commandes
  vocales multilingues**, **notifications en temps réel** : rien côté serveur ni côté web.
- **Finance** : budget carburant, coûts, rentabilité par ligne, échéancier fournisseurs : seules les recettes de
  billetterie sont enregistrées.
- **DRH** : formations obligatoires (le suivi est strictement individuel par conception), congés, recrutement,
  médiation sociale.
- **Technique** : entretien préventif (pas de kilométrage), rapport de renouvellement de flotte.
- **Directeur d'exploitation** : réaffectation d'un véhicule entre gares (un véhicule n'est rattaché à aucune
  gare), ouverture/fermeture d'une ligne.

## Comment tester manuellement

1. Lancer le backend (`python manage.py runserver`) puis le frontend (`npm run dev`).
2. Ouvrir `http://localhost:5173` — redirige vers `/login`.
3. Se connecter avec chacun des identifiants ci-dessus (mot de passe `Demo!2024`) et
   vérifier que le tableau de bord affiché correspond bien à la colonne
   « Tableau de bord ».
4. Vérifier la restriction par rôle : une fois connecté avec un compte (ex.
   `guichetier_stc`), essayer de naviguer directement vers l'URL d'un autre tableau
   de bord (ex. `http://localhost:5173/dashboard/direction`) — l'application doit
   rediriger automatiquement vers le tableau de bord du rôle réel, pas afficher la
   page demandée.
5. Sur `guichetier_stc`, vendre un ticket sur le départ affiché : la jauge de
   remplissage doit se mettre à jour après la vente.
6. Sur `chauffeur_stc`, ouvrir « Remplir la checklist avant-départ », mettre un item
   de sécurité (ex. « freins ») en défaut et valider : un message de défaut doit
   s'afficher, et le bouton « Démarrer » doit ensuite être refusé par le backend
   (véhicule bloqué pour raison de sécurité).
7. Se déconnecter (bouton en haut à droite) et vérifier le retour à `/login`.

## Vérifications automatiques

Côté backend (`cd ../transpt1 && pytest`) :

- `role_coverage_tests/test_matrice_conformite.py` teste **les 18 rôles sur chaque endpoint restreint** contre
  `PERMISSIONS.md`, la lecture générale, le cloisonnement RH et l'isolation entre compagnies ;
- `role_coverage_tests/test_contrat_frontend.py` **lit le code des pages** (`src/pages`), en extrait chaque appel
  `apiFetch` et vérifie que tous les rôles auxquels la page est proposée (`src/auth/roles.js`) y ont droit :
  une page qui appellerait une route interdite à l'un de ses rôles ferait échouer ce test.

Côté frontend : `npm run lint` et `npm run build`. Le frontend n'a pas de test unitaire ; le rendu a été vérifié
dans un vrai navigateur sur les 21 comptes de démonstration (connexion, page attendue, aucune erreur JavaScript ni
requête refusée, actions réelles sur les pages interactives).

## Structure

```
src/
├── api/                  # client.js : fetch authentifié (JWT + refresh) ; useChargement.js : chargement/rafraîchissement
├── auth/                 # contexte d'authentification, garde de route par rôle, table rôle → tableau de bord
├── components/           # Layout, Jauge, Badge, Kpi, Barres, TuilesGares, Alert, PlanificationDepart
├── lib/                  # format.js (montants, dates, libellés), ponctualite.js (même règle que le serveur)
└── pages/                # une page par tableau de bord + la page de connexion + AuditPage (journal d'audit)
```
