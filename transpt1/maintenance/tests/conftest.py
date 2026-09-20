import pytest

from core.models import Role
from maintenance.models import OrdreReparation, Piece, StatutOrdreReparation
from reseau.models import Vehicule, VehiculeStatut


@pytest.fixture
def vehicule_a(db, company_a):
    return Vehicule.objects.create(
        immatriculation="CI-3000-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )


@pytest.fixture
def vehicule_bloque_a(db, company_a):
    return Vehicule.objects.create(
        immatriculation="CI-3001-AA",
        capacite=30,
        statut=VehiculeStatut.BLOQUE_SECURITE,
        company=company_a,
    )


@pytest.fixture
def mecanicien_a(user_factory, company_a):
    return user_factory("mecanicien_a", Role.BAGAGISTE, company=company_a)


@pytest.fixture
def mecanicien_a2(user_factory, company_a):
    return user_factory("mecanicien_a2", Role.BAGAGISTE, company=company_a)


@pytest.fixture
def chef_atelier_a(user_factory, company_a):
    return user_factory("chef_atelier_a", Role.CHEF_ATELIER, company=company_a)


@pytest.fixture
def magasinier_a(user_factory, company_a):
    return user_factory("magasinier_a", Role.MAGASINIER, company=company_a)


@pytest.fixture
def directeur_technique_a(user_factory, company_a):
    return user_factory("directeur_technique_a", Role.DIRECTEUR_TECHNIQUE, company=company_a)


@pytest.fixture
def piece_a(db, company_a):
    return Piece.objects.create(
        nom="Plaquette de frein", reference="REF-FREIN-001", quantite_stock=10, seuil_alerte=5, company=company_a
    )


@pytest.fixture
def piece_basse_a(db, company_a):
    return Piece.objects.create(
        nom="Filtre à huile", reference="REF-HUILE-001", quantite_stock=2, seuil_alerte=5, company=company_a
    )


@pytest.fixture
def ordre_a(db, company_a, vehicule_a, mecanicien_a):
    return OrdreReparation.objects.create(
        vehicule=vehicule_a,
        company=company_a,
        description="Vidange et contrôle général.",
        statut=StatutOrdreReparation.OUVERT,
        mecanicien=mecanicien_a,
    )
