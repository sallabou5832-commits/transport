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
  charges des 17 rôles métier, mais son comportement est documenté ici par souci d'exhaustivité.
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
`directeur_technique`, `magasinier`, `chef_atelier`, `drh`, `directeur_financier`,
`responsable_juridique`.

---

## 1. Réseau (`reseau`) — Gare, Ligne, Vehicule

| Ressource | Lecture | Écriture (créer / modifier / supprimer) |
|---|---|---|
| **Gare** | Tous les rôles de la compagnie | `chef_gare` (uniquement la gare qu'il dirige — `chef` == lui), `directeur_exploitation`, `secretaire_general`, `pdg` |
| **Ligne** | Tous les rôles de la compagnie | `chef_ligne`, `directeur_exploitation`, `secretaire_general`, `pdg` |
| **Vehicule** | Tous les rôles de la compagnie | `directeur_technique`, `chef_atelier`, `directeur_exploitation`, `secretaire_general`, `pdg` |

Le statut d'un véhicule (`bloque_securite`, `en_maintenance`, `disponible`) est de toute façon
piloté automatiquement par les modules `personnel_roulant` (checklist) et `maintenance` (ordre
de réparation) — l'écriture manuelle ci-dessus ne sert qu'à l'enregistrement/modification de la
fiche véhicule elle-même (immatriculation, capacité, statut initial).

## 2. Billetterie (`billetterie`) — Depart, Ticket

| Ressource | Lecture | Écriture |
|---|---|---|
| **Depart** (planification) | Tous les rôles de la compagnie | `chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg` |
| **Ticket** (vente) | Tous les rôles de la compagnie | `guichetier` et tout rôle qui lui est hiérarchiquement supérieur (`chef_ligne`, `chef_gare`, `directeur_exploitation`, `qhse`, `secretaire_general`, `pdg`) |
| **Places restantes** (`/departs/{id}/places-restantes/`) | Tous les rôles de la compagnie | — (lecture seule) |
| **Réservation de places hors ligne** (`/tickets/reserver-hors-ligne/`, POST/DELETE) | — | `guichetier` et les rôles qui lui sont supérieurs, pour leurs propres réservations uniquement |
| **Clôture de caisse** (`/tickets/cloture-caisse/`) | `guichetier` (uniquement la sienne) et les rôles supérieurs (peuvent consulter celle de n'importe quel guichetier de la compagnie) | — (lecture seule) |
| **Remplaçants possibles** (`/departs/{id}/remplacants-possibles/`) | `chef_ligne`, `chef_gare`, `directeur_exploitation`, `secretaire_general`, `pdg` (et `superadmin`) uniquement : c'est un annuaire des chauffeurs libres | — (lecture seule) |

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
| **FeuilleDeRoute** / **ChecklistDepart** | Tous les rôles de la compagnie | `chauffeur_principal` / `chauffeur_relais` (uniquement leurs propres feuilles/checklists), `chef_ligne`, `chef_gare`, `directeur_exploitation`, `controleur_ligne`, `qhse`, `secretaire_general`, `pdg` |
| **Incident** | Tous les rôles de la compagnie | mêmes rôles que ci-dessus (un chauffeur ne déclare/modifie que ses propres incidents) |
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
| **OrdreReparation** — modification/suppression | — | `chef_atelier` (tout ordre), le `mecanicien` assigné (uniquement son propre ordre) |
| **SortiePiece** | Tous les rôles de la compagnie | `magasinier`, `chef_atelier`, `directeur_technique` |

Règles métier automatiques (aucun rôle ne peut les contourner) : un `OrdreReparation` créé sur
un véhicule déjà `bloque_securite`/`en_maintenance` passe le véhicule à `en_maintenance` ; un
`OrdreReparation` qui passe à `termine` remet le véhicule à `disponible` ; une `SortiePiece`
décrémente le stock et est refusée si le stock est insuffisant.

## 5. Supports (`supports`) — DossierAgent, Assurance, Sinistre, synthèse financière

| Ressource | Lecture | Écriture |
|---|---|---|
| **DossierAgent** | `drh` (tous les dossiers de la compagnie), chaque agent (uniquement le sien) | `drh` uniquement |
| **Agents sans dossier** (`/dossiers-agents/agents-sans-dossier/`) | `drh` uniquement (données RH : pas de transparence par défaut, `superadmin` inclus) | — (lecture seule) |
| **Assurance** | `responsable_juridique`, `directeur_technique` uniquement | `responsable_juridique`, `directeur_technique` |
| **Assurances à échéance proche** (`/assurances/echeance-proche/`) | `responsable_juridique`, `directeur_technique` uniquement | — (lecture seule) |
| **Sinistre** | `responsable_juridique`, `directeur_technique` uniquement | `responsable_juridique`, `directeur_technique` |
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

`role_coverage_tests/test_matrice_conformite.py` teste **les 18 rôles sur chaque endpoint restreint** contre les
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

---

## Synthèse par rôle

| Rôle | Peut voir (au-delà du droit de lecture générale) | Peut créer/modifier |
|---|---|---|
| `pdg` | Tout ce qui est en lecture générale, tableau de bord direction, synthèse financière | Gares, lignes, véhicules, départs, tickets |
| `secretaire_general` | Idem `pdg` | Gares, lignes, véhicules, départs, tickets |
| `qhse` | Tableau de bord direction et QHSE, incidents graves | Tickets, feuilles de route/checklists/incidents |
| `directeur_exploitation` | Tout ce qui est en lecture générale | Gares, lignes, véhicules, départs, tickets, feuilles de route/checklists/incidents, ordres de réparation (création) |
| `chef_gare` | — | Sa propre gare, départs, tickets, feuilles de route/checklists/incidents |
| `chef_ligne` | — | Lignes, départs, tickets, feuilles de route/checklists/incidents |
| `guichetier` | Sa propre clôture de caisse | Tickets |
| `bagagiste` | — | Aucun droit d'écriture particulier |
| `chauffeur_principal` | — | Ses propres feuilles de route, checklists, incidents |
| `chauffeur_relais` | — | Ses propres feuilles de route, checklists, incidents |
| `controleur_ligne` | — | Feuilles de route/checklists/incidents |
| `directeur_technique` | — | Véhicules, ordres de réparation (création), pièces, sorties de pièces, assurances, sinistres |
| `magasinier` | — | Pièces, sorties de pièces |
| `chef_atelier` | — | Véhicules, ordres de réparation (tous, création et modification), pièces, sorties de pièces |
| `drh` | Tous les dossiers agents de la compagnie | Dossiers agents |
| `directeur_financier` | Synthèse financière | Aucun droit d'écriture particulier |
| `responsable_juridique` | — | Assurances, sinistres |
