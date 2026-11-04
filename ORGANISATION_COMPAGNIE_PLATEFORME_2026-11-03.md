# L'organisation d'une compagnie sur la plateforme — 3 novembre 2026

Ce rapport décrit comment la plateforme organise une compagnie de transport interurbain : ce qui la constitue, qui y fait quoi,
ce qu'elle règle à sa main, comment se déroule une journée, comment elle est pilotée et contrôlée, et comment on la met en
service. Il est tiré du code de l'application tel qu'il est aujourd'hui. Les liens entre pôles et la hiérarchie sont détaillés
dans [ANALYSE_POLES_HIERARCHIE_2026-11-03.md](ANALYSE_POLES_HIERARCHIE_2026-11-03.md).

## En bref

- Une plateforme, **plusieurs compagnies**, chacune **strictement cloisonnée** : aucun membre d'une compagnie ne voit l'activité
  d'une autre ; seul l'opérateur de la plateforme les voit toutes. Ce cloisonnement n'est pas réglable.
- Une compagnie, c'est **son réseau** (gares, quais, lignes, véhicules), **son personnel** (18 postes en 5 pôles, une ligne
  hiérarchique), **son activité** (départs, billets, colis, caisses, atelier, stock) et **ses fonctions supports** (finances,
  ressources humaines, juridique).
- Elle **démarre sans rien régler** : chaque réglage part d'un défaut qui reproduit le fonctionnement d'origine. Elle ajuste
  ensuite son **cadre**, son **règlement intérieur**, la **configuration** de chaque poste et son **mode de billetterie**.
- Chaque agent a **son tableau de bord**, ses alertes, son guide ; les postes de terrain ont l'**application mobile** (vente et
  feuille de route **hors ligne**, dictée vocale).
- Tout est **tracé** au journal d'audit, et les alertes relient les pôles entre eux au moment où il faut agir.

## 1. La plateforme et ses compagnies

| Élément | Comment c'est organisé |
|---|---|
| **Compagnies** | Plusieurs sur la même plateforme. Toute donnée appartient à une compagnie ; un accès à la donnée d'une autre est refusé comme si elle n'existait pas. Vérifié par une sonde qui rejoue chaque route pour chaque poste. |
| **Opérateur de la plateforme** | Hors des compagnies : il voit l'activité de toutes (tableau de bord « Plateforme », journal d'audit de toutes), n'en dirige aucune. |
| **Entrée d'une compagnie** | L'opérateur la crée, avec le compte de son PDG, dans l'**administration Django** (pas encore d'écran dédié : voir §9). Ensuite, la compagnie se tient seule, sans l'administration. |
| **Identité** | Raison sociale, sigle, siège, coordonnées, service client, RCCM, compte contribuable, autorisation de transport et son échéance (rappelée), mentions légales, logo. Tenue par le PDG dans « Ma compagnie ». |

## 2. Ce qui constitue une compagnie

| Domaine | Ce que la compagnie y tient | Qui le tient |
|---|---|---|
| **Réseau** | Gares (adresse, horaires, chef, coordonnées sur la carte) et leurs quais ; lignes (deux gares, tarif ou prix libre, distance, durée prévue, ouverte ou fermée) ; véhicules (places, classe, papiers, carte de transport, gare d'attache, kilométrage, statut) | PDG, secrétaire général, directeur d'exploitation ; chef de ligne (lignes) ; technique (véhicules) ; chef de gare (sa gare) |
| **Personnel** | Comptes (poste, gare d'affectation, téléphone, matricule), mot de passe provisoire à la création, dossier agent (contrats, évaluations, discipline, formations) | PDG (le DRH si le règlement le permet) ; DRH pour les dossiers |
| **Exploitation** | Départs planifiés (ligne, heure, car et chauffeur libres), billets (guichet, mobile hors ligne, logiciel de la compagnie), colis et bagages (code de retrait envoyé au destinataire), caisses du jour et leur clôture | Directeur d'exploitation, chefs de gare et de ligne, guichetiers, bagagistes |
| **Trajets** | Feuille de route, checklist avant-départ, suivi GPS, temps de conduite et relais, incidents, contrôle des billets à bord | Chauffeurs, contrôleur, chef de ligne, QHSE |
| **Atelier et magasin** | Ordres de réparation et leur file, entretien préventif, pièces (prix, coût moyen, emplacement), réceptions, sorties, inventaires, demandes de pièces | Directeur technique, chef d'atelier, mécaniciens, magasinier |
| **Finances** | Recettes (billets, fret), dépenses, budgets carburant par ligne, fournisseurs et factures, trésorerie, rentabilité par ligne et par gare | Directeur financier ; lecture par le PDG et le secrétaire général |
| **Ressources humaines** | Dossiers, congés, formations obligatoires (sécurité routière, permis, visite médicale), recrutement, médiation sociale | DRH ; chaque agent dans « Mon espace » |
| **Juridique** | Assurances de la flotte, sinistres et leurs pièces, conformité réglementaire, litiges sociaux, bibliothèque de modèles de documents, échanges avec la tutelle | Responsable juridique ; QHSE pour la conformité et la tutelle |
| **Direction** | Notes de service, agenda, archives, investissements, pouvoirs d'intervention (geler une ligne, réaffecter, suspendre un compte) | PDG, secrétaire général |

## 3. L'organisation humaine : 5 pôles, 18 postes, une hiérarchie

| Pôle (couleur) | Postes | Rattachement |
|---|---|---|
| **Direction Générale** (violet) | PDG, secrétaire général, QHSE | Le PDG ; le SG et le QHSE relèvent de lui |
| **Exploitation & Réseau** (bleu) | directeur d'exploitation, chef de gare, chef de ligne, guichetier, bagagiste | Directeur d'exploitation → chefs de gare et de ligne → guichetiers et bagagistes (chef de gare) |
| **Personnel roulant** (framboise) | chauffeur principal, chauffeur relais, contrôleur de ligne | Chauffeurs → chef de ligne ; contrôleur → directeur d'exploitation |
| **Technique & Maintenance** (gris acier) | directeur technique, magasinier, chef d'atelier, mécanicien | Directeur technique → magasinier et chef d'atelier → mécaniciens |
| **Fonctions supports** (bleu canard) | DRH, directeur financier, responsable juridique | Chacun relève du PDG |

Chaque poste a **un supérieur direct**, qui règle son poste ; le PDG peut en plus régler n'importe quel poste. Le pôle sert à
adresser (notes, modèles, guide, couleur de l'interface), la hiérarchie à régler et à décider.

## 4. Ce que chaque compagnie règle à sa main

Rien n'est à régler pour démarrer. Chaque réglage est appliqué par le serveur (un bouton caché ne suffit jamais) et tracé.

| Niveau | Qui règle | Ce qui se règle |
|---|---|---|
| **Cadre de la compagnie** | PDG | Plafonds que nul ne dépasse : niveau d'automatisation, niveau de jeu, durée de session la plus longue (« rester connecté »), code court exigé sur le mobile, gestion des comptes confiée au DRH |
| **Règlement intérieur** | PDG (tout) ; directeur technique (atelier, magasin) ; directeur d'exploitation (chauffeurs) | Sept règles : corriger une sortie de pièce, confier ou supprimer un ordre (mécanicien), supprimer sa feuille de route ou un incident (chauffeur), gestion des comptes par le DRH, remise en service d'un car bloqué par le QHSE. Les écrans n'affichent que les gestes permis |
| **Configuration des postes et des agents** | Chaque supérieur pour ses subordonnés directs | Automatisation (manuel, assisté, automatique : la caisse se clôture seule, par exemple), jeu (aucun, sobre, complet), mode vocal (imposable), aisance avec le numérique, durée de session, fonctions retirées (vente, colis, planification, clôture de caisse) |
| **Billetterie** | PDG, directeur d'exploitation | Intégrée (les guichets vendent ici), externe (le logiciel de la compagnie vend seul, la vente au guichet est fermée) ou mixte ; clés du logiciel ; import des ventes (le chef de gare pour sa gare) |
| **Préférences personnelles** | Chaque agent | Mot de passe, appareils connectés, code court mobile, mode vocal (sauf s'il est imposé), son et notification des alertes critiques |

## 5. Une journée de la compagnie

| Moment | Ce qui se passe, et entre qui |
|---|---|
| **Avant le départ** | Le chef de ligne ou le directeur d'exploitation **planifie** le départ : seuls les cars et chauffeurs libres sont proposés ; la feuille de route du chauffeur est créée. Le guichetier **vend** (au guichet, sur le téléphone même sans réseau, ou le logiciel de la compagnie envoie ses ventes). Le bagagiste **enregistre** les colis : le destinataire reçoit son code de retrait. |
| **Au départ** | Le chauffeur fait la **checklist** (dictée possible sur le téléphone) : un défaut de sécurité bloque le car et prévient le QHSE, l'atelier, le chef de ligne et le chef de gare. Le bagagiste **charge** les colis. Le chauffeur **démarre** et active le suivi GPS. |
| **En route** | La direction voit le car sur la **carte en temps réel**. Le temps de conduite est compté ; au-delà du seuil, le conducteur et le chef de ligne sont prévenus et un **relais** est proposé ; celui qui reprend fait la checklist de reprise. Le contrôleur **vérifie les billets** un à un et clôt son contrôle (une infraction grave prévient le PDG, l'exploitation et le QHSE). Un incident prévient le chef de ligne, l'atelier, et selon sa gravité l'exploitation, le QHSE et la gare. |
| **À l'arrivée** | Le chauffeur signale l'arrivée : le car redevient disponible, les colis passent « arrivés », les clients et la gare d'arrivée sont prévenus. Le bagagiste **remet** le colis contre le code (le chef de gare renvoie un code ou annule un enregistrement). |
| **Fin de journée** | Les **caisses** se clôturent (par le guichetier, le chef de gare, ou seules selon le niveau d'automatisation), le chef de gare en est prévenu. Le directeur financier suit les recettes et exporte. |
| **À l'atelier** | Une panne ou un blocage arrive au chef d'atelier, qui ouvre l'**ordre de réparation** ; le mécanicien est prévenu, demande ses pièces au magasinier, clôture avec le temps passé ; le chef de ligne et les gares savent quand le car revient. |
| **En continu** | Le QHSE suit défauts, incidents et conformité ; le DRH les congés (un congé qui touche des départs prévient l'exploitation), les formations et la médiation ; le juridique les assurances et sinistres ; la direction décide des investissements et arbitre. |

## 6. Pilotage et contrôle

| Outil | Ce qu'il apporte |
|---|---|
| **Un tableau de bord par poste** (18, plus celui de la plateforme) | Ce dont le poste a besoin, chiffres du jour en tête, actualisé tout seul |
| **Alertes inter-pôles** (la cloche) | Chaque événement prévient les postes qui doivent agir (blocage, défaut, panne, pénurie, retard, fatigue, stock bas, échéance, caisse, congé, compte...) ; son et notification possibles pour une alerte critique |
| **Journal d'audit** | Qui a fait quoi, quand et d'où ; ne se modifie ni ne se supprime. Lu par la direction et le QHSE |
| **Conformité et tutelle** | Tableau de conformité de la flotte (assurances, obligations réglementaires, blocages) ; flux préparés pour le ministère et les organismes (OSER, AMUGA, OFT) |
| **Jeu** (réglable) | Points, missions du jour, badges et classements pour les postes de terrain ; sobre ou coupé pour la direction et les supports |
| **Guide** | La fiche de chaque poste par pôle : écrans, gestes pas à pas dans l'ordre de la journée, postes avec qui chacun se coordonne, ce que le règlement de la compagnie permet |

## 7. Les outils de l'agent

| Où | Pour qui | Ce qu'il y trouve |
|---|---|---|
| **Site** | Tous les postes | Son tableau de bord ; « Mon espace » (congés, formations, doléance) ; notes de service ; modèles juridiques ; « Mes paramètres » ; le Guide ; selon le poste, les pages de paramètres (compagnie, personnel, règlement, billetterie, gares, lignes, véhicules, pièces) |
| **Application mobile** | Guichetier, chauffeurs | Vente de billets et feuille de route **hors ligne** (envoyées au retour du réseau), checklist avant-départ, dictée vocale, code court pour rouvrir l'application, guide lisible hors ligne |
| | Autres postes de terrain (bagagiste, contrôleur, chef d'atelier) | Un accueil qui annonce leur espace mobile à venir ; ils travaillent sur le site |

## 8. Mettre une compagnie en service

1. **L'opérateur** crée la compagnie et le compte de son PDG (administration Django).
2. **Le PDG** remplit « Ma compagnie » (identité, logo), crée les **gares** et leurs quais, les **lignes** et leurs tarifs, le
   **parc**, puis les **comptes** du personnel (chacun reçoit un mot de passe provisoire qu'il remplace à la première connexion).
3. **Le PDG** fixe, s'il le souhaite, le **cadre** (sessions, code court, gestion des comptes par le DRH), le **règlement
   intérieur** et le **mode de billetterie**. Sinon, les défauts s'appliquent.
4. **Les chefs** composent leur équipe (le chef de gare affecte guichetiers et bagagistes à sa gare) et règlent leurs
   subordonnés (automatisation, mode vocal, fonctions retirées).
5. **Les fonctions supports** complètent : le DRH les dossiers et les formations obligatoires, le directeur financier le solde
   de départ et les budgets carburant, le juridique les assurances et les modèles de documents, le technique les plans
   d'entretien et le catalogue de pièces.
6. **Le terrain** commence : planification, vente, départs. Chacun trouve dans le Guide la fiche de son poste.

## 9. Limites et points d'attention

| Point | Situation |
|---|---|
| Entrée d'une compagnie | Création de la compagnie et de son PDG seulement par l'administration Django : pas d'écran pour l'opérateur |
| Formation par poste | Le **parcours de formation** (démarrer, terminer une étape) existe côté serveur mais **n'a aucun écran** ; corriger une session de formation ou modifier une obligation non plus (O-13, oubli du relevé des boutons) : **placé au lot P9, côté RH** |
| Mobile | Écran dédié pour le guichetier et les chauffeurs seulement |
| Langue | Français seulement |
| Messages aux clients | SMS et WhatsApp en **mode simulation** par défaut (journalisés, non envoyés) tant que le fournisseur n'est pas activé au déploiement |
| Tutelle | Les flux sont préparés et suivis ; aucune liaison réelle avec les systèmes du ministère n'existe encore |
| Organisation | Les sept points relevés par l'analyse des pôles sont **décidés** (OR-01 à OR-07, §10) et placés au plan : lots P2b, P6 et P9 |
| Base de développement | Les nouvelles migrations des lots récents sont à appliquer (`manage.py migrate`) |

## 10. Décisions d'organisation (3 novembre)

Décidées par le propriétaire à partir de l'analyse des pôles ; aucune n'est encore construite. Elles sont placées au plan du §6
de l'analyse métier (voir la dernière colonne).

| # | Décision du 3 novembre | Lot |
|---|---|---|
| **OR-01** | Les notes de service adressées au pôle Personnel roulant partent aussi en copie à l'encadrement (chef de ligne, directeur d'exploitation), au choix de la compagnie. Par défaut, rien ne change. | P2b |
| **OR-02** | L'avis du supérieur direct sur un congé se règle en trois positions : ignorer (défaut), demander ou exiger. En position « demander », le DRH peut décider seul passé un délai de 48 h, réglable. | P2b |
| **OR-03** | La règle O-10 (`reparation_leve_le_blocage_qhse`) est réglée par accord du directeur technique et du QHSE : l'un propose, l'autre confirme, et la règle ne change qu'à la confirmation. Le PDG est informé de chaque changement et peut reprendre la main. | P2b |
| **OR-04** | Alertes croisées entre le directeur d'exploitation et le directeur technique (disponibilité de la flotte, pénurie de cars). Coupées par défaut, activables par la compagnie, incluses dans « appliquer les pratiques du secteur ». | P2b (puis inclus dans le bouton de P2a) |
| **OR-05** | Un dépassement du budget carburant prévient aussi le directeur d'exploitation et le chef de ligne de la ligne concernée. | P9 |
| **OR-06** | Fusionné avec R-06 et la ligne « Permis et visite médicale » du §5 de l'analyse métier : le chef de ligne est prévenu de l'expiration du permis ou de la visite médicale ; la planification peut ignorer (défaut), alerter ou bloquer. | P6 |
| **OR-07** | Alléger le travail du PDG par trois mesures. **Délégations** : depuis le règlement intérieur, le PDG confie un pouvoir à un poste ; il est informé de son usage et peut le reprendre. **Alertes** : le PDG ne reçoit en direct que les alertes critiques (la liste de ce qui est critique est réglable par la compagnie) ; le reste va dans une **synthèse du jour**, livrée en deux temps — version 1, sans IA : les alertes non critiques de la veille classées par pôle et par gravité (nombre et trois plus marquantes), ce qui a été traité par délégation (qui, quoi), ce qui reste ouvert et depuis quand, à une heure d'envoi réglable ; version 2 : l'IA d'analyse du pôle du PDG, quand elle existera. **Rattachement au secrétaire général** : en option, la compagnie rattache les Fonctions supports au secrétaire général et non plus au PDG (défaut : au PDG, comme aujourd'hui) ; activée, l'option lui fait passer la configuration hiérarchique de ces postes. À tester avec l'option activée et désactivée : la configuration hiérarchique, la matrice des rôles et le guide. | P2b (délégations ; rattachement en dernier) ; P9 (alertes, synthèse du jour) |
