import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.models import Company, Role, User


@pytest.mark.django_db
class TestUserCompanyInvariant:
    def test_create_user_with_company(self, company_a):
        user = User.objects.create_user(
            username="guichetier1",
            password="Demo!2024",
            role=Role.GUICHETIER,
            company=company_a,
        )
        assert user.pk is not None
        assert user.company == company_a
        assert user.role == Role.GUICHETIER
        assert user.check_password("Demo!2024")

    def test_create_superadmin_without_company(self):
        user = User.objects.create_user(
            username="superadmin1", password="Demo!2024", role=Role.SUPERADMIN
        )
        assert user.company is None
        assert user.role == Role.SUPERADMIN

    def test_non_superadmin_without_company_fails_validation(self):
        user = User(username="orphan", role=Role.CHEF_GARE, company=None)
        with pytest.raises(ValidationError):
            user.full_clean()

    def test_superadmin_with_company_fails_validation(self, company_a):
        user = User(username="badsuperadmin", role=Role.SUPERADMIN, company=company_a)
        with pytest.raises(ValidationError):
            user.full_clean()

    def test_db_constraint_rejects_non_superadmin_without_company(self):
        user = User(username="raw_bypass", role=Role.CHEF_GARE, company=None)
        user.set_password("Demo!2024")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                user.save()


@pytest.mark.django_db
def test_company_str_and_fields():
    company = Company.objects.create(
        name="Ivoire Trans", headquarters_city="Yamoussoukro", created_at=datetime.date(2020, 1, 1)
    )
    assert str(company) == "Ivoire Trans"
