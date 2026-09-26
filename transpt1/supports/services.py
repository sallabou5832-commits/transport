"""Ce que le juridique fait de l'actualité de l'exploitation : un accident déclaré ouvre son dossier de sinistre."""

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role
from personnel_roulant.models import GraviteIncident, TypeIncident
from supports.models import Sinistre, StatutSinistre


def ouvrir_sinistre_pour_incident(incident):
    """Un accident déclaré par le chauffeur ou le QHSE ouvre tout seul un dossier de sinistre lié à l'incident, et le responsable
    juridique en est prévenu. Une seule fois par incident. Renvoie le sinistre (nouveau ou existant), ou None si l'incident n'est pas un accident."""
    if incident.type_incident != TypeIncident.ACCIDENT:
        return None
    sinistre, cree = Sinistre.objects.get_or_create(
        incident=incident,
        defaults={
            "company": incident.company, "vehicule": incident.vehicule, "date": incident.date, "statut": StatutSinistre.OUVERT,
            "description": f"Accident déclaré : {incident.description}",
        },
    )
    if cree:
        alerter(
            incident.company,
            type=TypeAlerte.SINISTRE,
            gravite=GraviteAlerte.CRITIQUE if incident.gravite == GraviteIncident.GRAVE else GraviteAlerte.ATTENTION,
            titre=f"Sinistre à instruire : accident du véhicule {incident.vehicule.immatriculation}",
            message=incident.description,
            roles=[Role.RESPONSABLE_JURIDIQUE],
            objet=sinistre,
            cle=f"sinistre:incident:{incident.pk}",
        )
    return sinistre
