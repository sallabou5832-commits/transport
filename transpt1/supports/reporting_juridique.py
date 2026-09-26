"""Le reporting juridique remonté à la Direction Générale : assurances, sinistres, litiges sociaux et conformité en une page, avec les points
de vigilance. Il ne contient aucune donnée personnelle (les litiges sociaux n'y figurent que comptés)."""

import datetime

from django.db.models import Sum
from django.utils import timezone

from rh.models import Doleance, GraviteDoleance, StatutDoleance
from supports.conformite import tableau_conformite
from supports.models import ModeleJuridique, Sinistre, StatutSinistre

SINISTRE_ANCIEN_JOURS = 30


def reporting_juridique(company, maintenant=None):
    maintenant = maintenant or timezone.now()
    aujourdhui = timezone.localdate(maintenant)
    conformite = tableau_conformite(company, maintenant)["resume"]

    sinistres = Sinistre.objects.filter(company=company)
    ouverts = sinistres.exclude(statut=StatutSinistre.CLOS)
    anciens = ouverts.filter(date__lt=maintenant - datetime.timedelta(days=SINISTRE_ANCIEN_JOURS)).count()
    delais = [(s.clos_le - s.date).days for s in sinistres.filter(clos_le__isnull=False)]
    par_statut = {statut: sinistres.filter(statut=statut).count() for statut in StatutSinistre.values}

    litiges = Doleance.objects.filter(company=company, litige_signale_le__isnull=False)
    litiges_ouverts = litiges.exclude(statut__in=(StatutDoleance.RESOLUE, StatutDoleance.SANS_SUITE))
    litiges_critiques = litiges_ouverts.filter(gravite=GraviteDoleance.CRITIQUE).count()

    vehicules = conformite["vehicules"]
    sans_couverture = conformite["assurances_expirees"] + conformite["assurances_absentes"]
    assurances = {
        "vehicules": vehicules,
        "couverts_pourcent": round(100 * (vehicules - sans_couverture) / vehicules) if vehicules else None,
        "expirees": conformite["assurances_expirees"],
        "absentes": conformite["assurances_absentes"],
        "a_renouveler_30_jours": conformite["assurances_bientot_echues"],
    }
    vigilance = []
    for nombre, texte in (
        (assurances["expirees"], "véhicule(s) avec une assurance expirée"),
        (assurances["absentes"], "véhicule(s) sans assurance enregistrée"),
        (assurances["a_renouveler_30_jours"], "assurance(s) à renouveler sous 30 jours"),
        (anciens, f"sinistre(s) ouvert(s) depuis plus de {SINISTRE_ANCIEN_JOURS} jours"),
        (litiges_critiques, "litige(s) social(aux) critique(s) ouvert(s)"),
        (litiges_ouverts.count() - litiges_critiques, "autre(s) litige(s) social(aux) ouvert(s)"),
        (conformite["obligations_en_retard"], "obligation(s) réglementaire(s) en retard"),
        (conformite["vehicules_bloques"], "véhicule(s) bloqué(s) pour raison de sécurité"),
    ):
        if nombre:
            vigilance.append(f"{nombre} {texte}")

    return {
        "date": aujourdhui,
        "assurances": assurances,
        "sinistres": {
            "total": sinistres.count(),
            **par_statut,
            "anciens_ouverts": anciens,
            "montant_estime_en_cours": ouverts.aggregate(t=Sum("montant_estime"))["t"] or 0,
            "montant_indemnise": sinistres.aggregate(t=Sum("montant_indemnise"))["t"] or 0,
            "delai_moyen_cloture_jours": round(sum(delais) / len(delais)) if delais else None,
            "recents": [
                {
                    "id": s.id, "date": s.date, "statut": s.statut, "vehicule": s.vehicule.immatriculation if s.vehicule else None,
                    "description": s.description[:120],
                }
                for s in sinistres.select_related("vehicule")[:5]
            ],
        },
        "litiges_sociaux": {
            "ouverts": litiges_ouverts.count(),
            "critiques": litiges_critiques,
            "resolus_30_jours": litiges.filter(
                statut=StatutDoleance.RESOLUE, modifie_le__gte=maintenant - datetime.timedelta(days=30)
            ).count(),
        },
        "conformite": {
            "taux_pourcent": conformite["taux_conformite_pourcent"],
            "vehicules_non_conformes": vehicules - conformite["conformes"],
            "obligations_en_retard": conformite["obligations_en_retard"],
        },
        "modeles_disponibles": ModeleJuridique.objects.filter(company=company).count(),
        "points_de_vigilance": vigilance,
    }
