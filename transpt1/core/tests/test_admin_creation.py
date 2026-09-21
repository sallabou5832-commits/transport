import pytest
from django.contrib.auth import get_user_model

from core.models import Role

URL_AJOUT = "/admin/core/user/add/"
MOT_DE_PASSE = "Zx9!kQ7#mLp2vB"


@pytest.fixture
def admin_connecte(client, superadmin_user):
    superadmin_user.is_staff = True
    superadmin_user.is_superuser = True
    superadmin_user.save()
    client.force_login(superadmin_user)
    return client


def _donnees(**champs):
    donnees = {"username": "nouvel_agent", "usable_password": "true", "password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE}
    donnees.update(champs)
    return donnees


@pytest.mark.django_db
class TestCreationDUnUtilisateurParLAdministration:
    """L'administration est le seul moyen de créer les vrais comptes : elle ne doit pas fabriquer
    de superadmin par inadvertance."""

    def test_le_role_n_est_pas_prechoisi(self, admin_connecte):
        reponse = admin_connecte.get(URL_AJOUT)

        champ = reponse.context["adminform"].form.fields["role"]
        assert champ.initial == ""
        assert champ.choices[0] == ("", "— Choisir un rôle —")
        assert champ.required

    def test_sans_role_le_compte_n_est_pas_cree(self, admin_connecte):
        reponse = admin_connecte.post(URL_AJOUT, _donnees())

        assert reponse.status_code == 200  # formulaire réaffiché avec l'erreur
        assert not get_user_model().objects.filter(username="nouvel_agent").exists()

    def test_avec_role_et_compagnie_le_compte_est_cree(self, admin_connecte, company_a):
        reponse = admin_connecte.post(URL_AJOUT, _donnees(role=Role.GUICHETIER, company=company_a.id))

        assert reponse.status_code == 302
        agent = get_user_model().objects.get(username="nouvel_agent")
        assert (agent.role, agent.company_id) == (Role.GUICHETIER, company_a.id)
        assert agent.check_password(MOT_DE_PASSE)

    def test_un_agent_sans_compagnie_est_refuse(self, admin_connecte):
        admin_connecte.post(URL_AJOUT, _donnees(role=Role.GUICHETIER))

        assert not get_user_model().objects.filter(username="nouvel_agent").exists()

    def test_un_superadmin_rattache_a_une_compagnie_est_refuse(self, admin_connecte, company_a):
        admin_connecte.post(URL_AJOUT, _donnees(role=Role.SUPERADMIN, company=company_a.id))

        assert not get_user_model().objects.filter(username="nouvel_agent").exists()

    def test_un_superadmin_reste_possible_quand_on_le_choisit_explicitement(self, admin_connecte):
        reponse = admin_connecte.post(URL_AJOUT, _donnees(username="second_operateur", role=Role.SUPERADMIN))

        assert reponse.status_code == 302
        assert get_user_model().objects.get(username="second_operateur").role == Role.SUPERADMIN

    def test_un_mot_de_passe_trop_faible_est_refuse(self, admin_connecte, company_a):
        admin_connecte.post(
            URL_AJOUT, _donnees(role=Role.GUICHETIER, company=company_a.id, password1="12345678", password2="12345678")
        )

        assert not get_user_model().objects.filter(username="nouvel_agent").exists()
