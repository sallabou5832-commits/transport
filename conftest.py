import datetime

import pytest
from rest_framework.test import APIClient

from core.models import Company, Role

DEMO_PASSWORD = "Demo!2024"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def company_a(db):
    return Company.objects.create(
        name="STC Voyages", headquarters_city="Abidjan", created_at=datetime.date(2005, 3, 1)
    )


@pytest.fixture
def company_b(db):
    return Company.objects.create(
        name="Express Savane", headquarters_city="Bouaké", created_at=datetime.date(2011, 9, 15)
    )


@pytest.fixture
def user_factory(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    def _create(username, role, company=None, **kwargs):
        user = User.objects.create_user(
            username=username, password=DEMO_PASSWORD, role=role, company=company, **kwargs
        )
        return user

    return _create


@pytest.fixture
def company_a_user(user_factory, company_a):
    return user_factory("chef_gare_a", Role.CHEF_GARE, company=company_a)


@pytest.fixture
def company_b_user(user_factory, company_b):
    return user_factory("chef_gare_b", Role.CHEF_GARE, company=company_b)


@pytest.fixture
def superadmin_user(user_factory):
    return user_factory("superadmin_test", Role.SUPERADMIN, company=None)
