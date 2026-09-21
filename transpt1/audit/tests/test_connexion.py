import json

import pytest

from audit.models import ActionAudit, JournalAudit
from core.models import Role

URL = "/api/auth/login/"


@pytest.mark.django_db
class TestConnexionsTracees:
    def test_une_connexion_reussie_est_tracee(self, api_client, user_factory, company_a):
        agent = user_factory("agent_connexion", Role.GUICHETIER, company=company_a)

        reponse = api_client.post(URL, {"username": "agent_connexion", "password": "Demo!2024"}, REMOTE_ADDR="198.51.100.4")

        assert reponse.status_code == 200
        entree = JournalAudit.objects.get(action=ActionAudit.CONNEXION)
        assert (entree.acteur, entree.company, entree.objet_repr) == (agent, company_a, "agent_connexion")
        assert entree.adresse_ip == "198.51.100.4"

    def test_un_mauvais_mot_de_passe_est_trace_sans_conserver_le_mot_de_passe(self, api_client, user_factory, company_a):
        user_factory("agent_echec", Role.GUICHETIER, company=company_a)

        reponse = api_client.post(URL, {"username": "agent_echec", "password": "essai-secret-123"})

        assert reponse.status_code == 401
        entree = JournalAudit.objects.get(action=ActionAudit.CONNEXION_ECHEC)
        assert entree.acteur is None and entree.acteur_nom == "agent_echec"
        contenu = json.dumps([entree.objet_repr, entree.acteur_nom, entree.changements, entree.objet_type])
        assert "essai-secret" not in contenu

    def test_un_identifiant_inconnu_est_trace_aussi(self, api_client):
        api_client.post(URL, {"username": "personne", "password": "x"})

        assert JournalAudit.objects.get(action=ActionAudit.CONNEXION_ECHEC).objet_repr == "personne"

    def test_quarante_essais_laissent_quarante_traces(self, api_client, user_factory, company_a):
        user_factory("cible", Role.GUICHETIER, company=company_a)

        for i in range(40):
            api_client.post(URL, {"username": "cible", "password": f"mauvais{i}"})

        assert JournalAudit.objects.filter(action=ActionAudit.CONNEXION_ECHEC, objet_repr="cible").count() == 40

    def test_l_adresse_est_la_derniere_entree_de_x_forwarded_for(self, api_client):
        # La première entrée vient du client (falsifiable), la dernière est celle que le proxy a ajoutée.
        api_client.post(URL, {"username": "a", "password": "b"}, HTTP_X_FORWARDED_FOR="6.6.6.6, 10.0.0.9")

        assert JournalAudit.objects.get().adresse_ip == "10.0.0.9"

    def test_une_adresse_invalide_n_est_pas_enregistree(self, api_client):
        api_client.post(URL, {"username": "a", "password": "b"}, HTTP_X_FORWARDED_FOR="pas-une-adresse")

        assert JournalAudit.objects.get().adresse_ip is None
