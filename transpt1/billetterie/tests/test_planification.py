import datetime

import pytest
from django.utils import timezone

from audit.models import ActionAudit, JournalAudit
from billetterie.models import Depart, DepartStatut, StatutTicket, Ticket
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Vehicule, VehiculeStatut

ROLES_PLANIFICATION = ["chef_ligne", "chef_gare", "directeur_exploitation", "secretaire_general", "pdg"]


@pytest.fixture
def demain(db):
    return (timezone.localtime() + datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)


@pytest.fixture
def chef_ligne_a(user_factory, company_a):
    return user_factory("chef_ligne_planning", Role.CHEF_LIGNE, company=company_a)


@pytest.fixture
def parc(db, company_a, user_factory):
    return {
        "bus": Vehicule.objects.create(immatriculation="CI-PLAN-1", capacite=50, company=company_a),
        "bus2": Vehicule.objects.create(immatriculation="CI-PLAN-2", capacite=70, company=company_a),
        "chauffeur": user_factory("chauffeur_plan", Role.CHAUFFEUR_PRINCIPAL, company=company_a, first_name="Awa", last_name="Kone"),
        "chauffeur2": user_factory("chauffeur_plan2", Role.CHAUFFEUR_RELAIS, company=company_a),
    }


def _corps(ligne, vehicule, chauffeur, quand):
    return {"ligne": ligne.id, "vehicule": vehicule.id, "chauffeur": chauffeur.id, "date_heure": quand.isoformat()}


@pytest.mark.django_db
class TestPlanifier:
    def test_cree_le_depart_et_sa_feuille_de_route_en_une_operation(
        self, api_client, chef_ligne_a, ligne_a, parc, demain
    ):
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        assert reponse.status_code == 201
        depart = Depart.objects.get(pk=reponse.data["id"])
        feuille = FeuilleDeRoute.objects.get(pk=reponse.data["feuille_de_route"])
        assert (depart.statut, depart.company_id, depart.places_vendues) == (DepartStatut.PLANIFIE, chef_ligne_a.company_id, 0)
        assert (feuille.depart_id, feuille.chauffeur_id, feuille.heure_depart_prevue) == (depart.id, parc["chauffeur"].id, depart.date_heure)
        assert reponse.data["chauffeur_nom"] == "Awa Kone"

    def test_tout_ou_rien_si_la_feuille_echoue(self, api_client, chef_ligne_a, ligne_a, parc, demain, monkeypatch):
        def casse(**kwargs):
            raise RuntimeError("panne")

        monkeypatch.setattr(FeuilleDeRoute.objects, "create", casse)
        api_client.force_authenticate(user=chef_ligne_a)

        with pytest.raises(RuntimeError):
            api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        assert not Depart.objects.exists()

    def test_la_creation_est_tracee(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)

        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        entrees = JournalAudit.objects.filter(action=ActionAudit.CREATION, acteur=chef_ligne_a)
        assert {e.objet_type for e in entrees} == {"billetterie.depart", "personnel_roulant.feuillederoute"}

    @pytest.mark.parametrize("champ", ["ligne", "vehicule", "chauffeur", "date_heure"])
    def test_tous_les_champs_sont_obligatoires(self, api_client, chef_ligne_a, ligne_a, parc, demain, champ):
        corps = _corps(ligne_a, parc["bus"], parc["chauffeur"], demain)
        del corps[champ]
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.post("/api/departs/planifier/", corps).status_code == 400

    def test_un_vehicule_immobilise_ne_se_planifie_pas(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        parc["bus"].statut = VehiculeStatut.BLOQUE_SECURITE
        parc["bus"].save()
        api_client.force_authenticate(user=chef_ligne_a)

        reponse = api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        assert reponse.status_code == 400 and "immobilisé" in str(reponse.data["vehicule"])
        assert not Depart.objects.exists()

    def test_un_vehicule_deja_pris_a_cette_heure_est_refuse(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        reponse = api_client.post(
            "/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur2"], demain + datetime.timedelta(hours=3))
        )

        assert reponse.status_code == 400
        assert "déjà affecté" in str(reponse.data["vehicule"]) and "un autre véhicule" in str(reponse.data["vehicule"])

    def test_un_chauffeur_deja_pris_est_refuse(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        reponse = api_client.post(
            "/api/departs/planifier/", _corps(ligne_a, parc["bus2"], parc["chauffeur"], demain + datetime.timedelta(hours=2))
        )

        assert reponse.status_code == 400 and "chauffeur" in reponse.data and "vehicule" not in reponse.data

    def test_hors_de_la_fenetre_de_8_heures_c_est_libre(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        reponse = api_client.post(
            "/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain + datetime.timedelta(hours=9))
        )

        assert reponse.status_code == 201

    def test_un_depart_termine_ne_bloque_plus_ses_ressources(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        premier = api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))
        Depart.objects.filter(pk=premier.data["id"]).update(statut=DepartStatut.TERMINE)

        reponse = api_client.post(
            "/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain + datetime.timedelta(hours=1))
        )

        assert reponse.status_code == 201

    def test_une_date_passee_est_refusee_mais_pas_une_saisie_tardive_d_une_heure(
        self, api_client, chef_ligne_a, ligne_a, parc
    ):
        api_client.force_authenticate(user=chef_ligne_a)
        hier = timezone.now() - datetime.timedelta(days=1)
        il_y_a_30_min = timezone.now() - datetime.timedelta(minutes=30)

        assert api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], hier)).status_code == 400
        assert api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], il_y_a_30_min)).status_code == 201

    def test_un_chauffeur_doit_avoir_un_role_de_chauffeur(self, api_client, chef_ligne_a, ligne_a, parc, demain, user_factory, company_a):
        guichetier = user_factory("guichetier_plan", Role.GUICHETIER, company=company_a)
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], guichetier, demain)).status_code == 400

    def test_aucune_ressource_d_une_autre_compagnie(self, api_client, chef_ligne_a, ligne_a, parc, demain, user_factory, company_b):
        etranger = Vehicule.objects.create(immatriculation="CI-ETRANGER-9", capacite=50, company=company_b)
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.post("/api/departs/planifier/", _corps(ligne_a, etranger, parc["chauffeur"], demain)).status_code == 400

    @pytest.mark.parametrize("role", [r.value for r in Role])
    def test_seuls_les_roles_de_planification(self, api_client, user_factory, company_a, ligne_a, parc, demain, role):
        if role == "superadmin":
            pytest.skip("le superadmin n'a pas de compagnie : refusé pour un autre motif (testé à part)")
        api_client.force_authenticate(user=user_factory(f"{role}_plan_r", Role(role), company=company_a))

        statut = api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain)).status_code

        assert statut == (201 if role in ROLES_PLANIFICATION else 403)

    def test_le_superadmin_sans_compagnie_ne_planifie_pas(self, api_client, superadmin_user, ligne_a, parc, demain):
        api_client.force_authenticate(user=superadmin_user)

        assert api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain)).status_code == 400


@pytest.mark.django_db
class TestDisponibilites:
    URL = "/api/departs/disponibilites/"

    def test_propose_les_ressources_libres(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        donnees = api_client.get(self.URL, {"date_heure": (demain + datetime.timedelta(hours=2)).isoformat()}).data

        assert [v["immatriculation"] for v in donnees["vehicules"]] == ["CI-PLAN-2"]
        assert {c["id"] for c in donnees["chauffeurs"]} == {parc["chauffeur2"].id}

    def test_a_une_autre_heure_tout_est_libre(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        donnees = api_client.get(self.URL, {"date_heure": (demain + datetime.timedelta(days=1)).isoformat()}).data

        assert len(donnees["vehicules"]) == 2 and len(donnees["chauffeurs"]) == 2

    def test_exclut_les_vehicules_immobilises_et_trop_petits(self, api_client, chef_ligne_a, parc, demain):
        parc["bus"].statut = VehiculeStatut.EN_MAINTENANCE
        parc["bus"].save()
        api_client.force_authenticate(user=chef_ligne_a)

        donnees = api_client.get(self.URL, {"date_heure": demain.isoformat(), "places_min": 60}).data

        assert [v["immatriculation"] for v in donnees["vehicules"]] == ["CI-PLAN-2"]

    def test_un_agent_desactive_n_est_pas_propose(self, api_client, chef_ligne_a, parc, demain):
        parc["chauffeur2"].is_active = False
        parc["chauffeur2"].save()
        api_client.force_authenticate(user=chef_ligne_a)

        donnees = api_client.get(self.URL, {"date_heure": demain.isoformat()}).data

        assert {c["id"] for c in donnees["chauffeurs"]} == {parc["chauffeur"].id}

    @pytest.mark.parametrize("parametres", [{}, {"date_heure": "demain"}, {"date_heure": "2030-13-45T10:00"}, {"date_heure": "2030-01-01T10:00", "places_min": "beaucoup"}])
    def test_parametres_invalides(self, api_client, chef_ligne_a, parametres):
        api_client.force_authenticate(user=chef_ligne_a)

        assert api_client.get(self.URL, parametres).status_code == 400

    def test_une_heure_sans_fuseau_est_lue_dans_celui_du_projet(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain))

        donnees = api_client.get(self.URL, {"date_heure": demain.strftime("%Y-%m-%dT%H:%M")}).data  # sans fuseau

        assert [v["immatriculation"] for v in donnees["vehicules"]] == ["CI-PLAN-2"]

    def test_n_expose_rien_d_une_autre_compagnie(self, api_client, chef_ligne_a, parc, demain, user_factory, company_b):
        Vehicule.objects.create(immatriculation="CI-B-SECRET", capacite=90, company=company_b)
        user_factory("chauffeur_b_secret", Role.CHAUFFEUR_PRINCIPAL, company=company_b)
        api_client.force_authenticate(user=chef_ligne_a)

        donnees = api_client.get(self.URL, {"date_heure": demain.isoformat()}).data

        assert "CI-B-SECRET" not in [v["immatriculation"] for v in donnees["vehicules"]]
        assert "chauffeur_b_secret" not in [c["nom"] for c in donnees["chauffeurs"]]

    @pytest.mark.parametrize("role", [r.value for r in Role if r not in (Role.SUPERADMIN,) and r.value not in ROLES_PLANIFICATION])
    def test_annuaire_reserve_a_la_planification(self, api_client, user_factory, company_a, demain, role):
        api_client.force_authenticate(user=user_factory(f"{role}_dispo", Role(role), company=company_a))

        assert api_client.get(self.URL, {"date_heure": demain.isoformat()}).status_code == 403


@pytest.mark.django_db
class TestModifierEtSupprimer:
    @pytest.fixture
    def depart(self, api_client, chef_ligne_a, ligne_a, parc, demain):
        api_client.force_authenticate(user=chef_ligne_a)
        return Depart.objects.get(pk=api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus"], parc["chauffeur"], demain)).data["id"])

    def test_deplacer_l_heure_suit_sur_la_feuille(self, api_client, depart):
        nouvelle = depart.date_heure + datetime.timedelta(hours=2)

        reponse = api_client.patch(f"/api/departs/{depart.id}/", {"date_heure": nouvelle.isoformat()})

        assert reponse.status_code == 200
        assert FeuilleDeRoute.objects.get(depart=depart).heure_depart_prevue == nouvelle

    def test_deplacer_sur_un_creneau_deja_pris_est_refuse(self, api_client, depart, ligne_a, parc, demain):
        api_client.post("/api/departs/planifier/", _corps(ligne_a, parc["bus2"], parc["chauffeur2"], demain + datetime.timedelta(days=1)))
        cible = demain + datetime.timedelta(days=1, hours=1)

        reponse = api_client.patch(f"/api/departs/{depart.id}/", {"date_heure": cible.isoformat(), "vehicule": parc["bus2"].id})

        assert reponse.status_code == 400

    def test_un_depart_deja_parti_ne_se_deplace_plus(self, api_client, depart):
        FeuilleDeRoute.objects.filter(depart=depart).update(heure_depart_reelle=timezone.now())
        nouvelle = depart.date_heure + datetime.timedelta(hours=1)

        assert api_client.patch(f"/api/departs/{depart.id}/", {"date_heure": nouvelle.isoformat()}).status_code == 400

    def test_supprimer_une_erreur_de_planning(self, api_client, depart):
        assert api_client.delete(f"/api/departs/{depart.id}/").status_code == 204
        assert not Depart.objects.filter(pk=depart.pk).exists()
        assert not FeuilleDeRoute.objects.filter(depart_id=depart.pk).exists()

    def test_la_suppression_est_tracee(self, api_client, depart, chef_ligne_a):
        api_client.delete(f"/api/departs/{depart.id}/")

        assert JournalAudit.objects.filter(objet_type="billetterie.depart", action=ActionAudit.SUPPRESSION, acteur=chef_ligne_a).exists()

    def test_un_depart_avec_des_tickets_ne_se_supprime_pas_meme_annules(self, api_client, depart, user_factory, company_a):
        guichetier = user_factory("guichetier_suppr", Role.GUICHETIER, company=company_a)
        ticket = Ticket.objects.create(
            depart=depart, company=company_a, passager_nom="P", passager_telephone="+225", prix="5000",
            mode_paiement="especes", vendu_par=guichetier, statut=StatutTicket.ANNULE,
        )

        reponse = api_client.delete(f"/api/departs/{depart.id}/")

        assert reponse.status_code == 400 and "tickets" in str(reponse.data)
        assert Depart.objects.filter(pk=depart.pk).exists() and Ticket.objects.filter(pk=ticket.pk).exists()

    @pytest.mark.parametrize("statut", [DepartStatut.EN_COURS, DepartStatut.TERMINE])
    def test_seul_un_depart_planifie_se_supprime(self, api_client, depart, statut):
        Depart.objects.filter(pk=depart.pk).update(statut=statut)

        assert api_client.delete(f"/api/departs/{depart.id}/").status_code == 400

    def test_un_depart_dont_la_feuille_a_demarre_ne_se_supprime_pas(self, api_client, depart):
        FeuilleDeRoute.objects.filter(depart=depart).update(heure_depart_reelle=timezone.now())

        assert api_client.delete(f"/api/departs/{depart.id}/").status_code == 400
        assert Depart.objects.filter(pk=depart.pk).exists()
