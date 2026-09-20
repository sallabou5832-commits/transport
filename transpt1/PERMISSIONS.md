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
| **Clôture de caisse** (`/tickets/cloture-caisse/`) | `guichetier` (uniquement la sienne) et les rôles supérieurs (peuvent consulter celle de n'importe quel guichetier de la compagnie) | — (lecture seule) |

## 3. Personnel roulant (`personnel_roulant`) — FeuilleDeRoute, ChecklistDepart, Incident

| Ressource | Lecture | Écriture |
|---|---|---|
| **FeuilleDeRoute** / **ChecklistDepart** | Tous les rôles de la compagnie | `chauffeur_principal` / `chauffeur_relais` (uniquement leurs propres feuilles/checklists), `chef_ligne`, `chef_gare`, `directeur_exploitation`, `controleur_ligne`, `qhse`, `secretaire_general`, `pdg` |
| **Incident** | Tous les rôles de la compagnie | mêmes rôles que ci-dessus (un chauffeur ne déclare/modifie que ses propres incidents) |
| **Incidents graves** (`/incidents/graves/`) | `qhse`, `directeur_exploitation` uniquement | — (lecture seule) |

Règle métier : un défaut de checklist sur un item de sécurité bloque automatiquement le
véhicule (`bloque_securite`) et empêche la feuille de route de démarrer, quel que soit le rôle
qui a saisi la checklist.

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
| **Assurance** | `responsable_juridique`, `directeur_technique` uniquement | `responsable_juridique`, `directeur_technique` |
| **Assurances à échéance proche** (`/assurances/echeance-proche/`) | `responsable_juridique`, `directeur_technique` uniquement | — (lecture seule) |
| **Sinistre** | `responsable_juridique`, `directeur_technique` uniquement | `responsable_juridique`, `directeur_technique` |
| **Synthèse financière** (`/synthese-financiere/`) | `directeur_financier`, `pdg`, `secretaire_general` uniquement | — (lecture seule) |

## 6. Tableau de bord (`dashboard`)

| Endpoint | Accès |
|---|---|
| `/dashboard/direction/` | `pdg`, `secretaire_general`, `qhse` uniquement |
| `/dashboard/qhse/` | `qhse` uniquement |

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
