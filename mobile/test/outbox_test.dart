import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/storage/cache_store.dart';
import 'package:transport_mobile/storage/local_store.dart';
import 'package:transport_mobile/storage/outbox.dart';
import 'package:transport_mobile/storage/string_box.dart';
import 'package:transport_mobile/sync/pending_action.dart';

PendingAction action(String nom, {int userId = 1, String type = 'vente_ticket'}) =>
    PendingAction.create(userId: userId, type: type, payload: {'passager_nom': nom});

void main() {
  group('Outbox (mémoire)', () {
    late Outbox outbox;

    setUp(() => outbox = Outbox(MemoryStringBox()));

    test('conserve l\'ordre d\'arrivée', () async {
      for (final nom in ['A', 'B', 'C']) {
        await outbox.add(action(nom));
      }

      expect(outbox.all().map((a) => a.payload['passager_nom']), ['A', 'B', 'C']);
    });

    test('sépare les actions par utilisateur', () async {
      await outbox.add(action('Awa', userId: 1));
      await outbox.add(action('Koffi', userId: 2));

      expect(outbox.pendingFor(1).map((a) => a.payload['passager_nom']), ['Awa']);
      expect(outbox.pendingFor(2).map((a) => a.payload['passager_nom']), ['Koffi']);
      expect(outbox.pendingFor(3), isEmpty);
    });

    test('mise à jour et suppression par identifiant', () async {
      final a = action('Awa');
      await outbox.add(a);
      await outbox.add(action('Koffi'));

      await outbox.update(a.copyWith(status: ActionStatus.rejected, lastError: 'Plus de place'));
      expect(outbox.rejectedFor(1).single.lastError, 'Plus de place');
      expect(outbox.pendingFor(1), hasLength(1));
      expect(outbox.all().first.id, a.id); // l'ordre n'a pas bougé

      await outbox.remove(a.id);
      expect(outbox.find(a.id), isNull);
      expect(outbox.all(), hasLength(1));
    });

    test('ignore une entrée corrompue au lieu de bloquer la file', () async {
      final box = MemoryStringBox();
      await box.add('ceci n\'est pas du JSON');
      final outbox = Outbox(box);
      await outbox.add(action('Awa'));

      expect(outbox.all().single.payload['passager_nom'], 'Awa');
    });

    test('identifiants d\'action uniques, au format UUID v4', () {
      final ids = {for (var i = 0; i < 200; i++) newActionId()};

      expect(ids, hasLength(200));
      expect(
        ids.every((id) => RegExp(
              r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            ).hasMatch(id)),
        isTrue,
      );
    });

    test('sérialisation aller-retour', () {
      final a = action('Awa').copyWith(attempts: 2, status: ActionStatus.rejected, lastError: 'x');

      final b = PendingAction.fromJson(a.toJson());

      expect(b.id, a.id);
      expect(b.userId, a.userId);
      expect(b.payload, a.payload);
      expect(b.attempts, 2);
      expect(b.status, ActionStatus.rejected);
      expect(b.lastError, 'x');
      expect(b.createdAt, a.createdAt);
    });
  });

  group('CacheStore', () {
    test('enregistre et relit des données avec leur date', () async {
      final cache = CacheStore(MemoryStringBox());
      await cache.put('cle', {'a': 1});

      final entry = cache.get('cle')!;
      expect(entry.data, {'a': 1});
      expect(DateTime.now().difference(entry.savedAt).inSeconds, lessThan(5));

      await cache.remove('cle');
      expect(cache.get('cle'), isNull);
    });

    test('une entrée illisible est traitée comme absente', () async {
      final box = MemoryStringBox();
      await box.put('cle', '{pas du json');

      expect(CacheStore(box).get('cle'), isNull);
    });

    test('une donnée vide (null) est distinguée d\'une donnée absente', () async {
      final cache = CacheStore(MemoryStringBox());
      await cache.put('cle', null);

      expect(cache.get('cle'), isNotNull);
      expect(cache.get('cle')!.data, isNull);
      expect(cache.get('autre'), isNull);
    });
  });

  // Persistance réelle sur disque (Hive) : c'est ce qui protège une vente faite
  // hors ligne si l'application est fermée ou si le téléphone redémarre.
  group('Persistance Hive sur disque', () {
    late Directory dir;

    setUp(() => dir = Directory.systemTemp.createTempSync('transport_mobile_test_'));

    tearDown(() {
      if (dir.existsSync()) dir.deleteSync(recursive: true);
    });

    test('les actions en attente survivent à la fermeture de l\'application', () async {
      var store = await LocalStore.open(path: dir.path, namespace: 'persist');
      final outbox = Outbox(store.outboxBox);
      final premiere = action('Awa');
      await outbox.add(premiere);
      await outbox.add(action('Koffi'));
      await outbox.update(premiere.copyWith(attempts: 3, lastError: 'serveur en panne'));
      await store.close();

      store = await LocalStore.open(path: dir.path, namespace: 'persist');
      final rouverte = Outbox(store.outboxBox).pendingFor(1);

      expect(rouverte.map((a) => a.payload['passager_nom']), ['Awa', 'Koffi']);
      expect(rouverte.first.attempts, 3);
      expect(rouverte.first.lastError, 'serveur en panne');
      expect(rouverte.first.id, premiere.id);
      await store.close();
    });

    test('le cache survit lui aussi à la fermeture', () async {
      var store = await LocalStore.open(path: dir.path, namespace: 'persist_cache');
      await CacheStore(store.cacheBox).put('u1:departs', [1, 2, 3]);
      await store.close();

      store = await LocalStore.open(path: dir.path, namespace: 'persist_cache');

      expect(CacheStore(store.cacheBox).get('u1:departs')!.data, [1, 2, 3]);
      await store.close();
    });
  });
}
