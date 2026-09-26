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

## Variante B — Corriger une erreur de vente (annulation d'un ticket)

Un ticket vendu **ne se modifie ni ne se supprime** (aucun rôle) : une erreur se corrige par une annulation motivée.
À jouer après l'étape 1.

1. `guichetier_stc` : vendre un ticket « Client Erreur », 4 000 FCFA, espèces → « Ticket vendu à Client Erreur. », jauge
   **2 / 70 places**.
2. `chef_gare_stc` (`/dashboard/gare`) : sur le départ, cliquer « Tickets (2) ». Le bouton « Annuler le ticket » reste
   **grisé** tant que le motif fait moins de 5 caractères (« abc » : grisé ; « Erreur de saisie du prix » : actif).
3. Cliquer « Annuler le ticket ».

**Attendu**
- « **Ticket de Client Erreur annulé : la place est libérée et la vente sort des recettes.** » ; la ligne passe à
  « Annulé » avec le motif et l'heure ; la jauge revient à **1 / 70 places**. Le guichetier voit aussi 1 / 70.
- Les recettes du jour de la direction, la clôture de caisse et la synthèse financière ne comptent plus les 4 000 FCFA
  (vérifié par les tests de l'API, pas rejoué au navigateur). Le contrôleur (`controleur_stc`) ne doit plus lister ce
  passager parmi les tickets valides (à vérifier à la main : non rejoué au navigateur).
- Journal d'audit (variante D) : une ligne « **Annulation — Ticket** » signée du chef de gare, avec `statut valide → annule`
  et le motif.

## Variante C — Planifier, décaler et supprimer un départ

`chef_ligne_stc` (`/dashboard/ligne`, carte « Planifier un départ ») ; `directeur_exploitation_stc` dispose du même formulaire.

1. Choisir la ligne et une date et heure de départ (demain 06:00). Avant l'heure, les listes « Véhicule » et « Chauffeur »
   sont **grisées** (« Choisissez d'abord l'heure ») et le bouton « Planifier le départ » aussi.
2. Une fois l'heure choisie, seuls les véhicules et chauffeurs **libres à cette heure** sont proposés (véhicule ni bloqué ni
   en maintenance, aucun autre départ dans les 8 h). Choisir un véhicule et un chauffeur, « Planifier le départ ».
3. Refaire le formulaire pour la **même heure**, puis 3 h plus tard, puis le surlendemain.

**Attendu**
- « **Départ planifié : la feuille de route du chauffeur est créée.** » ; le départ apparaît dans le tableau, « Planifié ».
- Le véhicule et le chauffeur qu'on vient d'affecter **ne sont plus proposés** pour la même heure ni 3 h plus tard ; ils
  **reviennent** le surlendemain. (Sur la base de démonstration, le 21/09/2026 : 3 véhicules libres à 06:00, 2 après
  l'affectation ; les listes exactes dépendent des départs déjà planifiés.)
- « Réaffecter » → nouvelle heure → « Appliquer » : « Départ réaffecté. » ; la ligne du tableau change d'heure.
- Sur un départ qui a **déjà des tickets**, choisir une nouvelle heure affiche l'avertissement « N ticket(s) déjà vendu(s)
  pour l'heure actuelle : prévenez les voyageurs, aucun message n'est envoyé automatiquement. ». « Supprimer » y est
  **refusé** (« Ce départ a des tickets (même annulés) : il ne peut pas être supprimé. »).
- « Supprimer » un départ **sans ticket** : le départ et sa feuille de route disparaissent.

## Variante D — Le journal d'audit

`pdg_stc`, `secretaire_general_stc`, `qhse_stc` (et `superadmin_demo`) : lien « **Journal d'audit** » dans la barre du haut
(`/audit`). Les autres rôles ne voient pas ce lien, et l'adresse directe les renvoie à leur tableau de bord.

**Attendu** : une ligne par action — date, acteur (nom et rôle), action, objet, changements « avant → après », adresse.
Après les variantes B et C : « Annulation — Ticket », « Création », « Modification » (`date_heure` ancienne → nouvelle) et
« Suppression » de départ, par le bon acteur ; les connexions y figurent aussi. Aucun mot de passe ni empreinte n'apparaît.
Filtres par type d'objet, action et dates ; « Charger plus » ajoute 50 lignes (50 → 100 sur 310 dans l'essai).

Les variantes B, C et D ont été jouées dans un vrai navigateur (21/09/2026, base de démonstration neuve), à l'exception des
points signalés « non rejoué » : aucune erreur JavaScript, aucune réponse refusée hormis le refus volontaire de suppression.

## Variantes E à N — les fonctions ajoutées depuis (jouées automatiquement)

Les variantes suivantes couvrent ce qui a été ajouté après la première version de ce scénario. Elles sont **rejouées
automatiquement, dans un vrai Chrome, par `npm run e2e`** (voir plus bas) ; les étapes ci-dessous permettent de les jouer aussi
à la main. Base de démonstration complète (`seed_demo_users`, `seed_demo_reseau`, `seed_demo_operations`, `seed_demo_tableaux`).

**Variante E — Un colis, de l'enregistrement au retrait.** `bagagiste_stc` : enregistre un colis sur le départ du jour
(description, poids, frais de fret, expéditeur, destinataire + téléphone) → « le code de retrait a été envoyé au destinataire »
(le code n'apparaît **pas** à l'écran ; en mode simulation, lisez-le dans « Notification logs » de l'administration). « Marquer
chargé » → le plan de chargement de la soute s'affiche. `chauffeur_stc` démarre puis termine sa feuille de route ; le colis passe
« arrivé » (le bagagiste de la gare d'arrivée est alerté). Retrait : un mauvais code est refusé (« Code incorrect »), le bon
code remet le colis (statut « retiré »).

**Variante F — Clôture de caisse.** `guichetier_stc` vend deux tickets (espèces, mobile money), voit « Ma caisse du jour » puis
« Clôturer ma caisse » → « clôturée : le chef de gare en est prévenu ». `chef_gare_stc` : l'alerte « Caisse clôturée : … »
dans la cloche, et « Caisses du jour de l'équipe » montre la clôture. Le chef de gare peut régler le niveau d'automatisation de
son guichetier (« Configuration ») : en « manuel », c'est lui qui clôture ; en « automatique », `manage.py cloturer_caisses` le fait.

**Variante G — Contrôle à bord.** `controleur_stc` : « Ouvrir un contrôle » sur un trajet, puis saisir les codes des billets
(vus dans le SMS du voyageur) : un billet neuf = « Billet valide », le même présenté deux fois = « DÉJÀ UTILISÉ », un code
inventé = « INCONNU ». « Clôturer » avec le nombre de voyageurs comptés : le rapport compare aux billets vendus (« 3 voyageur(s) de
plus que de billets vendus »). Un second contrôle avec « Infraction grave » et son motif : `qhse_stc` reçoit l'alerte « Infraction
grave au contrôle » et voit l'incident grave créé.

**Variante H — Suivi GPS, fatigue et relais.** `chef_ligne_stc` planifie un départ demain à 3 h et `chauffeur_stc` (ou
`chauffeur2_stc`) démarre sa feuille de route. Sur la page du chauffeur : « Activer le suivi GPS » (le navigateur demande la
position) → « dernière position envoyée » ; `pdg_stc` voit le car sur la carte du réseau. Au-delà de 4 h 30 de conduite continue :
« Vous conduisez depuis plus de 4 h 30 » avec des relais suggérés ; « Passer le relais » à un autre conducteur, lieu « Toumodi » →
le nouveau conducteur a le trajet, sa fatigue repart de zéro, l'ancien ne conduit plus.

**Variante I — Pouvoirs d'exploitation et de direction.** `chef_ligne_stc` : « Demander la fermeture » d'une ligne (motif) → la
ligne reste ouverte. `directeur_exploitation_stc` : la demande apparaît sous « Arbitrage du réseau » → « Valider » : la ligne est
fermée (badge « Fermée »), `guichetier_stc` ne voit plus ses départs (« départ(s) non proposé(s) : ligne fermée »), `chef_gare_stc`
est alerté. Toujours chez lui : « Gares en tension » (départs des 24 h contre véhicules disponibles) → rattacher un véhicule à
une autre gare (motif) ; les chefs des deux gares sont alertés. `directeur_technique_stc` : « Investissements » → nouvelle
demande. `pdg_stc` : « Pilotage » → rouvrir la ligne, en geler une autre, valider un investissement, refuser l'autre
(**la raison est exigée**), puis suspendre le compte de `guichetier_stc` (motif) : sa session ouverte est coupée à
l'actualisation, sa connexion est refusée ; « Réactiver » le rend tel qu'il était.

**Variante J — L'atelier.** `directeur_technique_stc` : « Déclarer un plan d'entretien » (contrôle technique tous les 90 jours,
dernier il y a 80 jours) → « Bientôt dû ». Lancer `python manage.py generer_alertes` : `chef_atelier_stc` est alerté et un ordre
« Entretien préventif : Contrôle technique » apparaît dans la file, confié au mécanicien le moins chargé, avec son retour
estimé. Le directeur technique le monte devant la révision (même urgence), le confie au chef d'atelier ; l'urgence haute reste
en tête. `mecanicien_stc` : « Demander une pièce » (une en stock, une en rupture proche : la disponibilité s'affiche tout de
suite). `magasinier_stc` : sert la première (le stock baisse, la sortie est liée à l'ordre) et refuse l'autre avec un motif ;
« Réapprovisionnement suggéré » liste la pièce basse. `chef_ligne_stc` voit le retour estimé des véhicules à l'atelier ;
`pdg_stc`, le rapport de renouvellement de la flotte (un véhicule à plus de 600 000 km).

**Variante K — Secrétariat, santé de la gare, conformité.** `secretaire_general_stc` : « Secrétariat » → diffuser une note de service au
pôle technique, ajouter un rendez-vous à l'agenda (le directeur technique invité), classer puis archiver un dossier (il ne se supprime
pas). `mecanicien_stc` et `directeur_technique_stc` : la note et l'invitation sont dans leur cloche ; « Notes de service » la relit.
`chef_gare_stc` : « Santé de la gare » (ponctualité, recettes, véhicules), retirer puis réaffecter un bagagiste de son équipe, envoyer un
message à l'équipe : `guichetier_stc` le reçoit. `qhse_stc` : « Conformité de la flotte » signale « Visite technique périodique en retard »
pour CI-1002-AB.

**Variante L — Comptabilité.** `directeur_financier_stc` : le tableau de bord montre la trésorerie ; « Comptabilité » : le budget carburant du
mois (une ligne à plus de 80 %, une dépassée), fixer le solde de départ, relever un budget, saisir une dépense de carburant sur la ligne
dépassée (le directeur financier et le PDG sont alertés), payer la facture en retard (la dépense s'enregistre seule), ajouter un fournisseur et
sa facture, exporter la rentabilité par ligne et par gare (CSV pour Excel). `pdg_stc` : la trésorerie sur son tableau de bord, « Finances »
(lecture seule, sans bouton de saisie), l'alerte de dépassement.

**Variante M — Ressources humaines.** `guichetier_stc` : « Mon espace » → sa demande de congé en attente, aucune formation obligatoire pour
son poste, déposer une doléance grave. `chauffeur_stc` : sécurité routière (OSER) « à renouveler », visite médicale « à jour ». `drh_stc` :
« Formations obligatoires » → une formation expirée → « Enregistrer une session » → elle passe à jour ; « Congés » → le congé du guichetier
(seul à son poste) affiche un **impact critique** et demande « Valider malgré tout », celui du chauffeur signale les **départs à réaffecter**
(l'exploitation est alertée) ; « Médiation sociale » → instruire la doléance (une étape visible de l'agent, une note interne qui ne l'est pas) ;
« Recrutement » → personnaliser puis rétablir la fiche type d'un poste, retenir deux candidats : l'offre est pourvue ; « Dossiers » → « Fiche
complète » d'un agent : contrat, évaluation existante, nouvelle évaluation.

**Variante N — Juridique.** `responsable_juridique_stc` : l'alerte « Risque de litige social (grave) » et l'onglet « Litiges sociaux » (le poste de
l'auteur, jamais son identité) ; un accident déclaré par `chauffeur_stc` ouvre le sinistre → « Pièces » : référence de l'assureur, montant estimé,
joindre un constat PDF puis le télécharger (identique à l'original) ; « Modèles de documents » : publier un modèle réservé aux fonctions supports,
joindre un fichier à un autre. `guichetier_stc`, `mecanicien_stc`, `drh_stc` : « Modèles juridiques » ne montre que les modèles ouverts à leur pôle ;
recherche, lecture, copie du texte, téléchargement. `pdg_stc` : « Synthèse RH et juridique » (points de vigilance, chiffres de la gestion RH).

## Ce que ce scénario ne couvre pas

- **Le mobile** : l'application n'a pas été lancée sur un téléphone (aucun émulateur possible sur la machine de
  développement). Côté chauffeur, elle n'affiche que la feuille de route : checklist, départ et incident se font sur
  le web. L'APK *release* est compilé et signé, mais **jamais installé** : voir `mobile/TEST_TELEPHONES.md`.
- **Les envois réels de SMS et WhatsApp** (mode simulation), **le paiement mobile money réel**, **le vocal**.
- **Le GPS d'un vrai téléphone** : la variante H a été jouée avec une position simulée dans un navigateur de test, jamais en roulant.
- **Ce qui reste à faire du cahier des charges** (rotation des quais, passage de service, moteur vocal, application mobile à jour…) :
  voir `RAPPORT_CONFORMITE.md`. Les modules RH, finance et juridique n'ont été essayés qu'avec les données de démonstration.
- **L'avertissement des voyageurs quand un départ vendu est décalé** : aucun message automatique (avertissement à l'écran seulement).

## Rejouer automatiquement

```bash
cd transpt1
pytest role_coverage_tests/test_scenario_pilote.py
```

Les variantes E à N se rejouent dans un vrai navigateur :

```bash
cd frontend
npm run e2e                 # quatorze scénarios (base jetable, API et site lancés pour l'occasion) ; environ 8 minutes
npm run e2e -- atelier      # un seul (le filtre porte sur le nom du scénario ; « jeu,caisse » en joue deux)
```

Ces tests jouent le parcours nominal (étapes 1 à 7) et la variante A par l'API, chaque étape avec le compte du rôle
concerné. Les variantes B, C et D ont leurs propres tests : `role_coverage_tests/test_tickets_verrouilles.py` (annulation),
`billetterie/tests/test_planification.py` (planification) et `audit/tests/` (journal). Ils ne remplacent pas le passage à la main dans le navigateur, mais échouent si une permission ou une règle
métier casse le parcours.
