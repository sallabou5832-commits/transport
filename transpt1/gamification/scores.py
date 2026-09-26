"""Scores des gares et des lignes (classements inter-gares et inter-lignes) : ponctualité, remplissage, recettes."""

from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

from billetterie.models import Depart, StatutTicket, Ticket
from dashboard.ponctualite import pourcentage, statut_ponctualite
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Gare, Ligne

# Pondération du score d'une gare : la ponctualité pèse le plus (c'est ce que le cahier des charges met en avant), puis le
# remplissage des cars, puis les recettes (rapportées à la meilleure gare de la période).
POIDS_GARE = {"ponctualite": 50, "remplissage": 30, "recettes": 20}
POIDS_LIGNE = {"ponctualite": 60, "remplissage": 40}


def _mesures(company_id, debut, fin, maintenant):
    """(gare de départ, ligne) -> ponctualité et remplissage sur la période, pour les départs qui ont eu lieu ou ont dû avoir lieu."""
    par_gare, par_ligne = {}, {}
    departs = Depart.objects.filter(company_id=company_id, date_heure__gte=debut, date_heure__lt=fin).select_related(
        "ligne", "vehicule"
    )
    feuilles = FeuilleDeRoute.objects.filter(
        company_id=company_id, heure_depart_prevue__gte=debut, heure_depart_prevue__lt=fin
    ).select_related("depart__ligne")

    def case(dico, cle):
        return dico.setdefault(cle, {"places": 0, "capacite": 0, "a_l_heure": 0, "en_retard": 0, "departs": 0})

    for depart in departs:
        for dico, cle in ((par_gare, depart.ligne.gare_depart_id), (par_ligne, depart.ligne_id)):
            fiche = case(dico, cle)
            fiche["places"] += depart.places_vendues
            fiche["capacite"] += depart.vehicule.capacite
            fiche["departs"] += 1
    for feuille in feuilles:
        statut = statut_ponctualite(feuille, maintenant)
        if statut == "en_attente":
            continue
        ligne = feuille.depart.ligne
        for dico, cle in ((par_gare, ligne.gare_depart_id), (par_ligne, ligne.id)):
            case(dico, cle)["a_l_heure" if statut == "a_l_heure" else "en_retard"] += 1
    return par_gare, par_ligne


def _finaliser(fiche):
    mesures = fiche["a_l_heure"] + fiche["en_retard"]
    return {
        "ponctualite_pourcent": pourcentage(fiche["a_l_heure"], mesures),
        "remplissage_pourcent": pourcentage(fiche["places"], fiche["capacite"]),
        "departs": fiche["departs"],
    }


def _classer(lignes):
    """Trie par score décroissant et attribue le rang (ex æquo : même rang)."""
    lignes.sort(key=lambda ligne: (-ligne["score"], ligne["nom"]))
    rang, precedent = 0, None
    for index, ligne in enumerate(lignes, start=1):
        if ligne["score"] != precedent:
            rang, precedent = index, ligne["score"]
        ligne["rang"] = rang
    return lignes


def score_gares(company_id, debut, fin, maintenant=None):
    """Classement des gares (par gare de départ) sur la période [debut, fin)."""
    maintenant = maintenant or timezone.now()
    par_gare, _ = _mesures(company_id, debut, fin, maintenant)
    recettes = {
        ligne["gare"]: ligne["total"] or Decimal("0")
        for ligne in Ticket.objects.filter(
            company_id=company_id, statut=StatutTicket.VALIDE, date_vente__gte=debut, date_vente__lt=fin
        )
        .values(gare=F("depart__ligne__gare_depart_id"))
        .annotate(total=Sum("prix"))
        .order_by()
    }
    meilleure = max(recettes.values(), default=Decimal("0"))
    resultat = []
    for gare in Gare.objects.filter(company_id=company_id):
        fiche = _finaliser(par_gare.get(gare.id, {"places": 0, "capacite": 0, "a_l_heure": 0, "en_retard": 0, "departs": 0}))
        recette = recettes.get(gare.id, Decimal("0"))
        relative = round(100 * recette / meilleure) if meilleure else 0
        score = round(
            (fiche["ponctualite_pourcent"] or 0) * POIDS_GARE["ponctualite"] / 100
            + (fiche["remplissage_pourcent"] or 0) * POIDS_GARE["remplissage"] / 100
            + relative * POIDS_GARE["recettes"] / 100
        )
        resultat.append(
            {"id": gare.id, "nom": gare.nom, "score": score, "recettes": recette, "recettes_relatives_pourcent": relative, **fiche}
        )
    return _classer(resultat)


def score_lignes(company_id, debut, fin, maintenant=None):
    maintenant = maintenant or timezone.now()
    _, par_ligne = _mesures(company_id, debut, fin, maintenant)
    resultat = []
    for ligne in Ligne.objects.filter(company_id=company_id):
        fiche = _finaliser(par_ligne.get(ligne.id, {"places": 0, "capacite": 0, "a_l_heure": 0, "en_retard": 0, "departs": 0}))
        score = round(
            (fiche["ponctualite_pourcent"] or 0) * POIDS_LIGNE["ponctualite"] / 100
            + (fiche["remplissage_pourcent"] or 0) * POIDS_LIGNE["remplissage"] / 100
        )
        resultat.append({"id": ligne.id, "nom": ligne.nom, "score": score, **fiche})
    return _classer(resultat)
