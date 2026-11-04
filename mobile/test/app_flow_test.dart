import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/storage/outbox.dart';

import 'support/app_helpers.dart';
import 'support/harness.dart';

void main() {
  group('Connexion', () {
    appTest('affiche l\'écran de connexion et valide les champs', (tester, h) async {
      await demarrer(tester, h);

      expect(find.text('Connectez-vous à votre espace'), findsOneWidget);
      await tester.tap(find.byKey(const Key('login-button')));
      await tester.pumpAndSettle();

      expect(find.text('Saisissez votre identifiant.'), findsOneWidget);
      expect(find.text('Saisissez votre mot de passe.'), findsOneWidget);
      expect(h.server.requests, isEmpty);
    });

    appTest('identifiants incorrects : message clair, reste sur la connexion', (tester, h) async {
      h.server.onJson('POST', '/auth/login/', {'detail': 'No active account found'}, 401);
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.text('Identifiant ou mot de passe incorrect.'), findsOneWidget);
      expect(find.byKey(const Key('login-button')), findsOneWidget);
    });

    appTest('serveur injoignable : message clair', (tester, h) async {
      h.server.offline = true;
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.textContaining('Impossible de joindre le serveur'), findsOneWidget);
    });

    appTest('utilise le même endpoint JWT que le web', (tester, h) async {
      h.stubLogin();
      await demarrer(tester, h);

      await seConnecter(tester);

      final login = h.server.requestsTo('POST', '/auth/login/').single;
      expect(login.body, '{"username":"awa","password":"Demo!2024"}');
      expect(h.server.requestsTo('GET', '/auth/me/').single.headers['Authorization'],
          'Bearer acc-1');
    });

    appTest('reprend la session au démarrage, sans nouvelle saisie', (tester, h) async {
      h.stubLogin();
      h.tokens.access = 'acc-1';

      await demarrer(tester, h);

      expect(find.byKey(const Key('login-button')), findsNothing);
      expect(find.text('Bonjour Awa Koné'), findsOneWidget);
    });
  });

  group('Accueil selon le rôle', () {
    appTest('guichetier : bouton « Vendre un ticket »', (tester, h) async {
      h.stubLogin(role: 'guichetier');
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.text('Bonjour Awa Koné'), findsOneWidget);
      expect(find.text('Guichetier · STC Voyages'), findsOneWidget);
      expect(find.text('Vendre un ticket'), findsOneWidget);
    });

    appTest('chauffeur principal : sa feuille de route du jour', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.text('Feuille de route du jour'), findsOneWidget);
      expect(find.byKey(const Key('feuille-card')), findsOneWidget);
      expect(find.text('Adjamé-Bouaké'), findsOneWidget);
      expect(find.text('CI-1234-AB'), findsOneWidget);
      expect(find.text('Pas encore parti'), findsOneWidget);
      // Seule SA feuille est chargée, pas celle du collègue.
      expect(h.server.requestsTo('GET', '/departs/5/'), hasLength(1));
      expect(h.server.requestsTo('GET', '/departs/6/'), isEmpty);
      // Et le serveur est prié de ne renvoyer que celle-là, pour ce jour (pas toutes celles de la compagnie).
      final demande = h.server.requestsTo('GET', '/feuilles-de-route/').single.url.queryParameters;
      final maintenant = DateTime.now();
      final jour = '${maintenant.year.toString().padLeft(4, '0')}-${maintenant.month.toString().padLeft(2, '0')}-'
          '${maintenant.day.toString().padLeft(2, '0')}';
      expect(demande, {'chauffeur': '7', 'date': jour});
    });

    appTest('chauffeur relais : même accueil', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_relais');
      h.stubFeuilleDuJour(chauffeurId: 7);
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.byKey(const Key('feuille-card')), findsOneWidget);
    });

    appTest('chauffeur sans feuille aujourd\'hui : message adapté', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.server.onJson('GET', '/feuilles-de-route/', []);
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.byKey(const Key('feuille-vide')), findsOneWidget);
    });

    appTest('chauffeur hors ligne : dernière feuille enregistrée, signalée comme telle',
        (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      await demarrer(tester, h);
      await seConnecter(tester);
      expect(find.byKey(const Key('feuille-card')), findsOneWidget);

      // L'application est fermée, le réseau disparaît, puis elle est rouverte.
      await tester.pumpWidget(const SizedBox.shrink());
      h.server.offline = true;
      h.connectivity.setOnline(false);
      await demarrer(tester, h);

      expect(find.byKey(const Key('feuille-card')), findsOneWidget);
      expect(find.text('Adjamé-Bouaké'), findsOneWidget);
      expect(find.textContaining('Hors ligne : données du'), findsOneWidget);
    });

    appTest('chauffeur hors ligne sans rien d\'enregistré : explique la situation', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.tokens.access = 'acc-1';
      h.server.onJson('GET', '/auth/me/', userJson(id: 7, role: 'chauffeur_principal'));
      await demarrer(tester, h); // en ligne : profil mis en cache, feuille inconnue (404)
      await tester.pumpWidget(const SizedBox.shrink());
      h.server.offline = true;

      await demarrer(tester, h);

      expect(find.byKey(const Key('feuille-erreur')), findsOneWidget);
    });

    appTest('rôle de bureau : renvoie vers l\'application web', (tester, h) async {
      h.stubLogin(role: 'chef_gare');
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.textContaining('ordinateur'), findsOneWidget);
    });

    appTest('rôle de terrain sans écran dédié : « arrive bientôt »', (tester, h) async {
      h.stubLogin(role: 'bagagiste');
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.text('Votre espace mobile arrive bientôt.'), findsOneWidget);
    });
  });

  group('Billetterie externe (T-02)', () {
    appTest('la compagnie vend par son logiciel : l\'accueil ne propose plus la vente', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      h.server.onJson('GET', '/configuration/moi/', {'vente_au_guichet': false});
      await demarrer(tester, h);
      await seConnecter(tester);

      expect(find.byKey(const Key('vendre-ticket')), findsNothing);
      expect(find.byKey(const Key('vente-fermee')), findsOneWidget);
      expect(find.textContaining('propre logiciel'), findsOneWidget);
    });

    appTest('passée en externe après la connexion : l\'écran de vente se ferme à son ouverture', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      h.server.onJson('GET', '/configuration/moi/', {'vente_au_guichet': true});
      await demarrer(tester, h);
      await seConnecter(tester);
      expect(find.byKey(const Key('vendre-ticket')), findsOneWidget);

      h.server.onJson('GET', '/configuration/moi/', {'vente_au_guichet': false});
      await ouvrirVente(tester);

      expect(find.byKey(const Key('vente-fermee')), findsOneWidget);
      expect(find.byKey(const Key('valider-vente')), findsNothing);
      expect(h.server.requestsTo('POST', '/tickets/'), isEmpty);
    });

    appTest('hors ligne, la dernière configuration connue vaut : vente fermée gardée', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      h.server.onJson('GET', '/configuration/moi/', {'vente_au_guichet': false});
      await demarrer(tester, h);
      await seConnecter(tester);
      h.server.offline = true;
      h.connectivity.setOnline(false);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('vente-fermee')), findsOneWidget);
      expect(find.byKey(const Key('vendre-ticket')), findsNothing);
    });
  });

  group('Vente de ticket', () {
    appTest('en ligne : envoyée tout de suite au serveur', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      h.server.onJson('POST', '/tickets/', {'id': 99}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);

      await remplirEtValiderVente(tester);

      final vente = h.server.requestsTo('POST', '/tickets/').single;
      expect(vente.body, contains('"depart":5'));
      expect(vente.body, contains('"passager_nom":"Kouadio Yao"'));
      expect(vente.body, contains('"passager_telephone":"0700000000"'));
      expect(vente.body, contains('"prix":"5000"'));
      expect(vente.body, contains('"mode_paiement":"especes"'));
      expect(find.text('Ticket vendu.'), findsOneWidget);
      // Le départ terminé (id 6) n'est pas proposé.
      expect(Outbox(h.services.store.outboxBox).all(), isEmpty);
    });

    appTest('ligne à tarif : prix affiché et non modifiable, la vente part sans prix (G-02)', (tester, h) async {
      h.stubLogin();
      h.stubDeparts(tarif: '6000.00');
      h.server.onJson('POST', '/tickets/', {'id': 99}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);
      await choisirDepart(tester);

      TextField prix() => tester.widget<TextField>(
            find.descendant(of: find.byKey(const Key('prix')), matching: find.byType(TextField)),
          );
      expect(prix().controller!.text, '6000');
      expect(prix().readOnly, isTrue);
      expect(find.text('Prix (tarif de la ligne)'), findsOneWidget);

      await tester.enterText(find.byKey(const Key('passager-nom')), 'Kouadio Yao');
      await tester.enterText(find.byKey(const Key('passager-telephone')), '0700000000');
      await tester.tap(find.byKey(const Key('valider-vente')));
      await tester.pumpAndSettle();

      final vente = h.server.requestsTo('POST', '/tickets/').single;
      expect(vente.body, contains('"depart":5'));
      expect(vente.body, isNot(contains('"prix"')), reason: 'le serveur applique le tarif de la ligne');
      expect(find.text('Ticket vendu.'), findsOneWidget);
      // Le formulaire est prêt pour le voyageur suivant, au même tarif.
      expect(prix().controller!.text, '6000');
    });

    appTest('refusée par le serveur : l\'erreur est affichée et rien n\'est conservé', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      h.server.onJson(
        'POST',
        '/tickets/',
        {'depart': ['Plus aucune place disponible sur ce départ.']},
        400,
      );
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);

      await remplirEtValiderVente(tester);

      expect(find.text('depart : Plus aucune place disponible sur ce départ.'), findsOneWidget);
      expect(Outbox(h.services.store.outboxBox).all(), isEmpty);
    });

    appTest('formulaire incomplet : rien n\'est envoyé', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);

      await tester.tap(find.byKey(const Key('valider-vente')));
      await tester.pumpAndSettle();

      expect(find.text('Choisissez un départ.'), findsOneWidget);
      expect(find.text('Saisissez le nom du voyageur.'), findsOneWidget);
      expect(find.text('Saisissez un prix supérieur à 0.'), findsOneWidget);
      expect(h.server.requestsTo('POST', '/tickets/'), isEmpty);
    });

    appTest('HORS LIGNE : enregistrée sur le téléphone, envoyée au retour du réseau',
        (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      h.server.onJson('POST', '/tickets/', {'id': 99}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      // Première visite en ligne : les départs sont mis en cache sur l'appareil.
      await ouvrirVente(tester);
      await retour(tester);
      expect(find.text('Tout est synchronisé'), findsOneWidget);

      // Le réseau disparaît : la vente est quand même possible.
      h.server.offline = true;
      h.connectivity.setOnline(false);
      await tester.pumpAndSettle();
      expect(find.textContaining('Hors ligne'), findsOneWidget);
      await ouvrirVente(tester);
      expect(find.textContaining('Hors ligne : départs du'), findsOneWidget);
      await remplirEtValiderVente(tester);

      expect(find.textContaining('Vente enregistrée sur le téléphone'), findsOneWidget);
      expect(Outbox(h.services.store.outboxBox).pendingFor(7), hasLength(1));
      expect(h.server.requestsTo('POST', '/tickets/'), isEmpty);
      await retour(tester);
      expect(find.text('Hors ligne : 1 action(s) en attente d\'envoi'), findsOneWidget);

      // Retour du réseau : synchronisation automatique.
      h.server.offline = false;
      h.connectivity.setOnline(true);
      await tester.pumpAndSettle();

      final vente = h.server.requestsTo('POST', '/tickets/').single;
      expect(vente.body, contains('"passager_nom":"Kouadio Yao"'));
      expect(Outbox(h.services.store.outboxBox).all(), isEmpty);
      expect(find.text('Tout est synchronisé'), findsOneWidget);
    });

    appTest('vente hors ligne refusée à la synchronisation : signalée « à revoir »',
        (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);
      await retour(tester);
      h.server.offline = true;
      await ouvrirVente(tester);
      await remplirEtValiderVente(tester);
      await retour(tester);

      h.server.offline = false;
      h.server.onJson('POST', '/tickets/', {'depart': ['Plus aucune place.']}, 400);
      h.connectivity.setOnline(true);
      await tester.pumpAndSettle();

      expect(find.textContaining('1 action(s) refusée(s)'), findsOneWidget);
      await tester.tap(find.byKey(const Key('sync-status-bar')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Refusée : depart : Plus aucune place.'), findsOneWidget);
      expect(find.text('Vente de ticket : Kouadio Yao'), findsOneWidget);

      await tester.tap(find.byTooltip('Supprimer'));
      await tester.pumpAndSettle();
      expect(find.text('Aucune action en attente.'), findsOneWidget);
    });
  });

  group('Déconnexion', () {
    appTest('sans action en attente : directe', (tester, h) async {
      h.stubLogin();
      await demarrer(tester, h);
      await seConnecter(tester);

      await tester.tap(find.byKey(const Key('logout')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('login-button')), findsOneWidget);
      expect(h.tokens.access, isNull);
    });

    appTest('avec actions en attente : demande confirmation et les garde sur l\'appareil',
        (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);
      await retour(tester);
      h.server.offline = true;
      await ouvrirVente(tester);
      await remplirEtValiderVente(tester);
      await retour(tester);

      await tester.tap(find.byKey(const Key('logout')));
      await tester.pumpAndSettle();
      expect(find.textContaining('1 action(s) n\'ont pas encore été envoyées'), findsOneWidget);

      await tester.tap(find.text('Annuler'));
      await tester.pumpAndSettle();
      expect(find.text('Vendre un ticket'), findsOneWidget); // toujours connecté

      await tester.tap(find.byKey(const Key('logout')));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Se déconnecter'));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('login-button')), findsOneWidget);
      expect(Outbox(h.services.store.outboxBox).all(), hasLength(1)); // conservée
    });
  });
}
