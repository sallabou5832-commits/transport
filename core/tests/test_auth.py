import pytest

from conftest import DEMO_PASSWORD


@pytest.mark.django_db
class TestLogin:
    def test_login_with_valid_credentials_returns_tokens(self, api_client, company_a_user):
        response = api_client.post(
            "/api/auth/login/",
            {"username": company_a_user.username, "password": DEMO_PASSWORD},
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_with_invalid_credentials_is_rejected(self, api_client, company_a_user):
        response = api_client.post(
            "/api/auth/login/",
            {"username": company_a_user.username, "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_refresh_returns_new_access_token(self, api_client, company_a_user):
        login_response = api_client.post(
            "/api/auth/login/",
            {"username": company_a_user.username, "password": DEMO_PASSWORD},
        )
        refresh_token = login_response.data["refresh"]

        response = api_client.post("/api/auth/refresh/", {"refresh": refresh_token})
        assert response.status_code == 200
        assert "access" in response.data


@pytest.mark.django_db
class TestMeEndpoint:
    def test_me_requires_authentication(self, api_client):
        response = api_client.get("/api/auth/me/")
        assert response.status_code == 401

    def test_me_returns_current_user_role_and_company(self, api_client, company_a_user, company_a):
        api_client.force_authenticate(user=company_a_user)

        response = api_client.get("/api/auth/me/")

        assert response.status_code == 200
        assert response.data["username"] == company_a_user.username
        assert response.data["role"] == company_a_user.role
        assert response.data["company"]["id"] == company_a.id
        assert response.data["company"]["name"] == company_a.name

    def test_me_for_superadmin_has_no_company(self, api_client, superadmin_user):
        api_client.force_authenticate(user=superadmin_user)

        response = api_client.get("/api/auth/me/")

        assert response.status_code == 200
        assert response.data["company"] is None
