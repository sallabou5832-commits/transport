"""Carnet de route numérique du conducteur : ses derniers trajets et les documents du véhicule qu'il conduit (assurance, contrôle
technique, visite), à présenter en cas de contrôle."""

import datetime

from django.db.models import Count
from django.utils import timezone

from dashboard.ponctualite import pourcentage, retard_minutes, statut_ponctualite
from personnel_roulant import suivi
from personnel_roulant.models import FeuilleDeRoute, Incident
from supports.conformite import documents_du_vehicule

NOMBRE_DE_TRAJETS = 30
FENETRE_JOURS = 30


def carnet_de_route(conducteur, maintenant=None):
    maintenant = maintenant or timezone.now()
    feuilles = list(
        FeuilleDeRoute.objects.filter(chauffeur=conducteur)
        .select_related("depart__ligne", "depart__vehicule")
        .order_by("-heure_depart_prevue")[:NOMBRE_DE_TRAJETS]
    )
    incidents = dict(
        Incident.objects.filter(feuille_de_route__in=feuilles)
        .values_list("feuille_de_route_id")
        .annotate(n=Count("id"))
        .order_by()
    )
    trajets = [
        {
            "feuille_de_route": f.id,
            "ligne": f.depart.ligne.nom,
            "vehicule": f.depart.vehicule.immatriculation,
            "depart_prevu": f.heure_depart_prevue,
            "depart_reel": f.heure_depart_reelle,
            "arrivee_reelle": f.heure_arrivee_reelle,
            "en_cours": f.heure_depart_reelle is not None and f.heure_arrivee_reelle is None,
            "ponctualite": statut_ponctualite(f, maintenant),
            "retard_minutes": retard_minutes(f, maintenant) if statut_ponctualite(f, maintenant) == "en_retard" else 0,
            "incidents": incidents.get(f.id, 0),
        }
        for f in feuilles
    ]

    # Le véhicule dont il faut les papiers : celui du trajet en cours, sinon du prochain trajet, sinon du dernier.
    en_cours = suivi.trajet_en_cours_de(conducteur)
    prochain = next((f for f in reversed(feuilles) if f.heure_depart_reelle is None), None)
    retenue = en_cours or prochain or (feuilles[0] if feuilles else None)
    vehicule = None
    if retenue is not None:
        v = retenue.depart.vehicule
        vehicule = {
            "id": v.id, "immatriculation": v.immatriculation, "capacite": v.capacite, "kilometrage": v.kilometrage,
            "trajet": "en cours" if retenue is en_cours else "prochain" if retenue is prochain else "dernier",
            **documents_du_vehicule(v, timezone.localdate(maintenant)),
        }

    recents = [t for t in trajets if t["depart_prevu"] >= maintenant - datetime.timedelta(days=FENETRE_JOURS) and t["depart_prevu"] <= maintenant]
    mesurables = [t for t in recents if t["ponctualite"] != "en_attente"]
    return {
        "trajets": trajets,
        "vehicule": vehicule,
        "statistiques": {
            "trajets_30_jours": len(recents),
            "ponctualite_30_jours_pourcent": pourcentage(sum(1 for t in mesurables if t["ponctualite"] == "a_l_heure"), len(mesurables)),
            "incidents_30_jours": sum(t["incidents"] for t in recents),
        },
    }
