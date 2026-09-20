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

Le backend fournit des commandes de seed pour créer des utilisateurs de test, un
par rôle couvert par un tableau de bord, avec le mot de passe `Demo!2024` :

```bash
cd ../transpt1
python manage.py migrate
python manage.py seed_demo_users
python manage.py seed_demo_reseau       # gares/lignes/véhicules
python manage.py seed_demo_operations   # départ, ticket, feuille de route, pièces, ordre de réparation
```

| Identifiant | Rôle | Tableau de bord attendu |
|---|---|---|
| `pdg_stc` | pdg | Direction (`/dashboard/direction`) |
| `secretaire_general_stc` | secretaire_general | Direction |
| `qhse_stc` | qhse | Direction |
| `chef_gare_stc` | chef_gare | Départs de sa gare (`/dashboard/gare`) |
| `guichetier_stc` | guichetier | Vente de ticket (`/dashboard/guichetier`) |
| `chauffeur_stc` | chauffeur_principal | Feuille de route du jour (`/dashboard/chauffeur`) |
| `chauffeur_relais_stc` | chauffeur_relais | Feuille de route du jour |
| `magasinier_stc` | magasinier | Pièces / alerte de rupture (`/dashboard/magasinier`) |
| `chef_atelier_stc` | chef_atelier | Ordres de réparation en cours (`/dashboard/atelier`) |

Tous appartiennent à la compagnie **STC Voyages**. `pdg_savane` / `chef_gare_savane`
(compagnie **Express Savane**) existent aussi, utiles pour vérifier l'isolation
multi-compagnie.

## Comment tester manuellement

1. Lancer le backend (`python manage.py runserver`) puis le frontend (`npm run dev`).
2. Ouvrir `http://localhost:5173` — redirige vers `/login`.
3. Se connecter avec chacun des identifiants ci-dessus (mot de passe `Demo!2024`) et
   vérifier que le tableau de bord affiché correspond bien à la colonne
   « Tableau de bord attendu ».
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

## Structure

```
src/
├── api/client.js         # fetch authentifié (JWT + refresh automatique)
├── auth/                 # contexte d'authentification, garde de route par rôle
├── components/           # Layout, jauge de remplissage, bannière d'alerte
└── pages/                # une page par tableau de bord + la page de connexion
```
