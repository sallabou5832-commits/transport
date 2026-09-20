import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:transport_mobile/api/api_client.dart';
import 'package:transport_mobile/api/api_exception.dart';
import 'package:transport_mobile/auth/token_storage.dart';

import 'support/harness.dart';

void main() {
  late FakeServer server;
  late MemoryTokenStorage tokens;
  late ApiClient api;
  var expiredCalls = 0;

  setUp(() {
    server = FakeServer();
    tokens = MemoryTokenStorage()
      ..access = 'old-access'
      ..refresh = 'my-refresh';
    api = ApiClient(baseUrl: 'http://test/api', tokens: tokens, httpClient: server.client);
    expiredCalls = 0;
    api.onSessionExpired = () => expiredCalls++;
  });

  test('ajoute le jeton d\'accès aux requêtes authentifiées', () async {
    server.onJson('GET', '/auth/me/', {'id': 1});

    await api.get('/auth/me/');

    expect(server.requests.single.headers['Authorization'], 'Bearer old-access');
  });

  test('n\'envoie aucun jeton pour la connexion', () async {
    server.onJson('POST', '/auth/login/', {'access': 'a', 'refresh': 'r'});

    await api.post('/auth/login/', body: {'username': 'u', 'password': 'p'}, auth: false);

    expect(server.requests.single.headers.containsKey('Authorization'), isFalse);
    expect(server.requests.single.body, '{"username":"u","password":"p"}');
  });

  test('sur 401, renouvelle le jeton puis rejoue la requête', () async {
    server.on('GET', '/auth/me/', (request) {
      return request.headers['Authorization'] == 'Bearer new-access'
          ? jsonResponse({'id': 1})
          : jsonResponse({'detail': 'Token expiré'}, 401);
    });
    server.onJson('POST', '/auth/refresh/', {'access': 'new-access'});

    final data = await api.get('/auth/me/');

    expect(data, {'id': 1});
    expect(await tokens.readAccess(), 'new-access');
    expect(await tokens.readRefresh(), 'my-refresh');
    expect(server.requestsTo('POST', '/auth/refresh/').single.body, '{"refresh":"my-refresh"}');
  });

  test('plusieurs 401 simultanés ne déclenchent qu\'un seul renouvellement', () async {
    server.on('GET', '/a/', (r) => r.headers['Authorization'] == 'Bearer new-access'
        ? jsonResponse({'ok': true})
        : jsonResponse({}, 401));
    server.on('GET', '/b/', (r) => r.headers['Authorization'] == 'Bearer new-access'
        ? jsonResponse({'ok': true})
        : jsonResponse({}, 401));
    server.onJson('POST', '/auth/refresh/', {'access': 'new-access'});

    await Future.wait([api.get('/a/'), api.get('/b/')]);

    expect(server.requestsTo('POST', '/auth/refresh/'), hasLength(1));
  });

  test('refresh refusé : vide les jetons, prévient l\'application et lève 401', () async {
    server.onJson('GET', '/auth/me/', {'detail': 'expiré'}, 401);
    server.onJson('POST', '/auth/refresh/', {'detail': 'refresh expiré'}, 401);

    await expectLater(
      api.get('/auth/me/'),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
    );

    expect(await tokens.readAccess(), isNull);
    expect(await tokens.readRefresh(), isNull);
    expect(expiredCalls, 1);
  });

  test('sans jeton de renouvellement : session expirée', () async {
    tokens.refresh = null;
    server.onJson('GET', '/auth/me/', {'detail': 'expiré'}, 401);

    await expectLater(api.get('/auth/me/'), throwsA(isA<ApiException>()));

    expect(expiredCalls, 1);
  });

  test('hors ligne : lève NetworkException', () async {
    server.offline = true;

    await expectLater(api.get('/auth/me/'), throwsA(isA<NetworkException>()));
  });

  test('hors ligne pendant le renouvellement : ne déconnecte PAS l\'utilisateur', () async {
    var premierAppel = true;
    final flaky = MockClient((request) async {
      if (request.url.path.endsWith('/auth/refresh/')) {
        throw http.ClientException('Connexion perdue');
      }
      if (premierAppel) {
        premierAppel = false;
        return jsonResponse({'detail': 'expiré'}, 401);
      }
      return jsonResponse({});
    });
    final client = ApiClient(baseUrl: 'http://test/api', tokens: tokens, httpClient: flaky)
      ..onSessionExpired = () => expiredCalls++;

    await expectLater(client.get('/auth/me/'), throwsA(isA<NetworkException>()));

    expect(await tokens.readAccess(), 'old-access');
    expect(await tokens.readRefresh(), 'my-refresh');
    expect(expiredCalls, 0);
  });

  test('délai dépassé : lève NetworkException', () async {
    final slow = MockClient((request) async {
      await Future<void>.delayed(const Duration(milliseconds: 200));
      return jsonResponse({});
    });
    final client = ApiClient(
      baseUrl: 'http://test/api',
      tokens: tokens,
      httpClient: slow,
      timeout: const Duration(milliseconds: 20),
    );

    await expectLater(client.get('/x/'), throwsA(isA<NetworkException>()));
  });

  group('messages d\'erreur (même logique que le frontend web)', () {
    Future<ApiException> erreur(Object body, [int status = 400]) async {
      server.onJson('POST', '/x/', body, status);
      try {
        await api.post('/x/', body: {});
      } on ApiException catch (e) {
        return e;
      }
      fail('ApiException attendue');
    }

    test('detail', () async => expect((await erreur({'detail': 'Interdit.'}, 403)).message, 'Interdit.'));

    test('erreur de champ', () async {
      expect((await erreur({'prix': ['Valeur invalide.']})).message, 'prix : Valeur invalide.');
    });

    test('non_field_errors sans nom de champ', () async {
      expect((await erreur({'non_field_errors': ['Trop tard.']})).message, 'Trop tard.');
    });

    test('corps non JSON', () async {
      final client = ApiClient(
        baseUrl: 'http://test/api',
        tokens: tokens,
        httpClient: MockClient((_) async => http.Response('<html>oups</html>', 502)),
      );
      await expectLater(
        client.get('/x/'),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Erreur 502')),
      );
    });
  });
}
