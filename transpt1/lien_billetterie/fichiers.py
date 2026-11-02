"""Lire le fichier de ventes exporté par le logiciel de billetterie d'une compagnie : CSV (séparé par « ; », « , » ou une
tabulation, UTF-8 ou l'encodage Windows d'Excel) ou Excel (.xlsx, première feuille). Une ligne d'en-tête, puis une vente par
ligne. Les noms de colonnes courants sont reconnus, accents, majuscules et espaces ignorés (« N° billet », « Montant »,
« Téléphone », « Date de vente »…) ; la date et l'heure du départ peuvent être en une colonne ou en deux."""

import csv
import datetime
import io
import re
import unicodedata
import zipfile

from rest_framework.exceptions import ValidationError

TAILLE_MAX_MO = 5
LIGNES_MAX = 5000

# Champ d'une vente (voir `services.VenteExterneSerializer`) → noms de colonnes reconnus, déjà normalisés (`_normaliser`).
COLONNES = {
    "reference": (
        "reference", "ref", "numero", "numero_billet", "n_billet", "no_billet", "billet", "code", "code_billet", "ticket",
        "numero_ticket", "n_ticket",
    ),
    "depart": ("depart", "id_depart", "depart_id"),
    "ligne": ("ligne", "trajet", "itineraire", "nom_ligne"),
    "date_heure": ("date_heure", "date_heure_depart", "depart_le", "date_et_heure"),
    "date": ("date", "date_depart", "date_du_depart", "jour", "jour_depart"),
    "heure": ("heure", "heure_depart", "heure_du_depart"),
    "passager_nom": ("passager_nom", "passager", "nom", "nom_passager", "nom_du_passager", "client", "nom_client", "voyageur"),
    "passager_telephone": (
        "passager_telephone", "telephone", "tel", "contact", "telephone_passager", "telephone_client", "numero_telephone",
    ),
    "prix": ("prix", "montant", "tarif", "prix_billet", "prix_du_billet"),
    "mode_paiement": ("mode_paiement", "mode_de_paiement", "paiement", "moyen_paiement", "moyen_de_paiement", "mode"),
    "vendu_le": ("vendu_le", "date_vente", "date_de_vente", "vente_le", "date_heure_vente"),
}
OBLIGATOIRES = ("reference", "passager_nom", "mode_paiement")

# Ce que les logiciels écrivent pour un moyen de paiement, normalisé → nos modes (`billetterie.ModePaiement`).
MODES_PAIEMENT = {
    "especes": "especes", "espece": "especes", "cash": "especes", "liquide": "especes", "comptant": "especes",
    "mobile_money": "mobile_money", "mobile": "mobile_money", "momo": "mobile_money", "orange_money": "mobile_money",
    "mtn_money": "mobile_money", "mtn_momo": "mobile_money", "moov_money": "mobile_money", "flooz": "mobile_money",
    "wave": "mobile_money",
}


def _normaliser(texte):
    """« N° de billet » → « n_de_billet » : sans accents ni majuscules, un seul « _ » entre les mots."""
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texte.lower()).strip("_")


def _texte(valeur):
    """Une cellule en texte : une date ou une heure d'Excel au format que lit le sérialiseur, un nombre sans « .0 »."""
    if valeur is None:
        return ""
    if isinstance(valeur, datetime.datetime):
        return valeur.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valeur, datetime.date):
        return valeur.isoformat()
    if isinstance(valeur, datetime.time):
        return valeur.strftime("%H:%M")
    if isinstance(valeur, float) and valeur.is_integer():
        return str(int(valeur))
    return str(valeur).strip()


def _prix(texte):
    """« 5 000 FCFA », « 5000,00 » → « 5000.00 » ; le sérialiseur refuse ensuite ce qui n'est pas un montant."""
    texte = re.sub(r"[\s  ]|f\s*cfa|fcfa|xof|f$", "", texte, flags=re.IGNORECASE)
    return texte.replace(",", ".")


def _rangees_csv(fichier):
    brut = fichier.read()
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("cp1252", errors="replace")  # « CSV (séparateur : point-virgule) » d'Excel en français
    try:
        separateur = csv.Sniffer().sniff(texte[:4096], delimiters=";,\t").delimiter
    except csv.Error:
        separateur = ";"
    return csv.reader(io.StringIO(texte), delimiter=separateur)


def _rangees_excel(fichier):
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException

    try:
        classeur = openpyxl.load_workbook(fichier, read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, ValueError, OSError):
        raise ValidationError({"fichier": "Ce fichier Excel est illisible : enregistrez-le au format .xlsx ou en CSV."})
    try:
        for rangee in classeur.worksheets[0].iter_rows(values_only=True):
            yield rangee
    finally:
        classeur.close()


def lire_ventes(fichier):
    """Les ventes du fichier : `[(numéro de ligne dans le fichier, {champ: texte})]`, sans les lignes vides. Lève
    ValidationError si le fichier est trop gros, d'un autre format, sans en-tête reconnu ou trop long."""
    if fichier.size > TAILLE_MAX_MO * 1024 * 1024:
        raise ValidationError({"fichier": f"Ce fichier dépasse {TAILLE_MAX_MO} Mo : découpez-le."})
    nom = (fichier.name or "").lower()
    if nom.endswith(".xlsx"):
        rangees = _rangees_excel(fichier)
    elif nom.endswith((".csv", ".txt")):
        rangees = _rangees_csv(fichier)
    else:
        raise ValidationError({"fichier": "Format attendu : CSV (.csv) ou Excel (.xlsx)."})

    colonnes, ventes = None, []
    for numero, rangee in enumerate(rangees, start=1):
        cellules = [_texte(valeur) for valeur in rangee]
        if not any(cellules):
            continue
        if colonnes is None:
            colonnes = _colonnes(cellules)
            continue
        if len(ventes) >= LIGNES_MAX:
            raise ValidationError({"fichier": f"Plus de {LIGNES_MAX} ventes dans ce fichier : découpez-le."})
        ventes.append((numero, _vente(colonnes, cellules)))
    if colonnes is None:
        raise ValidationError({"fichier": "Ce fichier est vide."})
    return ventes


def _colonnes(entete):
    """{index de colonne: champ} d'après la ligne d'en-tête ; refuse un en-tête où manque une colonne indispensable."""
    connus = {nom: champ for champ, noms in COLONNES.items() for nom in noms}
    colonnes = {}
    for index, titre in enumerate(entete):
        champ = connus.get(_normaliser(titre))
        if champ is not None and champ not in colonnes.values():
            colonnes[index] = champ
    trouves = set(colonnes.values())
    manquants = [champ for champ in OBLIGATOIRES if champ not in trouves]
    heure_du_depart = "date_heure" in trouves or {"date", "heure"} <= trouves
    if "depart" not in trouves and not ("ligne" in trouves and heure_du_depart):
        manquants.append("depart (ou ligne avec date_heure, ou ligne avec date et heure)")
    if manquants:
        raise ValidationError(
            {"fichier": f"Colonnes introuvables dans l'en-tête : {', '.join(manquants)}. Colonnes lues : {', '.join(entete)}."}
        )
    return colonnes


def _vente(colonnes, cellules):
    vente = {champ: cellules[index] for index, champ in colonnes.items() if index < len(cellules)}
    date, heure = vente.pop("date", ""), vente.pop("heure", "")
    if not vente.get("date_heure") and date and heure:
        vente["date_heure"] = f"{date[:10]} {heure[:5]}" if re.match(r"\d{4}-\d{2}-\d{2}", date) else f"{date} {heure[:5]}"
    if vente.get("prix"):
        vente["prix"] = _prix(vente["prix"])
    if vente.get("mode_paiement"):
        vente["mode_paiement"] = MODES_PAIEMENT.get(_normaliser(vente["mode_paiement"]), vente["mode_paiement"])
    # Une cellule vide est une valeur absente (le tarif de la ligne pour le prix, la date de réception pour la vente).
    return {champ: valeur for champ, valeur in vente.items() if valeur != ""}
