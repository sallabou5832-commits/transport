import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/api/api_client.dart';
import 'package:transport_mobile/auth/token_storage.dart';
import 'package:transport_mobile/config.dart';
import 'package:transport_mobile/ui/config_error_app.dart';

void main() {
  group('validateApiBaseUrl', () {
    test('HTTPS accepté en release', () {
      expect(validateApiBaseUrl('https://api.exemple.ci/api', release: true), 'https://api.exemple.ci/api');
    });

    test('HTTP REFUSÉ en release (jeton et données des voyageurs en clair)', () {
      expect(
        () => validateApiBaseUrl('http://api.exemple.ci/api', release: true),
        throwsA(isA<ConfigurationException>().having((e) => e.message, 'message', contains('HTTPS'))),
      );
    });

    test('HTTP accepté en développement (serveur Django local)', () {
      expect(validateApiBaseUrl('http://192.168.1.20:8000/api', release: false), 'http://192.168.1.20:8000/api');
    });

    test('supprime les / finaux et les espaces', () {
      expect(validateApiBaseUrl('  https://api.exemple.ci/api//  ', release: true), 'https://api.exemple.ci/api');
    });

    test('adresses invalides refusées', () {
      for (final url in ['', 'localhost:8000/api', 'api.exemple.ci', 'ftp://api.exemple.ci', 'https://', '://x']) {
        expect(
          () => validateApiBaseUrl(url, release: false),
          throwsA(isA<ConfigurationException>()),
          reason: url,
        );
      }
    });

    test('la casse du protocole ne permet pas de contourner l\'exigence HTTPS', () {
      expect(() => validateApiBaseUrl('HTTP://api.exemple.ci/api', release: true), throwsA(isA<ConfigurationException>()));
      expect(validateApiBaseUrl('HTTPS://api.exemple.ci/api', release: true), 'HTTPS://api.exemple.ci/api');
    });
  });

  group('resolveApiBaseUrl', () {
    String resolve({
      String fromEnv = '',
      bool release = false,
      bool isWeb = false,
      TargetPlatform platform = TargetPlatform.android,
    }) =>
        resolveApiBaseUrl(fromEnv: fromEnv, release: release, isWeb: isWeb, platform: platform);

    test('release sans adresse configurée : refusé (jamais d\'adresse de développement)', () {
      expect(() => resolve(release: true), throwsA(isA<ConfigurationException>()));
    });

    test('release avec une adresse HTTPS : acceptée', () {
      expect(resolve(release: true, fromEnv: 'https://api.exemple.ci/api'), 'https://api.exemple.ci/api');
    });

    test('release avec une adresse HTTP : refusée', () {
      expect(() => resolve(release: true, fromEnv: 'http://api.exemple.ci/api'), throwsA(isA<ConfigurationException>()));
    });

    test('développement : émulateur Android -> machine hôte', () {
      expect(resolve(platform: TargetPlatform.android), 'http://10.0.2.2:8000/api');
    });

    test('développement : web, iOS, ordinateur -> localhost', () {
      expect(resolve(isWeb: true, platform: TargetPlatform.android), 'http://localhost:8000/api');
      expect(resolve(platform: TargetPlatform.iOS), 'http://localhost:8000/api');
      expect(resolve(platform: TargetPlatform.windows), 'http://localhost:8000/api');
    });

    test('développement : l\'adresse fournie l\'emporte', () {
      expect(resolve(fromEnv: 'http://192.168.1.20:8000/api'), 'http://192.168.1.20:8000/api');
    });
  });

  group('ApiClient : dernier garde-fou', () {
    test('refuse une adresse HTTP quand HTTPS est exigé', () {
      expect(
        () => ApiClient(baseUrl: 'http://api.exemple.ci/api', tokens: MemoryTokenStorage(), requireHttps: true),
        throwsStateError,
      );
      expect(
        () => ApiClient(baseUrl: 'HTTP://api.exemple.ci/api', tokens: MemoryTokenStorage(), requireHttps: true),
        throwsStateError,
      );
    });

    test('accepte HTTPS quand HTTPS est exigé', () {
      expect(
        () => ApiClient(baseUrl: 'https://api.exemple.ci/api', tokens: MemoryTokenStorage(), requireHttps: true),
        returnsNormally,
      );
    });

    test('en développement (tests, debug), HTTP reste possible', () {
      expect(
        () => ApiClient(baseUrl: 'http://localhost:8000/api', tokens: MemoryTokenStorage()),
        returnsNormally,
      );
    });
  });

  testWidgets('configuration invalide : un message clair remplace l\'application', (tester) async {
    await tester.pumpWidget(const ConfigErrorApp(message: 'L\'API doit être en HTTPS'));

    expect(find.text('Application mal configurée'), findsOneWidget);
    expect(find.byKey(const Key('config-error')), findsOneWidget);
    expect(find.text('L\'API doit être en HTTPS'), findsOneWidget);
  });
}
