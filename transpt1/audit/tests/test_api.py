import datetime

import pytest
from django.utils import timezone

from audit.models import ActionAudit, JournalAudit
from core.models import Role

URL = "/api/audit/"
ROLES_AUTORISES = {"pdg", "secretaire_general", "qhse"}


@pytest.fixture
def journal(db, company_a, company_b):
    def entree(company, objet_type="billetterie.ticket", action=ActionAudit.CREATION, **kw):
        return JournalAudit.objects.create(company=company, objet_type=objet_type, action=action, objet_id="1", **kw)

    return {
        "a1": entree(company_a),
        "a2": entree(company_a, "personnel_roulant.incident", ActionAudit.MODIFICATION, acteur_nom="qhse"),
        "b1": entree(company_b),
    }


@pytest.mark.django_db
class TestConsultationDuJournal:
    @pytest.mark.parametrize("role", [r.value for r in Role if r != Role.SUPERADMIN])
    def test_seuls_la_direction_et_le_qhse_consultent(self, api_client, user_factory, company_a, journal, role):
        api_client.force_authenticate(user=user_factory(f"{role}_j", Role(role), company=company_a))

        assert api_client.get(URL).status_code == (200 if role in ROLES_AUTORISES else 403)

    def test_le_superadmin_consulte(self, api_client, superadmin_user, journal):
        api_client.force_authenticate(user=superadmin_user)

        assert api_client.get(URL).status_code == 200

    def test_non_authentifie_refuse(self, api_client, journal):
        assert api_client.get(URL).status_code == 401

    def test_une_compagnie_ne_voit_que_son_journal(self, api_client, user_factory, company_a, journal):
        api_client.force_authenticate(user=user_factory("pdg_j", Role.PDG, company=company_a))

        ids = {e["id"] for e in api_client.get(URL).data["results"]}

        assert {journal["a1"].id, journal["a2"].id} <= ids
        assert journal["b1"].id not in ids

    def test_le_superadmin_voit_toutes_les_compagnies(self, api_client, superadmin_user, journal):
        api_client.force_authenticate(user=superadmin_user)

        ids = {e["id"] for e in api_client.get(URL).data["results"]}

        assert {journal["a1"].id, journal["a2"].id, journal["b1"].id} <= ids

    def test_lecture_seule(self, api_client, user_factory, company_a, journal):
        api_client.force_authenticate(user=user_factory("pdg_ro", Role.PDG, company=company_a))
        cible = f"{URL}{journal['a1'].id}/"

        assert api_client.post(URL, {}).status_code == 405
        assert api_client.patch(cible, {"objet_repr": "x"}).status_code == 404  # pas de route de détail
        assert api_client.delete(cible).status_code == 404

    def test_le_plus_recent_d_abord(self, api_client, user_factory, company_a, journal):
        JournalAudit.objects.filter(pk=journal["a1"].pk)  # (inchangé : le journal est en lecture seule)
        recente = JournalAudit.objects.create(
            company=company_a, action=ActionAudit.CREATION, date=timezone.now() + datetime.timedelta(hours=1)
        )
        api_client.force_authenticate(user=user_factory("pdg_ordre", Role.PDG, company=company_a))

        assert api_client.get(URL).data["results"][0]["id"] == recente.id


@pytest.mark.django_db
class TestFiltresEtPagination:
    @pytest.fixture
    def client(self, api_client, user_factory, company_a, journal):
        api_client.force_authenticate(user=user_factory("pdg_filtre", Role.PDG, company=company_a))
        return api_client

    def test_filtre_par_type_d_objet(self, client, journal):
        ids = {e["id"] for e in client.get(URL, {"objet_type": "personnel_roulant.incident"}).data["results"]}
        assert ids == {journal["a2"].id}

    def test_filtre_par_action(self, client, journal):
        ids = {e["id"] for e in client.get(URL, {"action": "modification"}).data["results"]}
        assert ids == {journal["a2"].id}

    def test_filtre_par_dates(self, client, journal):
        aujourdhui = timezone.localdate().isoformat()
        demain = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()

        du_jour = {"objet_type": "billetterie.ticket", "date_debut": aujourdhui, "date_fin": aujourdhui}
        assert client.get(URL, du_jour).data["count"] == 1
        assert client.get(URL, {"date_debut": demain}).data["count"] == 0

    @pytest.mark.parametrize("parametres", [{"date_debut": "hier"}, {"date_fin": "2030-13-45"}, {"acteur": "abc"}])
    def test_un_filtre_invalide_est_refuse(self, client, parametres):
        assert client.get(URL, parametres).status_code == 400

    def test_pagination(self, client, journal):
        page = client.get(URL, {"limit": 1}).data

        assert page["count"] >= 2 and len(page["results"]) == 1 and page["next"]

    def test_la_taille_de_page_est_plafonnee(self, client, journal):
        assert client.get(URL, {"limit": 100000}).status_code == 200
