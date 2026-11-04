# Plan du lot 1 « Fondations » (4 novembre 2026)

Ce plan répond au cahier du lot 1 (télématique, conduite, carburant, documents, permis à points, FNE, gamification
acceptable). **Aucun code n'est écrit.** Ce plan attend votre validation, puis chaque fonctionnalité attendra la sienne.
Les postes du cahier se lisent ainsi dans le code ([cahier.txt](cahier.txt), lignes 20 et 22) : « chef de parc » =
directeur technique, « régulateur » = chef de ligne, « directeur des opérations » = directeur d'exploitation.

## 1. Ce qui existe déjà (lu dans le code)

| Fonction | Ce qui existe | Ce qui manque |
|---|---|---|
| 1.1 Télématique | Le GPS ne vient que du téléphone du chauffeur. `PositionVehicule` garde la latitude, la longitude et la vitesse, et n'accepte une position que pendant un trajet en cours ([views.py:466-480](transpt1/personnel_roulant/views.py#L466-L480)). La carte est en temps réel ; une position de plus de 15 min s'affiche datée ; la purge se fait à 30 jours | Cap, accélérations, carburant, kilométrage ; la source de chaque car ; le boîtier ; le simulateur ; l'alerte de perte de signal |
| 1.2 Alertes de conduite | Des alertes par poste et par gravité, avec une clé anti-doublon (`alertes.services.alerter`). Une génération périodique (`generer_alertes`) ; le PDG reçoit déjà les seuils critiques | Vitesse, géofences, itinéraires, arrêts non prévus |
| 1.3 Score de conduite | Une gamification à points par poste, avec missions, badges et classements. Les scores de gare et de ligne sont pondérés en dur (`gamification/scores.py`). Au relais, le nouveau chauffeur est **choisi dans une liste** (`suivi.effectuer_relais`) | Aucun score de conduite, aucun score chauffeur composé ; aucune identification au relais par code, QR ou badge |
| 1.4 Carburant | Le carburant n'est qu'une **dépense en francs** (`Depense`, catégorie carburant). Le budget par ligne et par mois alerte la finance à 80 % puis au dépassement | Pleins en litres, capacité du réservoir, consommation, anomalies |
| 1.5 Échéances | **Trois mécanismes séparés** : permis, visite médicale et OSER sont des « obligations » RH par agent (`ObligationFormation`, `FormationSuivie`, préavis réglable) ; l'assurance a son registre (`supports.Assurance`, alertes à J-30 et J-7) ; la carte de transport est sur la fiche du véhicule (échéance montrée, jamais imposée). Rien ne bloque une affectation | Un registre commun ; les alertes à J0 ; le blocage réglable ; les types supplémentaires |
| 1.6 Permis à points | L'infraction grave du contrôleur (`ControleLigne`) et les mesures disciplinaires RH | Capital de points, retraits, amendes ; qui conduisait à telle heure |
| 1.7 FNE | Le ticket (prix, mode de paiement, clé anti-doublon) et les frais de colis ; le compte contribuable et le RCCM sur la fiche compagnie | Aucune facture |
| 1.8 Gamification | Niveau aucun / sobre / complet par compagnie, poste et agent. Le classement est **nominatif** ([moteur.py:249-251](transpt1/gamification/moteur.py#L249-L251)). Hors trajet, la position du téléphone est déjà refusée. Aucune sanction ne découle des points (les mesures disciplinaires se saisissent à la main) | Anonymat, numéro « Chauffeur #12 », règle écrite et testée « jamais de sanction automatique » |

**Mécanismes réutilisés, sans en créer de nouveaux** :

- les alertes (`alerter`) ;
- le règlement intérieur (une règle oui ou non par compagnie, défaut = comportement actuel) ;
- les fonctions retirées à un poste ou à un agent par l'échelon supérieur (`fonctions_desactivees`) ;
- le journal d'audit (chaque nouveau modèle ajouté au `REGISTRE`) ;
- les pièces jointes contrôlées ;
- les clés d'accès du lien billetterie (modèle pour la clé du boîtier) ;
- la file hors ligne du mobile, la dictée et la synthèse vocale (`flutter_tts`).

## 2. Articulation avec le plan en cours et les bugs

- **Recouvrements avec le plan §6** de l'analyse métier :
  - 1.4 couvre R-04 (carnet de bord, P6) et T-03 (consommation, P8) ;
  - 1.5 couvre J-02 (registre des documents, P9) et R-06/OR-06 (permis à la planification, chef de ligne prévenu, P6) ;
  - au lot 2, 2.1 = F-04, 2.2 = H-03, 2.4 = T-02 et F-06, et 2.8 existe en partie (clés du lien billetterie).

  Je propose que votre lot 1 **absorbe** ces points ; le §6 sera mis à jour une fois ce plan validé.
- **Préalable 1.0, les paramètres de la compagnie** : tous les seuils du lot 1 doivent être réglables par compagnie. Ce
  mécanisme est prévu en P2a (P-07) mais n'existe pas encore. Sans lui, il faudrait écrire les seuils en dur.
- **Bugs à corriger d'abord** ([ANALYSE_TOTALE_2026-11-04.md](ANALYSE_TOTALE_2026-11-04.md)) :
  - **T-01** : la file hors ligne jette une saisie refusée en 403 ;
  - **G-03** : la dictée ne comprend pas la négation.

  Les nouvelles saisies de terrain (pleins, relais) passeront par cette file et par cette dictée. Je recommande de corriger
  le lot A du mobile, ou au moins T-01 et G-03, avant 1.4.

## 3. Plan par fonctionnalité

Chaque fonctionnalité porte sur les mêmes points :

- **défaut** : une compagnie qui ne règle rien garde le comportement actuel ;
- **réglages** : par compagnie, puis par poste ;
- **mode manuel** : un mode manuel existe à côté de tout automatisme ;
- **audit** : chaque action est inscrite au journal d'audit ;
- **cloisonnement** : il est testé ;
- **tests** : unitaires et d'API, cas hors ligne et permissions compris ;
- **démonstration** : les données viennent du fournisseur simulé.

### 1.0 Paramètres de la compagnie (préalable, petit)

- **Modèle** `configuration.ParametresCompagnie` : la compagnie et ses valeurs `{code: valeur}`. Un registre
  `configuration/parametres.py` décrit chaque paramètre (libellé, type, bornes, défaut de la plateforme, pôle qui le règle),
  sur le modèle du règlement intérieur.
- **API et écran** : `GET/PATCH /api/configuration/parametres/` ; page site « Paramètres de la compagnie » dans le menu
  Paramètres. Chacun ne voit que les paramètres qu'il règle.
- **Périmètre** : ne contient d'abord que les paramètres du lot 1. Les seuils actuels de P-07 (fatigue, retard…) n'y
  passeront qu'en P2a.
- **Migration** : `configuration 0005_parametres_compagnie`.

### 1.1 Source de télématique

- **Nouvelle app `telematique`** :
  - `fournisseurs/base.py` : l'interface `FournisseurTelematique`, qui transforme ce qu'elle reçoit en `Releve` (car,
    instant, position, vitesse, cap, accélérations longitudinale et latérale, niveau ou consommation de carburant,
    kilométrage) ;
  - les trois fournisseurs : `telephone.py` (le flux actuel, inchangé), `boitier.py` (webhook générique, au format JSON
    documenté par nous, avec une clé par compagnie, montrée une fois et révocable) et `simulateur.py` (un car qui roule le
    long de sa ligne, avec la commande `simuler_telematique` pour la démonstration et les tests) ;
  - `services.enregistrer_releves()` : rattache les relevés au trajet en cours du car, les stocke et les diffuse sur la carte.
- **Modèles** :
  - `telematique.EquipementVehicule` : car, source, identifiant du boîtier unique par compagnie, dernier relevé. Sans fiche,
    la source est le téléphone, comme aujourd'hui ;
  - `telematique.CleBoitier` ;
  - champs facultatifs ajoutés à `PositionVehicule` : cap, accélérations, carburant, kilométrage relevé, source.
- **Perte de signal** : la génération périodique repère un trajet en cours sans relevé depuis N minutes et alerte le chef de
  ligne, une fois par coupure. N est un paramètre de la compagnie.
- **Écrans** :
  - sur la fiche du véhicule, la source et l'identifiant du boîtier (directeur technique) ;
  - les clés du boîtier ;
  - sur la carte, la source de chaque car et le signal perdu.
- **Mobile** : le téléphone envoie aussi le cap (déjà fourni par `geolocator`). Les accélérations ne viendront que d'un
  boîtier (voir Q-05).
- **Migrations** : `telematique 0001`, `personnel_roulant` (ajout de champs).

### 1.2 Alertes de conduite et d'itinéraire

- **Modèles** :
  - `telematique.Geofence` : type (gare, itinéraire d'une ligne, zone interdite, zone de vitesse), géométrie, limite de
    vitesse, active. La géométrie est un cercle (centre et rayon) ou un couloir (tracé et largeur) ;
  - `telematique.EvenementConduite` : trajet, car, chauffeur, type (excès de vitesse, sortie d'itinéraire, arrêt non prévu,
    zone interdite, freinage, accélération ou virage brusques), début, fin, valeur maximale, position, gravité.
- **Sans dessin sur une carte** (voir Q-08) :
  - le cercle d'une gare se place à sa position, déjà saisie sur sa fiche ;
  - l'itinéraire se tire du tracé d'un trajet de référence ;
  - une zone interdite se pose par un point et un rayon.
- **Calculs** : en Python (distance, point dans une zone, écart au tracé). Pas de PostGIS, suffisant à notre échelle.
- **Détection** : à la réception des relevés ; l'arrêt non prévu est repéré par la génération périodique.
- **Destinataires** selon la gravité (Q-07) : chef de ligne ; puis QHSE ; puis directeur d'exploitation ; le critique remonte
  au tableau de bord du PDG.
- **Accessibilité** : bouton « Écouter » sur chaque alerte du site (synthèse vocale du navigateur) ; lecture à voix haute sur
  le mobile.
- **Migration** : `telematique 0002`.

### 1.3 Score de conduite mesuré

- **Modèle** `telematique.ScoreTrajet` : trajet, conducteur (une part par conducteur en cas de relais), score sur 100,
  détail par critère, date du calcul, date où le chauffeur l'a vu.
- **Calcul** (`telematique/score.py`) : 100 moins des pénalités par événement, pondérées par type de route. Les poids sont
  des paramètres de la compagnie.
- **Couleurs** : vert au-dessus de 80, orange de 50 à 80, rouge en dessous.
- **Score chauffeur composé** (`gamification/score_chauffeur.py`) : conduite, ponctualité, pauses et incidents, avec des
  pondérations réglables. Les points actuels restent tels quels.
- **Visibilité** : le chauffeur voit et **entend** son score et ses conseils sur le mobile, avant son supérieur (Q-11).
- **Relais** : le nouveau conducteur s'identifie (Q-12), et la suite du trajet lui est attribuée. La liste actuelle reste
  disponible en mode manuel.
- **Écrans** : « Mon score » sur le mobile (couleur, conseils, lecture à voix haute, consultable hors ligne une fois chargé) ;
  le score sur le tableau du chauffeur et du chef de ligne, sur le site.
- **Migration** : `telematique 0003`.

### 1.4 Carburant

- **Modèles** :
  - `finance.Plein` : car, chauffeur, ligne, trajet, date et heure, litres, montant, kilométrage, plein complet ou non,
    station, photo du reçu (pièce jointe contrôlée), clé anti-doublon pour le hors ligne ;
  - champ `capacite_reservoir_litres` sur le véhicule.
- **Dépense** : un plein crée lui-même sa dépense carburant, comme une facture payée crée la sienne. Le budget par ligne se
  calcule donc à partir des pleins, sans ressaisie (voir Q-15).
- **Consommation** aux 100 km, d'un plein complet au suivant, comparée à la moyenne de la flotte.
- **Anomalies**, avec des seuils propres à la compagnie (Q-14) :
  - surconsommation ;
  - baisse brutale du niveau à l'arrêt (boîtier seulement) ;
  - plein plus grand que le réservoir.

  Elles préviennent le directeur technique et le directeur financier.
- **Mobile** : écran « Plein » (saisie, dictée, photo), file hors ligne avec la photo envoyée à la synchronisation. Nouvelle
  bibliothèque `image_picker` (téléchargement).
- **Site** : pleins, consommation par car et anomalies (directeur technique, directeur financier).
- **Migrations** : `finance` (Plein), `reseau` (ajout d'un champ).

### 1.5 Échéances des documents

- **Nouvelle app `documents`** :
  - `TypeDocument` : catalogue de la compagnie, avec les sept types préchargés et les types en plus. Chacun porte sur un
    agent ou sur un véhicule, a un pôle prévenu (DRH, directeur technique ou juridique) et un effet à l'échéance : ignorer
    (défaut), alerter ou bloquer ;
  - `DocumentEcheance` : un agent **ou** un véhicule, numéro, dates, pièce jointe, saisi par.
- **Alertes** à J-30, J-7 et J0, par la génération périodique. Le chef de ligne est prévenu pour le permis et la visite
  médicale (OR-06).
- **Blocage**, si la compagnie le choisit pour un type : refus de planifier, de réaffecter ou de démarrer avec un chauffeur
  ou un car dont le document est expiré. Un message dit lequel, et le chef de ligne est prévenu, comme pour le blocage QHSE.
- **Existant gardé** : obligations RH, registre des assurances et carte de transport restent en place ; Q-17 tranche
  comment les relier.
- **Écrans** : « Documents à échéance » (chacun ses types), sur la fiche de l'agent et du véhicule. Le chauffeur voit ses
  documents sur le mobile, en lecture.
- **Migration** : `documents 0001`.

### 1.6 Permis à points et amendes

- **Modèles** (`rh`) :
  - `PermisAPoints` : capital, 12 au départ, modifiable à la main ;
  - `MouvementPoints` : retrait ou restitution, motif, source manuelle ou Quipux ;
  - `Amende` : instant, lieu, motif, montant, référence, car, chauffeur, statut.
- **Qui conduisait** : la fonction `conducteur_a(car, instant)` le retrouve par le trajet et les relais. Sans réponse sûre,
  l'amende reste « à attribuer » à la main.
- **Adaptateur `Quipux`** : une interface et un fournisseur simulé. Aucune connexion réelle.
- **Alertes** : quand le capital passe sous un seuil réglable (Q-20 pour les destinataires).
- **Mission** de gamification « trajet sans excès de vitesse » ; elle dépend de 1.2.
- **Saisie** par le DRH ou le juridique.
- **Migration** : `rh` (ajouts).

### 1.7 Facture normalisée électronique (FNE)

- **Nouvelle app `facturation`** :
  - `FactureNormalisee` : numéro par compagnie, ticket ou colis, montants, date, statut (à certifier, certifiée, rejetée),
    référence rendue par la DGI, envoi et réponse gardés ;
  - adaptateur `FournisseurFNE.certifier()`. Le fournisseur `simule.py` est celui par défaut. Le fichier `dgi.py` est
    **vide à dessein** : un bloc « À BRANCHER ICI » dit ce que l'API réelle devra recevoir. Rien n'est inventé.
- **Génération** : à chaque vente (guichet, synchronisation du mobile) et à chaque colis enregistré.
- **Hors ligne** : la vente du mobile est déjà mise en file. Côté serveur, une facture non certifiée reste « à certifier » ; la
  commande `certifier_factures` la reprend au retour de la DGI.
- **Écrans** : la facture depuis le ticket ou le colis (imprimable) ; la liste et les statuts pour le directeur financier.
- **Migration** : `facturation 0001`.

### 1.8 Gamification acceptable

- **Classement anonymisé** : le classement montre « Chauffeur #12 », un numéro stable par agent. Chaque agent voit sa
  propre ligne exacte, avec son nom. Les noms ne s'affichent que si la compagnie l'active (Q-22, Q-23).
- **Hors service** : aucune position ni aucun score n'est collecté hors trajet. C'est déjà le cas pour le téléphone ; le
  boîtier suivra la même règle (Q-24).
- **Pas de sanction automatique** : un test vérifie qu'aucun score ne déclenche de blocage, de mesure disciplinaire ni de
  retenue. Le guide le dit.
- **Migration** : `configuration` (un champ).

## 4. Bibliothèques nouvelles

- **Mobile** : `image_picker` (photo du reçu, 1.4). Si le QR est retenu au relais, aussi `mobile_scanner` (1.3).
- **Site et serveur** : aucune, sauf si vous voulez une vraie carte à fond de plan (Q-08).

## 5. Questions (je n'invente aucune de ces valeurs)

**Pour démarrer 1.0 et 1.1**

| # | Question |
|---|---|
| Q-01 | Ordre : corriger d'abord le lot A du mobile (au moins T-01 et G-03), puis 1.0 et 1.1 ? Ou 1.0 et 1.1 tout de suite ? |
| Q-02 | Après combien de minutes sans relevé alerter le chef de ligne d'une perte de signal ? (Pour mémoire, la carte date déjà une position au bout de 15 min) |
| Q-03 | Visez-vous un boîtier précis (marque, protocole) ? Sinon, je documente notre propre format JSON générique, et chaque fabricant s'y adaptera |
| Q-04 | Qui règle la source d'un car et gère les clés du boîtier : le directeur technique seul, ou aussi le PDG ? |
| Q-05 | Le téléphone doit-il aussi mesurer accélérations et freinages (ses capteurs, moins fiables) ? Ou seulement le boîtier ? |

**Pour 1.2 et 1.3**

| # | Question |
|---|---|
| Q-06 | Quels **types de route** et quelles **limites** pour un autocar (agglomération, route nationale, autoroute, piste) ? Comment reconnaître le type de route : par des zones de vitesse que la compagnie pose, ou par une limite unique hors zone ? |
| Q-07 | Gravité et destinataires : quel dépassement est « attention » et lequel est « critique » ? Faut-il prévenir le chef de ligne seul, puis ajouter le QHSE, puis le directeur d'exploitation ? |
| Q-08 | Faut-il une **vraie carte** à fond de plan (Leaflet et OpenStreetMap, nouvelle bibliothèque et service de tuiles externe) pour dessiner les zones ? Sinon, cercles et tracés tirés d'un trajet, comme proposé |
| Q-09 | Durée d'un arrêt non prévu avant l'alerte ? Les arrêts en gare et les pauses déclarées sont exclus |
| Q-10 | Seuils de freinage, d'accélération et de virage brusques, et poids de chaque critère dans le score de conduite ? Et pondérations du score chauffeur composé (conduite, ponctualité, pauses, incidents) ? |
| Q-11 | « Avant son supérieur » : le supérieur le voit-il dès que le chauffeur l'a ouvert, ou après un délai (lequel) ? |
| Q-12 | Identification au relais : code, QR ou badge ? Un badge NFC demande des cartes et des téléphones compatibles. Je propose un QR montré par le téléphone du nouveau conducteur, avec un code personnel en secours |

**Pour 1.4 à 1.7**

| # | Question |
|---|---|
| Q-13 | Qui saisit un plein : le chauffeur seul, ou aussi le chef de ligne ou le chef de gare ? |
| Q-14 | Seuils d'anomalie : surconsommation (en % au-dessus de la moyenne de la flotte, ou de la même classe de car), baisse du niveau à l'arrêt (en litres ou en %), marge au-delà du réservoir ? |
| Q-15 | Un plein crée-t-il la dépense carburant ? Si la finance saisit aussi ses dépenses carburant à la main, le carburant sera compté deux fois : faut-il interdire alors la saisie manuelle de cette catégorie, ou la garder ? |
| Q-16 | Un plein pendant un trajet compte pour la ligne de ce trajet. À quelle ligne imputer un plein fait hors trajet (au dépôt) : la ligne du prochain départ du car, ou aucune ? |
| Q-17 | Documents existants : (a) le nouveau registre **lit aussi** les obligations RH, les assurances et la carte de transport, sans double saisie (ma recommandation) ; (b) les données existantes sont reprises dans le nouveau registre, et les anciens écrans écrivent dedans ? |
| Q-18 | Le blocage par document expiré agit-il sur la planification seulement, ou aussi au démarrage de la feuille de route ? Le défaut reste « ignorer » (votre règle sur la réglementation) : confirmez-vous ? |
| Q-19 | Une amende : qui la paie (la compagnie, le chauffeur) et faut-il le suivre ? Un retrait de points se saisit-il sans amende ? |
| Q-20 | Seuil du capital de points, et qui est prévenu (DRH, chef de ligne, chauffeur lui-même) ? |
| Q-21 | **FNE** : avez-vous le texte ou la documentation de la DGI (mentions obligatoires, numérotation, TVA sur le transport de voyageurs, avoir en cas d'annulation) ? La compagnie a-t-elle un accès de test ? Une facture par ticket, ou par vente ? |

**Pour 1.8**

| # | Question |
|---|---|
| Q-22 | Aujourd'hui les classements sont **nominatifs**. Votre règle veut que le défaut garde le comportement actuel, mais votre cahier demande l'anonymat par défaut. Faut-il anonymiser aussi les compagnies existantes, ou seulement les nouvelles ? |
| Q-23 | Anonymat : vaut-il aussi pour la direction et le DRH ? Le cahier donne au DRH une « vue transversale des scores par agent comme aide à l'évaluation » |
| Q-24 | Hors service, faut-il jeter toute position du boîtier, ou garder la position du **car seul** (vol, sécurité du parc), sans la rattacher à aucun chauffeur ? |

## 6. Façon de travailler

1. Une fonctionnalité à la fois, dans l'ordre 1.0, 1.1, 1.2, 1.3, 1.4, puis 1.5 à 1.8.
2. Pour chacune :
   - les tests du serveur (droits, cloisonnement, défaut inchangé, réglage appliqué, hors ligne) ;
   - les tests du site et du mobile ;
   - un parcours Chrome ;
   - un résumé de ce qui a changé ;
   - puis j'attends votre validation avant la suivante.
3. Je pose la question dès qu'une valeur manque, au lieu de l'inventer.
4. Aucun commit sans votre demande.
5. Le lot 2 attend la validation du lot 1.
