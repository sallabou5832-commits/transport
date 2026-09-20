import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/api/api_exception.dart';
import 'package:transport_mobile/auth/auth_controller.dart';
import 'package:transport_mobile/storage/cache_store.dart';
import 'package:transport_mobile/storage/string_box.dart';

import 'support/harness.dart';

void main() {
  late Harness h;
  late AuthController auth;
  late CacheStore cache;

  setUp(() {
    h = Harness();
    cache = CacheStore(MemoryStringBox());
    auth = AuthController(api: h.api, tokens: h.tokens, cache: cache);
  });

  test('connexion : appelle /auth/login/ puis /auth/me/, garde les jetons et le profil', () async {
    h.stubLogin(id: 7, role: 'chauffeur_principal');

    await auth.login('awa', 'Demo!2024');

    expect(auth.status, AuthStatus.authenticated);
    expect(auth.user!.id, 7);
    expect(auth.user!.role, 'chauffeur_principal');
    expect(auth.user!.displayName, 'Awa Koné');
    expect(auth.user!.companyName, 'STC Voyages');
    expect(await h.tokens.readAccess(), 'acc-1');
    expect(await h.tokens.readRefresh(), 'ref-1');
    expect(h.server.requestsTo('POST', '/auth/login/').single.body,
        '{"username":"awa","password":"Demo!2024"}');
  });

  test('identifiants refusés : reste déconnecté', () async {
    h.server.onJson('POST', '/auth/login/', {'detail': 'Aucun compte actif'}, 401);

    await expectLater(auth.login('awa', 'faux'), throwsA(isA<ApiException>()));

    expect(auth.status, isNot(AuthStatus.authenticated));
    expect(auth.user, isNull);
    expect(await h.tokens.readAccess(), isNull);
  });

  test('démarrage sans jeton : déconnecté', () async {
    await auth.restore();

    expect(auth.status, AuthStatus.unauthenticated);
  });

  test('démarrage avec jeton valide : reprend la session', () async {
    h.tokens.access = 'acc';
    h.server.onJson('GET', '/auth/me/', userJson(role: 'guichetier'));

    await auth.restore();

    expect(auth.status, AuthStatus.authenticated);
    expect(auth.user!.role, 'guichetier');
  });

  test('démarrage hors ligne : ouvre l\'app avec le dernier profil connu', () async {
    h.stubLogin();
    await auth.login('awa', 'x'); // remplit le cache du profil
    final second = AuthController(api: h.api, tokens: h.tokens, cache: cache);
    h.server.offline = true;

    await second.restore();

    expect(second.status, AuthStatus.authenticated);
    expect(second.user!.username, 'awa');
    expect(await h.tokens.readAccess(), 'acc-1'); // la session n'est pas perdue
  });

  test('démarrage hors ligne sans profil en cache : écran de connexion, jetons conservés', () async {
    h.tokens.access = 'acc';
    h.server.offline = true;

    await auth.restore();

    expect(auth.status, AuthStatus.unauthenticated);
    expect(await h.tokens.readAccess(), 'acc');
  });

  test('démarrage avec session expirée : déconnecte et efface les jetons', () async {
    h.tokens
      ..access = 'expiré'
      ..refresh = 'expiré';
    h.server.onJson('GET', '/auth/me/', {'detail': 'x'}, 401);
    h.server.onJson('POST', '/auth/refresh/', {'detail': 'x'}, 401);

    await auth.restore();

    expect(auth.status, AuthStatus.unauthenticated);
    expect(await h.tokens.readAccess(), isNull);
  });

  test('déconnexion : efface jetons et profil', () async {
    h.stubLogin();
    await auth.login('awa', 'x');

    await auth.logout();

    expect(auth.status, AuthStatus.unauthenticated);
    expect(auth.user, isNull);
    expect(await h.tokens.readAccess(), isNull);
    expect(cache.get('session_user'), isNull);
  });

  test('session expirée en cours d\'utilisation : repasse à l\'écran de connexion', () async {
    h.stubLogin();
    await auth.login('awa', 'x');
    h.server.onJson('GET', '/feuilles-de-route/', {'detail': 'expiré'}, 401);
    h.server.onJson('POST', '/auth/refresh/', {'detail': 'expiré'}, 401);

    await expectLater(h.api.get('/feuilles-de-route/'), throwsA(isA<ApiException>()));

    expect(auth.status, AuthStatus.unauthenticated);
  });
}
