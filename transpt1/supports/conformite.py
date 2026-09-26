"""Tableau de conformité réglementaire, partagé par le QHSE et le juridique : pour chaque véhicule, l'assurance, les obligations
réglementaires (contrôle technique, visite…), les défauts de sécurité ouverts et le blocage éventuel. Lecture seule."""

from django.db.models import Count, Prefetch
from django.utils import timezone

from maintenance import preventif
from maintenance.models import PlanEntretien
from personnel_roulant.models import BlocageSecurite, ChecklistDepart, EtatChecklist
from reseau.models import Vehicule, VehiculeStatut

PREAVIS_ASSURANCE_JOURS = 30


def _assurance(vehicule, aujourdhui):
    """L'assurance la plus récente du véhicule : valide, bientôt échue (30 jours), expirée ou absente."""
    assurances = list(vehicule.assurances.all())
    if not assurances:
        return {"etat": "absente", "date_echeance": None, "jours_restants": None, "police": None}
    derniere = max(assurances, key=lambda a: a.date_echeance)
    jours = (derniere.date_echeance - aujourdhui).days
    etat = "expiree" if jours < 0 else "bientot" if jours <= PREAVIS_ASSURANCE_JOURS else "valide"
    return {"etat": etat, "date_echeance": derniere.date_echeance, "jours_restants": jours, "police": derniere.numero_police}


def documents_du_vehicule(vehicule, aujourdhui=None):
    """Les documents d'un véhicule que son conducteur doit pouvoir présenter : assurance (police, échéance) et obligations
    réglementaires (contrôle technique, visite…) avec leurs échéances."""
    aujourdhui = aujourdhui or timezone.localdate()
    obligations = []
    for plan in vehicule.plans_entretien.filter(actif=True, reglementaire=True):
        e = preventif.echeance(plan, aujourdhui)
        obligations.append(
            {
                "plan": plan.id, "libelle": plan.libelle, "etat": e["etat"], "derniere_date": plan.derniere_date,
                "prochaine_date": e["prochaine_date"], "jours_restants": e["jours_restants"],
            }
        )
    return {"assurance": _assurance(vehicule, aujourdhui), "obligations": obligations}


def tableau_conformite(company, maintenant=None):
    maintenant = maintenant or timezone.now()
    aujourdhui = timezone.localdate(maintenant)
    vehicules = list(
        Vehicule.objects.filter(company=company)
        .prefetch_related(
            "assurances",
            Prefetch("plans_entretien", queryset=PlanEntretien.objects.filter(actif=True, reglementaire=True), to_attr="obligations"),
        )
        .order_by("immatriculation")
    )
    defauts = dict(
        ChecklistDepart.objects.filter(
            company=company, etat=EtatChecklist.DEFAUT, feuille_de_route__heure_arrivee_reelle__isnull=True
        )
        .values_list("feuille_de_route__depart__vehicule_id")
        .annotate(n=Count("id"))
    )
    bloques = set(BlocageSecurite.objects.filter(company=company, leve_le__isnull=True).values_list("vehicule_id", flat=True))

    lignes = []
    for vehicule in vehicules:
        assurance = _assurance(vehicule, aujourdhui)
        obligations = []
        for plan in vehicule.obligations:
            e = preventif.echeance(plan, aujourdhui)
            obligations.append(
                {
                    "plan": plan.id, "libelle": plan.libelle, "etat": e["etat"], "prochaine_date": e["prochaine_date"],
                    "jours_restants": e["jours_restants"], "km_restants": e["km_restants"],
                }
            )
        bloque = vehicule.statut == VehiculeStatut.BLOQUE_SECURITE or vehicule.id in bloques
        nombre_defauts = defauts.get(vehicule.id, 0)

        motifs = []
        if assurance["etat"] == "absente":
            motifs.append("Aucune assurance enregistrée")
        elif assurance["etat"] == "expiree":
            motifs.append(f"Assurance expirée depuis {-assurance['jours_restants']} jour(s)")
        for obligation in obligations:
            if obligation["etat"] == "en_retard":
                motifs.append(f"{obligation['libelle']} en retard")
        if bloque:
            motifs.append("Véhicule bloqué pour raison de sécurité")
        if nombre_defauts:
            motifs.append(f"{nombre_defauts} défaut(s) de checklist ouvert(s)")
        lignes.append(
            {
                "vehicule": vehicule.id,
                "immatriculation": vehicule.immatriculation,
                "statut": vehicule.statut,
                "assurance": assurance,
                "obligations": obligations,
                "defauts_ouverts": nombre_defauts,
                "bloque": bloque,
                "conforme": not motifs,
                "motifs": motifs,
            }
        )

    conformes = sum(1 for ligne in lignes if ligne["conforme"])
    return {
        "genere_le": maintenant,
        "resume": {
            "vehicules": len(lignes),
            "conformes": conformes,
            "taux_conformite_pourcent": round(100 * conformes / len(lignes)) if lignes else None,
            "assurances_expirees": sum(1 for l in lignes if l["assurance"]["etat"] == "expiree"),
            "assurances_absentes": sum(1 for l in lignes if l["assurance"]["etat"] == "absente"),
            "assurances_bientot_echues": sum(1 for l in lignes if l["assurance"]["etat"] == "bientot"),
            "obligations_en_retard": sum(1 for l in lignes for o in l["obligations"] if o["etat"] == "en_retard"),
            "obligations_bientot_dues": sum(1 for l in lignes for o in l["obligations"] if o["etat"] == "bientot"),
            "vehicules_bloques": sum(1 for l in lignes if l["bloque"]),
            "vehicules_sans_obligation_declaree": sum(1 for l in lignes if not l["obligations"]),
        },
        "vehicules": sorted(lignes, key=lambda l: (l["conforme"], l["immatriculation"])),
    }
