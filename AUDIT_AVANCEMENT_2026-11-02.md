# Audit d'avancement — ce qui est fait, ce qui reste à construire (2 novembre 2026)

Demande : analyser le projet et faire le point sur l'avancement et sur le reste à construire.
Référence : `cahier.txt` (5 pôles, 18 postes, 99 fonctionnalités découpées comme dans `RAPPORT_CONFORMITE.md` §2).
Méthode : le code a été relu là où les rapports existants pouvaient être dépassés, et toutes les vérifications automatiques
ont été relancées aujourd'hui (§3). Aucun fichier du projet n'a été modifié ; ce rapport est le seul fichier ajouté.

## 1. En bref

- **Avancement fonctionnel : 77 fonctionnalités complètes, 19 partielles, 3 absentes sur 99 (≈ 87 %)**, une partielle
  comptant pour moitié. `RAPPORT_CONFORMITE.md` affiche encore 62 / 20 / 17 (≈ 73 %) : il n'a pas été mis à jour après les
  modules finance, RH et juridique, qui sont pourtant construits, testés et à l'écran (§4.2).
- **Le serveur et le site web sont solides** : 4 725 tests du serveur réussis sans échec, 42 tests du site, **14 parcours
  sur 14 réussis dans Chrome** contre une vraie API (§3). Les tests WebSocket de la carte passent seuls (14/14), mais se
  bloquent quand la machine est chargée.
- **Le mobile fonctionne pour ce qu'il sait faire** : 209 tests, analyse propre, et **12 essais sur 12 contre un vrai
  serveur** (connexion, vente en ligne et hors ligne, places garanties, idempotence, feuille de route hors ligne).
- **L'application mobile est le principal retard.** Le cahier la destine aux postes de terrain, mais elle ne couvre que le
  guichetier et le chauffeur, et le chauffeur ne peut ni démarrer son trajet, ni déclarer un incident depuis le téléphone.
  Elle ignore le tarif des lignes et n'a **jamais été lancée sur un vrai téléphone** (§4.4).
- **Rien n'a encore été essayé en conditions réelles** : ni SMS, ni paiement Mobile Money, ni GPS dans un car, ni hébergement.
- **Risque immédiat : cinq semaines de travail ne sont ni commitées ni sauvegardées sur GitHub.** Le dernier commit date du
  26 septembre. Depuis, 120 fichiers ont été touchés (≈ 4 900 lignes ajoutées), dont l'app `lien_billetterie` entière et le
  règlement intérieur. Par ailleurs, **le dépôt GitHub est public** (§6).
- **Le projet a pris de l'avance sur le calendrier du cahier pour les fonctions supports et du retard pour le terrain.**
  RH, finance et juridique (prévus au jalon « Déploiement ») sont faits. Le mobile de terrain, indispensable au jalon
  « Pilote », ne l'est pas. La suite proposée (§7) remet le pilote au premier plan.

| Pôle | Fonctionnalités | RAPPORT_CONFORMITE (F / P / A) | Aujourd'hui (F / P / A) |
|---|---:|---|---|
| Direction Générale | 13 | 11 / 2 / 0 | **12 / 1 / 0** |
| Exploitation & Réseau | 31 | 21 / 7 / 3 | **21 / 7 / 3** |
| Personnel roulant | 19 | 10 / 7 / 2 | **11 / 8 / 0** |
| Technique & Maintenance | 18 | 16 / 2 / 0 | **16 / 2 / 0** |
| Fonctions supports | 18 | 4 / 2 / 12 | **17 / 1 / 0** |
| **Total** | **99** | 62 / 20 / 17 (≈ 73 %) | **77 / 19 / 3 (≈ 87 %)** |

F = complète (utilisable à l'écran, règles appliquées par le serveur) · P = partielle · A = absente — même règle que
`RAPPORT_CONFORMITE.md` §2, la classe la plus basse en cas de doute.

## 2. Le projet en chiffres

| Partie | Contenu | Taille |
|---|---|---|
| Serveur Django (`transpt1/`) | 20 apps, près de 200 routes d'API, 18 postes + super-administrateur, WebSocket pour la carte | ≈ 18 900 lignes de code, ≈ 21 100 lignes de tests |
| Site web React (`frontend/`) | 31 pages, 58 composants, un tableau de bord par poste + 12 pages transverses | ≈ 13 400 lignes ; 5 fichiers de tests unitaires ; 14 scénarios de bout en bout + 4 essais Playwright |
| Application mobile Flutter (`mobile/`) | Guichetier (vente hors ligne, dictée), chauffeur (feuille de route, checklist, GPS en arrière-plan) | ≈ 4 200 lignes ; 17 fichiers de tests |
| Documentation | Cahier, rapports de conformité, de sécurité et d'anomalies, permissions, déploiement, scénario pilote, carte du code, guides | Une quinzaine de documents |

Répartition du serveur par app (lignes de code hors tests et migrations) : `personnel_roulant` 2 141, `rh` 1 776,
`billetterie` 1 618, `maintenance` 1 471, `dashboard` 1 259, `core` 1 158, `supports` 1 093, `gamification` 949,
`lien_billetterie` 895, `reseau` 875, `finance` 858, `configuration` 742, `colis` 712, `formation` 662, `communication` 627,
`alertes` 532, `audit` 488, `tutelle` 486, `notifications` 337, `investissements` 249.

## 3. État de santé technique (relevé le 2 novembre 2026)

| Vérification | Résultat | Commentaire |
|---|---|---|
| Suite du serveur (sans `zz_probe/` ni les tests WebSocket) | **4 725 réussis, 1 ignoré, 0 échec** (41 min, machine chargée par les autres vérifications) | `DB_NAME=… python -m pytest --ignore=zz_probe --ignore=dashboard/tests/test_carte_consumer.py` ; 4 658 au 1er novembre |
| Tests WebSocket de la carte (`test_carte_consumer.py`) | **14 réussis en 46 s, lancés seuls** ; lancés en même temps que la suite complète : **bloqués** (aucune activité ni connexion à la base après 26 min, arrêtés) | Sensibles à la charge (A-04, non corrigé) : c'est ce qui rend la CI peu fiable |
| Site : tests unitaires (`vitest`) | **42 réussis** | |
| Site : analyse (`oxlint`) | 0 erreur, 1 avertissement (`AuthContext.jsx:52`, connu) | |
| Site : compilation | Réussie ; un seul fichier JS de 567 ko (146 ko compressé) | Pas de découpage par page (F-09) |
| Mobile : `flutter analyze` | **0 problème** | |
| Mobile : `flutter test` | **209 réussis** | 196 dans la suite complète + 13 relancés à part : `api_client_test.dart` n'avait pas chargé, machine chargée par la suite du serveur |
| Intégration continue GitHub | **Une seule exécution, le 27 septembre : en échec** (tests du serveur) | Site, mobile et audit des dépendances réussis, e2e non lancé. Les rapports disent à tort qu'elle n'a « jamais tourné ». La cause exacte n'est lisible qu'avec un compte GitHub ; les tests WebSocket instables sont le suspect le plus probable |
| Dépendances du serveur | `djangorestframework` 3.18.1 (**2 failles exploitables sans connexion**, corrigées en 3.18.2) | Relevé du 31 octobre (A-10), version inchangée ; `pip-audit` n'est installé dans aucun environnement local, pas relancé |
| Dépendances du site (`npm audit`) | 3 failles (1 haute, 2 moyennes), toutes dans `vite` 8.3.0 et `vitest` 5.0.1 | Outils de développement seulement, le site compilé n'est pas touché (A-05) ; `npm audit fix` les corrige |
| Site : 14 parcours de bout en bout dans Chrome (`npm run e2e`) | **14 réussis sur 14** | Base jetable, vraie API, site compilé : chaque poste se connecte, coordination QHSE, colis, jeu, configuration, caisse, GPS et relais, contrôle à bord, pouvoirs, atelier, secrétariat, comptabilité, RH, juridique. Base supprimée ensuite |
| Mobile contre un vrai serveur (`tool/e2e_smoke_test.dart`) | **12 réussis sur 12** | Serveur et base jetables (supprimés ensuite) ; voir §3.1 |

### 3.1 Le site web et le mobile en détail

**Site web : fonctionne de bout en bout, les défauts connus sont toujours là.**

- Vérifié aujourd'hui : les 14 parcours, les 42 tests unitaires, l'analyse, la compilation. Le contrat pages ↔ API (chaque appel
  de chaque page vise une route permise à son rôle) fait partie de la suite du serveur et passe.
- Le lot 5 de la revue du 31 octobre n'a pas commencé. Défauts relus aujourd'hui dans le code :
  - aucun filet d'erreur de rendu (F-15) : une valeur inattendue venue de l'API donne une page blanche ;
  - date mal tapée (F-16) : `PlanificationDepart.jsx:19` (pendant le rendu, page blanche), `SecretariatPage.jsx:148`,
    `ChefLigneDashboard.jsx:81` ;
  - vente et colis envoyés sans `Idempotency-Key` (F-02) : un nouvel essai après coupure double la vente et le SMS ;
  - message d'erreur tronqué au premier « : » (F-04, `ChauffeurDashboard.jsx:136`) ;
  - tampon GPS renvoyé en bloc (F-05, `SuiviTrajet.jsx:31-37`) : après ≈ 8 min sans réseau, plus aucune position ne part ;
  - une seule suppression sur douze demande confirmation (F-06, seule `ChefLigneDashboard.jsx:95` le fait) ;
  - aucun écran pour le règlement intérieur ni pour le lien billetterie ; un seul fichier JS de 567 ko.

**Mobile : ce qu'il fait marche contre le vrai serveur ; ce qui manque est fonctionnel, pas technique.**

- Essai de bout en bout contre un serveur et une base jetables (supprimés ensuite) : **12/12** — connexion, mauvais mot de
  passe, jeton renouvelé, départs à vendre, vente en ligne, vente hors ligne envoyée une seule fois au retour du réseau, refus
  du serveur restitué, feuille de route du chauffeur en ligne puis hors ligne, session reprise hors ligne, idempotence, places
  garanties hors ligne entre deux guichetiers sur un car de 3 places.
- Appels du chauffeur que cet essai ne couvre pas, rejoués avec les envois exacts du téléphone : les 6 items de checklist sont
  acceptés ; `/suivi/moi/` passe à « en cours » au départ et revient à « non » à l'arrivée ; un lot de 3 positions GPS au
  format du téléphone est accepté (201). Le départ et l'arrivée ont dû passer par les routes du site : le mobile ne sait pas
  les faire.
- **G-02 reproduit en réel** : tarif de 6 000 FCFA posé sur la ligne, vente envoyée comme le fait le mobile à 5 000 → refus 400
  « Le tarif de cette ligne est de 6000 FCFA : seul un chef peut vendre à un autre prix » ; à 6 000 → acceptée. Les lignes de
  démonstration n'ont pas de tarif : c'est pourquoi les essais passent sans montrer le défaut.
- Défauts du lot 6 relus aujourd'hui, toujours présents : **G-01** (`api_client.dart:130` : toute réponse en erreur au
  renouvellement du jeton, erreur serveur comprise, efface la session), **G-03** (aucun traitement de la négation dans
  `voice_text.dart`), **G-06** (`allowBackup` absent du manifeste Android).
- Non vérifié aujourd'hui : l'APK n'a pas été recompilé ; il n'a jamais tourné sur un téléphone ; le GPS n'a jamais roulé.

**Constat nouveau (N-01, non corrigé)** : le serveur compte l'**extincteur** parmi les 6 items de sécurité
(`personnel_roulant/models.py:11`), et le parcours de formation du chauffeur apprend à le vérifier. Pourtant, la checklist
avant-départ du site (`ChauffeurDashboard.jsx:10`) et celle du mobile (`checklist_depart_screen.dart:16`) proposent pneus,
freins, carburant, éclairage, direction, ceintures, **sans l'extincteur**. Il n'est donc jamais contrôlé avant un départ, et
un extincteur absent ne bloque jamais le car. À trancher : l'ajouter aux deux checklists, ou en faire un item réglable par
compagnie.

## 4. Avancement par rapport au cahier des charges

### 4.1 Ce qui est en place (vue d'ensemble)

- **Tous les postes** du cahier ont leur compte, leurs droits et leur tableau de bord web. Les droits sont vérifiés
  rôle par rôle et route par route par des tests. Le cloisonnement entre compagnies a été vérifié le 1er novembre
  (lectures, requêtes, écritures, temps réel).
- **Coordination entre pôles** : 35 types d'alertes (cloche sur toutes les pages), génération automatique (seuils critiques,
  retards prévisibles, fatigue, entretiens, assurances, budgets, factures, formations, contrats, litiges), blocage QHSE
  avec notification.
- **Exploitation** : vente au tarif imposé et idempotente, places garanties pour la vente hors ligne du mobile ; clôture de caisse manuelle, assistée ou
  automatique ; colis de bout en bout ; planification et réaffectation ; fermeture et gel de lignes ; gares en tension.
  Nouveau : lien avec un logiciel de billetterie existant, par API et par import CSV/Excel (API seulement, pas d'écran).
- **Personnel roulant** : feuille de route, checklist liée au blocage, incidents géolocalisés, suivi GPS par lots, alerte
  fatigue, relais avec checklist de reprise, mode convoyeur, carnet de route, contrôle des billets à bord avec rapport.
- **Technique** : file des réparations par urgence, préventif automatique, demandes de pièces, suggestions de commande,
  fiche véhicule, charge des mécaniciens, besoin de renouvellement.
- **Supports** : dossiers agents (contrats, évaluations, discipline), formations obligatoires, congés avec impact, fiches de
  poste et recrutement, médiation sociale, dépenses, budget carburant, fournisseurs et factures, rentabilité, trésorerie,
  export, assurances, sinistres avec pièces jointes, bibliothèque de modèles, reporting juridique et RH pour la direction.
- **Gamification** : missions, points, niveaux, badges, classements calculés sur les données réelles, niveau réglable par poste.
- **Configuration** : cadre de la compagnie → poste → agent (automatisation, gamification, fonctions, préférence vocale),
  et règlement intérieur par compagnie (5 règles, API seulement).
- **Transverse** : journal d'audit, sauvegardes avec test de restauration, HTTPS, échanges préparés avec la tutelle.

### 4.2 Ce qui a changé depuis `RAPPORT_CONFORMITE.md`

Fonctionnalités reclassées après vérification dans le code (le reste du §4 de ce rapport reste exact) :

| # | Fonctionnalité | Avant | Aujourd'hui | Preuve dans le code |
|---|---|---|---|---|
| 1 | Tableau de bord « santé de l'entreprise » (dont dépenses, marge, RH) | 🟡 | ✅ | Dépenses, marge et trésorerie : page Finances (`/finances`, PDG et secrétaire général) ; RH : page Synthèse (`/rh/synthese/`) — réparti sur trois pages, pas de vue unique |
| 49 | Carnet de route et documents du véhicule | ⬜ | ✅ | `personnel_roulant/carnet.py`, `CarnetDeRoute.jsx` sur la page Chauffeur |
| 55 | Checklist de reprise (vocale) | ⬜ | 🟡 | `ChecklistReprise` (modèle et écran) ; pas de version vocale |
| 82 | Dossier agent centralisé (contrat, formation, évaluations, discipline) | 🟡 | ✅ | `rh/models.py` (`ContratAgent`, `EvaluationAgent`, `MesureDisciplinaire`, `FormationSuivie`), `FicheAgent.jsx` |
| 83 | Formations obligatoires avec alerte de renouvellement | ⬜ | ✅ | `ObligationFormation`, `FormationSuivie`, alerte `formations_a_renouveler` ; aucun lien avec un système OSER (externe) |
| 85 | Plannings et congés avec impact avant validation | ⬜ | 🟡 | `DemandeConge` + `GET /conges/{id}/impact/` ; ni solde de congés ni planning de service du personnel |
| 86 | Recrutement avec fiche de poste type | ⬜ | ✅ | `FicheDePoste`, `OffreRecrutement`, `Candidature` |
| 87 | Canal de médiation sociale | ⬜ | ✅ | `Doleance`, `SuiviDoleance`, pages Médiation et Mon espace |
| 89 | Budget carburant avec alerte de dépassement par ligne | ⬜ | ✅ | `BudgetCarburant`, alerte `budgets_carburant` |
| 90 | Rentabilité par ligne / gare | ⬜ | ✅ | `/finance/rentabilite/`, `Rentabilite.jsx` |
| 91 | Fournisseurs et assurances : échéancier et rappels | ⬜ | ✅ | `Fournisseur`, `Facture`, alerte `factures_a_echeance`, `EcheancierFactures.jsx` |
| 92 | Trésorerie en temps réel visible du PDG | ⬜ | ✅ | `/finance/tresorerie/`, page Finances du PDG |
| 93 | Export financier PDF / Excel | ⬜ | ✅ | `/finance/export/` en CSV (s'ouvre dans Excel, protégé contre l'injection de formule) ; PDF par l'impression du navigateur |
| 95 | Sinistre lié à l'incident, pièces jointes, statut | 🟡 | ✅ | `Sinistre.incident`, ouverture automatique sur incident grave (`supports/services.py`), `PieceSinistre` |
| 97 | Alerte de litige social au juridique | ⬜ | ✅ | Alerte `litiges_a_signaler` (`rh/alertes.py`), `LitigesSociaux.jsx` |
| 98 | Bibliothèque de documents juridiques types | ⬜ | ✅ | `ModeleJuridique`, page Modèles ouverte à tous les postes |
| 99 | Reporting juridique pour la direction | ⬜ | ✅ | `/juridique/reporting/`, page Synthèse |

### 4.3 Les 22 fonctionnalités encore incomplètes, par cause

| Cause | Fonctionnalités | Ce qui manque |
|---|---|---|
| **Voix** (11) | 22 appel vocal du chef de gare · 29 affecter un chauffeur à la voix · 34 vendre à la voix · 41 colis à la voix · 45 feuille de route écoutable · 46 checklist vocale ou par icônes · 47 incident à la voix · 55 checklist de reprise vocale · 60 rapport de contrôle à la voix · 72 sortie de pièce à la voix · 78 demande de pièce à la voix | La dictée existe en français sur deux écrans du mobile (34, 46) : moteur générique réutilisable (`voice_form_session.dart`). Rien côté web ; aucune lecture à voix haute ; aucune langue locale |
| **Fonction à construire** (6) | 18 rotation des quais (**absente**) · 25 proposition d'un couple chauffeur + véhicule · 40 suivi du colis à la demande du client · 50 formation pour tous les postes et quiz vocaux · 58 lecture du QR code par la caméra · 85 solde de congés et planning de service | Développement interne seulement |
| **Paiement** (2) | 32 encaissement Mobile Money au guichet · 38 idem pour le fret | Contrat et intégration Orange Money / MTN MoMo / Wave ; le mode de paiement est aujourd'hui déclaratif |
| **Essai réel** (2) | 5 carte temps réel · 48 suivi GPS et fatigue | Chaîne complète en place, jamais essayée dans un car ; carte schématique sans fond de carte |
| **Choix d'organisation** (1) | 30 score de ligne réglé par le chef de gare | Réglé par le directeur des opérations (le chef de ligne dépend de lui) : à confirmer avec la compagnie pilote |

**Le levier principal est la voix** : la moitié des fonctionnalités incomplètes n'attendent qu'elle. En français, une grande
partie se fait avec les moteurs des téléphones et du navigateur. Les langues locales (dioula, baoulé…) demandent un
service spécialisé.

### 4.4 L'application mobile face au cahier

Le cahier réserve le mobile aux postes de terrain : chauffeurs, contrôleurs, mécaniciens, bagagistes.

| Poste | Sur le web | Sur le mobile |
|---|---|---|
| Guichetier | Complet | Vente hors ligne garantie et dictée vocale. **Ignore le tarif de la ligne** (G-02) : une vente hors ligne au mauvais prix est refusée à la synchronisation, voyageur déjà payé |
| Chauffeur principal / relais | Complet | Feuille de route (lecture), checklist avec dictée, GPS en arrière-plan. **Ni démarrer ni terminer le trajet, ni incident, ni relais, ni reprise, ni alertes** |
| Contrôleur de ligne | Complet | Rien (écran générique) |
| Bagagiste | Complet | Rien (écran générique) |
| Mécanicien | Complet | Rien (écran générique) |

Anomalies mobiles du 31 octobre toutes ouvertes (lot 6 non commencé), dont deux qui touchent directement le terrain :
**G-01** (une erreur serveur pendant le renouvellement du jeton déconnecte le chauffeur) et **G-03** (la dictée ne comprend
pas la négation : « freins pas bons » est enregistré **OK** sur un item de sécurité).

### 4.5 Exigences transverses

| Exigence du cahier | État | Détail |
|---|---|---|
| API centrale, web et mobile | 🟡 | API et web complets ; mobile limité au guichetier et aux chauffeurs, rien pour le contrôleur, le bagagiste et le mécanicien (§4.4) |
| Droits limités au périmètre du rôle, journal d'audit | ✅ | Matrice rôle × route testée ; cloisonnement vérifié le 1er novembre |
| Configuration par compagnie et par échelon, automatisation modulable | ✅ | Écrans Cadre et Configuration ; règlement intérieur sans écran (§5) |
| Gamification adaptée à chaque pôle | ✅ | |
| Mode hors ligne du mobile | 🟡 | Vente et checklist ; lecture de la feuille de route ; positions GPS en file. Rien pour les autres postes |
| Notifications client SMS / WhatsApp | 🟡 | Branchées (Orange SMS, Twilio), **en simulation**, jamais envoyées en réel ; WhatsApp sans modèle approuvé |
| Mobile Money | ⬜ | Aucune intégration |
| GPS des véhicules | 🟡 | Navigateur et mobile en arrière-plan, carte poussée en temps réel ; jamais essayé en roulant |
| Moteur vocal multilingue | 🟡 | Français, 2 écrans du mobile |
| Lien avec la tutelle (OSER, Ministère) | 🟡 | Flux préparés et compte d'API séparé ; aucun système réel en face |
| Interopérabilité avec la billetterie et la comptabilité existantes | 🟡 | Billetterie : lien générique par API et import (sans écran) ; comptabilité : export CSV seulement |

### 4.6 Ce que le cahier demande hors des 99 fonctionnalités

Ces points ne figurent pas dans le découpage des rapports précédents, mais le cahier les écrit :

| Demande du cahier | État | Remarque |
|---|---|---|
| « Chaque compagnie pourra configurer […] **nouveaux postes**, règles de coordination spécifiques, **KPI propres** » | ⬜ postes et KPI · 🟡 règles | Les 18 postes sont fixés dans le code (`core.Role`) : en ajouter par compagnie touche toutes les permissions. Le règlement intérieur compte 5 règles |
| Module « **RH et paie** » (exigences techniques) | ⬜ paie | Les salaires ne sont qu'une catégorie de dépense |
| Tableau de bord immersif : **animations** au départ, à l'arrivée, sur incident ; icônes de véhicules en mouvement | 🟡 | Couleurs des gares et cars en route sur une carte schématique ; pas d'animation ni de fond de carte |
| Ticket **physique** | 🟡 | Aucune impression de ticket papier (le code du billet part par SMS) |

## 5. Où en sont les corrections de la revue du 31 octobre

| Lot | Contenu | État |
|---|---|---|
| 1. Hygiène | Git, CI, Playwright | **Fait et vérifié** (1er novembre) |
| 2. Robustesse | Plus aucune erreur 500 sur entrée invalide (105 cas avant, 0 après) | **Fait et vérifié** |
| 3. Intégrité métier | Règlement intérieur réglable par compagnie (défaut = comportement actuel) | **Fait** ; corrections du socle refusées par le propriétaire |
| 4. Confidentialité | D-03 (caisse du chef de gare), D-05 (injection de formule à l'export) | **Fait** ; D-01, D-02 laissés tels quels par décision ; D-04 sans consigne |
| Demande du 1er novembre | Lien avec le logiciel de billetterie de la compagnie | **Serveur fait** (72 tests) ; écrans à faire |
| 5. Site web | F-01 à F-16 : filet d'erreur de rendu, double vente après coupure, dates invalides qui font une page blanche, tampon GPS bloqué, confirmations de suppression… | **Pas commencé** |
| 6. Mobile | G-01 à G-06 | **Pas commencé** |
| 7. Tests, dépendances, documentation | Tests WebSocket instables, `djangorestframework` 3.18.2, `vite`/`vitest`, documentation | **Pas commencé** |
| 8. À arbitrer | D-06 (configuration non bornée à la gare), D-07 (jeton non révocable), pagination des écrans, C-07 (fausses alertes d'assurance expirée), C-08 | **En attente de décision** |

Écrans annoncés « avec le lot 5 » et pas encore faits : réglage du règlement intérieur, mode de billetterie, clés du
logiciel, dépôt de fichier et compte rendu d'import. En billetterie externe, le formulaire de vente reste affiché (le serveur
refuse avec un message clair).

## 6. Risques, du plus urgent au moins urgent

| # | Risque | Conséquence | Ce qu'il faut faire |
|---|---|---|---|
| R1 | **Cinq semaines de travail non commitées** (84 fichiers suivis modifiés ou indexés, 36 nouveaux non suivis, ≈ 4 900 lignes ajoutées) ; seule copie sur ce poste | Une panne de disque ou une fausse manipulation efface les lots 1 à 4, le règlement intérieur et le lien billetterie | Commiter par lot et pousser (sur votre accord) |
| R2 | **Dépôt GitHub public** (`sallabou5832-commits/transport`) | Le code, le cahier des charges et l'audit de sécurité du 24 septembre (failles ouvertes comprises) sont lisibles par tous. Aucun secret n'est versionné (vérifié) | Le passer en privé, sauf choix délibéré |
| R3 | **Mobile de terrain incomplet et jamais essayé sur téléphone** | Le jalon « Pilote » du cahier repose sur lui ; G-03 peut enregistrer « OK » sur des freins signalés défectueux | Phase 1 du §7 |
| R4 | **Aucun essai réel** (SMS, paiement, GPS en roulant, hébergement, tâches planifiées) | Les problèmes de terrain (réseau, fabricants de téléphones, fournisseurs) restent inconnus | Comptes fournisseurs, téléphones, serveur |
| R5 | **CI non fiable** : une seule exécution, en échec ; tests WebSocket instables | Un vrai échec passe inaperçu au milieu des faux | Lot 7 (A-04), puis relancer la CI |
| R6 | **`djangorestframework` 3.18.1** : deux failles sans connexion (≈ 19 s de calcul ou ≈ 97 Mio de mémoire par requête) | Un serveur exposé peut être saturé par quelques requêtes | Passer en 3.18.2 avant toute mise en ligne |
| R7 | **Documentation en retard sur le code** | `RAPPORT_CONFORMITE.md` sous-estime l'avancement (73 % au lieu de 87 %) ; `DEPLOIEMENT.md` dit « pas de moteur vocal » et « mobile sans GPS » ; `CARTE_DU_CODE.md` marque 🔴 des fichiers suivis depuis et ne cite pas `mobile/lib/gps/` | Mise à jour (lot 7) |
| R8 | **Montée en charge** : les écrans téléchargent toutes les listes (tickets, départs, colis) chaque minute ; la gamification recalcule les classements à chaque consultation | Lenteur dès quelques milliers de tickets par mois | Pagination côté écrans (F-03, E-05) avant d'étendre au réseau entier |

Décisions déjà prises par le propriétaire (rappel, sans les rouvrir) : le journal d'audit reste lisible tel quel par la
direction et le QHSE (D-01), le code de retrait reste dans le journal des SMS (D-02), la clôture d'un ordre de réparation
libère le véhicule même sous blocage QHSE (C-02), la porte de sécurité reste sensible à la casse (C-03).

## 7. Reste à construire — ordre proposé

Taille indicative : **S** = moins d'une journée · **M** = quelques jours · **L** = une à trois semaines · **Ext.** = dépend
d'un tiers (compte, contrat, matériel). Chaque élément reste soumis à votre accord, lot par lot.

### Phase 0 — Mettre l'acquis à l'abri (immédiat)

| Élément | Taille |
|---|---|
| Commiter les lots 1 à 4, le règlement intérieur et le lien billetterie, puis pousser | S |
| Décider de la visibilité du dépôt GitHub | S (décision) |
| `djangorestframework` 3.18.2, `vite` et `vitest` corrigés (A-05, A-10) | S |
| Stabiliser les tests WebSocket (A-04), relancer la CI jusqu'au vert | S–M |
| Mettre à jour `RAPPORT_CONFORMITE.md`, `DEPLOIEMENT.md`, `CARTE_DU_CODE.md` (H-01 à H-04 et §4.2 ci-dessus) ; supprimer la sonde `zz_probe/` en fin de revue | S |

### Phase 1 — Ce qui bloque le pilote

| Élément | Taille |
|---|---|
| Mobile, corrections : tarif de la ligne (G-02), session gardée sur erreur serveur (G-01), négations dans la dictée (G-03), double abonnement GPS (G-04), `allowBackup` (G-06) | M |
| Extincteur dans la checklist avant-départ, site et mobile (N-01, §3.1) | S (décision) |
| Mobile chauffeur : démarrer / terminer le trajet, incident géolocalisé, relais et checklist de reprise, alertes | M–L |
| Site, lot 5 : filet d'erreur de rendu (F-15), dates invalides (F-16), anti-double vente et colis (F-02), tampon GPS (F-05), confirmations (F-06), messages tronqués (F-04) | M |
| Écrans du règlement intérieur et du lien billetterie ; formulaire de vente masqué en billetterie externe | M |
| Essai sur de vrais téléphones (`mobile/TEST_TELEPHONES.md`), GPS dans un car | Ext. |
| Comptes SMS réels (Orange SMS API ou Twilio), modèle WhatsApp approuvé | Ext. |
| Serveur, domaine, certificat, tâches planifiées (`generer_alertes`, `cloturer_caisses`, `evaluer_gamification`…), sauvegardes hors serveur (`DEPLOIEMENT.md`) | M + Ext. |
| Choix de la gare / ligne pilote et des utilisateurs (jalon « Cadrage » du cahier) | Ext. |

### Phase 2 — Pendant le pilote : le terrain sur mobile

| Élément | Taille |
|---|---|
| Mobile bagagiste (enregistrement, chargement, retrait de colis), contrôleur (contrôle à bord), mécanicien (ordres, pièces) | L |
| QR code sur le billet et lecture par la caméra (n° 58) | M |
| Notifications poussées sur téléphone (alertes visibles application fermée) | M + Ext. |
| Pagination des écrans et du mobile (F-03, G-05), coût de la gamification (E-05) | M |
| Sécurité : révocation des jetons (D-07), politique CSP, cache partagé pour la limitation des connexions, double authentification pour la direction et la finance | M |

### Phase 3 — Compléter le cahier

| Élément | N° | Taille |
|---|---|---|
| Voix en français étendue : lecture à voix haute (feuille de route, alertes), affecter un chauffeur, colis, incident, reprise, rapport de contrôle, pièces ; message vocal du chef de gare | 22, 29, 41, 45, 46, 47, 55, 60, 72, 78 | L |
| Rotation des quais : quais par gare, ordre d'embarquement proposé, validé ou ajusté | 18 | M |
| Planning : proposer le meilleur couple chauffeur + véhicule au lieu de lister les libres | 25 | S–M |
| Formation pour tous les postes, quiz vocaux | 50 | M |
| Solde de congés, planning de service du personnel | 85 | M |
| Suivi du colis à la demande du client (le client n'ayant pas accès au logiciel : par SMS) | 40 | M |
| Conducteurs dans le tableau de conformité : permis et visite médicale se suivent déjà comme obligations RH (échéances, alertes), mais n'entrent pas dans le tableau de conformité du QHSE et du juridique | 12, 96 | S |
| Fichier joint aux archives du secrétariat ; impression du ticket papier ; fond de carte et animations | 9, 31, 5 | S–M chacun |

### Phase 4 — Intégrations et extensions

| Élément | Taille |
|---|---|
| Mobile Money (Orange Money, MTN MoMo, Wave) pour billets et fret (n° 32, 38) | L + Ext. |
| Langues locales (dioula, baoulé…) pour la voix | Ext. (service spécialisé) |
| Échange réel avec la tutelle (Ministère, OSER) | Ext. |
| Adaptateur vers le logiciel de billetterie de la compagnie pilote, quand il sera connu | M |
| Postes et KPI propres à une compagnie ; paie (§4.6) | L chacun, à cadrer |

## 8. Limites de cet audit

- Le classement des fonctionnalités reste un jugement : il s'appuie sur le code (modèles, routes, écrans, alertes) et sur les
  rapports existants, pas sur une relecture ligne à ligne de tout le dépôt (faite le 31 octobre, `RAPPORT_ANOMALIES_2026-10-31.md`).
- `pip-audit` n'a pas pu être relancé (installé dans aucun environnement local) : l'état des dépendances du serveur vient du
  31 octobre, versions vérifiées inchangées. Les 4 essais Playwright (`npm run e2e:pw`) n'ont pas été relancés, les 14 parcours
  couvrant déjà la connexion de chaque poste.
- Toutes les vérifications ont tourné sur ce poste de développement Windows, dans Chrome seulement ; aucune sur téléphone.
- La cause de l'échec de la CI du 27 septembre n'a pas pu être lue (journal réservé aux comptes GitHub autorisés).
- Les tailles du §7 sont indicatives, pour ordonner le travail, pas des engagements de délai.
