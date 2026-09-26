"""Ce que la finance sait dire de la compagnie : rentabilité par ligne et par gare, budget carburant, trésorerie. Lecture seule."""

import datetime
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from billetterie.models import StatutTicket, Ticket
from colis.models import Colis, StatutColis
from finance.models import BudgetCarburant, CategorieDepense, ConfigurationFinance, Depense, Facture, StatutFacture
from reseau.models import Gare, Ligne

ZERO = Decimal("0")
SEUIL_ALERTE_BUDGET = 80


def _pourcent(numerateur, denominateur):
    return round(100 * numerateur / denominateur) if denominateur else None


def _billets(company, debut, fin):
    return Ticket.objects.filter(company=company, statut=StatutTicket.VALIDE, date_vente__date__gte=debut, date_vente__date__lte=fin)


def _fret(company, debut, fin):
    return Colis.objects.filter(company=company, enregistre_le__date__gte=debut, enregistre_le__date__lte=fin).exclude(statut=StatutColis.ANNULE)


def rentabilite(company, debut, fin):
    """Recettes (billets et fret) contre dépenses, par ligne et par gare de départ, sur la période. Les dépenses sans ligne ni gare
    (salaires, frais généraux) sont des charges communes : elles pèsent sur le total, pas sur une ligne."""
    billets = {r["depart__ligne_id"]: r["total"] for r in _billets(company, debut, fin).values("depart__ligne_id").annotate(total=Sum("prix")).order_by()}
    fret = {r["depart__ligne_id"]: r["total"] for r in _fret(company, debut, fin).values("depart__ligne_id").annotate(total=Sum("frais")).order_by()}
    lignes = {l.id: l for l in Ligne.objects.filter(company=company).select_related("gare_depart")}
    depenses = list(Depense.objects.filter(company=company, date__gte=debut, date__lte=fin).select_related("ligne"))

    par_ligne = {
        lid: {"billets": billets.get(lid) or ZERO, "fret": fret.get(lid) or ZERO, "depenses": ZERO, "categories": {}} for lid in lignes
    }
    par_gare = {g.id: {"nom": g.nom, "recettes": ZERO, "depenses": ZERO} for g in Gare.objects.filter(company=company)}
    for lid, ligne in lignes.items():
        par_gare[ligne.gare_depart_id]["recettes"] += par_ligne[lid]["billets"] + par_ligne[lid]["fret"]
    communes = ZERO
    for d in depenses:
        if d.ligne_id in par_ligne:
            entree = par_ligne[d.ligne_id]
            entree["depenses"] += d.montant
            entree["categories"][d.categorie] = entree["categories"].get(d.categorie, ZERO) + d.montant
        gare_id = d.gare_id or (d.ligne.gare_depart_id if d.ligne_id else None)
        if gare_id in par_gare:
            par_gare[gare_id]["depenses"] += d.montant
        if d.ligne_id is None and d.gare_id is None:
            communes += d.montant

    lignes_vue = []
    for lid, entree in par_ligne.items():
        recettes = entree["billets"] + entree["fret"]
        if not (recettes or entree["depenses"]):
            continue
        marge = recettes - entree["depenses"]
        lignes_vue.append(
            {
                "id": lid, "nom": lignes[lid].nom, "gare": lignes[lid].gare_depart.nom, "recettes": recettes, "billets": entree["billets"],
                "fret": entree["fret"], "depenses": entree["depenses"], "marge": marge, "taux_marge_pourcent": _pourcent(marge, recettes),
                "depenses_par_categorie": entree["categories"],
            }
        )
    lignes_vue.sort(key=lambda l: l["marge"], reverse=True)
    gares_vue = [
        {
            "id": gid, "nom": g["nom"], "recettes": g["recettes"], "depenses": g["depenses"], "marge": g["recettes"] - g["depenses"],
            "taux_marge_pourcent": _pourcent(g["recettes"] - g["depenses"], g["recettes"]),
        }
        for gid, g in par_gare.items()
        if g["recettes"] or g["depenses"]
    ]
    gares_vue.sort(key=lambda g: g["marge"], reverse=True)
    total_recettes = sum((e["billets"] + e["fret"] for e in par_ligne.values()), ZERO)
    total_depenses = sum((d.montant for d in depenses), ZERO)
    return {
        "periode": {"debut": debut, "fin": fin},
        "lignes": lignes_vue,
        "gares": gares_vue,
        "charges_communes": communes,
        "total": {
            "recettes": total_recettes, "depenses": total_depenses, "marge": total_recettes - total_depenses,
            "taux_marge_pourcent": _pourcent(total_recettes - total_depenses, total_recettes),
        },
    }


def premier_du_mois(jour):
    return jour.replace(day=1)


def suivi_budget_carburant(company, mois):
    """Par ligne : le budget carburant du mois, ce qui a été dépensé, et l'état (ok, alerte à 80 %, dépassé)."""
    mois = premier_du_mois(mois)
    fin = (mois + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    realise = {
        r["ligne_id"]: r["total"]
        for r in Depense.objects.filter(
            company=company, categorie=CategorieDepense.CARBURANT, date__gte=mois, date__lte=fin, ligne__isnull=False
        )
        .values("ligne_id")
        .annotate(total=Sum("montant"))
        .order_by()
    }
    budgets = {b.ligne_id: b for b in BudgetCarburant.objects.filter(company=company, mois=mois).select_related("ligne")}
    lignes = []
    for ligne in Ligne.objects.filter(company=company):
        budget, depense = budgets.get(ligne.id), realise.get(ligne.id) or ZERO
        if budget is None and not depense:
            continue
        pourcent = _pourcent(depense, budget.montant) if budget else None
        if budget is None:
            etat = "sans_budget"
        elif depense > budget.montant:
            etat = "depasse"
        elif pourcent is not None and pourcent >= SEUIL_ALERTE_BUDGET:
            etat = "alerte"
        else:
            etat = "ok"
        lignes.append(
            {
                "ligne": ligne.id, "nom": ligne.nom, "budget": budget.montant if budget else None, "budget_id": budget.id if budget else None,
                "realise": depense, "pourcentage": pourcent, "reste": (budget.montant - depense) if budget else None, "etat": etat,
            }
        )
    lignes.sort(key=lambda l: (-(l["pourcentage"] or 0), l["nom"]))
    return {"mois": mois, "lignes": lignes, "depasses": sum(1 for l in lignes if l["etat"] == "depasse")}


def tresorerie(company, aujourdhui=None):
    """Trésorerie en temps réel : solde de départ + tout ce qui a été encaissé - tout ce qui a été dépensé, ce mois-ci, et ce qui reste à
    payer (factures) avec le solde prévisionnel à 30 jours."""
    aujourdhui = aujourdhui or timezone.localdate()
    debut_mois = premier_du_mois(aujourdhui)
    reglages = ConfigurationFinance.objects.filter(company=company).first()
    solde_initial = reglages.solde_initial if reglages else ZERO

    def encaisse(debut, fin):
        b = _billets(company, debut, fin).aggregate(t=Sum("prix"))["t"] or ZERO
        f = _fret(company, debut, fin).aggregate(t=Sum("frais"))["t"] or ZERO
        return b + f

    def decaisse(debut, fin):
        return Depense.objects.filter(company=company, date__gte=debut, date__lte=fin).aggregate(t=Sum("montant"))["t"] or ZERO

    origine = datetime.date(2000, 1, 1)
    encaissements, decaissements = encaisse(origine, aujourdhui), decaisse(origine, aujourdhui)
    factures = Facture.objects.filter(company=company, statut=StatutFacture.A_PAYER)
    en_retard = factures.filter(echeance__lt=aujourdhui).aggregate(t=Sum("montant"), n=Count("id"))
    a_30_jours = factures.filter(echeance__gte=aujourdhui, echeance__lte=aujourdhui + datetime.timedelta(days=30)).aggregate(
        t=Sum("montant"), n=Count("id")
    )
    a_7_jours = factures.filter(echeance__gte=aujourdhui, echeance__lte=aujourdhui + datetime.timedelta(days=7)).aggregate(t=Sum("montant"))
    solde = solde_initial + encaissements - decaissements
    a_payer_30 = (en_retard["t"] or ZERO) + (a_30_jours["t"] or ZERO)

    serie = []
    for i in range(29, -1, -1):
        jour = aujourdhui - datetime.timedelta(days=i)
        serie.append({"date": jour, "encaissements": encaisse(jour, jour), "decaissements": decaisse(jour, jour)})
    return {
        "date": aujourdhui,
        "solde_initial": solde_initial,
        "solde": solde,
        "mois": {"encaissements": encaisse(debut_mois, aujourdhui), "decaissements": decaisse(debut_mois, aujourdhui)},
        "a_payer": {
            "en_retard": en_retard["t"] or ZERO,
            "factures_en_retard": en_retard["n"],
            "sous_7_jours": a_7_jours["t"] or ZERO,
            "sous_30_jours": a_30_jours["t"] or ZERO,
            "factures_sous_30_jours": a_30_jours["n"],
        },
        "solde_previsionnel_30_jours": solde - a_payer_30,
        "serie_30_jours": serie,
    }
