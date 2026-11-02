import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from lien_billetterie.models import CleLienBilletterie, ModeBilletterie, ReglageBilletterie
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut

ROLES = ["pdg", "directeur_exploitation", "chef_gare", "guichetier", "chef_ligne", "directeur_financier", "qhse"]


@pytest.fixture
def agents(user_factory, company_a):
    return {role: user_factory(f"{role}_lien", getattr(Role, role.upper()), company=company_a) for role in ROLES}


@pytest.fixture
def reseau(company_a, agents, user_factory):
    """Deux gares (Adjamé, dirigée par le chef de gare ; Yamoussoukro, par un autre), une ligne au tarif de 5 000 FCFA
    depuis chacune, un car de 3 places, un départ demain à 8 h depuis chaque gare."""
    adjame = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=agents["chef_gare"])
    yakro = Gare.objects.create(
        nom="Yamoussoukro", ville="Yamoussoukro", company=company_a,
        chef=user_factory("autre_chef_gare_lien", Role.CHEF_GARE, company=company_a),
    )
    bouake = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(
        nom="Adjamé-Bouaké", gare_depart=adjame, gare_arrivee=bouake, company=company_a, tarif=Decimal("5000")
    )
    ligne_yakro = Ligne.objects.create(
        nom="Yamoussoukro-Bouaké", gare_depart=yakro, gare_arrivee=bouake, company=company_a, tarif=Decimal("3000")
    )
    vehicule = Vehicule.objects.create(immatriculation="CI-7000-LB", capacite=3, statut=VehiculeStatut.DISPONIBLE, company=company_a)
    chauffeur = user_factory("chauffeur_lien", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
    demain_8h = timezone.make_aware(
        datetime.datetime.combine(timezone.localdate() + datetime.timedelta(days=1), datetime.time(8, 0))
    )
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company_a, date_heure=demain_8h, statut=DepartStatut.PLANIFIE
    )
    depart_yakro = Depart.objects.create(
        ligne=ligne_yakro, vehicule=Vehicule.objects.create(immatriculation="CI-7001-LB", capacite=30, company=company_a),
        chauffeur=chauffeur, company=company_a, date_heure=demain_8h, statut=DepartStatut.PLANIFIE,
    )
    return {"ligne": ligne, "ligne_yakro": ligne_yakro, "depart": depart, "depart_yakro": depart_yakro, "demain_8h": demain_8h}


def passer_en(company, mode):
    ReglageBilletterie.objects.update_or_create(company=company, defaults={"mode": mode})


@pytest.fixture
def cle(company_a, agents):
    """Une clé d'API pour le logiciel « BilletPro », la compagnie en billetterie mixte. Renvoie la clé en clair."""
    passer_en(company_a, ModeBilletterie.MIXTE)
    _, en_clair = CleLienBilletterie.creer(company=company_a, logiciel="BilletPro", par=agents["pdg"])
    return en_clair


def avec_cle(api_client, cle):
    api_client.force_authenticate(user=None)
    api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {cle}")
    return api_client


def vente(sur, reference="BP-0001", **champs):
    """Une vente du logiciel sur le départ `sur` ; `champs` remplace ou ajoute des champs (dont `depart`)."""
    return {
        "reference": reference, "depart": sur.id, "passager_nom": "Awa Koné", "passager_telephone": "+2250700000001",
        "mode_paiement": "mobile_money", **champs,
    }
