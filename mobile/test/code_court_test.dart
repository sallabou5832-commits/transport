import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/auth/app_user.dart';
import 'package:transport_mobile/auth/auth_controller.dart';
import 'package:transport_mobile/auth/code_court_controller.dart';
import 'package:transport_mobile/auth/code_court_store.dart';
import 'package:transport_mobile/data/ma_configuration.dart';
import 'package:transport_mobile/storage/cache_store.dart';
import 'package:transport_mobile/storage/encryption_key.dart';
import 'package:transport_mobile/storage/string_box.dart';

import 'support/harness.dart';

const awa = AppUser(id: 7, username: 'awa', role: 'guichetier');
const koffi = AppUser(id: 8, username: 'koffi', role: 'guichetier');

void main() {
  group('CodeCourtStore', () {
    late MemorySecretStore secrets;
    late CodeCourtStore store;

    setUp(() {
      secrets = MemorySecretStore();
      store = CodeCourtStore(secrets);
    });

    test('garde une empreinte salée, jamais le code lui-même', () async {
      await store.definir(7, '4821');

      expect(await store.existe(), isTrue);
      expect(await store.proprietaire(), 7);
      expect(secrets.values.values.join(), isNot(contains('4821')));
      // Deux codes identiques ne donnent pas la même empreinte (sel tiré au hasard).
      final premier = secrets.values['code_court'];
      await store.definir(7, '4821');
      expect(secrets.values['code_court'], isNot(premier));
    });

    test('vérifie le code et compte les erreurs, remises à zéro par un bon code', () async {
      await store.definir(7, '4821');

      expect(await store.verifier('1111'), isFalse);
      expect(await store.verifier('48210'), isFalse);
      expect(await store.echecs(), 2);
      expect(await store.verifier('4821'), isTrue);
      expect(await store.echecs(), 0);
    });

    test('les erreurs survivent à un nouveau démarrage (même coffre)', () async {
      await store.definir(7, '4821');
      await store.verifier('0000');

      expect(await CodeCourtStore(secrets).echecs(), 1);
    });

    test('effacé : plus de code', () async {
      await store.definir(7, '4821');
      await store.effacer();

      expect(await store.existe(), isFalse);
      expect(await store.verifier('4821'), isFalse);
    });

    test('une entrée illisible vaut « pas de code »', () async {
      secrets.values['code_court'] = 'pas du json';

      expect(await store.existe(), isFalse);
      expect(await store.echecs(), 0);
    });
  });

  group('CodeCourtController', () {
    late Harness h;
    late MemorySecretStore secrets;
    late CacheStore cache;
    late AuthController auth;
    late DateTime maintenant;
    late MaConfiguration configuration;
    late CodeCourtController code;

    // Un nouveau démarrage de l'application : même coffre et même cache, configuration relue.
    CodeCourtController nouveau() {
      configuration = MaConfiguration(api: h.api, cache: cache);
      return CodeCourtController(
        store: CodeCourtStore(secrets),
        configuration: configuration,
        auth: auth,
        horloge: () => maintenant,
      );
    }

    setUp(() {
      h = Harness();
      secrets = MemorySecretStore();
      cache = CacheStore(MemoryStringBox());
      auth = AuthController(api: h.api, tokens: h.tokens, cache: cache);
      maintenant = DateTime(2026, 11, 3, 8);
      code = nouveau();
    });

    test('sans code : jamais verrouillé, et rien d\'exigé par défaut', () async {
      await code.surUtilisateur(awa, reprise: true);

      expect(code.estPretPour(7), isTrue);
      expect(code.defini, isFalse);
      expect(code.verrouille, isFalse);
      expect(code.exige, isFalse);
    });

    test('avec un code : demandé à la reprise d\'une session, pas juste après le mot de passe', () async {
      await CodeCourtStore(secrets).definir(7, '4821');

      await code.surUtilisateur(awa, reprise: true);
      expect(code.verrouille, isTrue);

      final apresMotDePasse = nouveau();
      await apresMotDePasse.surUtilisateur(awa, reprise: false);
      expect(apresMotDePasse.verrouille, isFalse);
    });

    test('le bon code déverrouille', () async {
      await CodeCourtStore(secrets).definir(7, '4821');
      await code.surUtilisateur(awa, reprise: true);

      expect(await code.deverrouiller('4821'), isTrue);
      expect(code.verrouille, isFalse);
    });

    test('5 erreurs : code effacé, retour au mot de passe avec un message', () async {
      h.stubLogin();
      await auth.login('awa', 'Demo!2024');
      await CodeCourtStore(secrets).definir(7, '4821');
      await code.surUtilisateur(awa, reprise: true);

      for (var i = 0; i < 4; i++) {
        expect(await code.deverrouiller('0000'), isFalse);
      }
      expect(code.essaisRestants, 1);
      expect(auth.status, AuthStatus.authenticated);

      expect(await code.deverrouiller('0000'), isFalse);

      expect(auth.status, AuthStatus.unauthenticated);
      expect(await CodeCourtStore(secrets).existe(), isFalse);
      expect(code.prendreAvis(), contains('Trop d\'erreurs'));
      expect(code.prendreAvis(), isNull); // lu une seule fois
    });

    test('après 5 minutes en arrière-plan : verrouillé ; moins : non', () async {
      await code.surUtilisateur(awa, reprise: false);
      await code.definir('4821');

      code.didChangeAppLifecycleState(AppLifecycleState.paused);
      maintenant = maintenant.add(const Duration(minutes: 4, seconds: 59));
      code.didChangeAppLifecycleState(AppLifecycleState.resumed);
      expect(code.verrouille, isFalse);

      code.didChangeAppLifecycleState(AppLifecycleState.hidden);
      maintenant = maintenant.add(const Duration(minutes: 5));
      code.didChangeAppLifecycleState(AppLifecycleState.resumed);
      expect(code.verrouille, isTrue);
    });

    test('sans code, l\'arrière-plan ne verrouille rien', () async {
      await code.surUtilisateur(awa, reprise: false);

      code.didChangeAppLifecycleState(AppLifecycleState.paused);
      maintenant = maintenant.add(const Duration(hours: 2));
      code.didChangeAppLifecycleState(AppLifecycleState.resumed);

      expect(code.verrouille, isFalse);
    });

    test('un autre agent qui se connecte sur ce téléphone efface le code du précédent', () async {
      await CodeCourtStore(secrets).definir(7, '4821');

      await code.surUtilisateur(koffi, reprise: false);

      expect(code.defini, isFalse);
      expect(await CodeCourtStore(secrets).existe(), isFalse);
    });

    test('exigé par la compagnie : lu sur le serveur, gardé pour le mode hors ligne, et non retirable', () async {
      h.server.onJson('GET', '/configuration/moi/', {
        'session': {'duree_max': 'deconnexion', 'code_court_exige': true},
      });
      await configuration.charger(awa.id);
      await code.surUtilisateur(awa, reprise: false);
      expect(code.exige, isTrue);
      await code.definir('4821');
      await expectLater(code.retirer(), throwsStateError);
      expect(code.defini, isTrue);

      h.server.offline = true;
      final horsLigne = nouveau();
      await configuration.charger(awa.id);
      await horsLigne.surUtilisateur(awa, reprise: true);
      expect(horsLigne.exige, isTrue);
    });

    test('un code hors format est refusé', () async {
      await code.surUtilisateur(awa, reprise: false);

      await expectLater(code.definir('12'), throwsArgumentError);
      await expectLater(code.definir('1234567'), throwsArgumentError);
      await expectLater(code.definir('12a4'), throwsArgumentError);
      expect(code.defini, isFalse);
    });

    test('retirer son code (non exigé)', () async {
      await code.surUtilisateur(awa, reprise: false);
      await code.definir('4821');

      await code.retirer();

      expect(code.defini, isFalse);
      expect(await CodeCourtStore(secrets).existe(), isFalse);
    });
  });
}
