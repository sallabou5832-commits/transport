# Permissions — cahier des charges

Ce document liste, pour chaque rôle et chaque ressource exposée par l'API, ce qui est
consultable et modifiable. Il fait foi : tout écart entre ce tableau et le code est un bug.

Règles générales, valables sauf mention contraire dans les tableaux ci-dessous :

- **Multi-tenant** : toute donnée est strictement scopée à la compagnie de l'utilisateur.
  Un utilisateur ne voit jamais les données d'une autre compagnie (404 sur un accès direct
  par identifiant, absence de la ressource dans les listes).
- **`superadmin`** n'appartient à aucune compagnie (c'est l'opérateur de la plateforme). Il
  a accès en lecture à toutes les compagnies et est traité comme le rôle le plus élevé de la
  hiérarchie partout où une hiérarchie de rôle s'applique. Il ne figure pas dans le cahier des
  charges des 18 rôles métier, mais son comportement est documenté ici par souci d'exhaustivité.
- Sauf mention contraire, la **lecture (GET)** d'une ressource d'une compagnie est ouverte à
  tout utilisateur authentifié de cette compagnie, quel que soit son rôle — c'est le choix par
  défaut retenu pour ce projet : la transparence en interne est la norme, la restriction est
  l'exception et doit être justifiée (données RH, financières, juridiques, ou spécifiquement
  prévues comme telles au cahier des charges).
- L'**écriture (création / modification / suppression)** est, elle, restreinte rôle par rôle
  comme détaillé plus bas.

## Rôles couverts

`pdg`, `secretaire_general`, `qhse`, `directeur_exploitation`, `chef_gare`, `chef_ligne`,
`guichetier`, `bagagiste`, `chauffeur_principal`, `chauffeur_relais`, `controleur_ligne`,
`directeur_technique`, `magasinier`, `chef_atelier`, `mecanicien`, `drh`, `directeur_financier`,
`responsable_juridique`.

---

## 1. Réseau (`reseau`) — Gare, Ligne, Vehicule

| Ressource | Lecture | Écriture (créer / modifier / supprimer) |
|---|---|---|
| **Gare** | Tous les rôles de la compagnie | `chef_gare` (uniquement la gare qu'il dirige — `chef` == lui), `directeur_exploitation`, `secretaire_general`, `pdg` |
| **Ligne** | Tous les rôles de la compagnie | `chef_ligne`, `directeur_exploitation`, `secretaire_general`, `pdg` |
| **Vehicule** | Tous les rôles de la compagnie | `directeur_technique`, `chef_atelier`, `directeur_exploitation`, `secretaire_general`, `pdg` |

**Champs pilotés ailleurs** : sur une **ligne**, `statut`, `est_fermee`, `fermee_jusqu_au` et `motif_fermeture` sont en lecture
seule (une fermeture passe par une demande décidée, voir §14) et `tarif` (FCFA) est imposé à la vente quand il est renseigné ;
sur un **véhicule**, `gare` (gare d'attache) est en lecture seule (elle change par l'arbitrage `reaffecter-gare`, §14) et
`kilometrage` se relève par les mêmes rôles que la fiche du véhicule (il déclenche l'entretien préventif, §15).

| Ressource | Lecture | Écriture |
|---|---|---|
| **AffectationGare** (`/affectations-gare/`, `/agents-affectables/`) | Le `chef_gare`, la direction et la régulation voient les équipes ; un agent voit son propre rattachement | `chef_gare` (uniquement l'équipe de **sa** gare), `directeur_exploitation`, `secretaire_general`, `pdg` (toute gare). Seuls les guichetiers et bagagistes composent une équipe locale ; un agent n'est affecté qu'à une gare à la fois |

Le statut d'un véhicule (`bloque_securite`, `en_maintenance`, `disponible`) est de toute façon
piloté automatiquement par les modules `personnel_roulant` (checklist) et `maintenance` (ordre
de réparation) — l'écriture manuelle ci-dessus ne sert qu'à l'enregistrement/modification de la
fiche véhicule elle-même (immatriculation, capacité, statut initial).

## 2. Billetterie (`billetterie`) — Depart, Ticket

| Ressource | Lecture | Écriture |
|---|---|---|
| **Depart** (planification) | Tous les rôles de la compagnie | `chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg` |
| **Ticket** (vente) | Tous les rôles de la compagnie | **Création** : `guichetier` et tout rôle qui lui est hiérarchiquement supérieur (`chef_ligne`, `chef_gare`, `directeur_exploitation`, `qhse`, `secretaire_general`, `pdg`). **Aucune modification ni suppression, pour personne** (405). |
| **Annulation d'un ticket** (`POST /tickets/{id}/annuler/`) | — | `chef_gare`, `chef_ligne`, `directeur_exploitation`, `secretaire_general`, `pdg` (et `superadmin`) uniquement. Le guichetier qui a vendu **ne peut pas** annuler sa propre vente. |
| **Places restantes** (`/departs/{id}/places-restantes/`) | Tous les rôles de la compagnie | — (lecture seule) |
| **Réservation de places hors ligne** (`/tickets/reserver-hors-ligne/`, POST/DELETE) | — | `guichetier` et les rôles qui lui sont supérieurs, pour leurs propres réservations uniquement |
| **Clôture de caisse** (`/tickets/cloture-caisse/`) | `guichetier` (uniquement la sienne) ; le `chef_gare`, celle des guichetiers de **sa gare** seulement (403 sinon) ; les autres rôles supérieurs, celle de n'importe quel guichetier de la compagnie | — (lecture seule) |
| **Remplaçants possibles** (`/departs/{id}/remplacants-possibles/`) | `chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg` (et `superadmin`) uniquement : c'est un annuaire des chauffeurs libres | — (lecture seule) |

**Tarif et code.** Une ligne qui a un `tarif` l'impose : sans `prix` dans la requête, le ticket est vendu au tarif ; un autre prix
n'est accepté que de `chef_gare`, `chef_ligne`, `directeur_exploitation`, `secretaire_general`, `pdg`, avec un `motif_derogation`
(5 caractères au moins) ; le tarif d'origine reste sur le ticket (`prix_tarif`). Chaque ticket porte un **code** unique de
10 caractères (alphabet sans `0`, `O`, `1`, `I`), envoyé au voyageur par SMS et vérifié par le contrôleur de ligne (§10) ;
`utilise_le` / `utilise_par` disent quand et par qui il a été contrôlé. Aucun ticket n'est vendu sur une **ligne fermée** (§14).
En **billetterie externe** (§22), la vente au guichet est fermée (403) et aucune place n'est plus mise de côté pour la vente hors
ligne ; chaque ticket dit d'où il vient (`source` : `guichet`, `lien`, `import`, et le `logiciel` d'origine).

**Clôture de caisse** (`/clotures-caisse/`, `POST`, `GET /etat/`) : le guichetier clôture **la sienne** (niveau d'automatisation
« assisté » ou plus ; « manuel », c'est son chef qui la clôture), la supervision (`chef_gare`, `chef_ligne`,
`directeur_exploitation`, `secretaire_general`, `pdg`, `qhse`) clôture celle d'un guichetier (`guichetier` = identifiant) et voit
celles de **sa propre compagnie uniquement** (rien d'une autre compagnie : liste vide, détail en 404, clôture refusée, caisse en
direct à zéro ; seul le `superadmin` de la plateforme voit toutes les compagnies) (le `chef_gare` ne voit et ne clôture que la caisse des guichetiers de **sa gare** : liste, détail, `etat`
et clôture ; 403 pour un guichetier d'une autre gare ou sans gare). Une caisse ne se clôture qu'une fois par jour ; la clôture
est la photo figée (espèces, mobile money, annulations) et prévient le chef de gare. `manage.py cloturer_caisses` clôture en fin
de journée les caisses des guichetiers en niveau « automatique ».

**Ticket verrouillé.** Un ticket vendu est une pièce de caisse : `PUT`, `PATCH` et `DELETE` répondent 405 à tous les
rôles (et l'administration Django ne permet ni ajout, ni modification, ni suppression, superadmin compris). Une erreur
se corrige par l'annulation : `motif` obligatoire (5 caractères au moins), un ticket ne s'annule qu'une fois. Elle
garde le ticket (`statut = annule`, `annule_par`, `annule_le`, `motif_annulation`), **libère la place** (sauf sur un
départ terminé, qui n'a plus de places à rendre) et **sort la vente des recettes** : recettes du jour de la direction,
synthèse financière, vue plateforme et clôture de caisse ne comptent que les tickets valides ; la clôture déclare les
annulations à part (`annulations`), l'argent correspondant devant être rendu. Le statut ne se choisit jamais à la vente.

**Planification** (`chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg`) :

- `POST /departs/planifier/` (ligne, véhicule, chauffeur, date_heure) crée le départ **et** sa feuille de route en une
  opération, tout ou rien ; mêmes règles que `POST /departs/` et `PATCH` :
  - un véhicule `bloque_securite` ou `en_maintenance` ne se planifie pas ;
  - ni le véhicule ni le chauffeur ne doivent avoir un autre départ non terminé à moins de 8 h (le modèle ne connaît
    pas la durée d'un trajet) ;
  - pas de date passée de plus d'une heure ; le chauffeur doit avoir un rôle de chauffeur de la compagnie.
- `GET /departs/disponibilites/?date_heure=…[&places_min=]` propose les véhicules et chauffeurs libres à cette heure
  (annuaire des chauffeurs : réservé à ces rôles ; agents désactivés exclus).
- Changer l'heure d'un départ suit sur sa feuille de route pas encore démarrée.
- `DELETE /departs/{id}/` : seulement un départ `planifie`, sans ticket (même annulé) et dont la feuille n'a pas
  démarré ; sa feuille est supprimée avec lui. C'est la correction d'une erreur de planning, pas un moyen d'effacer un trajet.

Le **nom du chauffeur** (`chauffeur_nom`) est exposé, en lecture seule, sur les départs, feuilles de route
et incidents (lisibles par tous les rôles de la compagnie) : l'API n'a pas d'annuaire d'agents et les
tableaux de bord doivent afficher des noms. De même `mecanicien_nom` sur les ordres de réparation.

Règles de la **réaffectation** d'un départ (`PATCH /departs/{id}/` avec `vehicule` ou `chauffeur`) :

- seul un départ `planifie` dont la feuille de route n'a pas démarré peut changer de véhicule ou de chauffeur
  (400 sinon : démarrer une feuille de route ne change pas `Depart.statut`, c'est la feuille qui dit si le car
  est parti) ;
- un changement de chauffeur suit sur la feuille de route pas encore démarrée (c'est elle que le chauffeur
  consulte) ; une feuille déjà transférée à un chauffeur relais n'est pas écrasée ;
- le nouveau véhicule doit contenir toutes les places déjà vendues ou réservées hors ligne (400 sinon) ;
- `remplacants-possibles` ne propose que des véhicules `disponible` assez grands et sans autre départ non
  terminé à moins de 8 h (le modèle ne connaît pas la durée d'un trajet), et des chauffeurs sans autre départ
  non terminé à moins de 8 h. Ces suggestions restent indicatives : la validation ci-dessus s'applique
  toujours au `PATCH`.

Règles métier de la vente (`POST /tickets/`) :

- **Idempotence** : l'en-tête `Idempotency-Key` (1 à 64 caractères, propre à chaque vendeur) rend la vente rejouable.
  Rejouer la même vente renvoie le ticket existant (200) sans décompter de place ni renvoyer de notification ;
  la même clé avec une vente différente est refusée (409).
- **Places réservées hors ligne** : un guichetier connecté peut faire mettre de côté des places (quota par départ,
  `BILLETTERIE_QUOTA_HORS_LIGNE`, expiration `BILLETTERIE_RESERVATION_TTL_HEURES`) pour vendre sans réseau. Ses
  ventes consomment d'abord ces places, qui lui sont garanties ; un autre guichet ne peut vendre que les places non
  réservées. Invariant : places vendues + places réservées actives <= capacité du véhicule.
  `places_reservees` et `places_disponibles` (vendables sans réservation) sont exposées sur les départs.

## 3. Personnel roulant (`personnel_roulant`) — FeuilleDeRoute, ChecklistDepart, Incident

| Ressource | Lecture | Écriture |
|---|---|---|
| **FeuilleDeRoute** / **ChecklistDepart** (liste filtrable : `?chauffeur=<id>`, `?date=AAAA-MM-JJ` ; la feuille porte `ligne_nom`, `vehicule` et `vehicule_immatriculation`) | `chef_ligne`, `chef_gare`, `directeur_exploitation`, `controleur_ligne`, `qhse`, `secretaire_general`, `pdg` (et `superadmin`) : tous les trajets de la compagnie. `chauffeur_principal` / `chauffeur_relais` : **uniquement les leurs** (le trajet d'un collègue est introuvable, 404). Les autres postes (guichet, bagages, magasin, atelier, RH, finance, juridique, technique) : 403, leur travail n'y touche pas | `chauffeur_principal` / `chauffeur_relais` (uniquement leurs propres feuilles/checklists ; supprimer sa feuille : permis par défaut, le règlement intérieur, §12, peut l'interdire), `chef_ligne`, `chef_gare`, `directeur_exploitation`, `controleur_ligne`, `qhse`, `secretaire_general`, `pdg` |
| **Incident** | mêmes rôles de lecture que ci-dessus **plus** `responsable_juridique` (un accident ouvre son dossier de sinistre) ; un chauffeur ne voit que les siens | mêmes rôles que ci-dessus (un chauffeur ne déclare/modifie que ses propres incidents ; les supprimer : permis par défaut, le règlement intérieur, §12, peut l'interdire) |
| **Incidents graves** (`/incidents/graves/`) | `qhse`, `directeur_exploitation` uniquement | — (lecture seule) |

Règle métier : un défaut de checklist sur un item de sécurité bloque automatiquement le
véhicule (`bloque_securite`) et empêche la feuille de route de démarrer, quel que soit le rôle
qui a saisi la checklist.

Règle métier : un item de checklist est unique par feuille de route. `POST /checklists/` sur un item déjà saisi
(même nom, casse et espaces ignorés) met à jour l'existant (200) au lieu d'en créer un second : sinon un défaut de
sécurité serait permanent, la feuille de route restant refusée tant qu'un défaut y figure, même après la réparation.
Reprendre après un défaut suppose donc deux conditions : le véhicule est repassé `disponible` (clôture de l'ordre de
réparation) ET l'item a été ressaisi « OK ».

Règle métier : ce que fait le chauffeur se répercute sur les autres pôles. `POST /feuilles-de-route/{id}/demarrer/`
passe le départ `planifie` à `en_cours` et un véhicule `disponible` à `en_ligne` ; `POST …/arriver/` passe le
départ à `termine` (plus aucune vente dessus) et un véhicule `en_ligne` à `disponible`. Un véhicule devenu
`en_maintenance` ou `bloque_securite` en route n'est pas remis `disponible` à l'arrivée. Un incident déclaré ne change
pas, à lui seul, le statut du véhicule.

## 4. Maintenance (`maintenance`) — Piece, OrdreReparation, SortiePiece

| Ressource | Lecture | Écriture |
|---|---|---|
| **Piece** (catalogue stock) | Tous les rôles de la compagnie | `magasinier`, `chef_atelier`, `directeur_technique` |
| **Pièces sous seuil** (`/pieces/sous-seuil/`) | Tous les rôles de la compagnie | — (lecture seule) |
| **OrdreReparation** — création | — | `chef_atelier`, `directeur_technique`, `directeur_exploitation`, `secretaire_general`, `pdg` |
| **OrdreReparation** — lecture | Tous les rôles de la compagnie | — |
| **OrdreReparation** — modification/suppression | — | `chef_atelier` (tout ordre), le `mecanicien` assigné (uniquement son propre ordre) ; le règlement intérieur (§12) peut retirer au mécanicien le droit de confier son ordre à un collègue (il passe alors par `reaffecter`) ou de le supprimer |
| **SortiePiece** | Tous les rôles de la compagnie | `magasinier`, `chef_atelier`, `directeur_technique` ; le `mecanicien` peut en créer (le stock est mis à jour à chaque sortie qu'il enregistre) mais **uniquement pour ses propres ordres**. Corriger ou annuler une sortie après coup (`magasinier`, `chef_atelier`, `directeur_technique`) : permis par défaut, interdit si le **règlement intérieur** de la compagnie le décide (§12) ; une correction ou une annulation ne remet pas le stock à jour |

Règles métier automatiques (aucun rôle ne peut les contourner) : un `OrdreReparation` créé sur
un véhicule déjà `bloque_securite`/`en_maintenance` passe le véhicule à `en_maintenance` ; un
`OrdreReparation` qui passe à `termine` remet le véhicule à `disponible` ; une `SortiePiece`
décrémente le stock et est refusée si le stock est insuffisant.

## 5. Supports (`supports`) — DossierAgent, Assurance, Sinistre, synthèse financière

| Ressource | Lecture | Écriture |
|---|---|---|
| **DossierAgent** | `drh` (tous les dossiers de la compagnie), chaque agent (le sien), et **chaque échelon pour les postes placés sous son autorité** (`configuration.regles`, le `pdg` règle tous les postes) — sans les notes internes du DRH (`notes_rh`) | `drh` uniquement |
| **Agents sans dossier** (`/dossiers-agents/agents-sans-dossier/`) | `drh` uniquement (données RH : pas de transparence par défaut, `superadmin` inclus) | — (lecture seule) |
| **Assurance** | `responsable_juridique`, `directeur_technique` uniquement | `responsable_juridique`, `directeur_technique` |
| **Assurances à échéance proche** (`/assurances/echeance-proche/`) | `responsable_juridique`, `directeur_technique` uniquement | — (lecture seule) |
| **Sinistre** (et pièces jointes `/pieces-sinistre/`) | `responsable_juridique`, `directeur_technique` uniquement | `responsable_juridique`, `directeur_technique` (voir §21) |
| **Synthèse financière** (`/synthese-financiere/`) | `directeur_financier`, `pdg`, `secretaire_general` uniquement | — (lecture seule) |

Un dossier expose `agent_nom` et `agent_role` en lecture seule : mêmes destinataires que le dossier lui-même.
La synthèse financière renvoie, pour la période demandée (`date_debut`, `date_fin`) : `gares` (par gare de
départ), `total`, `par_mode_paiement` (espèces / mobile money, un mode sans vente y figure avec des zéros) et
`par_jour`. Ces agrégats sont calculés côté serveur : la liste des tickets étant lisible par tous, la calculer
côté client aurait exposé au front des montants réservés à la finance.

## 6. Tableau de bord (`dashboard`)

| Endpoint | Accès |
|---|---|
| `/dashboard/direction/` | `pdg`, `secretaire_general`, `qhse` uniquement |
| `/dashboard/qhse/` | `qhse` uniquement |
| `/dashboard/exploitation/` | `directeur_exploitation`, `pdg`, `secretaire_general` uniquement (pas le `superadmin` : les chiffres sont ceux d'une compagnie) |
| `/dashboard/plateforme/` | `superadmin` uniquement : une ligne par compagnie (effectifs, flotte, activité du jour) |

`/dashboard/exploitation/` calcule la ponctualité du jour et des 7 derniers jours à partir des feuilles de
route : un départ est « à l'heure » s'il a lieu au plus tard 10 minutes après l'heure prévue ; une feuille non
démarrée dont l'heure prévue + 10 min est dépassée compte comme « en retard » (le départ n'a pas eu lieu, il ne
faut pas attendre qu'il ait lieu pour le signaler). Couleur d'une gare ou d'une ligne : vert à partir de 90 %,
orange à partir de 70 %, rouge en dessous, neutre s'il n'y a aucun départ mesurable.

## Contrat entre tableaux de bord web et API

`role_coverage_tests/test_matrice_conformite.py` teste **les 19 rôles (18 métiers + superadmin) sur chaque endpoint restreint** contre les
tableaux ci-dessus, la lecture générale ouverte à tous, le cloisonnement RH et l'isolation entre compagnies.
`role_coverage_tests/test_contrat_frontend.py` vérifie que chaque route appelée par une page web est autorisée
aux rôles auxquels cette page est proposée.

## 7. Formation (`formation`) — ParcoursFormation, EtapeFormation, ProgressionFormation

| Endpoint | Accès |
|---|---|
| `/formation/mon-parcours/` (GET) | Tout utilisateur authentifié, uniquement le parcours **de son propre rôle** (404 si son rôle n'a pas de parcours) |
| `/formation/mon-parcours/demarrer/` (POST) | Idem — démarre (ou reprend) sa propre progression |
| `/formation/mon-parcours/etapes/{id}/terminer/` (POST) | Idem — uniquement l'étape courante de sa propre progression |

La création et la modification du contenu des parcours se font via l'administration Django
(pas d'endpoint d'écriture). Une progression est strictement individuelle : personne ne voit ni ne
modifie celle d'un autre utilisateur.

Règle d'isolation (absolue) : les actions de formation sont **simulées**. Elles n'écrivent que dans les
tables `formation_*`, ne référencent aucun modèle métier et n'en importent aucun ; les données fictives
sont portées par les étapes elles-mêmes. Aucun ticket, départ, checklist, incident, pièce ou notification
client n'est créé ou modifié par la formation, et rien de la formation n'apparaît dans les autres modules.
Ces garanties sont vérifiées par `formation/tests/test_isolation.py`.

## 8. Journal d'audit (`audit`)

| Endpoint | Accès |
|---|---|
| `/audit/` (GET) | `pdg`, `secretaire_general`, `qhse` (le journal de **leur** compagnie) et `superadmin` (toutes) |

Chaque création, modification et suppression d'un objet métier (tickets, départs, feuilles de route, checklists,
incidents, ordres de réparation, sorties et stock de pièces, véhicules, gares, lignes, dossiers RH, assurances,
sinistres, comptes, compagnies) laisse une entrée : **qui** (compte, nom et rôle copiés), **quoi** (action, objet),
**quand**, **d'où** (adresse), et **ce qui a changé** (`{champ: [avant, après]}` ; l'état initial à la création,
l'état supprimé à la suppression). Une annulation de ticket est tracée comme telle, avec son motif. Les connexions
sont tracées aussi, réussies ou non (l'identifiant saisi, jamais le mot de passe). Le mot de passe d'un compte n'est
jamais écrit : seule l'existence du changement l'est. Un compteur dérivé (places vendues) ne fait pas de bruit.

- **Inaltérable** : ni modification ni suppression, ni par l'API, ni par l'administration (lecture seule, superadmin
  compris), ni par l'ORM (une tentative lève `JournalImmuable`). Renforcement possible en base : retirer les droits
  `UPDATE` et `DELETE` de l'utilisateur de l'application sur la table `audit_journalaudit`.
- **Hors requête** (commande, migration, données de démonstration), l'acteur est « système ».
- **Lecture paginée** (`?limit=` jusqu'à 200, 50 par défaut) et filtrable : `objet_type`, `objet_id`, `action`,
  `acteur`, `date_debut`, `date_fin`.
- Une panne d'écriture du journal n'empêche pas l'action métier mais est journalisée en erreur.
- **Adresse** : la dernière entrée de `X-Forwarded-For` (celle que le proxy ajoute lui-même ; les précédentes viennent du
  client). Le proxy doit **écraser** cet en-tête (voir `DEPLOIEMENT.md`).

## 9. Alertes inter-pôles (`alertes`)

| Endpoint | Accès |
|---|---|
| `/alertes/` (GET ; `?non_lues=1`, `?limit=`) | Tout utilisateur d'une compagnie, **uniquement les alertes adressées à son poste ou à lui-même** (le superadmin n'en a pas) |
| `/alertes/{id}/lire/`, `/alertes/lire-tout/` (POST) | Idem : chacun marque lues **ses** alertes (la lecture est individuelle) |

Aucune écriture par l'API en dehors de la lecture : une alerte naît d'une action d'un pôle qui en concerne un autre
(`alertes.services.alerter`), jamais d'un formulaire, et un échec d'émission ne bloque jamais l'action qui la déclenche.
Une alerte vise des **postes** (tous les agents de la compagnie qui l'occupent) et/ou des **agents** précis (le chef de la
gare de départ d'un car, le demandeur d'une pièce…). Déclencheurs, par pôle :

- **Direction / QHSE** : blocage de départ (→ chef de gare, chef d'atelier, directeur technique, régulation), défaut de
  checklist, incident, infraction grave au contrôle (→ direction et QHSE, sans intermédiaire), seuils critiques du PDG
  (ponctualité, pannes en hausse, recette en baisse), échéances d'assurance (30 j, 7 j, expirée), renouvellement de véhicule.
- **Exploitation** : pénurie de véhicule ou de chauffeur, risque de retard d'un départ, clôture de caisse (→ chef de gare),
  colis arrivé (→ bagagiste de la gare d'arrivée), fermeture/réouverture de ligne et demande de fermeture, véhicule rattaché
  à une autre gare, compte d'agent suspendu ou réactivé.
- **Personnel roulant** : fatigue du conducteur, relais, anomalie de cargaison.
- **Technique** : stock bas ou rupture, véhicule libéré, entretien préventif à échéance, ordre de réparation ouvert ou
  confié, réparation critique, demande de pièce (→ magasinier) et sa réponse.
- **Génération automatique** : `manage.py generer_alertes` (toutes les 5 à 10 minutes, voir `DEPLOIEMENT.md`). Chaque
  situation porte une clé : relancer la commande ne prévient pas dix fois du même problème.

## 10. Suivi de trajet, blocages de sécurité, contrôles à bord (`personnel_roulant`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **BlocageSecurite** (`/blocages-securite/`, `POST /{id}/lever/`) | Tous les rôles de la compagnie | `qhse` uniquement : poser un blocage (motif obligatoire) ou le lever (motif obligatoire) |
| **Positions GPS** — envoi (`POST /positions/`, un relevé ou un lot de 500 au plus) | — | `chauffeur_principal`, `chauffeur_relais` : la position de **leur** trajet en cours, avec l'heure réelle du relevé (envoi différé possible) |
| **Dernières positions** (`/positions/dernieres/`) et **carte du réseau** (`/dashboard/carte/`) | `chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg`, `qhse`, `directeur_technique` (pas le superadmin : données d'une compagnie) | — |
| **Mon trajet** (`/suivi/moi/`) | Tout utilisateur : `en_cours: false` pour qui ne conduit pas | — |
| **Fatigue** (`GET /feuilles-de-route/{id}/fatigue/`) | Le conducteur du trajet, et les mêmes rôles que la carte | — |
| **Pause** (`POST …/pause/`) | — | Le conducteur du trajet uniquement |
| **Relais** (`POST …/relais/`) | — | Le conducteur du trajet, ou la régulation (`chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg`) |
| **Anomalie de cargaison** (`POST …/anomalie-cargaison/`) | — | Le conducteur du trajet (mode convoyeur), le `controleur_ligne` |
| **Contrôle à bord** (`/controles/`, `POST /{id}/verifier/`, `POST /{id}/cloturer/`, `GET /{id}/rapport/`) | `controleur_ligne` (les siens), `chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg`, `qhse` (toute la compagnie) | `controleur_ligne` uniquement, et seulement sur **ses** contrôles |

- **Fatigue** : au-delà de `SUIVI_SEUIL_FATIGUE_MINUTES` (270 min) de conduite continue, l'alerte propose des relais ; une
  pause remet le compteur à zéro. Un relais transfère la feuille de route et l'état du véhicule au nouveau conducteur (le
  suivi GPS et la fatigue continuent sur lui) ; l'ancien conducteur ne peut plus agir sur le trajet.
- **Contrôle** : chaque billet présenté est vérifié par son code (valide, déjà utilisé, annulé, inconnu, d'un autre départ, départ
  terminé) ; **un billet valide est marqué utilisé** et ne sert qu'une fois. Clôturer génère le rapport (billets, voyageurs et
  charge comparés à ce que le guichetier et le bagagiste ont enregistré, anomalies). Est grave : une infraction déclarée, une
  surcharge, ou 3 billets frauduleux ; elle crée un incident grave et alerte direction et QHSE.

## 11. Colis (`colis`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **Colis** (`/colis/`, `/departs/{id}/plan-chargement/`) | `bagagiste`, `guichetier`, `controleur_ligne`, `chauffeur_principal`, `chauffeur_relais`, `qhse`, `chef_gare`, `chef_ligne`, `directeur_exploitation`, `secretaire_general`, `pdg` (noms et téléphones des clients : pas de transparence par défaut) | Enregistrer, charger, remettre : `bagagiste`, `chef_gare`, `chef_ligne`, `directeur_exploitation`, `secretaire_general`, `pdg` |
| **Annuler** un colis, **renvoyer** un code de retrait | — | La supervision uniquement (`chef_gare`, `chef_ligne`, `directeur_exploitation`, `secretaire_general`, `pdg`), pas le bagagiste |

Le client n'a pas accès au logiciel : son **code de retrait** lui est envoyé par SMS ou WhatsApp à l'enregistrement. Le code
n'est **jamais** stocké en clair ni affiché à l'écran du bagagiste (empreinte seulement) ; trois essais erronés bloquent la
remise. Statuts : enregistré, chargé, arrivé, retiré (ou annulé). Les frais de fret entrent dans la synthèse financière.

## 12. Configuration hiérarchique (`configuration`)

| Endpoint | Accès |
|---|---|
| `/configuration/moi/`, `/configuration/catalogue/`, `/configuration/compagnie/` (GET) | Tout utilisateur de la compagnie |
| `/configuration/compagnie/` (PATCH) | `pdg` uniquement : le **cadre** (automatisation et gamification maximales) qu'aucun poste ne dépasse |
| `/configuration/postes/`, `/configuration/postes/{rôle}/` (GET, PUT) | Chaque échelon règle **les postes directement sous lui** (voir ci-dessous) ; le PDG règle n'importe quel poste |
| `/configuration/agents/`, `/configuration/agents/{id}/` (GET, PUT) | Idem, pour un agent précis (aisance numérique, préférence vocale, réglages propres) |
| `/configuration/reglement/` (GET) | Tout utilisateur de la compagnie : chaque règle, si elle est permise, son défaut, les postes concernés, le pôle qui la règle et si l'appelant peut la régler |
| `/configuration/reglement/` (PATCH `{code: vrai/faux, ...}`) | `pdg` : toutes les règles ; `directeur_technique` : atelier et magasin ; `directeur_exploitation` : chauffeurs. Une demande qui déborde du pôle est refusée en entier (403) |

Hiérarchie : PDG → secrétaire général, QHSE, directeur des opérations, directeur technique, DRH, directeur financier, responsable
juridique ; directeur des opérations → chef de gare, chef de ligne, contrôleur ; chef de gare → guichetier, bagagiste ; chef
de ligne → chauffeurs ; directeur technique → magasinier, chef d'atelier ; chef d'atelier → mécanicien. Un échelon ne règle ni
son supérieur, ni ses pairs. **Ce qui se règle** : niveau d'automatisation (manuel / assisté / automatique), niveau de
gamification (aucun / sobre / complet), fonctions désactivées, préférence vocale ; la valeur d'un agent prime sur celle de son
poste, qui prime sur le cadre, sans jamais le dépasser. Le serveur **applique** ces réglages (vente de tickets, enregistrement de
colis, planification, clôture de caisse refusent avec un message clair quand la fonction est retirée).

**Règlement intérieur** : chaque compagnie décide, à sa guise, de ce qu'elle permet à certains postes. Une règle non réglée
garde le comportement du socle (tout est permis par défaut) ; une règle interdite est refusée par le serveur (403, « Le
règlement intérieur de la compagnie ne permet pas… »), pour les seuls postes concernés. Chaque changement est tracé dans le
journal d'audit.

| Règle (`code`) | Postes concernés | Réglée par | Défaut |
|---|---|---|---|
| `sorties_pieces_corrigeables` : corriger ou annuler une sortie de pièce après coup | `magasinier`, `chef_atelier`, `directeur_technique` | `directeur_technique`, `pdg` | permis |
| `mecanicien_confie_ses_ordres` : confier soi-même son ordre à un collègue (`PATCH` du champ `mecanicien`) | `mecanicien` | `directeur_technique`, `pdg` | permis |
| `mecanicien_supprime_ses_ordres` : supprimer son ordre de réparation | `mecanicien` | `directeur_technique`, `pdg` | permis |
| `chauffeur_supprime_ses_feuilles` : supprimer sa feuille de route | `chauffeur_principal`, `chauffeur_relais` | `directeur_exploitation`, `pdg` | permis |
| `chauffeur_supprime_ses_incidents` : supprimer un incident qu'il a déclaré | `chauffeur_principal`, `chauffeur_relais` | `directeur_exploitation`, `pdg` | permis |

## 13. Gamification (`gamification`)

| Endpoint | Accès |
|---|---|
| `/gamification/moi/` | Tout utilisateur : niveau, points, missions du jour, badges (`actif: false` si son poste n'affiche pas le jeu) |
| `/gamification/classement/` (`?type=`, `?periode=`) | Tout utilisateur **dont le poste a la gamification complète** ; `visible: false` sinon (le classement est un choix de la compagnie, pas un droit) |
| `/gamification/agents/` | `drh`, `pdg` : les scores de tous les agents, comme aide à l'évaluation (pas de transparence par défaut) |

Les scores sont **calculés à partir des données réelles** (ponctualité, tickets, colis, contrôles, réparations…), jamais saisis ;
seules les missions accomplies et les badges obtenus sont conservés. Classements : gares, lignes, chauffeurs, guichetiers,
bagagistes, ateliers, contrôleurs.

## 14. Pouvoirs d'exploitation et de direction (`reseau`, `core`, `investissements`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **Fermeture d'une ligne** (`POST /lignes/{id}/changement/`) | — | `directeur_exploitation`, `pdg` : appliquée aussitôt ; `chef_ligne`, `chef_gare` : **déposent une demande** à valider |
| **Demandes sur les lignes** (`/changements-ligne/`, `POST /{id}/decider/`) | `directeur_exploitation`, `pdg` (toutes) ; `chef_ligne`, `chef_gare` (les leurs) | Décider (`valider` / `refuser`) : `directeur_exploitation`, `pdg` |
| **Gare d'attache d'un véhicule** (`POST /vehicules/{id}/reaffecter-gare/`) | Tous (champ `gare` du véhicule) | `directeur_exploitation`, `pdg` (arbitrage entre gares : motif obligatoire, prévient les deux chefs de gare et la régulation) |
| **Gares en tension** (`/dashboard/exploitation/`, champs `departs_24h`, `vehicules_disponibles`, `tension`) | `directeur_exploitation`, `pdg`, `secretaire_general` | — |
| **Comptes des agents** (`/comptes/`, `POST /{id}/suspendre/`, `POST /{id}/reactiver/`) | `pdg` uniquement (les autres comptes de sa compagnie, hors PDG) | `pdg` uniquement |
| **Investissements** (`/investissements/`) | `pdg`, `secretaire_general`, `directeur_financier` (toutes) ; `directeur_technique`, `directeur_exploitation` (les leurs) | Demander : `directeur_technique`, `directeur_exploitation`, `directeur_financier` ; **décider** (`POST /{id}/decider/`) : `pdg` seul |

- **Ligne fermée** : `statut`, `fermee_jusqu_au` (dernier jour, **inclus** : la ligne se rouvre d'elle-même le lendemain, sans
  intervention), `motif_fermeture` ne se modifient **pas** par la fiche de la ligne (lecture seule) : seules les demandes ci-dessus
  changent son état. Tant qu'elle est fermée, **on n'y planifie plus de départ** et **on n'y vend plus de billet** (400 avec le
  motif) ; les départs déjà en cours ne sont pas touchés. La fermeture prévient les chefs de gare des deux bouts, la
  régulation, le directeur des opérations et le PDG, et dit combien de départs planifiés sont à réaffecter ou à annuler.
- **Suspension de compte** : `is_active` passe à faux ; **les sessions ouvertes sont coupées à la requête suivante** (l'accès
  et le renouvellement du jeton sont refusés) et la connexion est refusée. Rien n'est supprimé (ventes, colis, journal d'audit
  intacts). Motif obligatoire ; le PDG ne suspend ni lui-même, ni un autre PDG ; le DRH et le chef de gare de l'agent sont
  prévenus ; l'action figure au journal d'audit avec le PDG comme acteur.
- **Investissement** : le refus exige une raison ; une demande ne se décide qu'une fois ; le demandeur (et la finance, quand un
  montant est engagé) est prévenu. Aucune modification ni suppression après dépôt.

## 15. Maintenance avancée (`maintenance`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **File d'attente** (`/ordres-reparation/file-attente/`) | Tous les rôles de la compagnie (elle porte le **retour estimé** des véhicules, remonté à la régulation) | — |
| **Réordonner** (`POST /ordres-reparation/reordonner/`), **prioriser** (`POST /{id}/prioriser/` : urgence, délai estimé), **répartir** (`POST /{id}/reaffecter/`) | — | `directeur_technique`, `chef_atelier` |
| **Charge de l'atelier** (`/maintenance/charge-mecaniciens/`) | `directeur_technique`, `chef_atelier` | — |
| **Plans d'entretien** (`/plans-entretien/`, `/echeances/`) | Tous les rôles de la compagnie | `directeur_technique`, `chef_atelier` (créer, modifier, supprimer, `POST /{id}/realise/`) |
| **Demandes de pièces** (`/demandes-pieces/`) | `magasinier`, `chef_atelier`, `directeur_technique` (toutes) ; `mecanicien` (les siennes) | Demander : `mecanicien` (pour **ses** ordres), `chef_atelier` ; **servir / refuser** : `magasinier` ; annuler : le demandeur ou le chef d'atelier |
| **Suggestions de commande** (`/pieces/suggestions-commande/`) | `magasinier`, `directeur_technique`, `chef_atelier` | — |
| **Fiche véhicule** (`/fiche-vehicule/{id}/`) | `directeur_technique`, `chef_atelier`, `mecanicien`, `magasinier`, `directeur_exploitation`, `pdg`, `secretaire_general`, `qhse` | — |
| **Besoin de renouvellement** (`/maintenance/besoin-renouvellement/`) | `directeur_technique`, `pdg`, `secretaire_general`, `directeur_exploitation`, `directeur_financier` | — |
| **Kilométrage** (`PATCH /vehicules/{id}/`) | — | Comme la fiche véhicule du §1 : `directeur_technique`, `chef_atelier`, `directeur_exploitation`, `secretaire_general`, `pdg` |

- **File d'attente** : urgence (critique, haute, normale, basse), puis position posée par le technique, puis ancienneté.
  **L'urgence prime toujours** (pour passer devant, on l'élève). L'urgence et le délai se fixent à l'ouverture de l'ordre ; ensuite
  seuls `prioriser` les change (un mécanicien ne se reclasse pas lui-même). La position ne se pose que par `reordonner`.
- **Préventif** : un plan se déclare en jours et/ou en kilomètres ; l'échéance est la première atteinte (préavis
  `ENTRETIEN_PREAVIS_JOURS` / `_KM`). `generer_alertes` prévient l'atelier **puis ouvre l'ordre de réparation** au mécanicien le
  moins chargé (urgence haute si en retard) ; clore cet ordre **renouvelle le plan**. Un plan sans mécanicien disponible n'ouvre que l'alerte.
- **Demande de pièce** : la disponibilité est confirmée à la demande ; servir enregistre la **sortie sur l'ordre** (mêmes règles
  que `SortiePiece` : le stock baisse, refusé s'il est insuffisant, alerte sous le seuil) ; refuser exige un motif.
- **Renouvellement** : un véhicule figure au rapport dès qu'il atteint un seuil (`RENOUVELLEMENT_KM`, réparations et jours
  d'immobilisation sur 12 mois) ; deux seuils = « à renouveler » (alerte trimestrielle au PDG et au technique).

---

## 16. Santé de la gare et équipe locale (`dashboard`, `reseau`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **Santé de la gare** (`/dashboard/gare/`, `?gare=` pour choisir la gare) | `chef_gare` (**sa** gare), `directeur_exploitation`, `pdg`, `secretaire_general` (toute gare) | — |
| **Équipe locale** (`/affectations-gare/`) | Voir §1 | Voir §1 : le chef de gare compose l'équipe de **sa** gare |

- La santé de la gare calcule côté serveur les recettes du jour (billets par mode de paiement et fret), la ponctualité (jour et 7 jours),
  le remplissage, les incidents ouverts, les retards, les véhicules et l'équipe. Un autre rôle reçoit 403 ; un chef de gare qui n'a pas de
  gare reçoit 404 (« Aucune gare ne vous est rattachée »), jamais celle d'une autre ; les rôles de supervision doivent indiquer `?gare=`
  (400 sinon, et 400 pour une gare d'une autre compagnie).

## 17. Secrétariat de la direction et messages des gares (`communication`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **Notes de service** (`/notes-service/`) | Tout poste de la compagnie, **pour les notes qui le visent** (pôles, postes, ou tous) | `secretaire_general`, `pdg` |
| **Agenda de la direction** (`/agenda/`) | `secretaire_general`, `pdg`, `qhse`, `directeur_exploitation`, `directeur_technique`, `directeur_financier`, `drh`, `responsable_juridique` | `secretaire_general`, `pdg` (les invités sont alertés) |
| **Archives** (`/archives/`) | `secretaire_general`, `pdg` | `secretaire_general`, `pdg` : classer, retrouver, **archiver — jamais supprimer** |
| **Messages directs** (`/messages-directs/`) | `chef_gare` (les siens), `directeur_exploitation`, `pdg`, `secretaire_general` | `chef_gare` : à l'équipe locale et/ou aux chauffeurs dont le car arrive à sa gare (ils les reçoivent dans leur cloche) |
| **Catalogue** (`/communication/catalogue/`) | Tout poste | — |

- Le superadmin, sans compagnie, n'en lit aucune. Le registre d'archives dit où retrouver le dossier ; il ne contient pas le fichier.

## 18. Conformité de la flotte et carnet de route (`supports`, `personnel_roulant`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **Tableau de conformité** (`/conformite/`) | `qhse`, `responsable_juridique`, `directeur_technique`, `directeur_exploitation`, `pdg`, `secretaire_general` | — (les obligations sont les plans d'entretien marqués « réglementaire », §15) |
| **Carnet de route** (`/carnet-de-route/`) | `chauffeur_principal`, `chauffeur_relais` : **le leur** (derniers trajets, documents du véhicule à présenter en cas de contrôle) | — |

## 19. Finance (`finance`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **Dépenses** (`/depenses/`), **budgets carburant** (`/budgets-carburant/`), **fournisseurs** (`/fournisseurs/`), **factures** (`/factures/`, `POST /{id}/payer/`, `POST /{id}/annuler/`) | `directeur_financier`, `pdg`, `secretaire_general` | `directeur_financier` uniquement |
| **Rentabilité** (`/finance/rentabilite/`), **suivi du budget carburant** (`/finance/budget-carburant/`), **trésorerie** (`/finance/tresorerie/`), **réglage** (`/finance/configuration/`) | `directeur_financier`, `pdg`, `secretaire_general` | Le solde de départ : `directeur_financier` (`PUT`) |
| **Export** (`/finance/export/?type=rentabilite\|depenses\|factures\|tresorerie`) | `directeur_financier`, `pdg`, `secretaire_general` (CSV pour Excel ; le site imprime la même vue pour un PDF). Un texte qui commence par `=`, `+`, `-` ou `@` est précédé d'une apostrophe : Excel ne l'exécute pas comme une formule | — |

- Données d'une compagnie : **le superadmin n'y a pas accès**. Toute donnée d'une autre compagnie est introuvable (404).
- Un **budget carburant** est mensuel, par ligne (un seul par ligne et par mois). La finance et le PDG sont alertés à **80 %** puis au **dépassement**
  (alerte à la saisie d'une dépense de carburant et à chaque passage de `generer_alertes`, une seule fois par situation).
- **Payer une facture** enregistre la dépense correspondante (catégorie « assurance » pour une prime, « fournisseur » sinon), en une
  opération ; une facture réglée ou annulée ne se modifie ni ne se supprime. Rappels de paiement à 7 jours, à 1 jour et au retard.
- **Rentabilité** : recettes (billets valides et fret non annulé) contre dépenses, par ligne et par gare de départ, avec les charges
  communes (dépenses sans ligne ni gare) qui pèsent sur le total. Une dépense ne peut pas être datée du futur.

## 20. Ressources humaines (`rh`)

Principe du cahier des charges : la **configuration hiérarchique**. Chacun voit ses propres informations, chaque échelon celles des postes
placés directement sous son autorité (`configuration.regles.SUBORDONNES` ; le `pdg` règle tous les postes), le `drh` et le `pdg` tout. Les
données sont celles d'une compagnie : **le superadmin n'y a pas accès**.

| Ressource | Lecture | Écriture |
|---|---|---|
| **Catalogue des formations obligatoires** (`/obligations-formation/`) | `drh`, `qhse`, `pdg`, `secretaire_general` | `drh`, `qhse` (une obligation qui a des sessions ne se supprime pas) |
| **Sessions suivies** (`/formations-suivies/`) et **suivi** (`/formations-obligatoires/suivi/`) | Chacun (les siennes) ; chaque échelon (les postes sous son autorité) ; `drh`, `qhse`, `pdg`, `secretaire_general` (tous) | `drh`, `qhse` |
| **Contrats** (`/contrats/`), **mesures disciplinaires** (`/mesures-disciplinaires/`) | Chacun (les siens) ; chaque échelon (ses postes) ; `drh`, `pdg` (tous) | `drh` uniquement |
| **Évaluations** (`/evaluations/`) | Comme les contrats | `drh` (tout le monde) ; chaque échelon **pour les postes sous son autorité** ; on ne modifie que ses propres évaluations (le `drh` toutes) |
| **Fiche complète** (`/dossiers-agents/{id}/fiche/`) | Comme le dossier (§5) : contrats, évaluations, discipline, formations ; sans `notes_rh` ni notes de contrat pour la hiérarchie | — |
| **Congés** (`/conges/`) | Chacun (les siens) ; chaque échelon (ses postes) ; `drh`, `pdg` (tous) | **Demander** : tout poste, pour soi (le `drh` peut saisir pour un agent) ; **décider** (`approuver`, `refuser`) : `drh` ; **annuler** : l'agent (sa demande) ou le `drh` |
| **Impact d'un congé** (`GET /conges/{id}/impact/`) | `drh`, `pdg` | — |
| **Fiches de poste** (`/fiches-poste/`, `POST /reinitialiser/`), **offres** (`/offres-recrutement/`), **candidatures** (`/candidatures/`) | `drh`, `pdg`, `secretaire_general` | `drh` uniquement |
| **Doléances** (`/doleances/`, `POST /{id}/suivre/`) | **Le déposant seulement** (avec les étapes qu'on a choisi de lui montrer) ; `drh` (toutes) — même la hiérarchie et le PDG ne les lisent pas | **Déposer** : tout poste (gravité jusqu'à « grave ») ; **instruire** (gravité, statut, étapes, doléances de syndicats) : `drh` uniquement |
| **Litiges sociaux** (`/litiges-sociaux/`) | `responsable_juridique`, `drh`, `pdg` : l'objet, le contenu, la gravité et le **poste** de l'auteur, jamais son identité | — |
| **Synthèse RH** (`/rh/synthese/`) | `drh`, `pdg`, `secretaire_general` | — |

- **Formations obligatoires** : l'état de chaque (agent, obligation) est `a_jour`, `a_renouveler` (dans le préavis), `expiree` ou `manquante` ;
  renouveler, c'est enregistrer une nouvelle session (l'historique reste). Le `drh`, le `qhse` et l'agent sont alertés d'une échéance qui approche
  ou d'une expiration (`generer_alertes`, une seule fois par situation) ; une formation manquante figure au suivi, pas parmi les alertes.
- **Congés** : la demande d'un congé annuel se fait avant, celle d'un arrêt maladie peut se faire après coup ; 60 jours au plus par demande ;
  deux demandes d'un même agent ne se chevauchent pas. **L'impact** compte, jour par jour, les collègues du même poste encore disponibles (pour
  les conducteurs, les départs au programme) : `ok`, `tendu` ou `critique`. Un impact critique, ou des départs déjà confiés au demandeur, **exigent
  une confirmation** (`forcer`, réponse 409 sinon) ; l'exploitation est alors alertée des départs à réaffecter. **Un conducteur en congé approuvé
  n'est plus proposé comme remplaçant et ne peut plus être affecté à un départ ce jour-là.**
- **Médiation sociale** : un agent ne dépose que ses doléances (`origine=agent`, gravité jusqu'à « grave ») ; le `drh` seul enregistre celles
  d'un syndicat et peut qualifier une doléance de « critique ». Au seuil de gravité (`MEDIATION_SEUIL_LITIGE`, « grave » par défaut), le
  `responsable_juridique` est alerté d'un **risque de litige social** (le `pdg` aussi si elle est critique) ; requalifier vers une gravité
  supérieure alerte à nouveau, la même situation n'alerte qu'une fois.
- **Contrats** : un contrat à durée déterminée (CDD, stage, journalier) qui se termine dans les 30 jours alerte le `drh`.

## 21. Juridique (`supports`)

| Ressource | Lecture | Écriture |
|---|---|---|
| **Sinistres** (`/sinistres/`) | `responsable_juridique`, `directeur_technique` | `responsable_juridique`, `directeur_technique` (statut, référence de l'assureur, montants estimé et indemnisé) |
| **Pièces jointes** (`/pieces-sinistre/`, `GET /{id}/telecharger/`) | `responsable_juridique`, `directeur_technique` | Envoyer (multipart) et retirer : les mêmes ; on corrige le libellé, jamais le fichier |
| **Bibliothèque de modèles** (`/modeles-juridiques/`) | **Tout poste de la compagnie**, pour les modèles ouverts à son pôle (ou à tous) ; `responsable_juridique` : tous | `responsable_juridique` (texte, pôles autorisés, fichier via `POST /{id}/fichier/` et `POST /{id}/retirer-fichier/`) |
| **Reporting juridique** (`/juridique/reporting/`) | `responsable_juridique`, `pdg`, `secretaire_general` | — |

- **Un accident déclaré ouvre le sinistre** : à la déclaration d'un incident de type « accident » (par le chauffeur ou le QHSE), ou quand un
  incident est requalifié en accident, le dossier de sinistre lié s'ouvre (un seul par incident) et le `responsable_juridique` est alerté. Un
  échec de cette ouverture n'empêche jamais de déclarer l'incident.
- **Pièces jointes** : PDF, PNG, JPEG, Word (`.docx`) et Excel (`.xlsx`), 5 Mo au plus (`PIECES_JOINTES_TAILLE_MAX_MO`). Le serveur contrôle que le
  **contenu** correspond à l'extension (un exécutable renommé « .pdf » est refusé), range le fichier sous un **nom aléatoire** hors du code et ne
  le sert **que par l'API**, après contrôle des droits, en téléchargement (`Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`) :
  aucun lien public. Une pièce d'une autre compagnie est introuvable.
- **Reporting** : flotte assurée (%), assurances expirées/absentes/à renouveler, sinistres par statut (montants, délai moyen de clôture), litiges
  sociaux **comptés seulement** (ni nom ni intitulé), conformité de la flotte, et les points de vigilance du moment.

---

## 22. Lien avec le logiciel de billetterie de la compagnie (`lien_billetterie`)

Une compagnie qui a déjà son logiciel de billetterie peut le garder. Elle choisit son **mode de billetterie** : `integre` (défaut :
le module de billetterie, rien ne change), `externe` (son logiciel vend ; la vente au guichet est fermée) ou `mixte` (les deux,
les places sont communes). Les ventes de son logiciel arrivent par une **API** (clé d'API de la compagnie) ou par l'**import d'un
fichier** (CSV ou Excel) et deviennent de vrais billets : places, recettes, tableaux de bord, contrôle à bord. Guide pour
l'éditeur du logiciel : `LIEN_BILLETTERIE.md`.

| Endpoint | Accès |
|---|---|
| `/lien-billetterie/reglage/` (GET) | Tout agent de la compagnie (le superadmin, sans compagnie, n'y a pas accès) |
| `/lien-billetterie/reglage/` (PATCH `{"mode": ...}`) | `pdg`, `directeur_exploitation` |
| `/lien-billetterie/cles/` (GET, POST `{"logiciel"}`), `POST /cles/{id}/revoquer/` | `pdg`, `directeur_exploitation` (clés de leur compagnie ; la clé en clair n'est montrée qu'une fois, à la création ; ni modification ni suppression) |
| `/lien-billetterie/imports/` (GET, POST `fichier` + `logiciel`, GET `/{id}/` avec le compte rendu ligne par ligne) | `pdg`, `directeur_exploitation` (tous les imports de la compagnie) ; `chef_gare` (seulement les départs de **sa** gare, et ses propres imports) |
| `/lien-billetterie/departs/`, `/ventes/`, `/annulations/` | **Le logiciel de la compagnie seulement**, par sa clé (`Authorization: ApiKey <clé>`) ; jamais un jeton d'agent. La clé n'ouvre aucune autre route |

- Ventes et imports sont refusés (403) tant que la compagnie est en billetterie `integre`.
- Une vente reçue prend une place sous verrou du départ, sans toucher aux places réservées pour la vente hors ligne des guichets ;
  un départ complet la refuse. Elle est reconnue par sa **référence** dans le logiciel : la recevoir deux fois (lot rejoué, fichier
  réimporté) ne crée rien de plus. Le prix du logiciel est gardé ; s'il s'écarte du tarif, l'écart reste visible
  (`motif_derogation` « Prix fixé par … »).
- Elle n'entre dans la caisse d'**aucun guichetier** (l'argent est dans le logiciel de la compagnie) et ne déclenche aucun SMS ; elle
  compte dans les recettes, les tableaux de bord et le remplissage. Le contrôleur la vérifie à bord par le code imprimé par le
  logiciel (casse, espaces et tirets ignorés).
- Le journal d'audit trace le réglage, les clés (jamais leur empreinte) et chaque billet créé (« système » pour l'API, l'agent qui
  a déposé le fichier pour un import).

## Synthèse par rôle

| Rôle | Peut voir (au-delà du droit de lecture générale) | Peut créer/modifier |
|---|---|---|
| `pdg` | Tout ce qui est en lecture générale, tableau de bord direction, synthèse financière, carte du réseau, comptes des agents, investissements, scores des agents, besoin de renouvellement | Gares, lignes, véhicules, départs, tickets ; **pouvoirs d'intervention directe** : geler/rouvrir une ligne, réaffecter un véhicule entre gares, suspendre un compte, valider un investissement, fixer le cadre et le règlement intérieur de la compagnie, choisir le mode de billetterie et gérer le lien avec son logiciel |
| `secretaire_general` | Idem `pdg` (sauf comptes, investissements et pouvoirs d'intervention), notes de service, agenda, archives, finance, synthèse RH et juridique | Gares, lignes, véhicules, départs, tickets ; **secrétariat de la direction** : notes de service, agenda, archives |
| `qhse` | Tableau de bord direction et QHSE, incidents graves, carte, contrôles, colis, fiche véhicule | Tickets, feuilles de route/checklists/incidents ; **poser et lever un blocage de sécurité** |
| `directeur_exploitation` | Tout ce qui est en lecture générale, carte, gares en tension, demandes sur les lignes | Gares, lignes, véhicules, départs, tickets, feuilles de route/checklists/incidents, ordres de réparation (création) ; fermer/rouvrir une ligne et **décider** les demandes des chefs, réaffecter un véhicule entre gares, demander un investissement ; régler le règlement intérieur pour les chauffeurs ; choisir le mode de billetterie, gérer les clés du lien et importer les ventes du logiciel de la compagnie |
| `chef_gare` | Caisses de son équipe, carte, contrôles, colis | Sa propre gare, départs, tickets, feuilles de route/checklists/incidents, l'équipe de sa gare, colis ; importer les ventes du logiciel de la compagnie pour sa gare ; **demander** la fermeture d'une ligne |
| `chef_ligne` | Carte, fatigue des conducteurs, contrôles, colis, retours estimés des véhicules à l'atelier | Lignes, départs, tickets, feuilles de route/checklists/incidents, relais de conducteur ; **demander** la fermeture d'une ligne |
| `guichetier` | Sa propre clôture de caisse | Tickets |
| `bagagiste` | — | Aucun droit d'écriture particulier |
| `chauffeur_principal` | — | Ses propres feuilles de route, checklists, incidents |
| `chauffeur_relais` | — | Ses propres feuilles de route, checklists, incidents |
| `controleur_ligne` | Ses contrôles, colis | Feuilles de route/checklists/incidents ; **contrôles à bord** (vérifier les billets, clôturer, rapport) ; anomalie de cargaison |
| `directeur_technique` | Charge de l'atelier, suggestions de commande, fiche véhicule, besoin de renouvellement | Véhicules (dont kilométrage), ordres de réparation (création, urgence, délai, ordre de la file, répartition), plans d'entretien, pièces, sorties de pièces, assurances, sinistres ; demander un investissement ; régler le règlement intérieur pour l'atelier et le magasin |
| `magasinier` | Demandes de pièces, suggestions de commande, fiche véhicule | Pièces, sorties de pièces ; servir ou refuser les demandes de pièces |
| `chef_atelier` | Charge de l'atelier, demandes de pièces, suggestions de commande, fiche véhicule | Véhicules (dont kilométrage), ordres de réparation (tous : création, modification, urgence, délai, file, répartition), plans d'entretien, pièces, sorties de pièces, demandes de pièces |
| `mecanicien` | Ses demandes de pièces, fiche véhicule | Ses propres ordres de réparation (statut, temps passé), sorties de pièces pour ses ordres, demandes de pièces pour ses ordres |
| `drh` | Tous les dossiers agents, contrats, évaluations et discipline, scores de gamification, suivi des formations, congés et leur impact, recrutement, doléances, litiges sociaux | Dossiers agents, contrats, mesures disciplinaires, évaluations, formations obligatoires et sessions, **décision des congés**, fiches de poste, offres et candidatures, **instruction des doléances** |
| `directeur_financier` | Synthèse financière, dépenses, budgets, factures, rentabilité, trésorerie | **La comptabilité** : dépenses, budgets carburant, fournisseurs, factures (payer, annuler), solde de départ ; demander un investissement |
| `responsable_juridique` | Tableau de conformité, litiges sociaux, reporting juridique | Assurances, sinistres et leurs pièces jointes, **bibliothèque de modèles**, statut des sinistres |
