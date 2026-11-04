import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/auth/code_court_store.dart';

import 'support/app_helpers.dart';
import 'support/harness.dart';

/// Accès au compte sur le téléphone : « rester connecté », code court, mot de passe (lot P1a).
void main() {
  Future<void> saisirCode(WidgetTester tester, String code, {String? confirmation}) async {
    await tester.enterText(find.byKey(const Key('code-court')), code);
    if (confirmation != null) await tester.enterText(find.byKey(const Key('code-court-confirmation')), confirmation);
    await tester.tap(find.byKey(const Key('code-court-valider')));
    await tester.pumpAndSettle();
  }

  group('Rester connecté', () {
    appTest('sans case cochée : rien de plus n\'est envoyé (1 jour, comme avant)', (tester, h) async {
      h.stubLogin();
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(h.server.requestsTo('POST', '/auth/login/').single.body, '{"username":"awa","password":"Demo!2024"}');
    });

    appTest('case cochée : la durée choisie part au serveur', (tester, h) async {
      h.stubLogin();
      await demarrer(tester, h);

      await tester.tap(find.byKey(const Key('rester-connecte')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('duree-session')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('30 jours').last);
      await tester.pumpAndSettle();
      await seConnecter(tester);

      expect(h.server.requestsTo('POST', '/auth/login/').single.body, contains('"duree_session":"mois"'));
      expect(find.text('Bonjour Awa Koné'), findsOneWidget);
    });
  });

  group('Code court', () {
    appTest('session reprise avec un code : demandé avant l\'accueil, qui ne s\'affiche qu\'ensuite', (tester, h) async {
      h.stubLogin();
      h.tokens.access = 'acc-1';
      await CodeCourtStore(h.secrets).definir(7, '4821');

      await demarrer(tester, h);

      expect(find.byKey(const Key('code-court')), findsOneWidget);
      expect(find.text('Vendre un ticket'), findsNothing);

      await saisirCode(tester, '1111');
      expect(find.textContaining('Encore 4 essais'), findsOneWidget);

      await saisirCode(tester, '4821');
      expect(find.text('Vendre un ticket'), findsOneWidget);
    });

    appTest('5 erreurs : retour à l\'écran de connexion, avec l\'explication', (tester, h) async {
      h.stubLogin();
      h.tokens.access = 'acc-1';
      await CodeCourtStore(h.secrets).definir(7, '4821');
      await demarrer(tester, h);

      for (var i = 0; i < 5; i++) {
        await saisirCode(tester, '0000');
      }

      expect(find.byKey(const Key('login-button')), findsOneWidget);
      expect(find.textContaining('Trop d\'erreurs de code court'), findsOneWidget);
      expect(h.tokens.access, isNull);
    });

    appTest('code oublié : retour au mot de passe', (tester, h) async {
      h.stubLogin();
      h.tokens.access = 'acc-1';
      await CodeCourtStore(h.secrets).definir(7, '4821');
      await demarrer(tester, h);

      await tester.tap(find.byKey(const Key('code-court-oublie')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('login-button')), findsOneWidget);
      expect(await CodeCourtStore(h.secrets).existe(), isFalse);
    });

    appTest('exigé par la compagnie : à choisir juste après la connexion, avant l\'accueil', (tester, h) async {
      h.stubLogin();
      h.server.onJson('GET', '/configuration/moi/', {
        'session': {'duree_max': 'deconnexion', 'code_court_exige': true},
      });
      await demarrer(tester, h);

      await seConnecter(tester);
      expect(find.text('Choisissez votre code court'), findsOneWidget);
      expect(find.text('Vendre un ticket'), findsNothing);

      await saisirCode(tester, '4821', confirmation: '4822');
      expect(find.text('La confirmation ne correspond pas au code.'), findsOneWidget);

      await saisirCode(tester, '4821', confirmation: '4821');
      expect(find.text('Vendre un ticket'), findsOneWidget);
      expect(await CodeCourtStore(h.secrets).existe(), isTrue);
    });

    appTest('facultatif : on le choisit depuis Mes paramètres, puis on le retire', (tester, h) async {
      h.stubLogin();
      await demarrer(tester, h);
      await seConnecter(tester);

      await tester.tap(find.byKey(const Key('mes-parametres')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Aucun'), findsOneWidget);

      await tester.tap(find.byKey(const Key('code-court-choisir')));
      await tester.pumpAndSettle();
      await saisirCode(tester, '482193', confirmation: '482193');

      expect(find.text('Code court enregistré.'), findsOneWidget);
      expect(find.textContaining('Actif'), findsOneWidget);

      await tester.tap(find.byKey(const Key('code-court-retirer')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Aucun'), findsOneWidget);
      expect(await CodeCourtStore(h.secrets).existe(), isFalse);
    });
  });

  group('Mot de passe', () {
    Future<void> ouvrirParametres(WidgetTester tester, Harness h) async {
      h.stubLogin();
      await demarrer(tester, h);
      await seConnecter(tester);
      await tester.tap(find.byKey(const Key('mes-parametres')));
      await tester.pumpAndSettle();
    }

    Future<void> remplir(WidgetTester tester, {String confirmation = 'Nouveau-Mot-2026'}) async {
      await tester.enterText(find.byKey(const Key('mdp-ancien')), 'Demo!2024');
      await tester.enterText(find.byKey(const Key('mdp-nouveau')), 'Nouveau-Mot-2026');
      await tester.enterText(find.byKey(const Key('mdp-confirmation')), confirmation);
      await tester.ensureVisible(find.byKey(const Key('mdp-changer')));
      await tester.tap(find.byKey(const Key('mdp-changer')));
      await tester.pumpAndSettle();
    }

    appTest('changé : ce téléphone garde sa session avec les nouveaux jetons', (tester, h) async {
      await ouvrirParametres(tester, h);
      h.server.onJson('POST', '/auth/mot-de-passe/', {'access': 'acc-2', 'refresh': 'ref-2', 'duree_session': 'jour'});

      await remplir(tester);

      final requete = h.server.requestsTo('POST', '/auth/mot-de-passe/').single;
      expect(requete.body, '{"ancien":"Demo!2024","nouveau":"Nouveau-Mot-2026","refresh":"ref-1"}');
      expect(find.textContaining('Mot de passe changé'), findsOneWidget);
      expect(h.tokens.access, 'acc-2');
      expect(h.tokens.refresh, 'ref-2');
    });

    appTest('refusé par le serveur : son message est affiché, les jetons restent', (tester, h) async {
      await ouvrirParametres(tester, h);
      h.server.onJson('POST', '/auth/mot-de-passe/', {'ancien': ['Mot de passe actuel incorrect.']}, 400);

      await remplir(tester);

      expect(find.textContaining('Mot de passe actuel incorrect.'), findsOneWidget);
      expect(h.tokens.access, 'acc-1');
    });

    appTest('provisoire : à remplacer avant l\'accueil, qui s\'ouvre ensuite', (tester, h) async {
      var provisoire = true;
      h.server.onJson('POST', '/auth/login/', {'access': 'acc-1', 'refresh': 'ref-1'});
      h.server.on('GET', '/auth/me/', (_) => jsonResponse({...userJson(), 'doit_changer_mot_de_passe': provisoire}));
      h.server.on('POST', '/auth/mot-de-passe/', (_) {
        provisoire = false;
        return jsonResponse({'access': 'acc-2', 'refresh': 'ref-2', 'duree_session': 'jour'});
      });
      await demarrer(tester, h);
      await seConnecter(tester);

      expect(find.byKey(const Key('mdp-provisoire')), findsOneWidget);
      expect(find.text('Vendre un ticket'), findsNothing);
      expect(find.text('Mot de passe provisoire'), findsOneWidget);

      await remplir(tester);

      expect(find.text('Vendre un ticket'), findsOneWidget);
      expect(h.tokens.access, 'acc-2');
    });

    appTest('provisoire : on peut aussi se déconnecter', (tester, h) async {
      h.server.onJson('POST', '/auth/login/', {'access': 'acc-1', 'refresh': 'ref-1'});
      h.server.onJson('GET', '/auth/me/', {...userJson(), 'doit_changer_mot_de_passe': true});
      await demarrer(tester, h);
      await seConnecter(tester);

      await tester.tap(find.byKey(const Key('logout')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('login-button')), findsOneWidget);
    });

    appTest('confirmation différente : rien n\'est envoyé', (tester, h) async {
      await ouvrirParametres(tester, h);

      await remplir(tester, confirmation: 'autre-chose');

      expect(find.text('La confirmation ne correspond pas.'), findsOneWidget);
      expect(h.server.requestsTo('POST', '/auth/mot-de-passe/'), isEmpty);
    });
  });
}
