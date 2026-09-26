"""Secrétariat général (notes de service, agenda partagé, archivage) et messages du chef de gare à son équipe et aux
chauffeurs en approche (cahier des charges : Direction Générale et Exploitation & Réseau)."""

import datetime

import pytest
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte
from billetterie.models import Depart, DepartStatut
from communication.models import DocumentArchive, EvenementAgenda, MessageDirect, NoteService
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import AffectationGare, Gare, Ligne, Vehicule

TOUS_LES_ROLES = [r.value for r in Role if r != Role.SUPERADMIN]


@pytest.fixture
def equipe(user_factory, company_a):
    return {r: user_factory(f"{r}_com", Role(r), company=company_a) for r in TOUS_LES_ROLES}


def ecrire(api_client, utilisateur, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/notes-service/", {"titre": "Nouveau règlement", "contenu": "Port du gilet obligatoire en gare.", **corps}, format="json")


@pytest.mark.django_db
class TestNotesDeService:
    @pytest.mark.parametrize("role", ["secretaire_general", "pdg"])
    def test_le_secretariat_diffuse_une_note_aux_poles_concernes(self, api_client, equipe, role):
        reponse = ecrire(api_client, equipe[role], poles=["technique", "roulant"])

        assert reponse.status_code == 201
        assert set(reponse.data["roles_destinataires"]) == {
            "directeur_technique", "magasinier", "chef_atelier", "mecanicien", "chauffeur_principal", "chauffeur_relais", "controleur_ligne",
        }
        assert reponse.data["auteur_nom"] == f"{role}_com"

    def test_la_note_previent_les_postes_vises_et_eux_seuls(self, api_client, equipe):
        ecrire(api_client, equipe["secretaire_general"], poles=["technique"], urgente=True)

        alerte = Alerte.objects.get(type=TypeAlerte.NOTE_SERVICE)
        assert alerte.titre == "Note de service : Nouveau règlement" and alerte.gravite == "attention"
        assert set(alerte.roles_destinataires) == {"directeur_technique", "magasinier", "chef_atelier", "mecanicien"}
        api_client.force_authenticate(user=equipe["mecanicien"])
        assert [a["titre"] for a in api_client.get("/api/alertes/").data["alertes"]] == ["Note de service : Nouveau règlement"]
        api_client.force_authenticate(user=equipe["guichetier"])
        assert api_client.get("/api/alertes/").data["alertes"] == []

    def test_une_note_normale_n_est_pas_urgente(self, api_client, equipe):
        ecrire(api_client, equipe["secretaire_general"], tous=True)

        assert Alerte.objects.get(type=TypeAlerte.NOTE_SERVICE).gravite == "info"

    def test_a_tous_les_postes(self, api_client, equipe):
        reponse = ecrire(api_client, equipe["secretaire_general"], tous=True)

        assert set(reponse.data["roles_destinataires"]) == set(TOUS_LES_ROLES)

    def test_par_postes_precis_et_combines_aux_poles(self, api_client, equipe):
        reponse = ecrire(api_client, equipe["secretaire_general"], roles=["drh"], poles=["direction"])

        assert set(reponse.data["roles_destinataires"]) == {"drh", "pdg", "secretaire_general", "qhse"}

    @pytest.mark.parametrize("corps", [{}, {"poles": []}, {"poles": ["cuisine"]}, {"roles": ["roi"]}, {"titre": "  ", "tous": True}, {"contenu": "ok", "tous": True}])
    def test_une_note_sans_destinataire_ou_vide_est_refusee(self, api_client, equipe, corps):
        assert ecrire(api_client, equipe["secretaire_general"], **corps).status_code == 400
        assert not NoteService.objects.exists()

    @pytest.mark.parametrize("role", ["directeur_exploitation", "chef_gare", "guichetier", "qhse", "drh", "directeur_technique"])
    def test_les_autres_postes_ne_redigent_pas(self, api_client, equipe, role):
        assert ecrire(api_client, equipe[role], tous=True).status_code == 403

    def test_un_poste_ne_relit_que_les_notes_qui_le_visent(self, api_client, equipe):
        ecrire(api_client, equipe["secretaire_general"], poles=["technique"], titre="Pour la technique")
        ecrire(api_client, equipe["secretaire_general"], poles=["direction"], titre="Pour la direction")
        ecrire(api_client, equipe["pdg"], tous=True, titre="Pour tous")

        def titres(role):
            api_client.force_authenticate(user=equipe[role])
            return {n["titre"] for n in api_client.get("/api/notes-service/").data}

        assert titres("mecanicien") == {"Pour la technique", "Pour tous"}
        assert titres("qhse") == {"Pour la direction", "Pour tous"}
        assert titres("secretaire_general") == {"Pour la technique", "Pour la direction", "Pour tous"}
        assert titres("pdg") == {"Pour la technique", "Pour la direction", "Pour tous"}

    def test_une_note_qui_ne_vous_vise_pas_est_introuvable(self, api_client, equipe):
        note = ecrire(api_client, equipe["secretaire_general"], poles=["technique"]).data["id"]

        api_client.force_authenticate(user=equipe["guichetier"])
        assert api_client.get(f"/api/notes-service/{note}/").status_code == 404
        api_client.force_authenticate(user=equipe["magasinier"])
        assert api_client.get(f"/api/notes-service/{note}/").status_code == 200

    def test_une_note_ne_se_modifie_ni_ne_se_supprime(self, api_client, equipe):
        note = ecrire(api_client, equipe["secretaire_general"], tous=True).data["id"]

        assert api_client.patch(f"/api/notes-service/{note}/", {"titre": "Autre"}, format="json").status_code == 405
        assert api_client.delete(f"/api/notes-service/{note}/").status_code == 405

    def test_une_autre_compagnie_ne_voit_rien(self, api_client, equipe, user_factory, company_b):
        ecrire(api_client, equipe["secretaire_general"], tous=True)
        etranger = user_factory("sg_b_com", Role.SECRETAIRE_GENERAL, company=company_b)

        api_client.force_authenticate(user=etranger)
        assert api_client.get("/api/notes-service/").data == []
        assert not Alerte.objects.filter(company=company_b).exists()

    def test_sans_authentification_rien(self, api_client):
        assert api_client.get("/api/notes-service/").status_code == 401

    def test_le_catalogue_des_poles_est_lisible_de_tous(self, api_client, equipe):
        api_client.force_authenticate(user=equipe["guichetier"])

        catalogue = api_client.get("/api/communication/catalogue/").data

        assert [p["pole"] for p in catalogue] == ["direction", "exploitation", "roulant", "technique", "supports"]
        assert {"role": "mecanicien", "libelle": "Mécanicien / électricien auto"} in next(p for p in catalogue if p["pole"] == "technique")["postes"]


@pytest.fixture
def gare(company_a, equipe):
    depart = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=equipe["chef_gare"])
    arrivee = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a)
    return {"depart": depart, "arrivee": arrivee}


def car_en_route(company, equipe, ligne, chauffeur, immatriculation, *, arrive=False):
    bus = Vehicule.objects.create(immatriculation=immatriculation, capacite=40, company=company)
    maintenant = timezone.now()
    d = Depart.objects.create(ligne=ligne, vehicule=bus, chauffeur=chauffeur, company=company, date_heure=maintenant, statut=DepartStatut.EN_COURS)
    return FeuilleDeRoute.objects.create(
        depart=d, chauffeur=chauffeur, company=company, heure_depart_prevue=maintenant, heure_depart_reelle=maintenant,
        heure_arrivee_reelle=maintenant if arrive else None,
    )


@pytest.fixture
def reseau(company_a, equipe, gare):
    ligne_vers_adjame = Ligne.objects.create(nom="Bouaké-Adjamé", gare_depart=gare["arrivee"], gare_arrivee=gare["depart"], company=company_a)
    ligne_depuis_adjame = Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=gare["depart"], gare_arrivee=gare["arrivee"], company=company_a)
    return {"vers": ligne_vers_adjame, "depuis": ligne_depuis_adjame}


def message(api_client, utilisateur, portee="les_deux", texte="Le car de 14 h aura 30 minutes de retard."):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/messages-directs/", {"portee": portee, "texte": texte}, format="json")


@pytest.mark.django_db
class TestMessagesDuChefDeGare:
    def preparer(self, company_a, equipe, gare, reseau):
        AffectationGare.objects.create(agent=equipe["guichetier"], gare=gare["depart"], company=company_a)
        car_en_route(company_a, equipe, reseau["vers"], equipe["chauffeur_principal"], "CI-MSG-1")

    def test_le_chef_de_gare_previent_son_equipe_et_les_chauffeurs_en_approche(self, api_client, company_a, equipe, gare, reseau):
        self.preparer(company_a, equipe, gare, reseau)

        reponse = message(api_client, equipe["chef_gare"])

        assert reponse.status_code == 201
        assert reponse.data["nombre_destinataires"] == 2 and reponse.data["gare_nom"] == "Adjamé"
        alerte = Alerte.objects.get(type=TypeAlerte.MESSAGE)
        assert set(alerte.destinataires.all()) == {equipe["guichetier"], equipe["chauffeur_principal"]}
        assert alerte.titre == "Message du chef de la gare Adjamé" and "30 minutes de retard" in alerte.message

    def test_le_message_atteint_la_cloche_des_destinataires(self, api_client, company_a, equipe, gare, reseau):
        self.preparer(company_a, equipe, gare, reseau)
        message(api_client, equipe["chef_gare"])

        api_client.force_authenticate(user=equipe["chauffeur_principal"])
        assert len(api_client.get("/api/alertes/").data["alertes"]) == 1
        api_client.force_authenticate(user=equipe["bagagiste"])
        assert api_client.get("/api/alertes/").data["alertes"] == []

    def test_portee_equipe_seulement(self, api_client, company_a, equipe, gare, reseau):
        self.preparer(company_a, equipe, gare, reseau)

        reponse = message(api_client, equipe["chef_gare"], portee="equipe")

        assert list(MessageDirect.objects.get().destinataires.all()) == [equipe["guichetier"]] and reponse.data["nombre_destinataires"] == 1

    def test_portee_chauffeurs_en_approche_seulement(self, api_client, company_a, equipe, gare, reseau):
        self.preparer(company_a, equipe, gare, reseau)

        message(api_client, equipe["chef_gare"], portee="approche")

        assert list(MessageDirect.objects.get().destinataires.all()) == [equipe["chauffeur_principal"]]

    def test_un_car_arrive_ou_qui_va_ailleurs_n_est_pas_en_approche(self, api_client, company_a, equipe, gare, reseau):
        car_en_route(company_a, equipe, reseau["vers"], equipe["chauffeur_principal"], "CI-MSG-2", arrive=True)
        car_en_route(company_a, equipe, reseau["depuis"], equipe["chauffeur_relais"], "CI-MSG-3")  # part d'Adjamé : ne va pas vers lui

        reponse = message(api_client, equipe["chef_gare"], portee="approche")

        assert reponse.status_code == 400 and "Personne à prévenir" in str(reponse.data)

    def test_sans_destinataire_rien_n_est_conserve(self, api_client, equipe, gare):
        reponse = message(api_client, equipe["chef_gare"])

        assert reponse.status_code == 400
        assert not MessageDirect.objects.exists() and not Alerte.objects.filter(type=TypeAlerte.MESSAGE).exists()

    @pytest.mark.parametrize("corps", [{"portee": "tout_le_monde"}, {"texte": " "}, {"texte": "x" * 501}, {"portee": ""}])
    def test_un_message_invalide_est_refuse(self, api_client, company_a, equipe, gare, reseau, corps):
        self.preparer(company_a, equipe, gare, reseau)
        api_client.force_authenticate(user=equipe["chef_gare"])

        assert api_client.post("/api/messages-directs/", {"portee": "les_deux", "texte": "Bonjour", **corps}, format="json").status_code == 400

    def test_un_chef_de_gare_sans_gare_n_a_personne_a_prevenir(self, api_client, user_factory, company_a):
        chef = user_factory("chef_sans_gare_com", Role.CHEF_GARE, company=company_a)

        reponse = message(api_client, chef)

        assert reponse.status_code == 400 and "Aucune gare" in str(reponse.data)

    @pytest.mark.parametrize("role", ["guichetier", "chef_ligne", "directeur_exploitation", "pdg", "chauffeur_principal"])
    def test_les_autres_postes_n_ecrivent_pas_aux_equipes(self, api_client, company_a, equipe, gare, reseau, role):
        self.preparer(company_a, equipe, gare, reseau)

        assert message(api_client, equipe[role]).status_code == 403

    def test_le_chef_relit_ses_messages_et_l_exploitation_ceux_de_toutes_les_gares(self, api_client, company_a, equipe, gare, reseau, user_factory):
        self.preparer(company_a, equipe, gare, reseau)
        message(api_client, equipe["chef_gare"], texte="Premier message")
        autre_gare = Gare.objects.create(nom="Yopougon", ville="Abidjan", company=company_a, chef=(chef2 := user_factory("chef_gare2_com", Role.CHEF_GARE, company=company_a)))
        AffectationGare.objects.create(agent=equipe["bagagiste"], gare=autre_gare, company=company_a)
        message(api_client, chef2, portee="equipe", texte="Message de l'autre gare")

        def textes(role_ou_user):
            utilisateur = equipe[role_ou_user] if isinstance(role_ou_user, str) else role_ou_user
            api_client.force_authenticate(user=utilisateur)
            return {m["texte"] for m in api_client.get("/api/messages-directs/").data}

        assert textes("chef_gare") == {"Premier message"}
        assert textes(chef2) == {"Message de l'autre gare"}
        assert textes("directeur_exploitation") == {"Premier message", "Message de l'autre gare"}
        assert textes("pdg") == textes("secretaire_general") == {"Premier message", "Message de l'autre gare"}

    @pytest.mark.parametrize("role", ["guichetier", "qhse", "chauffeur_principal", "chef_ligne"])
    def test_les_autres_postes_ne_lisent_pas_les_messages_des_gares(self, api_client, equipe, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/messages-directs/").status_code == 403

    def test_une_autre_compagnie_ne_voit_rien(self, api_client, company_a, equipe, gare, reseau, user_factory, company_b):
        self.preparer(company_a, equipe, gare, reseau)
        message(api_client, equipe["chef_gare"])
        etranger = user_factory("dirops_b_com", Role.DIRECTEUR_EXPLOITATION, company=company_b)

        api_client.force_authenticate(user=etranger)
        assert api_client.get("/api/messages-directs/").data == []


def evenement(api_client, utilisateur, **corps):
    api_client.force_authenticate(user=utilisateur)
    debut = (timezone.now() + datetime.timedelta(days=3)).replace(microsecond=0)
    return api_client.post("/api/agenda/", {"titre": "Comité de direction", "debut": debut.isoformat(), "lieu": "Siège", **corps}, format="json")


@pytest.mark.django_db
class TestAgendaDeLaDirection:
    @pytest.mark.parametrize("role", ["secretaire_general", "pdg"])
    def test_le_secretariat_tient_l_agenda(self, api_client, equipe, role):
        assert evenement(api_client, equipe[role]).status_code == 201

    def test_les_postes_invites_sont_alertes(self, api_client, equipe):
        evenement(api_client, equipe["secretaire_general"], participants=["directeur_technique", "qhse"], description="Ordre du jour : flotte")

        alerte = Alerte.objects.get(type=TypeAlerte.AGENDA)
        assert alerte.titre == "Agenda : Comité de direction" and "Siège" in alerte.message
        assert set(alerte.roles_destinataires) == {"directeur_technique", "qhse"}

    def test_sans_invite_pas_d_alerte(self, api_client, equipe):
        evenement(api_client, equipe["secretaire_general"])

        assert not Alerte.objects.filter(type=TypeAlerte.AGENDA).exists()

    @pytest.mark.parametrize(
        "role", ["pdg", "secretaire_general", "qhse", "directeur_exploitation", "directeur_technique", "directeur_financier", "drh", "responsable_juridique"]
    )
    def test_la_direction_lit_l_agenda(self, api_client, equipe, role):
        evenement(api_client, equipe["secretaire_general"])

        api_client.force_authenticate(user=equipe[role])
        assert [e["titre"] for e in api_client.get("/api/agenda/").data] == ["Comité de direction"]

    @pytest.mark.parametrize("role", ["guichetier", "chef_gare", "chef_ligne", "chauffeur_principal", "mecanicien", "magasinier", "bagagiste"])
    def test_le_terrain_ne_lit_pas_l_agenda_de_la_direction(self, api_client, equipe, role):
        api_client.force_authenticate(user=equipe[role])

        assert api_client.get("/api/agenda/").status_code == 403

    @pytest.mark.parametrize("role", ["directeur_technique", "qhse", "drh", "directeur_exploitation"])
    def test_seul_le_secretariat_ecrit(self, api_client, equipe, role):
        assert evenement(api_client, equipe[role]).status_code == 403

    def test_la_fin_ne_precede_pas_le_debut(self, api_client, equipe):
        debut = timezone.now() + datetime.timedelta(days=3)

        assert evenement(api_client, equipe["secretaire_general"], fin=(debut - datetime.timedelta(hours=2)).isoformat()).status_code == 400

    def test_les_evenements_se_filtrent_par_dates_et_a_venir(self, api_client, equipe, company_a):
        passe = EvenementAgenda.objects.create(company=company_a, auteur=equipe["pdg"], titre="Passé", debut=timezone.now() - datetime.timedelta(days=10))
        evenement(api_client, equipe["secretaire_general"], titre="À venir")
        api_client.force_authenticate(user=equipe["pdg"])

        assert [e["titre"] for e in api_client.get("/api/agenda/?a_venir=1").data] == ["À venir"]
        du = (timezone.localdate() - datetime.timedelta(days=11)).isoformat()
        au = (timezone.localdate() - datetime.timedelta(days=9)).isoformat()
        assert [e["id"] for e in api_client.get(f"/api/agenda/?du={du}&au={au}").data] == [passe.id]
        assert len(api_client.get("/api/agenda/").data) == 2

    def test_un_evenement_se_modifie_et_se_supprime(self, api_client, equipe):
        cree = evenement(api_client, equipe["secretaire_general"]).data["id"]

        assert api_client.patch(f"/api/agenda/{cree}/", {"lieu": "Salle B"}, format="json").data["lieu"] == "Salle B"
        assert api_client.delete(f"/api/agenda/{cree}/").status_code == 204

    def test_une_autre_compagnie_ne_voit_rien(self, api_client, equipe, user_factory, company_b):
        cree = evenement(api_client, equipe["secretaire_general"]).data["id"]
        pdg_b = user_factory("pdg_b_com", Role.PDG, company=company_b)

        api_client.force_authenticate(user=pdg_b)
        assert api_client.get("/api/agenda/").data == []
        assert api_client.get(f"/api/agenda/{cree}/").status_code == 404


def classer(api_client, utilisateur, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(
        "/api/archives/",
        {"titre": "Contrat de bail Adjamé", "categorie": "contrat", "date_document": "2026-03-15", "reference": "CTR-2026-014", "emplacement": "Armoire 3, chemise B", **corps},
        format="json",
    )


@pytest.mark.django_db
class TestArchivage:
    @pytest.mark.parametrize("role", ["secretaire_general", "pdg"])
    def test_le_secretariat_classe_un_dossier(self, api_client, equipe, role):
        reponse = classer(api_client, equipe[role])

        assert reponse.status_code == 201
        assert reponse.data["categorie_libelle"] == "Contrat" and reponse.data["archive"] is False and reponse.data["auteur_nom"] == f"{role}_com"

    def test_la_reference_est_unique_dans_la_compagnie(self, api_client, equipe, user_factory, company_b):
        classer(api_client, equipe["secretaire_general"])

        assert classer(api_client, equipe["secretaire_general"]).status_code == 400
        assert classer(api_client, equipe["secretaire_general"], reference="CTR-2026-015").status_code == 201
        assert classer(api_client, equipe["secretaire_general"], reference="").status_code == 201
        assert classer(api_client, equipe["secretaire_general"], reference="").status_code == 201, "plusieurs dossiers peuvent n'avoir aucune référence"
        pdg_b = user_factory("pdg_b_arch", Role.PDG, company=company_b)
        assert classer(api_client, pdg_b).status_code == 201, "une autre compagnie peut utiliser la même référence"

    @pytest.mark.parametrize("corps", [{"titre": " "}, {"categorie": "poesie"}, {"date_document": "hier"}, {"date_document": ""}])
    def test_un_dossier_invalide_est_refuse(self, api_client, equipe, corps):
        assert classer(api_client, equipe["secretaire_general"], **corps).status_code == 400

    def test_on_retrouve_un_dossier_par_mot_categorie_et_etat(self, api_client, equipe):
        classer(api_client, equipe["secretaire_general"], titre="Bail Adjamé", mots_cles="immobilier, loyer")
        classer(api_client, equipe["secretaire_general"], titre="Décision d'ouverture de ligne", categorie="decision", reference="DEC-1", description="Ligne Man")
        api_client.force_authenticate(user=equipe["secretaire_general"])

        def titres(requete):
            return [d["titre"] for d in api_client.get(f"/api/archives/?{requete}").data]

        assert titres("q=loyer") == ["Bail Adjamé"]
        assert titres("q=dec-1") == ["Décision d'ouverture de ligne"]
        assert titres("q=man") == ["Décision d'ouverture de ligne"]
        assert set(titres("q=armoire")) == {"Bail Adjamé", "Décision d'ouverture de ligne"}
        assert titres("categorie=decision") == ["Décision d'ouverture de ligne"]
        assert len(titres("")) == 2

    def test_archiver_et_desarchiver(self, api_client, equipe):
        cree = classer(api_client, equipe["secretaire_general"]).data["id"]

        archive = api_client.post(f"/api/archives/{cree}/archiver/")
        assert archive.status_code == 200 and archive.data["archive"] is True and archive.data["archive_le"] is not None
        assert api_client.post(f"/api/archives/{cree}/archiver/").status_code == 400
        assert [d["id"] for d in api_client.get("/api/archives/?archive=1").data] == [cree]
        assert api_client.get("/api/archives/?archive=0").data == []
        assert api_client.post(f"/api/archives/{cree}/desarchiver/").data["archive"] is False
        assert api_client.post(f"/api/archives/{cree}/desarchiver/").status_code == 400

    def test_la_fiche_se_corrige_mais_l_archivage_ne_se_change_pas_a_la_main(self, api_client, equipe):
        cree = classer(api_client, equipe["secretaire_general"]).data["id"]

        reponse = api_client.patch(f"/api/archives/{cree}/", {"emplacement": "Armoire 4", "archive": True}, format="json")

        assert reponse.status_code == 200 and reponse.data["emplacement"] == "Armoire 4" and reponse.data["archive"] is False

    def test_un_dossier_ne_se_supprime_pas(self, api_client, equipe):
        cree = classer(api_client, equipe["secretaire_general"]).data["id"]

        assert api_client.delete(f"/api/archives/{cree}/").status_code == 405
        assert DocumentArchive.objects.filter(pk=cree).exists()

    @pytest.mark.parametrize("role", ["directeur_exploitation", "qhse", "drh", "responsable_juridique", "chef_gare", "guichetier", "directeur_financier"])
    def test_seul_le_secretariat_voit_et_classe_les_dossiers(self, api_client, equipe, role):
        classer(api_client, equipe["secretaire_general"])

        api_client.force_authenticate(user=equipe[role])
        assert api_client.get("/api/archives/").status_code == 403
        assert classer(api_client, equipe[role], reference="X").status_code == 403

    def test_une_autre_compagnie_ne_voit_rien(self, api_client, equipe, user_factory, company_b):
        cree = classer(api_client, equipe["secretaire_general"]).data["id"]
        sg_b = user_factory("sg_b_arch", Role.SECRETAIRE_GENERAL, company=company_b)

        api_client.force_authenticate(user=sg_b)
        assert api_client.get("/api/archives/").data == []
        assert api_client.get(f"/api/archives/{cree}/").status_code == 404
        assert api_client.post(f"/api/archives/{cree}/archiver/").status_code == 404
