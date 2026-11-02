# Rapport de conformité au cahier des charges

**Document vérifié** : `cahier.txt` — « Logiciel de coordination gamifié pour compagnie de transport routier » (5 pôles, 18 postes,
99 fonctionnalités par poste, exigences techniques et transverses).
**Code vérifié** : ce dépôt — serveur Django (`transpt1/`), site web React (`frontend/`), application mobile Flutter (`mobile/`).
**Date** : 21 septembre 2026. Ces changements ont depuis été commités sur la branche `transport` (voir `git log`).

> **Mise à jour (24 septembre 2026).** Relecture demandée après l'audit sécurité du même jour
> (`AUDIT_SECURITE_FONCTIONNEL_2026-09-24.md`) : les résumés (§1, §6.1) affirmaient à tort que le secrétariat général
> (n° 7, 8, 9) et le tableau de conformité réglementaire (n° 12, 96) restaient à faire, alors que le §4 les listait déjà
> ✅ complets au moment même de la rédaction de ce rapport — corrigé ci-dessous. Par ailleurs, la commande vocale ajoutée
> au mobile depuis (vente de ticket, checklist avant-départ, en français) fait passer la fonctionnalité n° 34 d'absente à
> partielle et enrichit la n° 46 (§4.2, §4.3, §5) ; et l'app `tutelle`, ajoutée depuis, prépare désormais les flux vers le
> Ministère/OSER même si aucun système externe n'y répond encore (§5). Le compte des 99 fonctionnalités passe de
> 62/19/18 à **62/20/17** (≈ 73 %).
>
> **Complément (même jour, chantier GPS haute performance)** : suivi natif en arrière-plan dans l'application mobile
> (`mobile/lib/gps/`, démarré/arrêté tout seul selon l'état du trajet côté serveur, jamais essayé sur un vrai
> téléphone), carte du réseau poussée en temps réel par WebSocket au lieu d'un rafraîchissement périodique seul
> (`dashboard/consumers.py`, `frontend/src/api/useFluxCarte.js`), et passage à l'échelle du suivi GPS côté serveur
> (index manquant corrigé, purge des relevés anciens) — voir la n° 48 et la ligne « GPS des véhicules » du §5.

## 1. En bref

- **Avant** : sur les 99 fonctionnalités, 10 complètes, 30 partielles, 59 absentes (≈ 25 %, une partielle comptant pour moitié).
- **Maintenant** : **62 complètes, 20 partielles, 17 absentes** (≈ **73 %**). Le détail, ligne par ligne, est au §4.
- **Tout ce qui a été ajouté est testé** : 4 374 tests du serveur (1 206 au départ), 42 tests du site, et 14 scénarios de bout
  en bout joués dans un vrai navigateur contre une vraie base (chaque poste se connecte et voit son tableau de bord, blocage
  QHSE, colis, jeu, configuration, caisse, suivi GPS, contrôle des billets, pouvoirs de direction, atelier).
- **Ce qui manque encore** (§6) : la plupart des fonctions RH, finance et juridique au-delà de l'existant (congés,
  formations obligatoires, recrutement, médiation, budget carburant, rentabilité, fournisseurs, trésorerie, reporting,
  bibliothèque juridique), la rotation des quais, le carnet de route numérique, la checklist de reprise vocale, le
  **moteur vocal** multilingue (commencé en français sur deux écrans du mobile depuis), et l'essai réel de
  l'**application mobile** sur téléphone.
- **Ce qui ne pouvait pas être fait ici** : tout ce qui demande un compte, un appareil ou un service extérieur — envoi réel de
  SMS / WhatsApp, paiement Mobile Money, essai sur de vrais téléphones et de vrais cars, un vrai système côté Ministère/OSER,
  hébergement (§6).

| Pôle | Fonctionnalités | Avant (F / P / A) | Maintenant (F / P / A) |
|---|---|---|---|
| Direction Générale | 13 | 2 / 3 / 8 | **11 / 2 / 0** |
| Exploitation & Réseau | 31 | 4 / 8 / 19 | **21 / 7 / 3** |
| Personnel roulant | 19 | 0 / 8 / 11 | **10 / 7 / 2** |
| Technique & Maintenance | 18 | 2 / 8 / 8 | **16 / 2 / 0** |
| Fonctions supports | 18 | 2 / 3 / 13 | **4 / 2 / 12** |
| **Total** | **99** | 10 / 30 / 59 | **62 / 20 / 17** |

## 2. Méthode

1. **Lecture du cahier** et découpage en 99 fonctionnalités (chaque ligne « Actions clés » d'un poste, coupée à ses « ; » ; les lignes
   du secrétaire général et du QHSE, écrites sans « ; », sont découpées en 3 et 4). Le total par pôle est celui de `ANALYSE_PROJET.md`.
2. **Règle de classement** (la même avant et après) : **Complète** = utilisable dans l'interface web sans contournement (ni
   administration Django, ni appel d'API à la main), avec les règles métier appliquées par le serveur ; **Partielle** = une partie
   seulement, ou disponible par l'API seulement, ou une modalité demandée par le cahier manque (voix, carte réelle, paiement réel) ;
   **Absente** = rien d'utilisable. En cas de doute, la classe la plus basse.
3. **Vérification indépendante** : chaque fonctionnalité a été rapprochée du code (modèles, routes, écrans), pas de la documentation.
   Les écarts trouvés ont été corrigés ou consignés ici.
4. **Preuve par les tests** : chaque ajout a ses tests (règles métier, permissions par rôle, isolation entre compagnies), la matrice
   de conformité (chaque rôle × chaque endpoint restreint) et le contrat entre pages web et API ont été étendus, et les parcours
   d'ensemble sont rejoués dans Chrome (`npm run e2e`).

## 3. Ce qui a été fait

Ordre de réalisation ; chaque bloc renvoie aux fonctionnalités du §4.

| Bloc | Contenu | Fonctionnalités |
|---|---|---|
| **Poste manquant** | Le **mécanicien** n'existait pas comme rôle (les tests utilisaient un bagagiste ou un chauffeur à sa place) : rôle, page, droits (ses ordres, ses sorties de pièces), formation | 76–81 |
| **Alertes inter-pôles** | Application `alertes` : une action d'un pôle prévient le pôle concerné (cloche sur toutes les pages, lecture individuelle) ; génération automatique (seuils critiques, départs à risque, assurances, fatigue, entretiens, renouvellements) ; **blocage de sécurité par le QHSE** avec notification immédiate | 2, 13, 17, 23, 28 |
| **Sécurité et qualité** | Limitation des essais de connexion (429), **tarif de ligne imposé à la vente** (une fraude au prix était possible), unicité des références de pièces **par compagnie** (une compagnie pouvait deviner les références d'une autre), dépendances de production séparées de celles de test, `pip-audit` et `npm audit` sans vulnérabilité connue | — |
| **Colis** | Application `colis` : enregistrement, chargement, arrivée, retrait par **code** (empreinte seulement, jamais affiché), notifications aux clients, plan de chargement, fret dans la synthèse financière ; **équipes locales** des gares | 21, 37–44 |
| **Configuration hiérarchique** | Cadre de la compagnie → poste → agent (automatisation, gamification, fonctions), **appliqué par le serveur** ; **clôture de caisse** manuelle / assistée / automatique | 30, 35, 36 |
| **Gamification** | Missions du jour, points, niveaux, badges, classements (gares, lignes, chauffeurs, guichetiers, bagagistes, ateliers, contrôleurs), **calculés à partir des données réelles** ; niveau réglable par poste (direction, RH, finance, juridique démarrent « sobres ») | 6, 24, 30, 36, 43, 51, 57, 63, 75, 81, 84 |
| **Suivi de trajet** | Positions GPS par lots (zones sans réseau), conduite continue, pauses, **alerte fatigue**, **relais** de conducteur (feuille de route et suivi transférés), mode convoyeur (anomalie de cargaison), **carte du réseau**, incident géolocalisé | 5, 47, 48, 52–54, 56 |
| **Contrôle à bord** | Le billet a désormais un **code** et une date d'utilisation (migration de données relue et testée) ; le contrôleur ouvre un contrôle, vérifie les billets (valide, déjà utilisé, annulé, inconnu…), clôture avec ses constats, obtient le **rapport** (voyageurs et charge comparés) ; infraction grave = alerte directe direction et QHSE ; historique par ligne et par chauffeur | 58–63 |
| **Pouvoirs d'exploitation et de direction** | **Fermeture de ligne** (demandes des chefs, décision du directeur des opérations, « gel » par le PDG ; une ligne fermée refuse planification et vente et se rouvre seule), **gare d'attache** des véhicules et **arbitrage entre gares en tension**, **suspension de compte** par le PDG (sessions coupées aussitôt), **investissements** décidés par le PDG | 3, 4, 14–17 |
| **Maintenance avancée** | File des réparations par urgence (réordonnable), délai estimé remonté à la régulation, répartition avec vue de charge, **entretien préventif automatique** (alerte puis ordre ouvert au mécanicien le moins chargé), demandes de pièces au magasinier, suggestion de commande, fiche véhicule (pannes récurrentes), **besoin de renouvellement** | 64–69, 71, 73, 74, 76–80 |
| **Environnement d'essai** | Essais de bout en bout dans un vrai navigateur (Playwright + Chrome installé, base jetable), tests unitaires du site (vitest), règle de ponctualité **partagée** entre serveur et site (fichier de cas commun), intégration continue (`.github/workflows/ci.yml`, jamais exécutée sur GitHub) | — |
| **Documentation** | `PERMISSIONS.md` (qui peut quoi, fait foi), `DEPLOIEMENT.md` (tâches planifiées, réglages, limites), `README.md`, `SCENARIO_PILOTE.md` (variantes E à J), ce rapport | — |

### Anomalies trouvées et corrigées en chemin

- Le rôle **mécanicien** n'existait pas (voir plus haut).
- Un guichetier pouvait fixer librement le **prix** d'un billet (fraude de caisse) : le tarif de la ligne est imposé, un autre prix exige
  un chef et un motif, et le tarif d'origine reste sur le ticket.
- Impossible de détecter un **ticket déjà utilisé** : le serveur n'enregistrait pas la validation. Un billet valide est maintenant marqué
  utilisé, une seule fois, sous verrou de base de données.
- La liste d'alertes du **superadmin** (sans compagnie) répondait par une erreur : corrigée.
- Après la validation d'une demande de fermeture, un bloc de l'écran restait sur l'ancien état (« Ouverte ») : trouvé par l'essai de bout
  en bout, corrigé (les blocs d'une même page se rechargent ensemble).
- L'annonce « Mission accomplie » ne dure que 8 secondes : l'essai automatique du jeu a été réécrit pour ne plus en dépendre.
- Un test de migration créait des lignes avec un état ancien des tables voisines : rendu indépendant des migrations suivantes.

### Choix et écarts par rapport au cahier (à valider avec la compagnie)

- Le **score de ligne** est réglé par le directeur des opérations (dont dépend le chef de ligne), pas par le chef de gare (n° 30).
- **Investissements** : trois postes demandent (technique, exploitation, finance), le PDG seul décide. **Fermeture de ligne** : le chef de
  ligne et le chef de gare *demandent*, le directeur des opérations *valide*, le PDG et lui peuvent aussi *décider seuls*.
- **Suspension de compte** plutôt que suppression : l'historique (ventes, contrôles, journal d'audit) garde son auteur.
- Le **renouvellement de flotte** repose sur des seuils (600 000 km, 8 réparations et 60 jours d'immobilisation sur 12 mois) posés par
  défaut : à calibrer avec le technique.
- La **tension d'une gare** compare les départs des prochaines 24 h aux véhicules *disponibles* qui lui sont rattachés : c'est une
  heuristique (le modèle ne connaît pas la durée d'un trajet), pas un plan de flotte.
- Le **kilométrage** est relevé par le technique (pas par les chauffeurs).

## 4. Les 99 fonctionnalités, une par une

**Légende** : ✅ complète · 🟡 partielle · ⬜ absente. « Où c'est fait » renvoie à l'API, à l'écran ou aux tests ; « Ce qui reste »
dit précisément ce qui manque pour passer à ✅.

### 4.1 Direction Générale (PDG, secrétaire général, QHSE)

| # | Poste | Fonctionnalité du cahier | État | Où c'est fait / preuve | Ce qui reste |
|---|---|---|---|---|---|
| 1 | PDG | Tableau de bord « santé de l'entreprise » : KPIs financiers, opérationnels et RH, par gare et pour le réseau | 🟡 Partielle | `/api/dashboard/direction/`, page Direction : recettes du jour, disponibilité de la flotte, ponctualité, incidents, pièces, assurances, tuiles par gare, carte, renouvellement de flotte | Dépenses et marge (aucune donnée de dépenses), KPI RH consolidés |
| 2 | PDG | Alertes automatiques sur seuils critiques (recette en baisse, pannes en hausse, retards récurrents) | ✅ Complète | `alertes/generation.py` (`seuils_critiques`) → cloche du PDG ; tests `alertes/tests` | Nécessite `manage.py generer_alertes` planifié (DEPLOIEMENT.md §10) |
| 3 | PDG | Pouvoir d'intervention directe : geler une ligne, réaffecter un véhicule ou un chauffeur, bloquer un compte guichetier | ✅ Complète | Page Pilotage : geler/rouvrir une ligne, réaffecter un véhicule entre gares (« Gares en tension ») et le véhicule ou le chauffeur d'un départ planifié, suspendre/réactiver un compte (sessions coupées) ; tests `reseau/tests/test_fermeture_ligne.py`, `core/tests/test_comptes.py` ; e2e « pouvoirs » | — |
| 4 | PDG | Validation des investissements (achat de cars, ouverture de ligne) | ✅ Complète | `/api/investissements/` (demande par technique / exploitation / finance, décision du PDG seul, raison exigée au refus) ; pages Pilotage et Investissements ; 39 tests | — |
| 5 | PDG | Vue carte temps réel du réseau | 🟡 Partielle | Carte SVG du réseau avec les cars en route (`/api/dashboard/carte/`, `CarteReseau`) alimentée par les positions GPS des chauffeurs | Pas de fond de carte ; positions envoyées par le navigateur du chauffeur (page ouverte), jamais essayé sur un vrai téléphone en roulant |
| 6 | PDG | Classement des gares / chauffeurs | ✅ Complète | `/api/gamification/classement/` (gares, lignes, chauffeurs, guichetiers, bagagistes, ateliers, contrôleurs) ; bandeau « Classements » | — |
| 7 | Secrétaire général | Agenda partagé de la direction | ✅ Complète | `/api/agenda/` (lu par la direction, tenu par le secrétaire général et le PDG ; invités alertés) ; page Secrétariat ; e2e « secrétariat » | — |
| 8 | Secrétaire général | Diffusion directe de notes de service aux pôles concernés | ✅ Complète | `/api/notes-service/` : adressées à des pôles, des postes ou à tous, dans la cloche de chaque poste visé et relisibles (page Notes de service) ; e2e « secrétariat » | — |
| 9 | Secrétaire général | Classement et archivage des dossiers administratifs | ✅ Complète | `/api/archives/` : registre des dossiers (catégorie, référence, emplacement, mots-clés), recherche, archivage sans suppression ; page Secrétariat | Le registre ne contient pas le fichier (il dit où le retrouver) |
| 10 | QHSE | Checklist sécurité par véhicule/gare avant chaque départ | ✅ Complète | Checklist du chauffeur liée au blocage du véhicule (existait) ; alerte au QHSE sur défaut | — |
| 11 | QHSE | Déclaration et suivi des incidents depuis le terrain | ✅ Complète | Incidents (existait) ; désormais géolocalisés, alertés à la régulation, au QHSE et au technique | — |
| 12 | QHSE | Tableau de conformité réglementaire | ✅ Complète | `/api/conformite/` : assurance, obligations réglementaires (plans d'entretien marqués « réglementaire »), défauts de checklist ouverts, blocages, par véhicule et en taux ; page QHSE ; e2e « secrétariat » | Permis et visites médicales des conducteurs (aucune donnée : pas de dossier de conducteur détaillé) |
| 13 | QHSE | Pouvoir de bloquer le départ d'un véhicule en défaut de sécurité, avec notification immédiate au chef de gare et au chef d'atelier | ✅ Complète | `/api/blocages-securite/` (+ `lever`), page QHSE ; alerte au chef de la gare de départ, au chef d'atelier, au directeur technique et à la régulation ; e2e « coordination » | — |

### 4.2 Exploitation & Réseau

| # | Poste | Fonctionnalité du cahier | État | Où c'est fait / preuve | Ce qui reste |
|---|---|---|---|---|---|
| 14 | Directeur des opérations | Tableau de bord temps réel de toutes les gares et lignes | ✅ Complète | `/api/dashboard/exploitation/` : ponctualité, remplissage, retards, flotte, incidents ; désormais aussi tension par gare et état de fermeture des lignes | — |
| 15 | Directeur des opérations | Arbitrage direct des réaffectations de véhicules entre gares en tension | ✅ Complète | Gare d'attache des véhicules, « Gares en tension » (départs 24 h vs véhicules disponibles), `POST /api/vehicules/{id}/reaffecter-gare/` ; e2e « pouvoirs » | — |
| 16 | Directeur des opérations | Validation d'ouverture/fermeture temporaire d'une ligne | ✅ Complète | Demandes des chefs de ligne / de gare, décision du directeur ; une ligne fermée refuse planification et vente, se rouvre seule à la date de fin ; 76 tests, e2e « pouvoirs » | — |
| 17 | Directeur des opérations | Réception automatique des alertes des chefs de gare, chefs de ligne, QHSE et technique nécessitant un arbitrage | ✅ Complète | Cloche d'alertes : pénurie, demandes sur les lignes, incidents graves, retards ; `alertes/` (84 tests) | — |
| 18 | Chef de gare | Rotation des quais assistée (ordre d'embarquement proposé, validé ou ajusté) | ⬜ Absente | — | Proposition d'ordre d'embarquement par gare et par quai |
| 19 | Chef de gare | Recettes du jour calculées automatiquement depuis la billetterie guichet et mobile | ✅ Complète | « Santé de la gare » : recettes du jour de la gare (billets par mode de paiement + fret) calculées depuis la billetterie ; `/api/dashboard/gare/` | — |
| 20 | Chef de gare | Tableau de bord « santé de la gare » (ponctualité, remplissage, incidents) | ✅ Complète | « Santé de la gare » : ponctualité (jour et 7 jours), remplissage, incidents ouverts, retards, véhicules, équipe ; 26 tests ; e2e « secrétariat » | — |
| 21 | Chef de gare | Affectation des équipes locales (guichetiers, bagagistes) | ✅ Complète | « Mon équipe locale » : le chef de gare affecte ou retire guichetiers et bagagistes de sa gare (`/api/affectations-gare/`) ; e2e « secrétariat » | — |
| 22 | Chef de gare | Message/appel vocal direct vers son équipe et les chauffeurs en approche | 🟡 Partielle | `/api/messages-directs/` : message à l'équipe locale et/ou aux chauffeurs dont le car arrive à la gare, dans leur cloche d'alertes ; e2e « secrétariat » | Appel vocal (moteur vocal) |
| 23 | Chef de gare | Alerte prédictive de retard avant qu'il ne devienne un incident | ✅ Complète | `alertes/generation.py` (`departs_a_risque` : départ dans l'heure sans checklist, retard prévisible) → chef de la gare de départ | Nécessite `generer_alertes` planifié |
| 24 | Chef de gare | Score de gare alimentant le classement inter-gares | ✅ Complète | `gamification/scores.py` (ponctualité, remplissage, recettes) ; classement « gares » | — |
| 25 | Chef de ligne | Planning de rotation assisté (le système propose chauffeur + véhicule, le régulateur valide) | 🟡 Partielle | Écran de planification : `disponibilites` ne propose que véhicules et chauffeurs réellement libres (fenêtre de 8 h) ; niveau d'automatisation configurable | Pas de proposition d'un couple « meilleur » calculé : le régulateur choisit parmi les libres |
| 26 | Chef de ligne | Réaffectation en un geste avec suggestion automatique d'un remplaçant | ✅ Complète | `remplacants-possibles` + réaffectation (existait), alerte de pénurie | — |
| 27 | Chef de ligne | Tableau de bord « santé de la ligne » | ✅ Complète | Page Chef de ligne (existait) + retour estimé des véhicules à l'atelier | — |
| 28 | Chef de ligne | Alerte automatique au chef de gare ou au directeur des opérations en cas de pénurie de véhicule ou de chauffeur | ✅ Complète | Alerte `penurie` quand `remplacants-possibles` ne trouve personne ; tests `alertes` | — |
| 29 | Chef de ligne | Commande vocale multilingue pour affecter rapidement un chauffeur | ⬜ Absente | — | Moteur vocal (voir §5) |
| 30 | Chef de ligne | Score de ligne alimentant le classement, configurable par le chef de gare | 🟡 Partielle | Score et classement des lignes ; configuration hiérarchique (cadre → poste → agent) | Le score de ligne se règle par le directeur des opérations (le chef de ligne est sous son autorité), pas par le chef de gare |
| 31 | Guichetier | Vente assistée en un geste (ligne, horaire, tarif automatique, ticket physique ou mobile) | ✅ Complète | `Ligne.tarif` imposé à la vente, dérogation motivée réservée aux chefs, code du billet envoyé par SMS ; page Guichetier | Pas d'impression d'un ticket papier |
| 32 | Guichetier | Encaissement unifié espèces et mobile money | 🟡 Partielle | Les deux modes sont enregistrés et unifiés dans la caisse et la clôture | Aucune intégration de paiement (Orange Money, MTN MoMo, Wave) : le mode est déclaratif |
| 33 | Guichetier | Jauge de remplissage du car en direct, visible du chef de ligne | ✅ Complète | Jauge sur les départs (existait) | — |
| 34 | Guichetier | Commande vocale multilingue pour vendre un ticket | 🟡 Partielle | Application mobile (`mobile/lib/voice/`) : dicter la vente (ligne, place, prix, paiement), récapitulatif parlé avant confirmation, même validation que le bouton tactile | Français seulement (pas de langues locales) ; absente du site web guichetier |
| 35 | Guichetier | Clôture de caisse automatique en fin de service, transmise au chef de gare | ✅ Complète | `ClotureCaisse`, niveaux manuel / assisté / automatique, `manage.py cloturer_caisses`, alerte au chef de gare ; e2e « caisse » | Nécessite `cloturer_caisses` planifié |
| 36 | Guichetier | Score de guichetier alimentant le classement | ✅ Complète | Gamification (ventes, absence d'annulations) ; e2e « jeu » | — |
| 37 | Bagagiste | Enregistrement rapide bagage/colis (type, poids estimé, valeur déclarée, ticket ou envoi seul) | ✅ Complète | App `colis` (98 tests), page Bagagiste ; e2e « colis » | — |
| 38 | Bagagiste | Encaissement des frais de fret/colis unifié espèces et mobile money | 🟡 Partielle | Frais enregistrés avec le mode de paiement, consolidés dans la synthèse financière (`fret`, `total_general`) | Aucune intégration de paiement |
| 39 | Bagagiste | Aide au chargement (répartition du poids en soute) | ✅ Complète | `GET /api/departs/{id}/plan-chargement/` + page Bagagiste | — |
| 40 | Bagagiste | Suivi de statut colis de bout en bout, consultable par expéditeur et destinataire | 🟡 Partielle | Statuts enregistré → chargé → arrivé → retiré ; expéditeur et destinataire prévenus à chaque étape par SMS / WhatsApp | Pas de consultation à la demande par le client (le client n'a pas accès au logiciel) |
| 41 | Bagagiste | Commande vocale multilingue | ⬜ Absente | — | Moteur vocal (voir §5) |
| 42 | Bagagiste | Alerte de restitution envoyée au bagagiste de la gare d'arrivée au départ du car | ✅ Complète | Alerte `colis` à l'arrivée ; e2e « colis » | — |
| 43 | Bagagiste | Score du bagagiste alimentant le classement | ✅ Complète | Gamification (colis enregistrés, chargés, remis) ; classement « bagagistes » | — |
| 44 | Bagagiste | Code de retrait envoyé au client par SMS ou WhatsApp à l'enregistrement | ✅ Complète | Code stocké sous forme d'empreinte, jamais affiché ; essais limités ; simulation par défaut | Envoi réel non essayé ; WhatsApp en texte libre (pas de modèle approuvé) |

### 4.3 Personnel roulant

| # | Poste | Fonctionnalité du cahier | État | Où c'est fait / preuve | Ce qui reste |
|---|---|---|---|---|---|
| 45 | Chauffeur principal | Feuille de route du jour consultable ou écoutable, envoyée par le chef de ligne | 🟡 Partielle | Feuille de route web et mobile (existait) | Lecture à voix haute (moteur vocal) |
| 46 | Chauffeur principal | Checklist avant-départ simplifiée (vocale ou par icônes), liée au blocage du QHSE | 🟡 Partielle | Checklist liée au blocage (existait) ; commande vocale en français sur mobile depuis (`mobile/lib/voice/`) | Version par icônes ; voix en français seulement (langues locales absentes) |
| 47 | Chauffeur principal | Signalement d'incident/panne en un geste ou à la voix, géolocalisé, alerte au chef de ligne et au technique | 🟡 Partielle | Incident géolocalisé (position du navigateur), alertes ; page Chauffeur | Saisie à la voix |
| 48 | Chauffeur principal | Suivi GPS du trajet avec alerte fatigue suggérant une pause ou le relais | 🟡 Partielle | Positions par lots (`/api/positions/`), conduite continue, pauses, alerte à 4 h 30 avec relais suggérés ; 98 tests ; e2e « suivi ». Depuis, suivi natif dans l'application mobile (`mobile/lib/gps/`), continue en arrière-plan (service de premier plan Android), démarré/arrêté tout seul selon l'état du trajet côté serveur ; 19 tests | Mobile jamais essayé sur un vrai téléphone (comme le reste de l'application) ; le comportement des fabricants qui tuent agressivement les services d'arrière-plan n'a pas pu être vérifié |
| 49 | Chauffeur principal | Carnet de route et documents du véhicule numériques | ⬜ Absente | — | Documents du véhicule (assurance, contrôle technique) consultables par le chauffeur, historique des trajets |
| 50 | Chauffeur principal | Formation sécurité intégrée (modules courts et quiz, y compris vocaux) | 🟡 Partielle | Parcours de formation simulés par poste (`formation/`, existait) | Modules vocaux ; parcours pour tous les postes |
| 51 | Chauffeur principal | Score du chauffeur alimentant le classement | ✅ Complète | Gamification (ponctualité, pauses, zéro incident) ; classement « chauffeurs » | — |
| 52 | Chauffeur relais | Transfert de la feuille de route et de l'état du véhicule en un geste au relais | ✅ Complète | `POST /api/feuilles-de-route/{id}/relais/` ; e2e « suivi » | — |
| 53 | Chauffeur relais | Notification automatique du lieu et de l'heure de relais | ✅ Complète | Alerte `relais` au nouveau conducteur, à la régulation et aux gares | — |
| 54 | Chauffeur relais | Continuité du suivi GPS et de l'alerte fatigue, bascule sur le nouveau conducteur | ✅ Complète | Fatigue remise à zéro pour le nouveau conducteur, ancien conducteur dessaisi ; e2e « suivi » | — |
| 55 | Chauffeur relais | Checklist de reprise vocale | ⬜ Absente | — | Checklist de reprise au relais (et sa version vocale) |
| 56 | Chauffeur relais | Mode surveillance cargaison (convoyeur) avec alerte en cas d'anomalie | ✅ Complète | `anomalie-cargaison` : incident grave géolocalisé, alerte régulation / direction / QHSE ; bouton dans le suivi de trajet | — |
| 57 | Chauffeur relais | Score du relais alimentant le classement | ✅ Complète | Gamification (groupe « chauffeurs ») | — |
| 58 | Contrôleur de ligne | Scan/vérification instantanée des tickets (physique ou mobile), détection d'un ticket déjà utilisé ou invalide | 🟡 Partielle | Code du billet saisi ou lu par un lecteur de codes ; valide / déjà utilisé / annulé / inconnu / autre départ ; le billet valide est marqué utilisé ; 39 tests ; e2e « contrôle » | Pas de lecture de QR code par la caméra |
| 59 | Contrôleur de ligne | Vérification de charge comparée aux données du guichetier et du bagagiste | ✅ Complète | Rapport : voyageurs constatés vs billets vendus, charge constatée vs colis enregistrés | — |
| 60 | Contrôleur de ligne | Rapport de contrôle généré en un geste ou à la voix | 🟡 Partielle | Rapport généré à la clôture, consultable ensuite | Génération à la voix |
| 61 | Contrôleur de ligne | Alerte directe et indépendante vers la Direction/QHSE en cas d'infraction grave | ✅ Complète | Infraction déclarée, surcharge ou 3 billets frauduleux : incident grave + alerte direction / QHSE ; e2e « contrôle » | — |
| 62 | Contrôleur de ligne | Historique de contrôle par ligne et par chauffeur | ✅ Complète | `/api/controles/?ligne=&chauffeur=` + tableau filtrable | — |
| 63 | Contrôleur de ligne | Score de contrôle alimentant le classement | ✅ Complète | Gamification (contrôles, billets vérifiés, infractions) ; classement « contrôleurs » | — |

### 4.4 Technique & Maintenance

| # | Poste | Fonctionnalité du cahier | État | Où c'est fait / preuve | Ce qui reste |
|---|---|---|---|---|---|
| 64 | Directeur technique | Tableau de bord « santé de la flotte » (disponibilité, kilométrage, prochaine échéance, véhicules bloqués) | ✅ Complète | Page Technique : disponibilité, bloqués, kilométrage relevé, plans d'entretien par échéance | — |
| 65 | Directeur technique | Planning de maintenance préventive automatisé avec alerte avant échéance | ✅ Complète | `PlanEntretien` (jours et/ou km), alerte + ordre de réparation ouvert tout seul par `generer_alertes` ; 50 tests ; e2e « atelier » | Nécessite `generer_alertes` planifié |
| 66 | Directeur technique | File d'attente des réparations classée par urgence, validée ou réordonnée | ✅ Complète | `/api/ordres-reparation/{file-attente,reordonner,prioriser}` ; l'urgence prime sur la position | — |
| 67 | Directeur technique | Vue consolidée des ordres en cours avec délai estimé, remontée au régulateur | ✅ Complète | Retour estimé dans la file (lisible de tous) ; bloc « Véhicules à l'atelier » du chef de ligne et du directeur des opérations | — |
| 68 | Directeur technique | Rapport de besoin de renouvellement généré automatiquement pour la Direction Générale | ✅ Complète | `/api/maintenance/besoin-renouvellement/` (kilométrage, réparations, immobilisation) ; page Direction ; alerte trimestrielle | Seuils à calibrer avec la compagnie |
| 69 | Directeur technique | Score de disponibilité de flotte alimentant le tableau de bord du PDG | ✅ Complète | `disponibilite_flotte_pourcent` sur le tableau de bord de la direction | — |
| 70 | Magasinier | Stock en temps réel, mis à jour à chaque sortie enregistrée par un mécanicien | ✅ Complète | Sortie de pièce du mécanicien pour ses ordres (existait, testé) | — |
| 71 | Magasinier | Alerte rupture de stock avec seuil configurable par pièce | ✅ Complète | Seuil par pièce, alerte au magasinier et au technique quand la sortie passe sous le seuil | — |
| 72 | Magasinier | Sortie de pièce en un geste ou à la voix, liée à l'ordre de réparation | 🟡 Partielle | Sortie liée à l'ordre ; « Servir » une demande de pièce en un geste | Saisie à la voix |
| 73 | Magasinier | Suggestion de commande de réapprovisionnement selon la consommation habituelle | ✅ Complète | `/api/pieces/suggestions-commande/` (consommation 90 jours, deux mois de couverture) ; bloc « Réapprovisionnement suggéré » | — |
| 74 | Magasinier | Traçabilité pièce ↔ véhicule pour repérer les pannes récurrentes | ✅ Complète | Fiche véhicule : pièces montées, pièce remplacée 2 fois en 180 jours = panne récurrente | — |
| 75 | Magasinier | Score du magasinier alimentant le classement | ✅ Complète | Gamification (sorties enregistrées, ruptures évitées) | — |
| 76 | Chef d'atelier / Mécanicien | Ordre de réparation numérique reçu du directeur technique ou déclenché par une alerte de maintenance préventive | ✅ Complète | Ordres créés par le technique ou ouverts par le préventif, alerte au mécanicien ; page Mécanicien | — |
| 77 | Chef d'atelier / Mécanicien | Fiche véhicule complète (historique, pannes récurrentes, pièces montées) | ✅ Complète | `/api/fiche-vehicule/{id}/` + composant « Fiche véhicule » | — |
| 78 | Chef d'atelier / Mécanicien | Demande de pièce en un geste ou à la voix au magasinier, avec confirmation de disponibilité | 🟡 Partielle | `/api/demandes-pieces/` : disponibilité confirmée à la demande, magasinier alerté, servie = sortie sur l'ordre ; 44 tests ; e2e « atelier » | Saisie à la voix |
| 79 | Chef d'atelier / Mécanicien | Clôture d'intervention simplifiée (temps, pièces, statut du véhicule) qui libère le véhicule | ✅ Complète | Clôture par le mécanicien : temps passé, véhicule redevenu disponible, alerte à la régulation | — |
| 80 | Chef d'atelier / Mécanicien | Répartition des interventions entre mécaniciens avec vue de charge | ✅ Complète | `/api/maintenance/charge-mecaniciens/` + réaffectation d'un ordre | — |
| 81 | Chef d'atelier / Mécanicien | Score de l'atelier alimentant le classement | ✅ Complète | Gamification (interventions clôturées dans les délais) ; classement « ateliers » | — |

### 4.5 Fonctions supports

| # | Poste | Fonctionnalité du cahier | État | Où c'est fait / preuve | Ce qui reste |
|---|---|---|---|---|---|
| 82 | DRH | Dossier agent centralisé par poste (contrat, formation, évaluations, discipline), selon la configuration hiérarchique | 🟡 Partielle | Dossier agent (statut, poste, embauche, notes) réservé au DRH (existait) | Contrat, évaluations, discipline, formations suivies |
| 83 | DRH | Suivi automatique des formations obligatoires avec alerte de renouvellement OSER, lié au QHSE | ⬜ Absente | — | Formations obligatoires, échéances, alertes ; lien OSER = intégration externe |
| 84 | DRH | Vue transversale des scores de gamification par agent comme aide à l'évaluation | ✅ Complète | `/api/gamification/agents/` (DRH, PDG) ; page RH | — |
| 85 | DRH | Plannings et congés avec vue d'impact sur le personnel disponible avant validation | ⬜ Absente | — | Congés, validation, impact sur les effectifs |
| 86 | DRH | Recrutement simplifié avec fiche de poste type par rôle | ⬜ Absente | — | Fiches de poste par rôle, suivi des candidatures |
| 87 | DRH | Canal de médiation sociale pour les doléances des agents et syndicats | ⬜ Absente | — | Dépôt et suivi des doléances |
| 88 | Directeur financier | Consolidation automatique des recettes de toutes les gares en temps réel | ✅ Complète | `/api/synthese-financiere/` par gare, par mode de paiement, par jour, avec le fret | — |
| 89 | Directeur financier | Suivi du budget carburant avec alerte de dépassement par ligne | ⬜ Absente | — | Saisie des dépenses de carburant, budget par ligne, alerte |
| 90 | Directeur financier | Tableau de rentabilité par ligne/gare (recettes vs coûts) | ⬜ Absente | Les recettes existent ; aucun coût n'est enregistré | Coûts (carburant, maintenance, salaires) et marge par ligne |
| 91 | Directeur financier | Paiements fournisseurs et assurances avec échéancier et rappels | ⬜ Absente | Les échéances d'assurance existent côté juridique | Fournisseurs, factures, échéancier, rappels |
| 92 | Directeur financier | Trésorerie en temps réel visible du PDG | ⬜ Absente | — | Encaissements moins décaissements ; dépend des dépenses saisies |
| 93 | Directeur financier | Export de reporting financier prêt à partager (PDF/Excel) | ⬜ Absente | — | Export PDF / Excel de la synthèse |
| 94 | Responsable juridique | Registre des assurances flotte centralisé avec alerte de renouvellement | ✅ Complète | Registre + alertes à 30 j, 7 j et à l'expiration (`assurances_proches`) | — |
| 95 | Responsable juridique | Suivi des sinistres lié à l'incident déclaré, avec pièces jointes et statut | 🟡 Partielle | Sinistres avec véhicule, description, statut (existait) | Lien à l'incident déclaré, pièces jointes |
| 96 | Responsable juridique | Tableau de conformité réglementaire partagé avec le QHSE | ✅ Complète | Même tableau `/api/conformite/`, lu par le responsable juridique (page Juridique) et le QHSE | — |
| 97 | Responsable juridique | Alerte automatique de litige social issu du canal de médiation du DRH | ⬜ Absente | — | Dépend du canal de médiation (n° 87) |
| 98 | Responsable juridique | Bibliothèque de documents juridiques types accessible aux autres pôles | ⬜ Absente | — | Bibliothèque de modèles de documents |
| 99 | Responsable juridique | Reporting juridique synthétique remonté à la Direction Générale | ⬜ Absente | — | Synthèse assurances / sinistres / litiges pour la direction |

## 5. Exigences transverses du cahier

| Exigence | État | Détail |
|---|---|---|
| Une API centrale, un site web, une application mobile | 🟡 | API et site à jour ; l'application mobile a reçu la commande vocale (n° 34, 46) et sa signature release depuis, mais pas le reste du chantier (GPS, contrôle des billets, colis, alertes — voir §6) |
| Authentification par poste, droits limités au périmètre du rôle | ✅ | 19 rôles × chaque endpoint restreint testés contre `PERMISSIONS.md` ; isolation entre compagnies testée |
| Journal d'audit de toutes les actions | ✅ | Ajout seulement, connexions comprises ; étendu à tous les nouveaux objets (lignes fermées, comptes, investissements, plans d'entretien, demandes de pièces…) |
| Configuration par entreprise et par échelon ; niveau d'automatisation modulable | ✅ | Cadre → poste → agent, appliqué par le serveur (vente, colis, planification, clôture de caisse) |
| Gamification (missions, points, badges, classements) adaptée à chaque pôle, niveau réglable | ✅ | Calculée à partir des données réelles ; « sobre » par défaut pour direction, RH, finance, juridique |
| Mode hors ligne du mobile | 🟡 | Fait pour la vente du guichetier (avant ce chantier) ; le chauffeur n'a que la lecture ; le suivi GPS du web n'a pas de file d'attente hors ligne complète |
| Notifications client par SMS / WhatsApp | 🟡 | Tickets (avec code du billet) et colis ; **simulation par défaut, jamais essayé en réel** ; WhatsApp en texte libre |
| Mobile Money (Orange, MTN, Wave) | ⬜ | Le mode de paiement est enregistré ; **aucune intégration de paiement** |
| GPS des véhicules | 🟡 | Positions envoyées par le navigateur du chauffeur **et**, depuis, par l'application mobile en arrière-plan (`mobile/lib/gps/`) ; carte poussée en temps réel par WebSocket (`dashboard/consumers.py`) au lieu d'un simple rafraîchissement périodique ; carte schématique, pas de boîtier GPS dédié ; rien de tout cela jamais essayé sur un vrai véhicule en roulant |
| **Moteur vocal multilingue** | 🟡 | Une commande vocale **en français** existe depuis sur deux écrans du mobile (vente de ticket n° 34, checklist avant-départ n° 46) ; aucune langue locale prise en charge (limite des moteurs natifs des téléphones) ; c'est ce qui rend encore « partielles » les fonctionnalités 45, 47, 60, 72 et 78 et « absentes » les 29, 41 et 55 |
| Lien OSER / Ministère des Transports | 🟡 | L'app `tutelle`, ajoutée depuis, prépare les flux (sécurité, conformité) prêts à transmettre et à recevoir, avec un compte d'API séparé pour la tutelle ; rien ne parle encore à un vrai système du Ministère / OSER / AMUGA / OFT (accès externe requis, voir §6.2) |

## 6. Ce qui reste à faire

### 6.1 Développement (rien d'extérieur n'est nécessaire)

Par ordre de valeur décroissante pour un pilote :

1. **Finance** (n° 89–93) : dépenses (carburant, maintenance), budget par ligne avec alerte, rentabilité par ligne, fournisseurs et
   échéancier, trésorerie, export PDF / Excel. *Préalable : saisir les dépenses.*
2. **RH** (n° 83, 85–87) : congés avec impact sur les effectifs, formations obligatoires et échéances, fiches de poste par rôle, canal de
   médiation (puis n° 97 : alerte de litige au juridique).
3. **Juridique** (n° 95, 98, 99) : sinistre lié à l'incident avec pièces jointes, bibliothèque de modèles, reporting pour la direction.
4. **Rotation des quais** (n° 18), **carnet de route et documents du véhicule** (n° 49), **checklist de reprise** au relais (n° 55).
5. **Moteur vocal** : étendre au-delà des deux écrans déjà faits (vente de ticket, checklist avant-départ) — affecter un chauffeur
   (n° 29), colis (n° 41), incident (n° 47), rapport de contrôle (n° 60), demande/sortie de pièce (n° 72, 78), lecture à voix haute
   de la feuille de route (n° 45) et des alertes ; message vocal direct du chef de gare à son équipe (n° 22, aujourd'hui en texte
   seulement). Les langues locales (baoulé, dioula…) restent hors de portée des moteurs natifs des téléphones et navigateurs :
   elles demanderaient un service spécialisé.
6. **Compléments mineurs déjà repérés** : dossier de conducteur (permis, visite médicale) pour finir le tableau de conformité
   (n° 12, 96, déjà ✅ pour le reste) ; le registre d'archives ne contient pas le fichier lui-même (n° 9).
7. **Application mobile** : reprendre le tarif de la ligne (aujourd'hui elle envoie toujours un prix, que le serveur refuse si le tarif
   existe), le suivi GPS, le contrôle des billets, les colis, les alertes ; relancer `flutter analyze` et `flutter test`.
8. **Sécurité** : authentification à deux facteurs, jetons hors du `localStorage`, pagination des listes (tickets, départs…), cache
   partagé pour la limitation des connexions (réglable : `DEPLOIEMENT.md` §2) — détail app par app dans
   `AUDIT_SECURITE_FONCTIONNEL_2026-09-24.md`.
9. **Alertes poussées** (notification téléphone, SMS aux agents) : aujourd'hui les alertes ne se voient que dans la cloche, page ouverte.

### 6.2 Ce qui demande une action extérieure

| Action | Pourquoi |
|---|---|
| Comptes **Orange SMS API** et/ou **Twilio** (WhatsApp : modèle de message approuvé) | Envoyer réellement les SMS de billets, codes de colis, clôtures |
| Intégration **Orange Money / MTN MoMo / Wave** | Encaissement mobile réel (n° 32, 38) |
| **Téléphones** Android (et cars) pour les essais | L'APK signé n'a jamais été lancé (`mobile/TEST_TELEPHONES.md`) ; le GPS n'a jamais été essayé en roulant |
| Accès **OSER / Ministère des Transports** | Formations obligatoires et conformité réglementaire (n° 83) |
| Hébergement, nom de domaine, certificat, sauvegardes hors serveur | `DEPLOIEMENT.md` |
| Dépôt **GitHub** | Faire tourner l'intégration continue (`.github/workflows/ci.yml` écrite, jamais exécutée) |
| **Utilisateurs du pilote** | Calibrer seuils (renouvellement, fatigue, préavis d'entretien), niveaux d'automatisation et de gamification, vocabulaire |

## 7. Limites et ce qui n'a pas été vérifié

- **Aucun essai sur téléphone ni sur un vrai car.** Les essais de bout en bout tournent dans Chrome avec une position simulée.
- **Aucun envoi réel** de SMS ou de WhatsApp ; aucun paiement réel.
- **L'application mobile n'a pas été touchée** : `flutter analyze` et `flutter test` n'ont pas été relancés depuis ces changements.
- **L'intégration continue n'a jamais tourné sur GitHub** ; les commandes qu'elle enchaîne ont été lancées à la main avec succès.
- **Interface vérifiée dans Chrome seulement** (captures d'écran des essais) ; pas de vérification dans d'autres navigateurs ni sur petit écran.
- Les **tâches planifiées** (`generer_alertes`, `cloturer_caisses`, `evaluer_gamification`) sont à installer : sans elles, les alertes
  automatiques, le préventif et la clôture automatique ne se déclenchent pas (`DEPLOIEMENT.md` §10).
- **Simplifications connues** : la clôture d'un ordre de réparation remet le véhicule « disponible » même s'il est en ligne (comportement
  antérieur, non modifié) ; les listes de l'API ne sont pas paginées ; la carte du réseau est un schéma sans fond de carte ;
  la « tension » d'une gare est une heuristique.
- La **classification** des fonctionnalités reste un jugement : la règle est explicite (§2) et chaque ligne du §4 dit sur quoi elle repose.

## 8. Vérifications exécutées

| Vérification | Résultat | Comment la rejouer |
|---|---|---|
| Suite du serveur | **4 374 réussis**, 1 ignoré (15 min, relevé du 6 octobre 2026) — 1 206 au départ | `cd transpt1 && python -m pytest` |
| Matrice de conformité et contrat site ↔ API | Inclus ci-dessus (rôles × endpoints, chaque appel des pages) | `pytest role_coverage_tests` |
| Tests du site | 42 réussis | `cd frontend && npm test` |
| Analyse statique et compilation du site | 0 erreur ; 1 avertissement **antérieur** (`AuthContext`, rechargement à chaud en développement seulement) ; compilation réussie | `npm run lint && npm run build` |
| Essais de bout en bout (Chrome, base jetable) | **14 scénarios réussis** (relevé du 6 octobre 2026 : 12 au premier passage, « colis » au second après un délai dépassé sous charge, « caisse » après correction d'un sélecteur ambigu) | `npm run e2e` (≈ 8 min ; `npm run e2e -- atelier` pour un seul) |
| Dépendances | `pip-audit` : aucune vulnérabilité connue ; `npm audit` : 0 | `pip-audit -r requirements.txt` ; `npm audit` |

Fichiers à lire ensuite : `transpt1/PERMISSIONS.md` (qui peut quoi), `transpt1/DEPLOIEMENT.md` (tâches planifiées et limites),
`SCENARIO_PILOTE.md` (jouer les parcours à la main), `ANALYSE_PROJET.md` (l'analyse d'avant le chantier),
`AUDIT_SECURITE_FONCTIONNEL_2026-09-24.md` (audit sécurité app par app, le plus récent).
