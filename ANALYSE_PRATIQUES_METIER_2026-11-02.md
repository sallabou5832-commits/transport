# Analyse métier — la logique de l'application face aux pratiques du secteur (2 novembre 2026)

Demande : « analyse la logique de fonctionnalité de toute l'application avec les pratiques réelles dans le secteur ; si l'une de
mes fonctionnalités n'est pas conforme, ne la supprime pas mais ajoute-la comme une extension d'usage, puis ajoute ce qui devrait
normalement faire partie des fonctionnalités, que ce soit dans les paramètres et partout sur l'application ; avec plus d'attention
de vérification ». Précision : « au niveau de tout ce qui est réglementation, laisser toujours le choix aux compagnies d'agir à
leur guise ». Et, plus tôt : ne plus redemander le « code » (mot de passe) à chaque accès, chacun réglant cela à sa guise.

Ce document est l'**analyse et la proposition**. Aucun code n'a été modifié pour l'écrire : chaque lot du §6 attend votre accord.

## 0. Principes appliqués

1. **Rien n'est supprimé.** Une fonction qui s'écarte des usages du métier reste disponible comme **extension d'usage**
   (une option, un mode) ; le mode habituel du secteur est **ajouté à côté**.
2. **La réglementation est toujours au choix de la compagnie.** Pour chaque obligation légale, l'application **propose,
   rappelle et alerte** ; la compagnie choisit pour chacune : **ignorer**, **alerter** ou **bloquer**. Rien n'est imposé en dur.
3. **Le défaut reste le comportement actuel** (règle déjà fixée) : rien ne change tant qu'une compagnie ne règle rien. Pour
   éviter de tout régler un par un, un bouton **« Appliquer les pratiques du secteur »** basculerait d'un coup les réglages
   concernés vers les usages décrits ici ; chacun reste ensuite modifiable.
4. **Le cloisonnement entre compagnies n'est pas réglable** (règle absolue) : tout nouveau réglage, écran ou export reste propre
   à la compagnie.

Légende : ✅ conforme aux usages · 🔁 écart : l'existant devient une extension d'usage et le mode du secteur s'ajoute ·
➕ manque : pratique habituelle absente · ⚖️ réglementaire : réglage de la compagnie (ignorer / alerter / bloquer).

## 1. Méthode et vérification

- **L'application telle qu'elle est** : le schéma a été extrait du code en marche (`manage.py shell`) — 19 apps métier, 71 modèles
  avec tous leurs champs, 202 routes d'API — puis recoupé avec les écrans (`frontend/src`) et le mobile (`mobile/lib`). Chaque
  constat « Aujourd'hui » ci-dessous cite le modèle, le champ ou le fichier qui le prouve. Les états du 2 novembre (tests,
  parcours) sont dans `AUDIT_AVANCEMENT_2026-11-02.md`.
- **Les pratiques du secteur** : usages des grandes compagnies interurbaines ivoiriennes et de la gestion de flotte en général,
  et textes en vigueur. Les recherches faites aujourd'hui ont confirmé certains points (sources au §7) ; quand aucune source
  officielle n'a été trouvée, la ligne le dit et la valeur devient **un réglage à calibrer avec la compagnie pilote**, jamais une
  règle figée.

## 2. En bref

- **Le constat le plus important touche les paramètres** : une compagnie ne peut pas démarrer seule. Aucun écran ne permet de
  créer ses gares, ses lignes (ni de fixer un tarif), ses véhicules, ses pièces, ni les comptes de son personnel (l'API sait
  déjà créer gares, lignes, véhicules et pièces : ce sont les écrans qui manquent ; vérification du 2 novembre au soir) ; aucun agent ne
  peut changer son mot de passe ; le magasinier ne peut pas enregistrer une entrée en stock. Tout passe par l'administration
  Django (§3).
- **Les réglages métier sont les mêmes pour toutes les compagnies** : seuil de fatigue (4 h 30), tolérance de retard (10 min),
  fenêtre de planification (8 h), places garanties hors ligne (2), préavis d'entretien, seuil de renouvellement (600 000 km)… sont
  fixés dans le code ou dans les variables du serveur, pas par chaque compagnie (§3, P-07).
- **10 points sont déjà conformes** aux usages : tarif imposé à la vente, vente hors ligne garantie, contrôle à bord, blocage de
  sécurité, préventif par jours et kilomètres, relais de conducteur, colis suivis de bout en bout, cloisonnement, journal d'audit (§4, ✅).
- **16 écarts** deviennent des extensions d'usage avec le mode habituel ajouté à côté. Exemples : places non numérotées, toute
  pause qui remet la fatigue à zéro, arrêté de caisse sans comptage, frais de colis libres, checklist figée à 6 items.
- **41 manques** sont relevés (une ligne en regroupe souvent plusieurs), dont les plus courants dans le métier : manifeste des passagers, ticket imprimé
  avec QR code, réservation et report de billet, escales et tarifs par tronçon, grille horaire récurrente, départ au remplissage,
  comptage de caisse et versements, barème et « port dû » des colis, coût des réparations, consommation de carburant, âge des
  véhicules, solde de congés.
- **10 points réglementaires** deviennent des réglages de compagnie (§5).
- **Proposition** : 9 lots (§6), en commençant par les **paramètres de base et l'accès aux comptes**. C'est le préalable à un
  pilote, et c'est là que se règle votre demande sur le code de connexion.

## 3. Les paramètres : ce qui manque pour qu'une compagnie travaille sans l'administration Django

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| P-01 ➕ | `Company` ne connaît que `name`, `headquarters_city`, `created_at` | Les billets, reçus et exports portent la raison sociale, le sigle, le logo, l'adresse, le téléphone du service client, le RCCM, le numéro de compte contribuable et l'autorisation d'exercer (décret n° 2015-269 sur l'accès à la profession) | Écran **Ma compagnie** (PDG) : identité, mentions légales, logo, coordonnées ; repris sur billets, reçus, manifestes, exports |
| P-02 ➕ | Gares : aucun écran de création ni de modification (`/gares/` sans écriture côté site) ; ni quais, ni téléphone, ni horaires | Une gare a ses quais, ses horaires d'ouverture, son téléphone | Écran **Gares** : création, modification, quais, coordonnées, chef de gare |
| P-03 🔁➕ | `Ligne` : une gare de départ, une d'arrivée, **un seul tarif** facultatif ; aucun écran pour créer une ligne ni fixer son tarif | Lignes avec **escales** et **tarif par tronçon**, **classes** (standard, climatisé, VIP), tarifs particuliers (enfant, période de fêtes), distance et durée prévues | Écran **Lignes et tarifs**. Le tarif unique reste (extension d'usage « ligne simple ») ; s'ajoutent escales, grille tarifaire par tronçon et par classe, tarifs particuliers, distance et durée |
| P-04 ➕ | `Vehicule` : immatriculation, capacité, statut, gare, kilométrage ; aucun écran de création | Fiche complète : marque, modèle, **année de mise en circulation** (le décret n° 2017-793 fixe des durées d'exploitation), classe, **plan des places**, carte grise, carte de transport | Écran **Véhicules** : création, fiche complète, plan des places, documents du véhicule (§5) |
| P-05 ➕ | `Piece` : nom, référence, stock, seuil ; aucun écran de création ; **aucune entrée en stock tracée** : les sorties font baisser le stock, et seule une correction directe de `quantite_stock` par l'API (magasinier, chef d'atelier, directeur technique ; visible au journal d'audit, sans écran) le fait remonter | Bon de commande → réception → entrée en stock ; prix unitaire, fournisseur, emplacement ; inventaire périodique | Écran **Pièces** (création, prix, fournisseur) et **réception** (entrée en stock tracée) ; inventaire avec écart |
| P-06 ➕ | Comptes : création, rôle et mot de passe seulement dans l'administration Django ; `/comptes/` sert à lister, suspendre, réactiver ; `User` n'a ni téléphone ni matricule | Le DRH ou le PDG crée le compte à l'embauche, réinitialise un mot de passe oublié, désactive au départ | Écran **Personnel et comptes** (PDG, DRH) : créer, rôle, gare, téléphone, matricule, mot de passe provisoire à changer à la première connexion, réinitialiser ; lié au dossier agent |
| P-07 🔁 | Réglages métier **communs à toute la plateforme** : `SUIVI_SEUIL_FATIGUE_MINUTES` 270, `BILLETTERIE_QUOTA_HORS_LIGNE` 2, `..._TTL_HEURES` 12, `..._HORIZON_..._HEURES` 24, `ENTRETIEN_PREAVIS_JOURS` 15 / `_KM` 1 000, `RENOUVELLEMENT_KM` 600 000, `POSITIONS_RETENTION_JOURS` 30 (variables du serveur) ; `TOLERANCE_RETARD` 10 min (`dashboard/ponctualite.py`) et `FENETRE_OCCUPATION` 8 h (`billetterie/planning.py`) écrits dans le code | Chaque compagnie fixe ses propres politiques (taille des cars, longueur des trajets, organisation) | Les valeurs actuelles deviennent le **défaut de la plateforme** (extension d'usage) ; chaque compagnie peut les remplacer dans **Paramètres de la compagnie** |
| P-08 ➕ | Mot de passe : aucune route pour le changer (`auth/` = `login`, `refresh`, `me`) ; session de 1 jour au plus, puis mot de passe redemandé | Chacun change son mot de passe ; sur un appareil personnel on **reste connecté** ; sur le terrain, un **code court** ou l'empreinte rouvre l'application ; sur un poste partagé (guichet), le mot de passe reste exigé | Écran **Mes paramètres** : changer son mot de passe ; **rester connecté** (1 j, 7 j, 30 j, jusqu'à déconnexion) ; **code court** à 4–6 chiffres sur le mobile ; plafond éventuel fixé par la compagnie (défaut : comportement actuel) — c'est votre demande sur le « code » |
| P-09 🔁 | La préférence vocale d'un agent est réglée **par son supérieur** (`ConfigurationAgent.prefere_vocal`) ; aucun réglage personnel (langue, sons, notifications) | L'agent règle lui-même ses préférences d'usage | Le réglage par le supérieur reste (extension d'usage) ; **Mes paramètres** ajoute voix, langue d'affichage, son, notifications ; le choix de l'agent s'applique sauf si son supérieur l'a imposé |
| P-10 ➕ | Les 18 postes sont fixés dans le code (`core.Role`) | Chaque compagnie a ses intitulés (« caissier principal », « chef de quai »…) — le cahier le demande aussi | **Intitulés de poste propres à la compagnie**, chacun adossé à un poste du socle dont il hérite les droits (sans toucher au contrôle des permissions) |
| P-11 ➕ | Ouverture d'une compagnie sur la plateforme : administration Django | Le super-administrateur crée la compagnie et son premier PDG, qui configure le reste | Écran **plateforme** : nouvelle compagnie + premier compte PDG |

## 4. Analyse par domaine

### 4.1 Billetterie

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| B-01 ✅ | Tarif de la ligne imposé, autre prix réservé à un chef avec motif (`Ticket.prix_tarif`, `motif_derogation`) | Prix affichés, homologués, sans négociation au guichet | Garder |
| B-02 🔁 | Places comptées, **non numérotées** (`Depart.places_vendues`, aucun numéro de siège sur `Ticket`) | Places **numérotées** sur la plupart des lignes des grandes compagnies (source non officielle, §7) ; places libres sur les minicars | « Places non numérotées » reste (extension d'usage) ; **plan des places** et choix du siège à la vente, réglable par ligne |
| B-03 ➕ | Un billet est une vente immédiate ; pas de réservation (`ReservationHorsLigne` ne sert qu'aux places garanties hors ligne des guichetiers) | Réservation par téléphone ou en ligne, payée ou à confirmer avant une heure limite ; achat à l'avance conseillé pour les fêtes | **Réservation** avec échéance de confirmation et libération automatique de la place ; acompte facultatif |
| B-04 🔁 | Annulation par un chef, remboursement intégral implicite (`billetterie/ventes.annuler_ticket`) | Conditions écrites : **report** sur un autre départ (avec ou sans frais), remboursement partiel selon le délai | L'annulation intégrale reste (extension d'usage) ; **politique de la compagnie** : report, frais, retenue selon le délai |
| B-05 ➕ | Aucun manifeste : la liste des billets d'un départ se lit à l'écran du chef de gare | **Manifeste** des passagers (liste nominative du départ, remise à l'équipage, présentée aux contrôles) ; la CEDEAO numérise le manifeste des transports inter-États (§7) | **Manifeste** imprimable et PDF par départ ; pièce d'identité facultative, rendue obligatoire au choix de la compagnie, par ligne (⚖️, §5) |
| B-06 ➕ | Pas de ticket papier ; le code du billet part par SMS | Ticket imprimé au guichet (souvent imprimante thermique), avec QR ou code-barres, le SMS en complément | **Ticket imprimable** (format 58 / 80 mm et A4) avec QR code ; le SMS reste |
| B-07 🔁 | Mode de paiement : `especes` ou `mobile_money`, sans opérateur ni référence | Opérateur (Orange Money, MTN MoMo, Moov Money, Wave) et **numéro de transaction** pour rapprocher les encaissements | Le mode à deux valeurs reste ; s'ajoutent **opérateur** et **référence de transaction** (sans intégration de paiement, qui reste un lot externe) |
| B-08 ➕ | Le bagage est un colis lié au billet ; pas de franchise | **Franchise** de bagage incluse (≈ 20 kg selon des sources non officielles), excédent facturé au kilo ou à la pièce | **Franchise et barème d'excédent** réglables par compagnie et par classe |
| B-09 ➕ | Ni aller-retour ni tarif enfant | Aller-retour, enfant, catégories particulières | Types de billet réglables (§3 P-03) |
| B-10 ✅ | Vente hors ligne garantie, idempotence, lien avec un logiciel de billetterie existant | — | Garder (écrans du lien prévus au lot P2) |

### 4.2 Caisse

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| K-01 🔁 | `ClotureCaisse` = totaux **théoriques** (billets, espèces, mobile, annulations), clôture manuelle, assistée ou automatique | **Arrêté de caisse** : fond de caisse, **comptage physique** des espèces, **écart** justifié, double signature (guichetier et chef de gare) | La clôture théorique reste (extension d'usage, utile à la clôture automatique) ; s'ajoutent fond de caisse, montant compté, écart et motif, validation du chef |
| K-02 ➕ | L'argent clôturé ne va nulle part dans l'application | **Versement** de la gare à la caisse centrale ou à la banque, bordereau de dépôt | **Versements** gare → caisse centrale → banque, suivis jusqu'à la trésorerie |
| K-03 ➕ | Fret (colis) hors de la clôture du guichetier | Une seule caisse par agent, billets et fret confondus | Caisse unifiée (billets + colis) au choix de la compagnie |

### 4.3 Exploitation et réseau

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| E-01 ✅ | Planification sans conflit de chauffeur ni de véhicule, réaffectation, remplaçant suggéré | — | Garder ; la fenêtre de 8 h devient un réglage (P-07) |
| E-02 ➕ | Chaque départ se planifie un par un | **Grille horaire** récurrente (départs de 6 h, 8 h, 10 h… chaque jour), départs supplémentaires en période de pointe | **Grille horaire** par ligne et par jour, qui génère les départs ; ajout ponctuel conservé |
| E-03 🔁 | Départ à heure fixe uniquement (`Depart.date_heure`) | En gare routière et sur les minicars : **départ au remplissage** (le car part quand il est plein) | L'heure fixe reste ; mode **« au remplissage »** par ligne (ponctualité mesurée autrement) |
| E-04 ➕ | Aucun quai (rotation des quais du cahier, n° 18) | Quais affectés, ordre d'embarquement affiché | **Quais** par gare, affectation et ordre d'embarquement proposés, ajustés par le chef de gare |
| E-05 ➕ | Le billet est validé à bord par le contrôleur | **Embarquement** au quai : billet vérifié à la montée, absents relevés | Étape **embarquement** (même vérification que le contrôle à bord), absents marqués au manifeste |
| E-06 🔁 | Ponctualité mesurée **au départ** seulement (tolérance 10 min) | Retard au départ **et** à l'arrivée | Arrivée mesurée aussi, tolérances réglables |
| E-07 ➕ | Les voyageurs ne sont prévenus que de leur achat | SMS aux voyageurs d'un départ **retardé, avancé ou annulé** | Message aux voyageurs d'un départ, au choix du chef de gare (SMS / WhatsApp, simulation par défaut) |

### 4.4 Personnel roulant et sécurité

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| R-01 🔁 | Checklist avant-départ **figée à 6 items** dans le site et le mobile (`ITEMS_CHECKLIST`, `checklistItems`) ; l'**extincteur**, item de sécurité côté serveur, n'y figure pas (N-01) | Liste plus large : pneus, freins, direction, éclairage, ceintures, **extincteur, trousse de secours, triangles, roue de secours**, essuie-glaces, niveaux, **documents de bord** | Les 6 items restent (« checklist de base ») ; **checklist réglable par compagnie** : items, item de sécurité ou non, obligatoire ou non ; renvoyée par le serveur au site et au mobile |
| R-02 ➕ | Pas de contrôle d'aptitude | Alcootest ou déclaration d'aptitude avant départ dans certaines compagnies | Item d'aptitude facultatif dans la checklist réglable |
| R-03 🔁 | Fatigue : 4 h 30 de conduite continue ; **une pause de n'importe quelle durée remet le compteur à zéro** (`suivi.py`, fin de la dernière pause) | Pause minimale pour compter comme repos, plafond de conduite par jour, repos entre deux services | Le comportement actuel reste (pause minimale = 0) ; s'ajoutent **pause minimale**, **plafond journalier**, **repos minimal** (⚖️ : aucun texte ivoirien trouvé, valeurs à fixer par la compagnie) |
| R-04 ➕ | `FeuilleDeRoute` : heures seulement | **Carnet de bord** : kilométrage au départ et à l'arrivée, plein de carburant (litres, montant), péages, frais de route | Champs de carnet de bord sur la feuille de route ; alimentent consommation, coût au km et kilométrage du véhicule |
| R-05 ➕ | Accident : type, gravité, texte, position | Nombre de blessés et de décès, procès-verbal de police, constat, photos | Détails d'accident et pièces jointes dès la déclaration (aujourd'hui seulement via le sinistre) |
| R-06 ⚖️ | Permis et visite médicale suivis comme obligations RH, sans effet sur la planification | Un conducteur au permis ou à la visite expirés ne prend pas le volant | À la planification : **ignorer / alerter / bloquer**, au choix de la compagnie (défaut : ignorer, comme aujourd'hui) ; le **chef de ligne est prévenu** de l'expiration (fusionné avec OR-06, lot P6) |
| R-07 ✅ | Relais, checklist de reprise, mode convoyeur, contrôle à bord, blocage QHSE | — | Garder |

### 4.5 Colis et messagerie

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| C-01 🔁 | `Colis.frais` **saisis à la main** par le bagagiste | **Barème** : nature, poids, destination ; **assurance ad valorem** sur la valeur déclarée | La saisie libre reste ; **barème** de la compagnie, frais calculés, dérogation motivée (comme le tarif des billets) |
| C-02 🔁 | Frais payés **à l'enregistrement** seulement | **Port dû** très courant : le destinataire paie au retrait | Mode **port dû** ajouté (encaissé au retrait, dans la caisse de la gare d'arrivée) |
| C-03 ➕ | Retrait : code + nom du retirant (`retire_par_nom`) | Pièce d'identité relevée, procuration possible | Numéro de pièce d'identité au retrait, au choix de la compagnie |
| C-04 ➕ | Aucun délai de garde | Garde gratuite quelques jours, puis **frais de magasinage** ; procédure des colis non réclamés | Délai de garde, frais par jour, relances SMS, liste des colis non réclamés |
| C-05 ➕ | Plan de chargement à l'écran ; pas de reçu | **Reçu** à l'expéditeur, **bordereau de fret** par départ remis à l'équipage | Reçu et bordereau imprimables |
| C-06 ✅ | Code de retrait par SMS, statuts de bout en bout, alerte à la gare d'arrivée | — | Garder |

### 4.6 Technique et maintenance

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| T-01 ✅ | Préventif par jours et/ou kilomètres, ordres ouverts tout seuls, file par urgence, fiche véhicule | — | Garder ; préavis réglables par compagnie (P-07) |
| T-02 ➕ | `OrdreReparation` : temps passé seulement | **Coût** de l'intervention : pièces valorisées + main-d'œuvre + garage extérieur (sous-traitance) | Coût de chaque ordre, garage extérieur, coût cumulé par véhicule (alimente la rentabilité) |
| T-03 ➕ | Carburant : dépense en francs (`Depense`, sans litres) | Pleins en **litres** et kilométrage → **consommation** (L/100 km), détection des anomalies | Pleins saisis avec litres et compteur (carnet de bord R-04), consommation par véhicule et par ligne |
| T-04 🔁 | Renouvellement : kilométrage, nombre de réparations, immobilisation (`maintenance/analyses.py`) ; **l'âge du véhicule n'existe pas** | L'âge compte, et le décret n° 2017-793 fixe des durées d'exploitation des véhicules de transport | Les trois critères restent ; s'ajoute l'**âge** (année de mise en circulation, P-04) avec une durée maximale réglable (⚖️) |
| T-05 ➕ | Pas de suivi des pneus | Suivi par pneu (pose, kilométrage, rechapage) dans les flottes de cars | Facultatif, activable par la compagnie |
| T-06 🔁 | Clore un ordre de réparation rend le véhicule disponible même sous blocage QHSE (C-02 du 31 octobre, laissé tel quel par décision) | Un blocage de sécurité n'est levé que par celui qui l'a posé | Le comportement actuel reste ; **réglage** « le blocage QHSE prime sur la clôture de l'atelier » proposé à la compagnie, défaut : non |

### 4.7 Ressources humaines

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| H-01 ✅ | Dossier agent, contrats, évaluations, discipline, formations obligatoires, recrutement, médiation | — | Garder |
| H-02 ➕ | `DemandeConge` sans **solde** | Droits acquis chaque mois de service, solde affiché avant la demande | Solde de congés : droits par mois réglables par la compagnie (⚖️ Code du travail), décompte automatique |
| H-03 ➕ | Pas de paie (le cahier dit « RH et paie ») | Paie, cotisations sociales, primes de route des chauffeurs, avances sur salaire | **Éléments variables de paie** (primes de route, heures, avances, absences) exportés vers le logiciel de paie ; la paie complète reste un choix ultérieur |
| H-04 ➕ | Pas de pointage ni de planning du personnel sédentaire | Présences et planning de service par gare | Planning de service et présences, au choix de la compagnie |

### 4.8 Finance

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| F-01 ✅ | Recettes consolidées, dépenses, budget carburant, factures et échéancier, rentabilité, trésorerie, export CSV | — | Garder |
| F-02 ➕ | Encaissements mobile money non rapprochés | Rapprochement des transactions avec le relevé de l'opérateur | Rapprochement par référence de transaction (B-07) |
| F-03 ➕ | Pas de caisse centrale ni de comptes bancaires | Caisses de gares, caisse centrale, banques | Comptes de trésorerie alimentés par les versements (K-02) |
| F-04 ➕ | Export CSV de synthèse | Export pour le comptable selon le plan **SYSCOHADA** (journaux des ventes, achats, caisse) | Export comptable, correspondance des catégories avec les comptes, réglable |
| F-05 ➕ | Budget pour le carburant seulement ; catégories de dépenses limitées | Budgets maintenance, salaires… ; péages, frais de route, loyers, taxes | Budgets et catégories de dépenses réglables par la compagnie |
| F-06 ➕ | Pas de coût de revient au kilomètre | Indicateur central du métier | Coût au km par ligne et par véhicule (après R-04 et T-02) |

### 4.9 Juridique, conformité, données

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| J-01 ➕ | `Assurance` : assureur, numéro de police, échéance | Type de garantie (responsabilité civile, voyageurs transportés, tous risques), prime, attestation à bord | Type, prime, attestation jointe, rappel de renouvellement (existe déjà pour l'échéance) |
| J-02 ⚖️➕ | Documents réglementaires du véhicule suivis comme « plans d'entretien réglementaires » | Registre des documents (carte grise, visite technique, carte de transport ou autorisation, patente) avec échéances et copie | **Registre des documents du véhicule** avec échéances ; à l'échéance : ignorer / alerter / bloquer le départ, au choix de la compagnie |
| J-03 ⚖️ | Sinistre ouvert tout seul sur incident grave | L'assureur doit être prévenu dans le délai du contrat (au moins 5 jours ouvrés selon une source non officielle sur le Code CIMA, §7) | Délai de déclaration réglable, alerte au juridique avant son terme |
| J-04 ⚖️➕ | Noms et téléphones des voyageurs et destinataires conservés sans limite de durée | Loi n° 2013-450 : formalités auprès de l'ARTCI, information des personnes, durée de conservation, droits d'accès et de suppression | **Durée de conservation** réglable avec effacement automatique, mention sur billets et reçus, export et effacement à la demande ; la compagnie choisit de l'activer |
| J-05 ✅ | Journal d'audit, pièces jointes contrôlées, conformité partagée QHSE / juridique | — | Garder |

### 4.10 Gamification, alertes, communication

| # | Aujourd'hui (vérifié) | Pratique du secteur | Proposition |
|---|---|---|---|
| G-01 🔁 | Missions, points, badges, classements ; niveau réglable par poste | Peu répandu dans le secteur ; les compagnies pratiquent plutôt des **primes de performance** | C'est déjà une extension d'usage réglable : garder ; lien facultatif points → prime (avec H-03) |
| N-01 ➕ | Alertes visibles seulement page ouverte (cloche) | Les postes de terrain sont prévenus sur leur téléphone (notification ou SMS) | Notifications poussées et SMS pour les alertes critiques, au choix de chaque agent (P-09) et de la compagnie |
| N-02 ✅ | Notes de service, agenda, messages du chef de gare, archives | — | Garder |

## 5. Réglementation : au choix de chaque compagnie

Chaque point devient un réglage de la compagnie à trois positions — **ignorer** (défaut, comportement actuel), **alerter**,
**bloquer** — avec une valeur proposée modifiable. L'application rappelle l'obligation, elle ne l'impose pas.

| Obligation | Source trouvée | Valeur proposée (modifiable) | Où elle agit |
|---|---|---|---|
| Visite technique des véhicules de transport public | Périodicité semestrielle selon la presse et un site spécialisé ; le cahier des charges officiel n'a pas pu être lu | 6 mois | Registre des documents (J-02), départ |
| Durée d'exploitation des véhicules | Décret n° 2017-793 (les durées pour les autocars n'ont pas pu être lues) | À saisir par la compagnie | Renouvellement (T-04), planification |
| Autorisation d'exercer, carte de transport | Décret n° 2015-269 | Numéro et échéance | Ma compagnie (P-01), véhicules (P-04) |
| Assurance du véhicule et des voyageurs | Code CIMA | Échéance, type de garantie | Registre (J-01), départ |
| Déclaration de sinistre | Code CIMA, art. 12 (délai du contrat, au moins 5 jours ouvrés selon une source non officielle) | 5 jours ouvrés | Sinistres (J-03) |
| Temps de conduite et de repos | **Aucun texte ivoirien trouvé** | 4 h 30 continues (actuel), pause minimale et plafond journalier à fixer | Suivi de trajet (R-03) |
| Permis et visite médicale du conducteur | Obligations RH déjà suivies | Échéances saisies ; le chef de ligne est prévenu de l'expiration | Planification : ignorer (défaut) / alerter / bloquer (R-06 et OR-06, lot P6) |
| Manifeste des passagers | Manifeste des transports inter-États en cours de numérisation à la CEDEAO (presse, 2023) | Pièce d'identité exigée : par ligne | Vente et manifeste (B-05) |
| Données personnelles | Loi n° 2013-450, ARTCI (déclaration ou autorisation préalable, correspondant) | Durée de conservation à fixer | Données des voyageurs (J-04) |
| Congés payés | Code du travail (droits par mois de service) | À saisir par la compagnie | Solde de congés (H-02) |

## 6. Plan proposé, par lots (chacun soumis à votre accord, puis vérifié)

Taille : **S** moins d'un jour · **M** quelques jours · **L** une à trois semaines. Les lots C, A et B déjà approuvés sont repris :
C dans P2 (fait depuis : écrans du règlement intérieur et du lien billetterie, §8.8), A et B (mobile) après P1 et P3, parce que le mobile doit suivre les nouveaux tarifs, places et réglages.

| Lot | Contenu | Points | Taille |
|---|---|---|---|
| **P1 — Paramètres de base et accès aux comptes** | Ma compagnie ; gares et quais ; lignes et tarifs (tarif unique, escales en P3) ; véhicules (fiche complète, année) ; pièces et entrées en stock ; personnel et comptes (création, mot de passe provisoire, réinitialisation) ; **mes paramètres** (changer son mot de passe, rester connecté, code court mobile, voix, langue, notifications) ; plafond de connexion par compagnie | P-01 à P-06, P-08, P-09 | L |
| **P2a — Réglages métier** | Paramètres de la compagnie (seuils et tolérances aujourd'hui communs à la plateforme, P-07) ; checklist réglable, extincteur compris (R-01), avec un item d'aptitude facultatif (R-02) ; réglementation à trois positions ignorer / alerter / bloquer (§5) ; bouton « appliquer les pratiques du secteur ». Les écrans du règlement intérieur et du lien billetterie (ancien lot C) sont faits (§8.8) | P-07, R-01, R-02, §5 | M |
| **P2b — Organisation** | Dans cet ordre : copie des notes du pôle Personnel roulant à l'encadrement, au choix de la compagnie (OR-01) ; avis du supérieur direct sur un congé, ignorer / demander / exiger, délai de 48 h réglable (OR-02) ; règle O-10 par accord du directeur technique et du QHSE, le PDG informé et pouvant reprendre la main (OR-03) ; alertes croisées exploitation–technique, coupées par défaut (OR-04) ; délégations du PDG depuis le règlement intérieur (OR-07) ; **en dernier**, rattachement des Fonctions supports au secrétaire général en option (OR-07), testé option activée et désactivée (configuration hiérarchique, matrice des rôles, guide). Une fois P2b fait, le bouton « pratiques du secteur » de P2a **inclut OR-04** | OR-01 à OR-04, OR-07 | M–L |
| **P3 — Billetterie du secteur** | Escales et tarifs par tronçon et par classe, types de billet ; plan des places ; ticket imprimé avec QR ; manifeste ; opérateur et référence mobile money ; franchise bagages ; réservation ; report et politique d'annulation | P-03, B-02 à B-09 | L |
| **P4 — Caisse** | Arrêté de caisse avec comptage et écart, validation du chef ; versements vers caisse centrale et banque ; caisse unifiée billets + colis | K-01 à K-03, F-03 | M |
| **P5 — Exploitation** | Grille horaire récurrente ; départ au remplissage ; quais et embarquement ; ponctualité à l'arrivée ; SMS aux voyageurs d'un départ retardé ou annulé | E-02 à E-07 | L |
| **P6 — Roulant et sécurité** | Carnet de bord (km, carburant, frais) ; pause minimale, plafond journalier, repos ; détails d'accident ; documents du conducteur à la planification, avec **le chef de ligne prévenu de l'expiration du permis ou de la visite médicale** et la planification ignorer (défaut) / alerter / bloquer (R-06 fusionné avec OR-06) | R-03 à R-06, OR-06 | M |
| **P7 — Colis** | Barème et assurance ad valorem ; port dû ; pièce d'identité au retrait ; garde et magasinage ; reçu et bordereau | C-01 à C-05 | M |
| **P8 — Technique** | Coût des réparations et garage extérieur ; consommation de carburant ; âge et renouvellement ; pneus (facultatif) ; réglage « le blocage QHSE prime » | T-02 à T-06 | M |
| **P9 — RH, finance, juridique, données** | Solde de congés ; éléments variables de paie ; rapprochement mobile money ; export SYSCOHADA ; budgets et catégories ; coût au km ; assurances détaillées ; registre des documents ; délai de déclaration de sinistre ; conservation des données ; postes propres à la compagnie ; ouverture d'une compagnie ; notifications poussées ; **alertes du PDG** : en direct les seules alertes critiques (liste réglable), le reste dans une **synthèse du jour** (version 1 sans IA, heure réglable ; version 2 avec l'IA d'analyse du pôle du PDG) (OR-07) ; côté RH, **parcours de formation par poste** et gestion des sessions (O-13) ; budget carburant dépassé prévenant le directeur d'exploitation et le chef de ligne (OR-05) | H-02 à H-04, F-02 à F-06, J-01 à J-04, P-10, P-11, N-01, OR-05, OR-07, O-13 | L |
| Mobile A puis B | Chauffeur complet, tarif du guichetier, puis bagagiste, contrôleur, mécanicien — en suivant P1 à P3 | (lots déjà approuvés) | M–L chacun |

Vérification de chaque lot, avant de passer au suivant : tests du serveur (dont la matrice des rôles, le contrat pages ↔ API et le
cloisonnement entre compagnies, avec un test par nouveau réglage : défaut inchangé, réglage appliqué, autre compagnie non
touchée), tests du site, parcours de bout en bout dans Chrome étendus aux nouveaux écrans, essai du mobile contre un vrai
serveur ; compte rendu ajouté à ce document ; un commit par lot, rien n'est poussé sans votre accord.

## 7. Limites et sources

- Les usages cités sans texte officiel (places numérotées, franchise de bagages, port dû, frais de garde, alcootest…) sont
  courants dans le secteur mais **varient d'une compagnie à l'autre** : ils sont proposés comme réglages, à calibrer avec la
  compagnie pilote, jamais imposés.
- Les chiffres réglementaires non confirmés par un texte officiel lisible (périodicité de la visite technique, durées
  d'exploitation des autocars, délais CIMA, temps de conduite) sont des **valeurs proposées**, modifiables par chaque compagnie.
- L'analyse porte sur la logique fonctionnelle ; la sécurité et la robustesse sont traitées dans `RAPPORT_ANOMALIES_2026-10-31.md`
  et `AUDIT_AVANCEMENT_2026-11-02.md`.

Sources consultées le 2 novembre 2026 :
- [Décret n° 2015-269 — activité de transport routier (DGTTC)](https://dgttc.ci/fichiers_uploades/files/DECRET_N2015-269_ACTIVITE_DE_TRANSPORT_ROUTIER.pdf)
- [Décret n° 2017-793 — durées d'exploitation des véhicules (CivLII)](https://civlii.laws.africa/en/akn/ci/act/decree/2017/793/fra@2023-07-18/source)
- [Cahier des charges de la visite technique en Côte d'Ivoire (ministère des Transports)](https://transports.gouv.ci/sites/default/files/cahier_des_charges_de_la_visite_technique_en_cote_divoire_10012018-1.pdf)
- [Visite technique : « deux visites, soit un contrôle tous les six mois » (Abidjan.net)](https://news.abidjan.net/articles/339507/visite-technique-automobile-les-automobilistes-fuient-abidjan-pour-linterieur)
- [Contrôle technique automobile en Côte d'Ivoire, tarifs et périodicités 2026 (site spécialisé)](https://erooamba.com/posts/controle-technique-automobile-cote-ivoire-tarifs-centres-2026)
- [CEDEAO : passage du manifeste des passagers au numérique (Koaci, 2023)](https://www.koaci.com/article/2023/06/12/cote-divoire/politique/cote-divoire-libre-circulation-des-vehicules-de-transport-inter-etats-des-personnes-les-etats-de-la-cedeao-planchent-sur-le-passage-du-manifeste-des-passagers-au-numerique_170012.html)
- [Horaires et tarifs UTB Abidjan–Bouaké : places numérotées, bagages (blog)](https://blog.iambeezy.app/fr/horaires-tarifs-utb-abidjan-bouake-2026/)
- [Transport en Côte d'Ivoire : UTB, principal réseau interurbain (SPF Affaires étrangères, Belgique)](https://diplomatie.belgium.be/fr/pays/cote-divoire/voyager-en-cote-divoire-conseils-aux-voyageurs/transport-en-cote-divoire)
- [Courrier et mandat express : les compagnies de transport dans la danse (Abidjan.net)](https://news.abidjan.net/articles/344679/courrier-et-mandat-express-les-compagnies-de-transport-dans-la-danse)
- [Déclarer un sinistre en Côte d'Ivoire, délais CIMA (blog)](https://blog.iambeezy.app/fr/declarer-sinistre-cote-ivoire-checklist-refus-2026/)
- [ARTCI : traitement des données personnelles soumis à formalité préalable (Cio Mag)](https://cio-mag.com/cote-divoire-artci-le-traitement-des-donnees-personnelles-desormais-soumis-a-une-autorisation-prealable)
- [ARTCI : enquête nationale sur la conformité des traitements (Digital Mag)](https://digitalmag.ci/protection-des-donnees-lartci-lance-une-enquete-nationale-sur-la-conformite-des-traitements-de-donnees-personnelles/?amp=1)
- [Loi n° 2013-450 relative à la protection des données à caractère personnel (NATLEX)](https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=104182)

## 8. Avancement

### 8.1 Corroboration de l'analyse par le code (2 novembre, soir)

Chaque constat « Aujourd'hui (vérifié) » des §3 et §4 a été relu dans le code : modèles (`core`, `reseau`, `billetterie`,
`maintenance`, `personnel_roulant`, `colis`, `supports`, `rh`, `finance`, `configuration`), routes d'authentification et durée
des jetons (`SIMPLE_JWT` : accès 30 min, renouvellement 1 jour, sans rotation ni liste de révocation), réglages communs
(`settings.py`, `dashboard/ponctualite.py`, `billetterie/planning.py`), écrans (`frontend/src`) et mobile (`mobile/lib`).
L'analyse est confirmée, avec deux précisions apportées au texte :
- l'**API** sait déjà créer gares, lignes, véhicules et pièces pour les rôles autorisés : ce sont les **écrans** qui manquent ;
- le stock d'une pièce peut remonter par une correction directe de `quantite_stock` par l'API (tracée au journal d'audit,
  sans écran) ; il n'y a toujours **aucune entrée en stock tracée** (P-05).

Le lot P1 est découpé en cinq sous-lots soumis un par un : **P1a** accès aux comptes, **P1b** personnel et comptes, **P1c** ma
compagnie et réseau, **P1d** pièces et stock, **P1e** préférences personnelles. Choix du propriétaire : **P1c d'abord**. Déjà
tranché pour P1a : plafond de session par défaut « jusqu'à déconnexion » (sans case cochée, 1 jour comme aujourd'hui ; le PDG
peut abaisser, un supérieur réduire pour un poste) ; code court mobile facultatif, exigible par la compagnie.

### 8.2 P1c — Ma compagnie et réseau (fait)

Rien n'est retiré et tout est facultatif : une compagnie qui ne remplit rien fonctionne exactement comme avant (testé).

| Point | Ce qui est ajouté |
|---|---|
| P-01 Ma compagnie | Fiche (PDG) : raison sociale, sigle, ville du siège, date de création, adresse, téléphone du service client, courriel, RCCM, compte contribuable, n° et échéance de l'autorisation d'exercer (rappel à l'écran, jamais imposé), **logo** (PNG ou JPEG, 1 Mo, contrôlé comme toute pièce jointe, jamais servi par un lien public). Tous les membres lisent la fiche de **leur** compagnie ; les objets métier gardent la compagnie en abrégé (la fiche n'est servie que par `/api/compagnie/`) |
| P-02 Gares | Écran **Gares et quais** (PDG, secrétaire général, directeur des opérations) : créer, renseigner adresse, téléphone, horaires, position sur la carte, **désigner le chef** (annuaire des chefs de gare réservé à la direction ; un chef ne dirige qu'une gare, refus qui dit laquelle) ; **quais** déclarés, fermés ou rouverts, retirés. Le chef de gare tient la fiche et les quais de **sa** gare depuis son tableau de bord |
| P-03 Lignes | Écran **Lignes et tarifs** (PDG, SG, directeur des opérations, chef de ligne) : créer une ligne (nom proposé à partir du trajet), fixer son tarif unique (vide = prix saisi à la vente, comme avant), distance et durée prévue. Les escales et tarifs par tronçon restent pour P3 |
| P-04 Véhicules | Écran **Véhicules** (PDG, SG, directeur des opérations, directeur technique, chef d'atelier) : ajouter un véhicule (avec son kilométrage d'entrée), marque, modèle, année de mise en circulation (âge affiché), classe (standard, climatisé, VIP, ou non précisée), n° de carte grise, carte de transport et son échéance (rappel à l'écran) |
| Navigation | Menu **Paramètres** dans la barre du haut, qui accueillera aussi P1a, P1b, P1d, P1e et P2 ; les liens existants ne bougent pas |

Volontairement **non fait** par les écrans (l'API reste telle qu'elle était) : supprimer une gare, une ligne ou un véhicule
(départs, caisses, dépenses et budgets y sont rattachés), changer le statut d'un véhicule (il suit checklists, blocages QHSE
et atelier : un écran ne doit pas lever un blocage par mégarde), changer la gare d'attache (arbitrage existant).

**Vérification** :
- serveur : 52 tests nouveaux (`core/tests/test_compagnie.py`, `reseau/tests/test_fiches_reseau.py`) : défaut inchangé, réglage
  appliqué, droits par rôle, autre compagnie intacte, journal d'audit, fichiers refusés (PDF, exécutable renommé, GIF, trop
  lourd) ; suites touchées (réseau, core, colis, audit, configuration) : 631 réussis ; matrice des rôles et contrat pages ↔ API :
  2 247 réussis (le contrat couvre les nouvelles pages, rôle par rôle) ; **suite complète : 4 821 réussis, 1 ignoré,
  aucun échec** (hors sondes temporaires `zz_probe`) ;
- cloisonnement : la sonde qui interroge toutes les routes en lecture (155 routes, 9 216 requêtes, un compte de chaque rôle
  d'Express Savane contre les données de STC, quais et fiches compris) ne relève **aucune fuite sur les nouvelles routes** ; ses
  4 signalements sont ceux d'avant P1c, à l'identique ;
- site : 44 tests unitaires réussis (dont l'état d'une échéance et l'écriture des durées) ; parcours de bout en bout dans
  Chrome contre une vraie API (« paramètres » : PDG, directeur des opérations, chef de ligne, directeur technique, chef de gare),
  réussi sans aucune erreur ni réponse 4xx/5xx ; « smoke » des 20 postes réussi avec la nouvelle fiche du chef de gare ;
- migrations : `core 0004_fiche_compagnie`, `reseau 0008_fiches_gares_lignes_vehicules_quais` (ajouts seuls ; à appliquer sur
  la base de développement par `manage.py migrate`, non faite ici).

### 8.3 Points relevés en passant, laissés tels quels (à décider)

| # | Constat (comportement existant de l'API) | Proposition |
|---|---|---|
| O-01 | Deux gares d'une même compagnie peuvent porter le même nom (rencontré en essai : la démo a déjà une « Gare Yamoussoukro ») | Refuser un doublon de nom dans la compagnie, ou le signaler seulement |
| O-02 | Réduire le nombre de places d'un véhicule ne regarde pas les billets déjà vendus sur ses départs à venir | L'écran prévient déjà ; refuser côté serveur sous le maximum vendu, ou laisser |
| O-03 | Le chef de gare peut, par l'API, créer une gare ou changer le chef de sa propre gare (l'écran ne le lui propose pas) | Règle du règlement intérieur, défaut : comportement actuel |
| O-04 | Supprimer une ligne sans départ par l'API efface ses budgets carburant et l'historique de ses fermetures (`on_delete=CASCADE`) ; ses départs, eux, l'empêchent (409) | Protéger budgets et historique comme les départs |
| O-05 | `/api/companies/<id>/` répond 403 pour l'identifiant d'une autre compagnie et 404 pour un identifiant inexistant : cela révèle qu'une compagnie existe (relevé par la sonde, antérieur à P1c) | Répondre 404 dans les deux cas |

### 8.4 P1a, P1b, P1d, P1e — accès, personnel, pièces, préférences (faits le 3 novembre)

Demande du propriétaire : « construis les écrans, le choix du code te revient ». Les quatre sous-lots restants de P1 sont
écrits ; rien n'est retiré, et une compagnie qui ne règle rien fonctionne comme avant (testé à chaque fois).

| Sous-lot | Ce qui est ajouté |
|---|---|
| **P1a Accès aux comptes** (P-08) | Case **« Rester connecté »** à la connexion, sur le site et le mobile (7 jours, 30 jours, jusqu'à la déconnexion ; décochée : 1 jour comme avant). **Plafond** fixé par le PDG dans le cadre de la compagnie (défaut : jusqu'à la déconnexion), réductible par le supérieur pour un poste (un guichet partagé) ; abaissé, il ferme au renouvellement suivant les sessions ouvertes depuis plus longtemps. **Mes paramètres** (tous, l'opérateur de la plateforme compris) : changer son mot de passe (l'actuel est exigé, essais limités, règles de robustesse du serveur, messages en français), voir la durée de sa session, **déconnecter ses autres appareils**. Changer son mot de passe ferme toutes les autres sessions, jetons d'accès et carte en temps réel compris (version de session du compte). **Code court** sur le mobile (4 à 6 chiffres, empreinte salée dans le coffre du téléphone, jamais envoyé au serveur) : demandé à la reprise d'une session et après 5 minutes en arrière-plan, 5 erreurs = retour au mot de passe ; facultatif, **exigible par la compagnie** (case du cadre, défaut non) |
| **P1b Personnel et comptes** (P-06) | Écran **Personnel et comptes** : créer un compte (prénom, nom, identifiant proposé, poste, téléphone, matricule, courriel ; gare pour un guichetier ou un bagagiste ; date d'embauche, qui ouvre le dossier agent), modifier sa fiche, **réinitialiser un mot de passe**. Le compte reçoit un **mot de passe provisoire**, montré une seule fois à celui qui l'a créé ; tant que l'agent ne l'a pas remplacé, le serveur lui refuse tout le reste (site et mobile le conduisent à l'écran du mot de passe). Le PDG gère les comptes ; le **DRH aussi si le règlement intérieur le lui permet** (nouvelle règle `drh_gere_les_comptes`, **non permise par défaut** pour garder le comportement d'avant, que le PDG coche dans le cadre de la compagnie). Suspendre un compte reste un pouvoir du PDG (page Pilotage). Garde-fous : identifiant unique sur la plateforme sans dire à qui il appartient, matricule unique dans la compagnie, personne ne change son propre poste, un changement de poste ferme les sessions de l'agent et est refusé pour un chef qui dirige une gare ou un agent d'une équipe de gare ; le PDG est prévenu de ce que fait le DRH, et inversement |
| **P1d Pièces et stock** (P-05) | Écran **Pièces et stock** (magasinier, chef d'atelier, directeur technique) : catalogue avec prix unitaire, fournisseur habituel, emplacement et **valeur du stock** ; **réception** tracée (quantité, prix, fournisseur, n° de bon) qui fait monter le stock, le prix devenant le **coût moyen pondéré** ; **inventaire** : le stock prend la quantité comptée, l'écart est gardé avec son **motif obligatoire**, un manque prévient le directeur technique ; **historique** d'une pièce (réceptions, sorties, inventaires). Réceptions et inventaires ne se modifient ni ne se suppriment. La correction directe du stock par l'API reste possible (extension d'usage, tracée au journal) |
| **P1e Préférences personnelles** (P-09) | Dans **Mes paramètres** : mode vocal (« comme réglé par mon supérieur », oui, non), un **son** et une **notification du navigateur** pour une alerte critique quand l'onglet est en arrière-plan. Le réglage par le supérieur reste ; le choix de l'agent l'emporte **sauf si le supérieur l'impose** (nouvelle case « Imposer ce mode vocal » dans la configuration du poste ou de l'agent). Sur le mobile, le mode vocal préféré **démarre la dictée de lui-même** (vente de ticket au choix du départ, checklist à l'ouverture), « Annuler » la coupe. La langue d'affichage n'est pas proposée : l'application n'a pas encore de traduction, un choix sans effet aurait trompé |
| Navigation | Le menu **Paramètres** s'ouvre maintenant à tous (au moins « Mes paramètres ») ; il gagne « Personnel et comptes » et « Pièces et stock » pour les postes concernés |

**Vérification** :
- serveur : 125 tests nouveaux (`core/tests/test_sessions.py`, `test_personnel.py`, `maintenance/tests/test_receptions_inventaires.py`, `configuration/tests/test_preferences.py`, deux tests de la carte en temps réel) : défaut inchangé, réglage appliqué, droits par rôle, autre compagnie intacte, journal d'audit ; trois tests existants complétés parce qu'ils énuméraient les règles du règlement intérieur ou le contenu exact d'une réponse ; **suite complète : 4 996 réussis, 1 ignoré, aucun échec** (puis `core`, `audit` et la matrice de conformité relancés après le dernier ajout, la « dernière connexion » : 2 235 réussis)
- page ↔ API et matrice des rôles : 2 298 réussis (les nouvelles pages vérifiées rôle par rôle ; le DRH sur « Personnel et comptes » est vérifié règle permise, puisque la page affiche sinon le refus) ; la route du règlement intérieur annonce désormais l'écriture seulement à ceux qui peuvent régler
- cloisonnement : 160 routes, 10 242 requêtes, un compte de chaque rôle d'Express Savane contre les données de STC : **aucune fuite sur les nouvelles routes** ; les 4 signalements sont ceux d'avant P1, à l'identique
- site : 49 tests unitaires réussis (lecture d'un jeton, identifiant proposé, alertes critiques nouvelles) ; analyse sans nouvelle remarque ; compilation de production réussie
- mobile : 241 tests réussis, dont 32 nouveaux (code court : empreinte, erreurs, 5 minutes, autre agent, exigé hors ligne ; rester connecté ; mot de passe et mot de passe provisoire ; mode vocal) ; `flutter analyze` sans remarque ; aucune bibliothèque téléchargée (`crypto` était déjà là)
- parcours de bout en bout dans Chrome contre une vraie API : 8 parcours réussis, sans erreur ni réponse 4xx/5xx inattendue : « smoke » des 20 postes, configuration, juridique, paramètres, **accès** (plafond de 7 jours, mot de passe changé, autres appareils déconnectés), **personnel** (création, première connexion, réinitialisation, DRH refusé puis permis), **pièces** (réception au coût moyen, inventaire avec écart, directeur technique prévenu), **préférences** (mode vocal et son, mode vocal imposé). Deux défauts trouvés par ces parcours ont été corrigés : un sélecteur ambigu dans le script d'essai, et des cases à cocher qui ne montraient le choix qu'après la réponse du serveur (le choix s'affiche maintenant tout de suite, et revient en arrière si le serveur refuse)
- migrations (ajouts seuls, à appliquer sur la base de développement par `manage.py migrate`) : `core 0005_acces_aux_comptes`,
  `core 0006_fiche_des_comptes`, `configuration 0003_acces_aux_comptes`, `configuration 0004_preferences_personnelles`,
  `maintenance 0005_receptions_et_inventaires`.

### 8.5 Nouveaux points relevés (à décider)

| # | Constat | Proposition |
|---|---|---|
| O-06 | La préférence « mode vocal » que le supérieur réglait depuis la configuration n'était lue ni par le site ni par le mobile : elle n'avait aucun effet. Depuis P1e, préférée, elle démarre la dictée du mobile (aucune donnée de démonstration ne la règle) | Garder ; dire aux supérieurs ce qu'elle fait désormais |
| O-07 | La gestion des comptes par le DRH est prête mais coupée par défaut (règle du règlement intérieur) | Le PDG la coche s'il le souhaite ; ou passer le défaut à « permis » si vous le décidez |
| O-08 | La langue d'affichage (P-09) demande de traduire l'application | À traiter avec un besoin réel (anglais pour les lignes inter-États, par exemple) |
| O-09 | Le bagagiste est invité à demander un nouveau code de retrait à son chef de gare (colis verrouillé), mais aucun écran ne permet au chef de gare de le renvoyer ni d'annuler un enregistrement : seule l'API le fait | **Fait** (§8.8) : « Colis de la gare » |
| O-10 | Clôturer la réparation d'un car **bloqué par le QHSE** le remet en service sans que le QHSE ait levé le blocage | **Fait** (§8.8) : règle `reparation_leve_le_blocage_qhse`, permise par défaut (comme avant) |
| O-11 | Cinq gestes réglés par le règlement intérieur n'ont aucun écran (supprimer sa feuille de route ou un incident, confier ou supprimer un ordre de réparation, corriger une sortie de pièce) : l'API seule les permet | **Fait** (§8.8) : boutons affichés seulement si le règlement les permet |

### 8.6 Suite proposée

**P2a — Réglages métier**, puis **P2b — Organisation** (§6, découpage du 3 novembre) : P2a règle les seuils et tolérances
aujourd'hui communs à la plateforme, la checklist (extincteur compris, aptitude facultative), la réglementation à trois positions et
le bouton « appliquer les pratiques du secteur » ; P2b construit les décisions d'organisation OR-01 à OR-04, les délégations du PDG
et, en dernier, le rattachement des supports au secrétaire général (§8.10). Les écrans du règlement intérieur et du lien
billetterie sont faits (§8.8). Aucun lot ne commence sans votre accord.

### 8.7 Guide d'utilisation par pôle (fait le 3 novembre)

Demande du propriétaire : « à chaque pôle, créer un catalogue qui guide à l'usage du pôle » ; précisé : un guide par poste,
rangé par pôle, lisible par tous. Puis : « revérifie la logique de la pratique, puis coordonne les éléments ».

| Élément | Ce qui est fait |
|---|---|
| Contenu | Une fiche par poste (18) rangée sous les 5 pôles, plus une section « pour tous les postes » et la fiche de l'opérateur de la plateforme (montrée à lui seul). Chaque fiche : mission, écrans, **gestes pas à pas rangés par moment de la journée** (pour démarrer, début de journée, au fil de la journée, fin de journée, au besoin), postes **avec qui chaque geste se coordonne**, à qui s'adresser, bon à savoir. Les noms des boutons et rubriques sont ceux des écrans |
| Ce qui dépend de la compagnie | Calculé pour le lecteur, jamais écrit en dur : qui règle ce poste et quels postes il règle (configuration hiérarchique), ce que **le règlement intérieur de sa compagnie** permet au poste (« permis » / « non permis », et qui en décide) |
| Site | Lien « Guide » dans la barre du haut, pour tous : onglets par pôle puis par poste, la fiche du lecteur ouverte d'abord ; liens vers les écrans qu'il peut ouvrir ; « Avec » ouvre la fiche du poste lié ; « Imprimer cette fiche » |
| Mobile | Icône livre de l'accueil : même guide, pôle et poste au choix, « Avec », lisible hors ligne une fois lu |
| Logique revérifiée | Chaque « qui est prévenu » confronté aux alertes du serveur ; une dizaine de mentions corrigées (ex. un incident prévient toujours le chef de ligne ; une infraction grave, aussi le PDG ; la réparation clôturée libère le car). Les gestes sans écran retirés des pas à pas (O-11) ; deux écarts métier relevés (O-09, O-10), non corrigés |
| Coordination verrouillée par les tests | Tout passage de relais est décrit **des deux côtés** (si la fiche A cite B, B cite A) ; les gestes suivent l'ordre de la journée ; chaque fiche cite **toutes** les pages que le site ouvre à son poste et **seulement** celles-là ; seuls les postes à écran mobile dédié citent le téléphone |

**Vérification** :
- serveur : 52 tests nouveaux (31 sur le guide : lecture par tous, contenu, ordre de la journée, réciprocité des passages de
  relais, règlement de la compagnie du lecteur et d'elle seule ; 21 de concordance avec les pages du site) ; contrat page ↔ API
  rejoué avec la page « Guide » ; suite complète : 5 113 réussis, 1 ignoré, 2 échecs intermittents **étrangers au guide**
  (badge « caisse juste » et ordre de la file de l'atelier : deux enregistrements dans le même palier de l'horloge de Windows,
  ~15 ms), qui passent 3 fois sur 3 relancés ;
- site : 53 tests unitaires (4 nouveaux), lint sans nouvel avertissement, compilation ;
- mobile : 246 tests (5 nouveaux : fiche du lecteur d'abord, « Avec », autre pôle, relecture hors ligne, sans réseau ni guide lu),
  analyse statique propre ;
- parcours dans Chrome contre une vraie API : « guide » (fiche du guichetier, « Avec » vers le chef de gare, autre pôle, règlement
  du DRH avant et après le choix du PDG) et connexion des 20 postes avec le nouveau lien : réussis.

Aucune migration. Les deux tests fragiles se corrigent en départageant les ex aequo (par numéro d'enregistrement) : à faire
si vous le souhaitez.

### 8.8 Les boutons manquants de l'application (faits le 3 novembre)

Demande du propriétaire : « je valide tes propositions […] concentre-toi sur tous les boutons nécessaires à toute l'application,
construis-les et vérifie leur efficacité ». Méthode : chaque action d'écriture de l'API confrontée aux appels du site et du
mobile ; 54 n'en avaient aucun. Chacune a été classée. Les chiffres de ce premier relevé sont réconciliés plus bas avec le test
d'inventaire, qui fait désormais référence.

| Écran | Boutons ajoutés |
|---|---|
| Tableau de bord du **chef de gare** | « Colis de la gare » : **Renvoyer le code** (colis verrouillé, SMS perdu), **Annuler l'enregistrement** (motif obligatoire, frais à rendre), **Marquer arrivé** (colis resté « chargé » alors que le car est arrivé) — O-09. « Importer les ventes du logiciel de billetterie » (départs de sa gare) |
| **Règlement intérieur** (nouvelle page : PDG, directeurs technique et d'exploitation) | Une case par règle, chacun ne voyant que celles qu'il règle ; nouvelle règle **O-10** « la réparation terminée remet en service un car bloqué par le QHSE » (permise par défaut ; sinon le car attend la levée du QHSE, qui est prévenu) |
| **Billetterie** (nouvelle page : PDG, directeur d'exploitation) | Mode intégré / externe / mixte, **Créer une clé** (montrée une fois), **Révoquer**, **Importer les ventes** avec compte rendu ligne à ligne |
| **Chauffeur** | **Supprimer cette feuille de route** (avant le départ), « Mes incidents déclarés » et **Supprimer** — seulement si le règlement le permet (O-11) |
| **Mécanicien** | **Confier** son intervention à un collègue (liste des intervenants de l'atelier ; lui et le chef d'atelier sont prévenus), **Supprimer** un ordre — selon le règlement (O-11) |
| **Pièces et stock** | Sur chaque sortie : **Corriger** la quantité, **Annuler la sortie** — selon le règlement (O-11) ; **Supprimer la pièce** |
| **Gares, Lignes, Véhicules** | **Supprimer** depuis la fiche (refusé avec un message clair si l'élément sert déjà) |
| **Entretien préventif**, **Juridique**, **Comptabilité** | **Retirer** un plan d'entretien ; **Supprimer** une assurance, un sinistre sans pièce jointe ; **Retirer** un fournisseur sans facture |
| **QHSE** et **Juridique** (onglet « Tutelle ») | « Échanges avec la tutelle » : **Marquer traité**, **Rattraper les flux automatiques** |

**Correction du relevé (3 novembre, plus tard)** : le script du relevé écartait par erreur toute route contenant « format »
(pour ignorer les variantes de format de réponse), donc aussi celles de la **formation**. Relancé corrigé, il trouve cinq actions
de plus sans écran : le **parcours de formation par poste** (démarrer un parcours, terminer une étape : aucun écran), corriger ou
supprimer une **session de formation** enregistrée, modifier une **obligation de formation** (O-13, placées au lot P9, côté RH).
Le relevé est désormais un test (`role_coverage_tests/test_inventaire_boutons.py`) : chaque action d'écriture de l'API est appelée
par un écran du site ou du mobile, ou figure dans une **liste explicite d'exclusions, chacune avec son motif** ; plus aucun filtre
de texte.

**Décompte de référence (le test `test_inventaire_boutons.py`)**

| Nombre | Ce qu'il compte |
|---|---|
| **181** | Actions d'écriture de l'API : couples (méthode, chemin) sous `/api/`, en POST, PATCH (PUT compris quand il double PATCH) ou DELETE, que la vue accepte vraiment |
| **29** | Exclusions, chacune avec son motif : 24 laissées sans bouton à dessein, plus les 5 de la formation (O-13, lot P9) |
| 152 | Actions appelées par au moins un écran du site ou du mobile (181 − 29) |

**D'où venait « 414 »** : c'était le nombre de lignes du premier script, qui comptait chaque couple (méthode, motif d'URL) du
routage. Relu sans le filtre fautif, ce nombre est de **433** ; on passe de 433 à 181 en retirant :

| Étape | Retirées | Reste |
|---|---|---|
| Couples (méthode, motif d'URL) du routage | | 433 |
| Variantes « .json » d'une même route (format de réponse) | 204 | 229 |
| Méthodes annoncées par le routeur mais refusées par la vue (modifier ou supprimer un blocage de sécurité, un congé ; supprimer une doléance) | 7 | 222 |
| PUT qui double PATCH sur la même route (une seule action, « modifier ») | 41 | **181** |

Le premier script, lui, avait écarté par erreur les 19 couples de la formation (433 − 19 = 414) et normalisé à sa façon les
variantes et les doublons.

**D'où venaient « 54 » et « 14 »** : les 54 actions sans appel du premier relevé se répartissent ainsi :

| Devenir | Nombre |
|---|---|
| Bouton construit dans ce lot | 22 |
| Déjà appelées, mal lues par le premier script (renouvellement du jeton, réservation hors ligne en POST et en DELETE) | 3 |
| Annoncées par le routeur mais refusées par la vue : pas de vraie action | 5 |
| Laissées sans bouton à dessein, avec motif | **24** |

Le compte rendu annonçait « 14 actions volontairement sans bouton » : c'était faux, il y en avait **24**. Le paragraphe
ci-dessous décrivait bien les catégories, mais ne comptait pas les modifications couvertes par une suppression ou une annulation
(dépenses, factures, rendez-vous, contrats, évaluations, mesures, fournisseurs, pièces jointes, plans d'entretien, dossiers
d'archives) ni la suppression d'un billet. Avec les 5 de la formation, oubliées par le premier relevé, on retrouve les 29
exclusions du test.

**Constat corrigé en route (O-12)** : corriger ou annuler une sortie de pièce ne touchait pas au stock (annuler une sortie de
2 filtres laissait le stock diminué). La correction reporte désormais l'écart sur le stock (refusée si le stock ne la couvre
pas ; une sortie ne change ni de pièce ni d'ordre), l'annulation remet les pièces en stock. Sans cela le bouton aurait faussé le
stock.

**Volontairement sans bouton** (24 actions, liste exacte et motifs dans `EXCLUSIONS` du test) : ce qu'envoie un logiciel externe (ventes et annulations du logiciel de billetterie,
flux entrants de la tutelle), le ticket vendu (verrouillé par conception, on l'annule), l'historique de sécurité (blocages,
checklists : on lève, on ne modifie pas), ce que l'application fait déjà autrement (feuille de route créée par la planification,
départ créé par « Planifier », congé annulé plutôt que supprimé, réservation hors ligne et renouvellement du jeton gérés par le
mobile et le site), les dossiers et doléances (on les clôt, on ne les efface pas). Les modifications de dépenses, factures, rendez-vous,
contrats, évaluations et offres restent couvertes par leur suppression, leur annulation ou leur statut.

**Fiabilisation** : les deux tests intermittents du §8.7 départagent désormais les ex aequo (file de l'atelier : premier
enregistré d'abord ; badge « caisse juste » : fenêtre ouverte jusqu'à maintenant).

**Le guide** (§8.7) cite chaque nouvel écran et chaque nouveau geste ; sa vérification de réciprocité a d'ailleurs signalé un
oubli corrigé (le directeur technique règle les gestes du mécanicien).

**Vérification** :
- serveur : nouveaux tests (atelier : stock suivi par la correction et l'annulation d'une sortie, refus si le stock ne couvre
  pas, ordre confié et collègue prévenu, liste des intervenants, règle O-10 dans les deux sens et cloisonnée ; colis filtrés par
  gare, code renvoyé, enregistrement annulé ; règlement donné à chaque poste) ; les applications touchées : 4 242 réussis ;
  contrat page ↔ API : 353 réussis (chaque bouton est permis à chaque poste qui le voit) ;
- site : 53 tests unitaires, lint sans nouvel avertissement, compilation ;
- parcours dans Chrome contre une vraie API : les 20 parcours existants réussis ; les 2 nouveaux (« boutons terrain »,
  « boutons direction »), qui cliquent chaque bouton et vérifient son effet côté serveur (stock revenu, code renvoyé, règle
  enregistrée, vente importée puis non dupliquée, gare supprimée...), réussis après trois corrections révélées par eux :
  choix du mode de billetterie affiché sans attendre le serveur, confirmation gardée après la suppression du dernier incident et
  après l'annulation d'une sortie ;
- mobile : inchangé dans ce lot.

Aucune migration (la nouvelle règle vit dans le règlement intérieur existant).

### 8.9 Charte graphique (faite le 3 novembre)

Demandes du propriétaire : « que le style des entêtes soit un peu plus esthétique », puis « orange, blanc, vert comme couleurs de
référence, et à chaque pôle une couleur pour le différencier des autres ».

- **Couleurs de référence** : vert (actions, liens, barre du haut en dégradé vert), orange (logo, accents, cars sur la carte du
  réseau), blanc (fond des cartes). Les couleurs de sens (rouge d'alerte, vert « à jour », orange « attention ») restent.
- **Une couleur par pôle** : Direction Générale violet, Exploitation & Réseau bleu, Personnel roulant framboise, Technique &
  Maintenance gris acier, Fonctions supports bleu canard (l'opérateur de la plateforme : anthracite). Elle marque le liseré sous la
  barre du haut, l'étiquette du pôle et l'avatar de l'agent, le souligné du titre de page, la barre des titres de rubrique et
  l'onglet actif ; dans le guide, chaque pôle a ses onglets et sa fiche à sa couleur. Sur le mobile : même thème vert et orange,
  liseré du pôle sous la barre de l'accueil.
- **Entêtes** : barre du haut en deux étages (marque et compte, puis navigation), page ouverte surlignée, menu « Paramètres » en
  liste, titre de page en tête du contenu, en-têtes de tableaux en petites majuscules espacées.
- **Cohérence verrouillée** : le rangement des postes par pôle du site (`POLE_DU_ROLE`) et du mobile est confronté à celui du
  serveur (`communication/poles.py`) par les tests.

**Vérification** : site 54 tests unitaires (1 nouveau), lint, compilation ; mobile 249 tests (3 nouveaux : couleur de chaque poste,
liseré du guichetier et du chauffeur), analyse propre ; serveur : concordance des pôles (test nouveau) ; captures contrôlées pour
les cinq pôles et le guide. Les parcours Chrome restent à rejouer avec la nouvelle charte (les serveurs laissés pour la
consultation occupent leurs ports).

### 8.10 Décisions d'organisation (3 novembre)

Décidées par le propriétaire à partir de l'analyse des pôles et de la hiérarchie
([ANALYSE_POLES_HIERARCHIE_2026-11-03.md](ANALYSE_POLES_HIERARCHIE_2026-11-03.md)). Rien n'est encore construit ; chaque décision
est placée au plan du §6 :

- **P2b — Organisation** (P2 est découpé en P2a, réglages métier, et P2b, organisation) : OR-01, OR-02, OR-03, OR-04, les
  délégations du PDG, et **en dernier** le rattachement des Fonctions supports au secrétaire général. Une fois P2b fait, le bouton
  « appliquer les pratiques du secteur » (P2a) inclut OR-04 ;
- **P6** : OR-06, fusionné avec R-06 ;
- **P9** : la synthèse du jour et les alertes du PDG ; OR-05 ; le parcours de formation (O-13), côté RH.

Placements confirmés par le propriétaire le 3 novembre. Aucun lot ne commence sans son accord.

| # | Décision du 3 novembre |
|---|---|
| **OR-01** | Les notes de service adressées au pôle Personnel roulant partent aussi en copie à l'encadrement (chef de ligne, directeur d'exploitation), au choix de la compagnie. Par défaut, rien ne change. |
| **OR-02** | L'avis du supérieur direct sur un congé se règle en trois positions : ignorer (défaut), demander ou exiger. En position « demander », le DRH peut décider seul passé un délai de 48 h, réglable. |
| **OR-03** | La règle O-10 (`reparation_leve_le_blocage_qhse`) est réglée par accord du directeur technique et du QHSE : l'un propose, l'autre confirme, et la règle ne change qu'à la confirmation. Le PDG est informé de chaque changement et peut reprendre la main. |
| **OR-04** | Alertes croisées entre le directeur d'exploitation et le directeur technique (disponibilité de la flotte, pénurie de cars). Coupées par défaut, activables par la compagnie, incluses dans « appliquer les pratiques du secteur ». |
| **OR-05** | Un dépassement du budget carburant prévient aussi le directeur d'exploitation et le chef de ligne de la ligne concernée. |
| **OR-06** | Fusionné avec R-06 et la ligne « Permis et visite médicale » du §5 de l'analyse métier : le chef de ligne est prévenu de l'expiration du permis ou de la visite médicale ; la planification peut ignorer (défaut), alerter ou bloquer. |
| **OR-07** | Alléger le travail du PDG par trois mesures. **Délégations** : depuis le règlement intérieur, le PDG confie un pouvoir à un poste ; il est informé de son usage et peut le reprendre. **Alertes** : le PDG ne reçoit en direct que les alertes critiques (la liste de ce qui est critique est réglable par la compagnie) ; le reste va dans une **synthèse du jour**, livrée en deux temps — version 1, sans IA : les alertes non critiques de la veille classées par pôle et par gravité (nombre et trois plus marquantes), ce qui a été traité par délégation (qui, quoi), ce qui reste ouvert et depuis quand, à une heure d'envoi réglable ; version 2 : l'IA d'analyse du pôle du PDG, quand elle existera. **Rattachement au secrétaire général** : en option, la compagnie rattache les Fonctions supports au secrétaire général et non plus au PDG (défaut : au PDG, comme aujourd'hui) ; activée, l'option lui fait passer la configuration hiérarchique de ces postes. À tester avec l'option activée et désactivée : la configuration hiérarchique, la matrice des rôles et le guide. |
