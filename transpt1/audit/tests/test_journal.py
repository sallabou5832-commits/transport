import json

import pytest

from audit.models import ActionAudit, JournalAudit, JournalImmuable
from billetterie.models import Depart, DepartStatut
from core.models import Role
from personnel_roulant.models import GraviteIncident, Incident, StatutIncident, TypeIncident
from reseau.models import Gare, Ligne, Vehicule


@pytest.fixture
def parc(db, company_a, user_factory):
    gare = Gare.objects.create(nom="Gare Adjamé", ville="Abidjan", company=company_a)
    ligne = Ligne.objects.create(nom="Abidjan-Bouaké", gare_depart=gare, gare_arrivee=gare, company=company_a)
    vehicule = Vehicule.objects.create(immatriculation="CI-AUDIT-1", capacite=50, company=company_a)
    chauffeur = user_factory("chauffeur_audit", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=chauffeur, company=company_a,
        date_heure="2030-01-01T10:00:00Z", statut=DepartStatut.PLANIFIE,
    )
    return {"gare": gare, "ligne": ligne, "vehicule": vehicule, "chauffeur": chauffeur, "depart": depart}


def _entrees(**filtres):
    return JournalAudit.objects.filter(**filtres)


@pytest.mark.django_db
class TestEnregistrementAutomatique:
    def test_une_vente_par_l_api_est_tracee_avec_son_acteur_et_son_adresse(self, api_client, user_factory, company_a, parc):
        guichetier = user_factory("guichetier_audit", Role.GUICHETIER, company=company_a)
        api_client.force_authenticate(user=guichetier)

        reponse = api_client.post(
            "/api/tickets/",
            {"depart": parc["depart"].id, "passager_nom": "Awa", "passager_telephone": "+2250700000001",
             "prix": "5000", "mode_paiement": "especes"},
            REMOTE_ADDR="203.0.113.7",
        )

        assert reponse.status_code == 201
        entree = _entrees(objet_type="billetterie.ticket").get()
        assert entree.action == ActionAudit.CREATION
        assert (entree.acteur, entree.acteur_nom, entree.acteur_role) == (guichetier, "guichetier_audit", "guichetier")
        assert entree.company == company_a
        assert entree.adresse_ip == "203.0.113.7"
        assert entree.objet_id == str(reponse.data["id"])
        assert entree.changements["prix"] == "5000.00"

    def test_une_modification_garde_l_avant_et_l_apres(self, api_client, user_factory, company_a, parc):
        qhse = user_factory("qhse_audit", Role.QHSE, company=company_a)
        incident = Incident.objects.create(
            vehicule=parc["vehicule"], chauffeur=parc["chauffeur"], company=company_a,
            type_incident=TypeIncident.PANNE, description="Panne", gravite=GraviteIncident.GRAVE,
            statut=StatutIncident.OUVERT,
        )
        api_client.force_authenticate(user=qhse)

        api_client.patch(f"/api/incidents/{incident.id}/", {"statut": "traite"})

        entree = _entrees(objet_type="personnel_roulant.incident", action=ActionAudit.MODIFICATION).get()
        assert entree.changements == {"statut": ["ouvert", "traite"]}
        assert entree.acteur == qhse

    def test_une_suppression_garde_l_etat_supprime(self, api_client, user_factory, company_a, parc):
        pdg = user_factory("pdg_audit", Role.PDG, company=company_a)
        vehicule = Vehicule.objects.create(immatriculation="CI-A-SUPPR", capacite=30, company=company_a)
        api_client.force_authenticate(user=pdg)

        reponse = api_client.delete(f"/api/vehicules/{vehicule.id}/")

        assert reponse.status_code == 204
        entree = _entrees(objet_type="reseau.vehicule", action=ActionAudit.SUPPRESSION).get()
        assert entree.changements["immatriculation"] == "CI-A-SUPPR"
        assert entree.acteur == pdg

    def test_un_changement_de_mot_de_passe_est_trace_sans_jamais_garder_de_secret(self, user_factory, company_a):
        agent = user_factory("agent_mdp", Role.GUICHETIER, company=company_a)
        avant = agent.password

        agent.set_password("Nouveau-Mdp-Secret-9!")
        agent.save()

        entree = _entrees(objet_type="core.user", action=ActionAudit.MODIFICATION).get()
        assert entree.changements == {"password": "modifié"}
        tout = json.dumps({"c": entree.changements, "r": entree.objet_repr})
        assert "Nouveau-Mdp" not in tout and avant not in tout and agent.password not in tout

    def test_une_action_hors_requete_est_attribuee_au_systeme(self, company_a):
        Gare.objects.create(nom="Gare seed", ville="X", company=company_a)

        entree = _entrees(objet_type="reseau.gare").get()
        assert entree.acteur is None and entree.acteur_nom == "système" and entree.acteur_role == ""

    def test_l_acteur_ne_fuit_pas_d_une_requete_a_la_suivante(self, api_client, user_factory, company_a):
        agent = user_factory("agent_fuite", Role.PDG, company=company_a)
        api_client.force_authenticate(user=agent)
        api_client.get("/api/gares/")

        Gare.objects.create(nom="Après la requête", ville="X", company=company_a)  # hors requête

        assert _entrees(objet_type="reseau.gare").get().acteur is None

    def test_le_compteur_de_places_seul_ne_fait_pas_de_bruit(self, parc):
        avant = JournalAudit.objects.count()

        parc["depart"].places_vendues += 1
        parc["depart"].save(update_fields=["places_vendues"])

        assert JournalAudit.objects.count() == avant

    def test_une_modification_sans_changement_reel_n_est_pas_tracee(self, parc):
        avant = JournalAudit.objects.count()

        parc["gare"].save()

        assert JournalAudit.objects.count() == avant

    def test_une_panne_du_journal_ne_bloque_pas_l_action_metier(self, company_a, monkeypatch):
        def casse(**kwargs):
            raise RuntimeError("journal indisponible")

        monkeypatch.setattr(JournalAudit.objects, "create", casse)

        gare = Gare.objects.create(nom="Gare résiliente", ville="X", company=company_a)

        assert Gare.objects.filter(pk=gare.pk).exists()


@pytest.mark.django_db
class TestInalterabilite:
    @pytest.fixture
    def entree(self, company_a):
        return JournalAudit.objects.create(company=company_a, action=ActionAudit.CREATION, objet_type="x.y", objet_id="1")

    def test_une_entree_ne_se_modifie_pas(self, entree):
        entree.action_libelle = "x"
        entree.objet_repr = "falsifié"
        with pytest.raises(JournalImmuable):
            entree.save()

    def test_une_entree_ne_se_supprime_pas(self, entree):
        with pytest.raises(JournalImmuable):
            entree.delete()

    def test_ni_en_masse(self, entree):
        with pytest.raises(JournalImmuable):
            JournalAudit.objects.all().update(objet_repr="effacé")
        with pytest.raises(JournalImmuable):
            JournalAudit.objects.all().delete()
        assert JournalAudit.objects.filter(pk=entree.pk).exists()

    def test_le_journal_n_est_pas_journalise_lui_meme(self, entree):
        assert not JournalAudit.objects.filter(objet_type="audit.journalaudit").exists()
