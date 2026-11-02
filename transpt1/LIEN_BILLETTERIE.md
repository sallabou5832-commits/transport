# Relier un logiciel de billetterie à Transport Coord

Ce guide s'adresse à l'éditeur ou à l'informaticien du logiciel de billetterie qu'une compagnie utilise déjà. Il décrit les deux
façons de lui transmettre les ventes : l'**API** (en temps réel) et l'**import d'un fichier** (CSV ou Excel). Les droits de
chacun sont dans `PERMISSIONS.md` §22.

## 1. Ce qu'il faut d'abord côté compagnie

1. Le PDG ou le directeur des opérations passe la billetterie en mode **mixte** (le guichet de Transport Coord continue de vendre)
   ou **externe** (seul le logiciel de la compagnie vend) : `PATCH /api/lien-billetterie/reglage/` `{"mode": "mixte"}`.
   En mode `integre` (défaut), l'API et l'import répondent 403.
2. Pour l'API : il crée une clé pour le logiciel, `POST /api/lien-billetterie/cles/` `{"logiciel": "NomDuLogiciel"}`. La réponse
   contient la clé (`"cle": "lb_…"`) **une seule fois** : la copier aussitôt dans la configuration du logiciel. Une clé perdue ne
   se retrouve pas : la révoquer (`POST /api/lien-billetterie/cles/{id}/revoquer/`) et en créer une autre.

## 2. L'API

Chaque appel porte l'en-tête `Authorization: ApiKey lb_…`. La clé n'ouvre que les trois routes ci-dessous, pour une seule
compagnie. Sans clé ou avec une clé invalide ou révoquée : 401. Compagnie en mode `integre` : 403. Les corps sont en JSON.

### Lire le planning — `GET /api/lien-billetterie/departs/?du=AAAA-MM-JJ&au=AAAA-MM-JJ`

Par défaut, aujourd'hui et les 7 jours suivants ; 31 jours au plus.

```json
[{"id": 412, "ligne": 3, "ligne_nom": "Adjamé-Bouaké", "gare_depart": "Adjamé", "gare_arrivee": "Bouaké",
  "date_heure": "2026-11-02T08:00:00Z", "statut": "planifie", "ligne_fermee": false,
  "capacite": 70, "places_vendues": 41, "places_disponibles": 25, "tarif": "5000.00"}]
```

`places_disponibles` est ce que le logiciel peut vendre maintenant : les places mises de côté pour la vente hors ligne des guichets
n'en font pas partie.

### Envoyer des ventes — `POST /api/lien-billetterie/ventes/`

```json
{"ventes": [
  {"reference": "BP-2026-000123", "depart": 412,
   "passager_nom": "Awa Koné", "passager_telephone": "+2250700000001",
   "prix": "5000", "mode_paiement": "mobile_money", "vendu_le": "2026-11-01T17:42:00Z"}
]}
```

| Champ | Obligatoire | Règle |
|---|---|---|
| `reference` | oui | Le numéro du billet dans votre logiciel, 64 caractères au plus. C'est lui que le contrôleur saisit à bord (majuscules, espaces et tirets ignorés). |
| `depart` | oui, ou `ligne` + `date_heure` | L'`id` lu dans le planning. Sinon : `ligne` (son nom ou son `id`) et `date_heure` du départ, à la minute près (`2026-11-02T08:00:00Z`, `2026-11-02 08:00` ou `02/11/2026 08:00`, heure de la compagnie si aucun fuseau n'est donné). |
| `passager_nom` | oui | 255 caractères au plus. |
| `passager_telephone` | non | 30 caractères au plus. |
| `prix` | non | Sans prix, le tarif de la ligne ; obligatoire si la ligne n'a pas de tarif. Un prix différent du tarif est accepté et signalé à la compagnie. |
| `mode_paiement` | oui | `especes` ou `mobile_money`. |
| `vendu_le` | non | La date de la vente (sinon, sa réception) ; jamais dans le futur. |

500 ventes au plus par envoi. Chaque vente est traitée à part ; la réponse (200) dit ce qu'il en est advenu :

```json
{"resultats": [
   {"reference": "BP-2026-000123", "statut": "creee", "ticket": 9031, "code": "7KQ2M9XPLA"},
   {"reference": "BP-2026-000124", "statut": "refusee", "erreurs": {"depart": ["Plus aucune place disponible sur ce départ."]}}],
 "creee": 1, "deja_recue": 0, "annulee": 0, "deja_annulee": 0, "refusee": 1}
```

- `creee` : le billet existe. `deja_recue` : cette `reference` est déjà enregistrée, rien n'a changé. **Renvoyer un lot (après une
  coupure, un délai dépassé) est donc sans danger** : c'est la façon de faire en cas de doute.
- `refusee` : rien n'est enregistré pour cette vente ; `erreurs` dit pourquoi (départ introuvable, complet, mode de paiement
  inconnu…). Corriger puis renvoyer.
- Un corps mal formé (pas de liste `ventes`, plus de 500 ventes) : 400, rien n'est traité.

### Annuler des ventes — `POST /api/lien-billetterie/annulations/`

```json
{"annulations": [{"reference": "BP-2026-000123", "motif": "client absent"}]}
```

Réponse du même format : `annulee` (la place est rendue, la vente sort des recettes), `deja_annulee`, ou `refusee` (référence
inconnue). Seules les ventes reçues de votre logiciel s'annulent ainsi.

## 3. L'import de fichier

Pour un logiciel qui ne sait qu'exporter. Le directeur des opérations ou le PDG (toutes les gares), ou le chef de gare (les départs
de sa gare), dépose le fichier : `POST /api/lien-billetterie/imports/` en `multipart/form-data`, champs `fichier` et `logiciel`.

- Formats : **CSV** (`;`, `,` ou tabulation ; UTF-8 ou l'encodage Windows d'Excel) ou **Excel** `.xlsx` (première feuille).
  5 Mo et 5 000 ventes au plus par fichier.
- Une ligne d'en-tête, puis une vente par ligne. Les noms courants sont reconnus, sans tenir compte des accents ni des majuscules :

| Champ | Noms de colonnes reconnus (exemples) |
|---|---|
| `reference` | Référence, N° billet, Numéro billet, Code billet, Ticket |
| `depart` | Départ, Id départ |
| `ligne` | Ligne, Trajet, Itinéraire |
| `date_heure` | Date heure, Date et heure — ou deux colonnes : Date (Date départ, Jour) et Heure (Heure départ) |
| `passager_nom` | Passager, Nom, Client, Voyageur |
| `passager_telephone` | Téléphone, Tél, Contact |
| `prix` | Prix, Montant, Tarif (« 5 000 FCFA » et « 5000,00 » sont compris) |
| `mode_paiement` | Mode de paiement, Moyen de paiement, Paiement (Espèces, Cash, Mobile money, Orange Money, MTN, Moov, Wave…) |
| `vendu_le` | Date de vente, Vendu le |

- Obligatoires : référence, passager, mode de paiement, et le départ (identifiant, ou ligne avec date et heure). Sans elles, le
  fichier est refusé en entier (400), avec la liste des colonnes lues.
- Chaque ligne est traitée comme une vente reçue par l'API : réimporter le même fichier ne double rien. Le compte rendu
  (`GET /api/lien-billetterie/imports/{id}/`) dit, ligne par ligne, ce qui a été créé, déjà reçu ou refusé, et pourquoi.

## 4. Ce que devient une vente reçue

Un vrai billet : il prend sa place sur le départ (jamais celles réservées aux guichets hors ligne), compte dans les recettes et les
tableaux de bord, et se contrôle à bord par sa référence. Il n'entre dans la caisse d'aucun guichetier et ne déclenche aucun SMS :
l'encaissement et la confirmation au voyageur restent ceux de votre logiciel.
