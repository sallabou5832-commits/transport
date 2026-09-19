import pytest

from core.permissions import IsSameCompany


@pytest.mark.django_db
class TestCompanyDetailEndpoint:
    def test_user_can_access_own_company(self, api_client, company_a_user, company_a):
        api_client.force_authenticate(user=company_a_user)

        response = api_client.get(f"/api/companies/{company_a.id}/")

        assert response.status_code == 200
        assert response.data["id"] == company_a.id

    def test_user_cannot_access_other_company(self, api_client, company_a_user, company_b):
        api_client.force_authenticate(user=company_a_user)

        response = api_client.get(f"/api/companies/{company_b.id}/")

        assert response.status_code == 403

    def test_superadmin_can_access_any_company(self, api_client, superadmin_user, company_a, company_b):
        api_client.force_authenticate(user=superadmin_user)

        response_a = api_client.get(f"/api/companies/{company_a.id}/")
        response_b = api_client.get(f"/api/companies/{company_b.id}/")

        assert response_a.status_code == 200
        assert response_b.status_code == 200

    def test_anonymous_user_is_rejected(self, api_client, company_a):
        response = api_client.get(f"/api/companies/{company_a.id}/")
        assert response.status_code == 401


class FakeRequest:
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
class TestIsSameCompanyUnit:
    def test_denies_when_company_differs(self, company_a_user, company_b):
        permission = IsSameCompany()
        assert not permission.has_object_permission(FakeRequest(company_a_user), None, company_b)

    def test_allows_when_company_matches(self, company_a_user, company_a):
        permission = IsSameCompany()
        assert permission.has_object_permission(FakeRequest(company_a_user), None, company_a)

    def test_allows_superadmin_regardless_of_company(self, superadmin_user, company_a):
        permission = IsSameCompany()
        assert permission.has_object_permission(FakeRequest(superadmin_user), None, company_a)

    def test_denies_unauthenticated(self, company_a):
        from django.contrib.auth.models import AnonymousUser

        permission = IsSameCompany()
        assert not permission.has_object_permission(FakeRequest(AnonymousUser()), None, company_a)
