// Test de bout en bout : l'application (réseau, authentification, file hors ligne,
// synchronisation) face au VRAI backend Django. Il n'est PAS lancé par `flutter test`
// seul : il crée de vraies données (tickets) et exige un serveur démarré.
//
//   cd transpt1 && python manage.py runserver 0.0.0.0:8000     (base avec les comptes de démo)
//   cd mobile   && flutter test tool/e2e_smoke_test.dart
//
// Autre serveur : --dart-define=API_BASE_URL=http://192.168.1.20:8000/api
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:transport_mobile/api/api_client.dart';
import 'package:transport_mobile/api/api_exception.dart';
import 'package:transport_mobile/auth/auth_controller.dart';
import 'package:transport_mobile/auth/token_storage.dart';
import 'package:transport_mobile/data/depart_repository.dart';
import 'package:transport_mobile/data/feuille_repository.dart';
import 'package:transport_mobile/data/quota_service.dart';
import 'package:transport_mobile/storage/cache_store.dart';
import 'package:transport_mobile/storage/outbox.dart';
import 'package:transport_mobile/storage/string_box.dart';
import 'package:transport_mobile/sync/action_handlers.dart';
import 'package:transport_mobile/sync/sync_service.dart';

const baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000/api');
const demoPassword = 'Demo!2024';

/// Vrai réseau, mais coupable à volonté pour simuler une perte de connexion.
class SwitchableClient extends http.BaseClient {
  final _inner = http.Client();
  bool offline = false;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    if (offline) throw http.ClientException('Réseau coupé (simulation)');
    return _inner.send(request);
  }
}

class Session {
  Session() {
    api = ApiClient(baseUrl: baseUrl, tokens: tokens, httpClient: network);
    cache = CacheStore(MemoryStringBox());
    outbox = Outbox(MemoryStringBox());
    auth = AuthController(api: api, tokens: tokens, cache: cache);
    sync = SyncService(
      outbox: outbox,
      handlers: buildActionHandlers(api),
      currentUserId: () => auth.user?.id,
      probe: () => api.get('/auth/me/'),
    );
    quota = QuotaService(api: api, cache: cache, outbox: outbox, currentUser: () => auth.user);
    sync.afterSync = quota.onSynced;
  }

  final network = SwitchableClient();
  final tokens = MemoryTokenStorage();
  late final ApiClient api;
  late final CacheStore cache;
  late final Outbox outbox;
  late final AuthController auth;
  late final SyncService sync;
  late final QuotaService quota;
}

Map<String, dynamic> vente(int departId, String nom, {String prix = '5000'}) => {
      'depart': departId,
      'passager_nom': nom,
      'passager_telephone': '0700000000',
      'prix': prix,
      'mode_paiement': 'especes',
    };

Future<List<Map<String, dynamic>>> tickets(Session s) async =>
    (await s.api.get('/tickets/') as List).cast<Map<String, dynamic>>();

void main() {
  final marque = 'E2E-${DateTime.now().millisecondsSinceEpoch}';

  test('connexion guichetier : mêmes endpoints JWT que le web', () async {
    final s = Session();

    await s.auth.login('guichetier_stc', demoPassword);

    expect(s.auth.status, AuthStatus.authenticated);
    expect(s.auth.user!.role, 'guichetier');
    expect(s.auth.user!.companyName, isNotEmpty);
    expect(await s.tokens.readAccess(), isNotEmpty);
    expect(await s.tokens.readRefresh(), isNotEmpty);
  });

  test('mauvais mot de passe : refusé (401)', () async {
    final s = Session();

    await expectLater(
      s.auth.login('guichetier_stc', 'faux'),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
    );
    expect(await s.tokens.readAccess(), isNull);
  });

  test('jeton d\'accès périmé : renouvelé automatiquement avec le refresh', () async {
    final s = Session();
    await s.auth.login('guichetier_stc', demoPassword);
    await s.tokens.save(access: 'jeton.invalide.perime');

    final me = await s.api.get('/auth/me/') as Map<String, dynamic>;

    expect(me['username'], 'guichetier_stc');
    expect(await s.tokens.readAccess(), isNot('jeton.invalide.perime'));
  });

  test('départs à vendre : lus et nommés avec leur ligne', () async {
    final s = Session();
    await s.auth.login('guichetier_stc', demoPassword);

    final departs = await DepartRepository(api: s.api, cache: s.cache).loadSellable(s.auth.user!);

    expect(departs.fromCache, isFalse);
    expect(departs.data, isNotEmpty);
    expect(departs.data.map((d) => d.ligneNom), contains('Abidjan-Bouaké'));
  });

  test('vente EN LIGNE : acceptée par le serveur', () async {
    final s = Session();
    await s.auth.login('guichetier_stc', demoPassword);
    final depart = (await DepartRepository(api: s.api, cache: s.cache).loadSellable(s.auth.user!)).data.first;

    final result = await s.sync.submit(type: ActionTypes.venteTicket, payload: vente(depart.id, '$marque en ligne'));

    expect(result.status, SubmitStatus.sent, reason: result.message);
    expect((await tickets(s)).where((t) => t['passager_nom'] == '$marque en ligne'), hasLength(1));
    expect(s.outbox.all(), isEmpty);
  });

  test('vente HORS LIGNE : conservée, puis envoyée au retour du réseau (une seule fois)', () async {
    final s = Session();
    await s.auth.login('guichetier_stc', demoPassword);
    final depart = (await DepartRepository(api: s.api, cache: s.cache).loadSellable(s.auth.user!)).data.first;
    final avant = (await tickets(s)).length;

    s.network.offline = true;
    final result = await s.sync.submit(type: ActionTypes.venteTicket, payload: vente(depart.id, '$marque hors ligne'));
    expect(result.status, SubmitStatus.queued);
    expect(s.sync.pendingCount, 1);

    s.network.offline = false;
    final sync = await s.sync.syncNow();
    await s.sync.syncNow(); // une seconde synchronisation ne doit rien renvoyer

    expect(sync.sent, 1);
    expect(s.outbox.all(), isEmpty);
    final apres = await tickets(s);
    expect(apres.length, avant + 1);
    expect(apres.where((t) => t['passager_nom'] == '$marque hors ligne'), hasLength(1));
  });

  test('vente refusée par le serveur : le message d\'erreur DRF est restitué', () async {
    final s = Session();
    await s.auth.login('guichetier_stc', demoPassword);
    final depart = (await DepartRepository(api: s.api, cache: s.cache).loadSellable(s.auth.user!)).data.first;

    final result = await s.sync.submit(
      type: ActionTypes.venteTicket,
      payload: vente(depart.id, '$marque prix nul', prix: '0'),
    );

    expect(result.status, SubmitStatus.rejected);
    expect(result.message, startsWith('prix : '));
    expect(s.outbox.all(), isEmpty);
  });

  test('chauffeur : sa feuille de route du jour', () async {
    final s = Session();
    await s.auth.login('chauffeur_stc', demoPassword);

    final feuille = await FeuilleRepository(api: s.api, cache: s.cache).loadToday(s.auth.user!);

    expect(s.auth.user!.role, 'chauffeur_principal');
    expect(feuille.data, isNotNull, reason: 'lancez seed_demo_operations (feuille du jour du chauffeur)');
    expect(feuille.data!.ligneNom, 'Abidjan-Bouaké');
    expect(feuille.data!.immatriculation, isNotEmpty);
    expect(feuille.data!.aDemarre, isFalse);
  });

  test('chauffeur hors ligne : retombe sur la dernière feuille enregistrée', () async {
    final s = Session();
    await s.auth.login('chauffeur_stc', demoPassword);
    final repository = FeuilleRepository(api: s.api, cache: s.cache);
    await repository.loadToday(s.auth.user!);

    s.network.offline = true;
    final horsLigne = await repository.loadToday(s.auth.user!);

    expect(horsLigne.fromCache, isTrue);
    expect(horsLigne.data!.ligneNom, 'Abidjan-Bouaké');
  });

  test('reprise de session hors ligne : profil relu depuis le cache', () async {
    final s = Session();
    await s.auth.login('guichetier_stc', demoPassword);
    final rouverte = AuthController(api: s.api, tokens: s.tokens, cache: s.cache);

    s.network.offline = true;
    await rouverte.restore();

    expect(rouverte.status, AuthStatus.authenticated);
    expect(rouverte.user!.username, 'guichetier_stc');
  });

  // --- Idempotence : la même vente rejouée ne crée pas de second ticket -------------------
  test('IDEMPOTENCE : la même vente rejouée renvoie le ticket existant, sans doublon', () async {
    final s = Session();
    await s.auth.login('guichetier_stc', demoPassword);
    final depart = (await DepartRepository(api: s.api, cache: s.cache).loadSellable(s.auth.user!)).data.first;
    final avant = (await tickets(s)).length;
    final cle = 'e2e-${DateTime.now().microsecondsSinceEpoch}';
    final corps = vente(depart.id, '$marque idempotent');

    final premiere = await s.api.post('/tickets/', body: corps, headers: {'Idempotency-Key': cle}) as Map;
    final rejeu = await s.api.post('/tickets/', body: corps, headers: {'Idempotency-Key': cle}) as Map;

    expect(rejeu['id'], premiere['id']);
    expect((await tickets(s)).length, avant + 1);
    // Même clé, vente différente : refusée (409).
    await expectLater(
      s.api.post('/tickets/', body: vente(depart.id, '$marque autre', prix: '9999'), headers: {'Idempotency-Key': cle}),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 409)),
    );
  });

  // --- Places garanties hors ligne (nécessite le départ « E2E-Garantie », voir plus bas) ----
  group('GARANTIE hors ligne, deux guichetiers, un car de 3 places', () {
    Future<Session> guichetier(String compte) async {
      final s = Session();
      await s.auth.login(compte, demoPassword);
      return s;
    }

    Future<int> departGarantie(Session s) async {
      final departs = await DepartRepository(api: s.api, cache: s.cache).loadSellable(s.auth.user!);
      return departs.data.firstWhere((d) => d.ligneNom == 'E2E-Garantie').id;
    }

    test('réserver, vendre hors ligne, synchroniser : tout est accepté', () async {
      final a = await guichetier('guichetier_stc');
      final b = await guichetier('guichetier2_stc');
      final departId = await departGarantie(a);
      await a.quota.release();
      await b.quota.release();

      // A (avec réseau) fait mettre 2 places de côté ; B n'obtient que la dernière.
      await a.quota.refresh();
      await b.quota.refresh();
      expect(a.quota.remainingFor(departId), 2);
      expect(b.quota.remainingFor(departId), 1);

      // B, en ligne, vend sa place réservée puis se heurte aux places réservées par A.
      final venteB = await b.sync.submit(type: ActionTypes.venteTicket, payload: vente(departId, '$marque B1'));
      expect(venteB.status, SubmitStatus.sent, reason: venteB.message);
      final refus = await b.sync.submit(type: ActionTypes.venteTicket, payload: vente(departId, '$marque B2'));
      expect(refus.status, SubmitStatus.rejected);
      expect(refus.message, contains('réservées'));

      // A perd le réseau : ses 2 ventes sont autorisées (garanties), la 3e est bloquée.
      a.network.offline = true;
      for (final nom in ['A1', 'A2']) {
        expect(a.quota.remainingFor(departId), greaterThan(0));
        final r = await a.sync.submit(type: ActionTypes.venteTicket, payload: vente(departId, '$marque $nom'));
        expect(r.status, SubmitStatus.queued);
        await a.quota.consume(departId);
      }
      expect(a.quota.remainingFor(departId), 0);
      expect(await a.sync.canReachServer(), isFalse);

      // Retour du réseau : les 2 ventes de A sont ACCEPTÉES (aucune n'est refusée).
      a.network.offline = false;
      final bilan = await a.sync.syncNow();
      expect(bilan.sent, 2);
      expect(bilan.rejected, 0);
      final vendus = (await tickets(a)).where((t) => t['depart'] == departId && '${t['passager_nom']}'.startsWith(marque));
      expect(vendus, hasLength(3)); // le car de 3 places est plein, sans dépassement

      await a.quota.release();
      await b.quota.release();
    });
  });
}
