"""Un ticket vendu est une pièce de caisse : verrouillé pour tous, corrigé seulement par une annulation tracée.

Motivation : sonde de l'analyse du projet (un guichetier ramenait le prix d'un ticket vendu par un autre de
5 000 à 1, puis le supprimait, sans trace ni place libérée).
"""

import datetime

import pytest
from django.utils import timezone

from audit.models import ActionAudit, JournalAudit
from billetterie.models import DepartStatut, StatutTicket
from core.models import Role

ROLES_ANNULATION = {"chef_gare", "chef_ligne", "directeur_exploitation", "secretaire_general", "pdg", "superadmin"}
MOTIF = "Erreur de saisie du guichetier"


def _annuler(client, ticket, motif=MOTIF):
    return client.post(f"/api/tickets/{ticket.id}/annuler/", {"motif": motif})


@pytest.mark.django_db
class TestVerrouillage:
    @pytest.mark.parametrize("role", [r.value for r in Role])
    @pytest.mark.parametrize("methode", ["put", "patch", "delete"])
    def test_personne_ne_modifie_ni_ne_supprime_un_ticket_vendu(
        self, api_client, tous_les_roles, monde_a, role, methode
    ):
        api_client.force_authenticate(user=tous_les_roles[role])
        ticket = monde_a["ticket"]

        reponse = getattr(api_client, methode)(f"/api/tickets/{ticket.id}/", {"prix": "1"})

        # 405 pour qui a le droit de vendre, 403 pour les autres : jamais 200/204.
        assert reponse.status_code in (403, 405)
        ticket.refresh_from_db()
        assert str(ticket.prix) == "5000.00"

    def test_le_message_explique_la_marche_a_suivre(self, api_client, tous_les_roles, monde_a):
        api_client.force_authenticate(user=tous_les_roles["pdg"])

        reponse = api_client.patch(f"/api/tickets/{monde_a['ticket'].id}/", {"prix": "1"})

        assert "annulation" in str(reponse.data["detail"])

    def test_le_statut_ne_se_choisit_pas_a_la_vente(self, api_client, tous_les_roles, monde_a):
        api_client.force_authenticate(user=tous_les_roles["guichetier"])

        reponse = api_client.post(
            "/api/tickets/",
            {"depart": monde_a["depart"].id, "passager_nom": "X", "passager_telephone": "+225", "prix": "5000",
             "mode_paiement": "especes", "statut": "annule", "motif_annulation": "triche"},
        )

        assert reponse.status_code == 201
        assert (reponse.data["statut"], reponse.data["motif_annulation"]) == ("valide", "")

    def test_l_administration_ne_permet_ni_modification_ni_suppression(self, client, superadmin_user, monde_a):
        superadmin_user.is_staff = superadmin_user.is_superuser = True
        superadmin_user.save()
        client.force_login(superadmin_user)
        ticket = monde_a["ticket"]

        assert client.post(f"/admin/billetterie/ticket/{ticket.id}/change/", {"prix": "1"}).status_code == 403
        assert client.post(f"/admin/billetterie/ticket/{ticket.id}/delete/", {"post": "yes"}).status_code == 403
        assert client.get("/admin/billetterie/ticket/add/").status_code == 403
        ticket.refresh_from_db()
        assert str(ticket.prix) == "5000.00"


@pytest.mark.django_db
class TestAnnulation:
    @pytest.mark.parametrize("role", [r.value for r in Role])
    def test_seule_la_supervision_annule(self, api_client, tous_les_roles, monde_a, role):
        api_client.force_authenticate(user=tous_les_roles[role])

        statut = _annuler(api_client, monde_a["ticket"]).status_code

        assert statut == (200 if role in ROLES_ANNULATION else 403), f"{role} : {statut}"

    def test_le_guichetier_ne_peut_pas_annuler_sa_propre_vente(self, api_client, monde_a):
        api_client.force_authenticate(user=monde_a["guichetier"])  # le vendeur du ticket

        assert _annuler(api_client, monde_a["ticket"]).status_code == 403

    def test_l_annulation_garde_le_ticket_et_dit_qui_quand_pourquoi(self, api_client, tous_les_roles, monde_a):
        chef = tous_les_roles["chef_gare"]
        api_client.force_authenticate(user=chef)

        reponse = _annuler(api_client, monde_a["ticket"])

        assert reponse.status_code == 200
        ticket = monde_a["ticket"]
        ticket.refresh_from_db()
        assert ticket.statut == StatutTicket.ANNULE
        assert (ticket.annule_par, ticket.motif_annulation) == (chef, MOTIF)
        assert abs(timezone.now() - ticket.annule_le) < datetime.timedelta(minutes=1)
        assert reponse.data["statut"] == "annule" and reponse.data["motif_annulation"] == MOTIF

    def test_le_motif_est_obligatoire(self, api_client, tous_les_roles, monde_a):
        api_client.force_authenticate(user=tous_les_roles["chef_gare"])

        assert _annuler(api_client, monde_a["ticket"], motif="").status_code == 400
        assert _annuler(api_client, monde_a["ticket"], motif="oups").status_code == 400
        assert api_client.post(f"/api/tickets/{monde_a['ticket'].id}/annuler/").status_code == 400
        monde_a["ticket"].refresh_from_db()
        assert monde_a["ticket"].statut == StatutTicket.VALIDE

    def test_on_n_annule_pas_deux_fois(self, api_client, tous_les_roles, monde_a):
        api_client.force_authenticate(user=tous_les_roles["chef_gare"])
        _annuler(api_client, monde_a["ticket"])

        assert _annuler(api_client, monde_a["ticket"]).status_code == 400

    def test_la_place_est_liberee_et_revendable(self, api_client, tous_les_roles, monde_a):
        depart, vehicule = monde_a["depart"], monde_a["vehicule"]
        vehicule.capacite = 1
        vehicule.save()
        depart.places_vendues = 1  # plein
        depart.save()
        api_client.force_authenticate(user=tous_les_roles["guichetier"])
        vente = {"depart": depart.id, "passager_nom": "Nouveau", "passager_telephone": "+225", "prix": "5000",
                 "mode_paiement": "especes"}
        assert api_client.post("/api/tickets/", vente).status_code == 400  # complet

        api_client.force_authenticate(user=tous_les_roles["chef_gare"])
        _annuler(api_client, monde_a["ticket"])
        depart.refresh_from_db()
        assert depart.places_vendues == 0

        api_client.force_authenticate(user=tous_les_roles["guichetier"])
        assert api_client.post("/api/tickets/", vente).status_code == 201

    def test_un_depart_termine_ne_recupere_pas_de_place_mais_l_annulation_reste_possible(
        self, api_client, tous_les_roles, monde_a
    ):
        depart = monde_a["depart"]
        depart.statut, depart.places_vendues = DepartStatut.TERMINE, 5
        depart.save()
        api_client.force_authenticate(user=tous_les_roles["chef_gare"])

        assert _annuler(api_client, monde_a["ticket"]).status_code == 200

        depart.refresh_from_db()
        assert depart.places_vendues == 5

    def test_un_ticket_d_une_autre_compagnie_est_introuvable(self, api_client, tous_les_roles, monde_b):
        api_client.force_authenticate(user=tous_les_roles["chef_gare"])

        assert _annuler(api_client, monde_b["ticket"]).status_code == 404

    def test_l_annulation_est_tracee_dans_le_journal_avec_son_motif(self, api_client, tous_les_roles, monde_a):
        chef = tous_les_roles["chef_gare"]
        api_client.force_authenticate(user=chef)

        _annuler(api_client, monde_a["ticket"])

        entree = JournalAudit.objects.get(objet_type="billetterie.ticket", action=ActionAudit.ANNULATION)
        assert (entree.acteur, entree.acteur_nom) == (chef, chef.username)
        assert entree.changements["statut"] == ["valide", "annule"]
        assert entree.changements["motif_annulation"] == ["", MOTIF]


@pytest.mark.django_db
class TestUnTicketAnnuleN_EstPasUneRecette:
    def _aujourdhui(self):
        return timezone.localdate().isoformat()

    def test_cloture_de_caisse(self, api_client, tous_les_roles, monde_a):
        guichetier = monde_a["guichetier"]
        api_client.force_authenticate(user=tous_les_roles["chef_gare"])
        _annuler(api_client, monde_a["ticket"])
        jour = self._aujourdhui()

        cloture = api_client.get(
            f"/api/tickets/cloture-caisse/?guichetier={guichetier.id}&date_debut={jour}&date_fin={jour}"
        ).data

        assert cloture["nombre_tickets"] == 0 and float(cloture["montant_total"]) == 0.0
        assert cloture["annulations"]["nombre"] == 1 and float(cloture["annulations"]["montant"]) == 5000.0

    def test_recettes_du_jour_de_la_direction(self, api_client, tous_les_roles, monde_a):
        api_client.force_authenticate(user=tous_les_roles["pdg"])
        assert float(api_client.get("/api/dashboard/direction/").data["recettes_du_jour"]) == 5000.0

        _annuler(api_client, monde_a["ticket"])

        assert float(api_client.get("/api/dashboard/direction/").data["recettes_du_jour"]) == 0.0

    def test_synthese_financiere(self, api_client, tous_les_roles, monde_a):
        jour = self._aujourdhui()
        url = f"/api/synthese-financiere/?date_debut={jour}&date_fin={jour}"
        api_client.force_authenticate(user=tous_les_roles["directeur_financier"])
        assert float(api_client.get(url).data["total"]["montant_total"]) == 5000.0

        api_client.force_authenticate(user=tous_les_roles["pdg"])
        _annuler(api_client, monde_a["ticket"])

        api_client.force_authenticate(user=tous_les_roles["directeur_financier"])
        donnees = api_client.get(url).data
        assert float(donnees["total"]["montant_total"]) == 0.0 and donnees["gares"] == []

    def test_le_ticket_annule_reste_visible_dans_la_liste(self, api_client, tous_les_roles, monde_a):
        api_client.force_authenticate(user=tous_les_roles["chef_gare"])
        _annuler(api_client, monde_a["ticket"])

        liste = {t["id"]: t["statut"] for t in api_client.get("/api/tickets/").data}

        assert liste[monde_a["ticket"].id] == "annule"
