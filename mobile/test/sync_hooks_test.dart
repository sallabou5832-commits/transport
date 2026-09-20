import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/api/api_exception.dart';
import 'package:transport_mobile/storage/outbox.dart';
import 'package:transport_mobile/storage/string_box.dart';
import 'package:transport_mobile/sync/pending_action.dart';
import 'package:transport_mobile/sync/sync_service.dart';

const type = 'test_action';

void main() {
  late Outbox outbox;
  late List<SyncResult> apres;
  late Future<void> Function() sonde;
  late Future<void> Function(PendingAction) envoi;

  SyncService creer() => SyncService(
        outbox: outbox,
        handlers: {type: (action) => envoi(action)},
        currentUserId: () => 1,
        probe: () => sonde(),
      )..afterSync = (result) async => apres.add(result);

  Future<void> enfiler() =>
      outbox.add(PendingAction.create(userId: 1, type: type, payload: {'nom': 'A'}));

  setUp(() {
    outbox = Outbox(MemoryStringBox());
    apres = [];
    sonde = () async {};
    envoi = (_) async {};
  });

  group('canReachServer', () {
    test('le serveur répond : joignable, et l\'état en ligne est mis à jour', () async {
      final sync = creer()..setOnline(false);

      expect(await sync.canReachServer(), isTrue);
      expect(sync.online, isTrue);
    });

    test('réseau absent : injoignable, état hors ligne', () async {
      sonde = () async => throw const NetworkException('coupé');
      final sync = creer();

      expect(await sync.canReachServer(), isFalse);
      expect(sync.online, isFalse);
    });

    test('une réponse d\'erreur du serveur (401, 500) prouve qu\'il est joignable', () async {
      for (final status in [401, 403, 500]) {
        sonde = () async => throw ApiException(status, 'erreur');

        expect(await creer().canReachServer(), isTrue, reason: '$status');
      }
    });

    test('sans sonde configurée : se fie à l\'état connu', () async {
      final sync = SyncService(outbox: outbox, handlers: const {}, currentUserId: () => 1);

      expect(await sync.canReachServer(), isTrue);
      sync.setOnline(false);
      expect(await sync.canReachServer(), isFalse);
    });
  });

  group('afterSync (fin de synchronisation)', () {
    test('appelé avec le bilan quand la file est allée au bout', () async {
      await enfiler();
      await enfiler();

      await creer().syncNow();
      await Future<void>.delayed(Duration.zero);

      expect(apres.single.sent, 2);
      expect(apres.single.stop, SyncStop.none);
    });

    test('appelé aussi quand il n\'y a rien à envoyer (tâches périodiques)', () async {
      final sync = creer();

      await sync.syncNow();
      await Future<void>.delayed(Duration.zero);

      expect(apres.single.sent, 0);
      expect(sync.isSyncing, isFalse);
    });

    test('file vide : aucune notification d\'interface (pas de faux « synchronisation »)', () async {
      final sync = creer();
      var notifications = 0;
      sync.addListener(() => notifications++);

      await sync.syncNow();

      expect(notifications, 0);
    });

    test('pas appelé si la synchronisation s\'est arrêtée (hors ligne)', () async {
      await enfiler();
      envoi = (_) async => throw const NetworkException('coupé');

      await creer().syncNow();
      await Future<void>.delayed(Duration.zero);

      expect(apres, isEmpty);
    });

    test('une erreur dans le crochet ne casse pas la synchronisation', () async {
      await enfiler();
      final sync = creer()..afterSync = (_) async => throw StateError('boum');

      final result = await sync.syncNow();
      await Future<void>.delayed(Duration.zero);

      expect(result.sent, 1);
      expect(outbox.all(), isEmpty);
    });

    test('ne retarde pas l\'appelant : la vente rend la main sans attendre le crochet', () async {
      var termine = false;
      final sync = creer()
        ..afterSync = (_) async {
          await Future<void>.delayed(const Duration(milliseconds: 200));
          termine = true;
        };

      final resultat = await sync.submit(type: type, payload: {'nom': 'A'});

      expect(resultat.status, SubmitStatus.sent);
      expect(termine, isFalse);
      await Future<void>.delayed(const Duration(milliseconds: 300));
      expect(termine, isTrue);
    });
  });
}
