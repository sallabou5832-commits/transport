# Scénario de test de bout en bout — pilote

Un cas réel, d'un bout à l'autre de la chaîne : **un guichetier vend un ticket, un chauffeur remplit sa checklist et
part, un incident est déclaré, l'atelier répare, le PDG consulte son tableau de bord.** Durée : 15 minutes environ.

Ce scénario se joue à la main dans le navigateur, un rôle après l'autre. Il a été exécuté dans un vrai navigateur
sur une base neuve (8 étapes sur 8, aucune erreur JavaScript ni requête refusée) : les valeurs données sous
« Attendu » sont celles qui ont été relevées.

## 0. Préparation

**Il faut une base neuve** : le scénario consomme les données de démonstration (le départ, sa feuille de route, le
véhicule). Pour le rejouer, repartez d'une base vide.

```bash
cd transpt1
cp .env.example .env            # DJANGO_DEBUG=True : les commandes de démonstration sont refusées sinon
python manage.py migrate
python manage.py seed_demo_users        # les comptes (quelques minutes : hachage de mot de passe réel)
python manage.py seed_demo_reseau
python manage.py seed_demo_operations
python manage.py runserver              # API sur http://localhost:8000

cd ../frontend
npm install
npm run dev                             # web sur http://localhost:5173
```

Ouvrez `http://localhost:5173`. Utilisez **une fenêtre de navigation privée par rôle** (ou déconnectez-vous entre
deux étapes) : la connexion est mémorisée par navigateur. Mot de passe de tous les comptes : `Demo!2024`.

| Étape | Rôle | Compte | Page |
|---|---|---|---|
| 1 | Guichetier | `guichetier_stc` | `/dashboard/guichetier` |
| 2 | Chauffeur | `chauffeur_stc` | `/dashboard/chauffeur` |
| 3 | Chauffeur, puis QHSE et directeur d'exploitation | `chauffeur_stc`, `qhse_stc`, `directeur_exploitation_stc` | `chauffeur`, `qhse`, `exploitation` |
| 4 | Atelier | `chef_atelier_stc` | `/dashboard/atelier` |
| 5 | PDG | `pdg_stc` | `/dashboard/direction` |
| 6 | QHSE, puis directeur d'exploitation | `qhse_stc`, `directeur_exploitation_stc` | `qhse`, `exploitation` |
| 7 | Chauffeur, puis directeur d'exploitation | `chauffeur_stc`, `directeur_exploitation_stc` | `chauffeur`, `exploitation` |

**État de départ** (à vérifier avant de commencer) : un départ « Abidjan-Bouaké » aujourd'hui, avec le véhicule
`CI-1001-AB` (70 places) et le chauffeur `chauffeur_stc` ; **1 ticket déjà vendu** (« Passager Démo », 5 000 FCFA en
espèces) ; un ordre de réparation ouvert sur `CI-1002-AB` ; une pièce sous son seuil d'alerte (« Filtre à huile »).

---

## Étape 1 — Le guichetier vend un ticket

**Qui / où** : `guichetier_stc`, page « Tableau de bord — Guichetier ».

1. Choisir le départ « Abidjan-Bouaké — … ». La jauge indique **1 / 70 places (1%)**.
2. Nom du passager `Awa Pilote`, téléphone `+2250700000001`, prix `7500`, mode de paiement **Mobile money**.
3. Cliquer « Vendre le ticket ».

**Attendu**
- Message vert « **Ticket vendu à Awa Pilote.** » ; le formulaire se vide.
- La jauge passe à **2 / 70 places (3%)**.
- Notification client : `NOTIFICATIONS_SIMULATION_MODE` est vrai par défaut, **aucun message réel n'est envoyé**. Dans
  l'administration (`/admin/`, compte `superadmin_demo`), « Notification logs » contient **2 lignes** (SMS et WhatsApp)
  au statut « Simulé ».

**Autres rôles** : `chef_gare_stc` voit le même départ avec 2 places vendues.
**Variante mobile** : la vente (y compris hors ligne, puis synchronisation) se fait aussi depuis l'application
mobile : voir `mobile/README.md` §6.

## Étape 2 — Le chauffeur remplit sa checklist et part

**Qui / où** : `chauffeur_stc`, page « Tableau de bord — Chauffeur ».

1. La feuille de route du jour s'affiche : « Abidjan-Bouaké — Départ prévu … — Statut : **pas encore parti** ».
2. « Remplir la checklist avant-départ » : laisser les six éléments à « OK », puis « Valider la checklist ».
3. Cliquer « Démarrer ».

**Attendu**
- « **Checklist enregistrée, aucun défaut.** » puis « **Feuille de route démarrée.** ».
- Le statut devient « **parti à HH:MM** » (avant l'heure prévue : le départ est à l'heure).
- **Ce que voient les autres** : le directeur d'exploitation (`/dashboard/exploitation`) affiche « Départs du jour = 1 (0
  planifié · **1 en cours** · 0 terminé) » et « Ponctualité du jour = **100 %** » ; le véhicule est « En ligne ».

## Étape 3 — Un incident est déclaré

**Qui / où** : `chauffeur_stc`, même page.

1. Cliquer « Signaler un incident » : type **Panne**, gravité **Grave**, description
   « Panne moteur à 40 km de Bouaké : le car est immobilisé. » puis « Envoyer le signalement ».

**Attendu**
- « **Incident signalé. Il apparaît sur les tableaux de bord de l'exploitation et du QHSE.** »
- `qhse_stc` (`/dashboard/qhse`) : « Incidents ouverts = **1** (dont 1 grave) » en rouge ; la ligne « Grave — Panne —
  CI-1001-AB — Panne moteur… » porte un bouton « Marquer traité ».
- `directeur_exploitation_stc` : « Incidents graves ouverts = **1** », avec sa description.

## Étape 4 — L'atelier ouvre puis clôture la réparation

**Qui / où** : `chef_atelier_stc`, page « Tableau de bord — Chef d'atelier ». (Le modèle n'a pas de rôle
« mécanicien » distinct : l'atelier ouvre et clôture ; le mécanicien responsable est celui qui ouvre l'ordre.)

1. La liste montre l'ordre existant sur `CI-1002-AB` (« Révision moteur programmée. »).
2. « Ouvrir un ordre de réparation » : véhicule `CI-1001-AB`, description
   « Panne moteur : remplacement de la pompe à eau », puis « Ouvrir l'ordre ».
3. Sur la ligne du nouvel ordre : « Démarrer », puis saisir **90** dans « Temps passé (min) » et « Clôturer ».

**Attendu**
- « Ordre de réparation ouvert. » — « Intervention #2 démarrée. » —
  « **Intervention #2 clôturée : le véhicule est de nouveau disponible pour le régulateur.** »
- L'ordre quitte la liste « en cours » et apparaît dans « Dernières interventions clôturées » avec « **90 min** ».
- Le véhicule `CI-1001-AB` est « Disponible ».

## Étape 5 — Le PDG consulte son tableau de bord

**Qui / où** : `pdg_stc`, page « Tableau de bord — Direction ».

**Attendu** (base neuve, jour de la vente)
- « Recettes du jour = **12 500 FCFA** » (5 000 de la démonstration + 7 500).
- « Ponctualité du jour = **100 %** » (le départ est parti dans la tolérance de 10 minutes).
- « Pièces sous seuil d'alerte = **1** » ; « Assurances à échéance proche = **0** ».
- Statut des gares : « Gare Adjamé — 1 départ · **100 % à l'heure** » (tuile verte) ; « Gare Bouaké — 0 départ ».
- « Incidents ouverts (7 derniers jours) » : **Grave 1**.
- « Véhicules par statut » : Disponible 1, En ligne 1 (`CI-1002-AB`, donnée de démonstration).

## Étape 6 — Le QHSE clôt l'incident

**Qui / où** : `qhse_stc` → « Marquer traité » sur l'incident.

**Attendu** : « **Incident #1 marqué comme traité.** » ; chez `directeur_exploitation_stc`, « Incidents graves ouverts = **0** »
(après actualisation, la page se rafraîchit d'elle-même chaque minute).

## Étape 7 — Le car arrive

**Qui / où** : `chauffeur_stc` → « Signaler l'arrivée ».

**Attendu**
- « **Arrivée enregistrée, le départ est terminé.** » ; le statut devient « arrivé à HH:MM ».
- `directeur_exploitation_stc` : « Départs du jour = 1 (0 planifié · 0 en cours · **1 terminé**) ».
- Le départ terminé n'est plus proposé au guichetier (plus aucune vente possible dessus).

---

## Contrôles à faire en même temps

| Contrôle | Comment | Attendu |
|---|---|---|
| Isolation entre compagnies | Se connecter avec `pdg_savane` (Express Savane) | Recettes du jour 0, aucune gare ni ligne de STC Voyages |
| Restriction par rôle | Connecté en `guichetier_stc`, ouvrir `http://localhost:5173/dashboard/direction` | Redirection immédiate vers le tableau du guichetier |
| API protégée | Appeler `GET /api/dashboard/direction/` avec le jeton d'un guichetier | `403` |
| Déconnexion | Bouton « Déconnexion » | Retour à `/login`, jetons effacés |

## Variante A — Défaut de sécurité (le pouvoir de blocage)

À jouer à la place de l'étape 2, sur une base neuve.

1. `chauffeur_stc` : dans la checklist, mettre **« freins » en Défaut**, « Valider la checklist » →
   « Checklist enregistrée. Défaut signalé sur : freins. »
2. « Démarrer » est **refusé** : le véhicule est bloqué pour raison de sécurité.
3. `qhse_stc` : « Véhicules bloqués (sécurité) = 1 », « Défauts avant départ = 1 » ;
   `directeur_exploitation_stc` : `CI-1001-AB` listé « Bloqué sécurité » dans « Indisponibles » ;
   `chef_ligne_stc` : alerte « 1 départ(s) prévu(s) avec un véhicule indisponible ».
4. `chef_atelier_stc` : ouvrir un ordre sur `CI-1001-AB` → « Ordre de réparation ouvert : le véhicule bloqué passe en
   maintenance. », puis le clôturer → le véhicule redevient « Disponible ».
5. `chauffeur_stc` : « Démarrer » reste refusé tant que le défaut est inscrit : **refaire la checklist** avec
   « freins » à OK (l'élément existant est mis à jour), puis « Démarrer » réussit.

Cette variante est couverte par un test automatique de l'API (voir ci-dessous) ; elle n'a pas été rejouée au navigateur.

## Ce que ce scénario ne couvre pas

- **Le mobile** : l'application n'a pas été lancée sur un téléphone (aucun émulateur possible sur la machine de
  développement). Côté chauffeur, elle n'affiche que la feuille de route : checklist, départ et incident se font sur
  le web. Un APK de débogage est produit par `flutter build apk --debug`.
- **La création des départs et des feuilles de route** : aucune page ne le permet. Avant le pilote, ils sont saisis
  dans l'administration Django (`/admin/`, modèles « Départs » et « Feuilles de route ») ; voir `transpt1/DEPLOIEMENT.md`.
- **Les envois réels de SMS et WhatsApp** (mode simulation), **le paiement mobile money réel**, **le vocal**.

## Rejouer automatiquement

```bash
cd transpt1
pytest role_coverage_tests/test_scenario_pilote.py
```

Ces tests jouent le parcours nominal (étapes 1 à 7) et la variante A par l'API, chaque étape avec le compte du rôle
concerné. Ils ne remplacent pas le passage à la main dans le navigateur, mais échouent si une permission ou une règle
métier casse le parcours.
