import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/storage/cache_store.dart';
import 'package:transport_mobile/storage/encryption_key.dart';
import 'package:transport_mobile/storage/local_store.dart';
import 'package:transport_mobile/storage/outbox.dart';
import 'package:transport_mobile/sync/pending_action.dart';

const nom = 'Kouadio Yao';
const telephone = '0700000000';

PendingAction vente() => PendingAction.create(
      userId: 1,
      type: 'vente_ticket',
      payload: {'passager_nom': nom, 'passager_telephone': telephone, 'prix': '5000'},
    );

/// Tout ce que l'application a écrit sur le disque, lu octet par octet.
String contenuBrutDesFichiers(Directory dir) => dir
    .listSync(recursive: true)
    .whereType<File>()
    .map((f) => latin1.decode(f.readAsBytesSync()))
    .join('\n');

List<int> cle(int graine) => List<int>.generate(32, (i) => (i * 7 + graine) % 256);

void main() {
  late Directory dir;

  setUp(() => dir = Directory.systemTemp.createTempSync('transport_mobile_enc_'));

  tearDown(() {
    if (dir.existsSync()) dir.deleteSync(recursive: true);
  });

  Future<void> ecrireDonnees(LocalStore store) async {
    await Outbox(store.outboxBox).add(vente());
    await CacheStore(store.cacheBox).put('u1:feuille', {'passager': nom, 'tel': telephone});
    await store.close();
  }

  group('Données du voyageur sur le disque', () {
    test('TÉMOIN : sans chiffrement, nom et téléphone sont lisibles dans les fichiers', () async {
      await ecrireDonnees(await LocalStore.open(path: dir.path, namespace: 'clair'));

      final brut = contenuBrutDesFichiers(dir);

      // Si ce test échouait, la vérification ci-dessous ne prouverait rien.
      expect(brut, contains(nom));
      expect(brut, contains(telephone));
    });

    test('avec chiffrement : ni nom, ni téléphone, ni champs, ni file d\'attente lisibles', () async {
      await ecrireDonnees(
        await LocalStore.open(path: dir.path, namespace: 'chiffre', encryptionKey: cle(1)),
      );

      final brut = contenuBrutDesFichiers(dir);

      expect(brut, isNot(contains('Kouadio')));
      expect(brut, isNot(contains(telephone)));
      expect(brut, isNot(contains('passager_nom')));
      expect(brut, isNot(contains('vente_ticket')));
      expect(brut, isNot(contains('5000')));
    });

    test('avec la bonne clé, tout est relu normalement (file d\'attente et cache)', () async {
      final action = vente();
      var store = await LocalStore.open(path: dir.path, namespace: 'relire', encryptionKey: cle(2));
      await Outbox(store.outboxBox).add(action);
      await CacheStore(store.cacheBox).put('u1:feuille', {'tel': telephone});
      await store.close();

      store = await LocalStore.open(path: dir.path, namespace: 'relire', encryptionKey: cle(2));

      expect(store.wasReset, isFalse);
      final relue = Outbox(store.outboxBox).pendingFor(1).single;
      expect(relue.id, action.id);
      expect(relue.payload['passager_nom'], nom);
      expect(CacheStore(store.cacheBox).get('u1:feuille')!.data, {'tel': telephone});
      await store.close();
    });
  });

  group('Clé perdue ou données incompatibles', () {
    test('mauvaise clé : la base illisible est effacée, l\'application repart proprement', () async {
      await ecrireDonnees(
        await LocalStore.open(path: dir.path, namespace: 'perdue', encryptionKey: cle(3)),
      );

      var store = await LocalStore.open(path: dir.path, namespace: 'perdue', encryptionKey: cle(4));

      expect(store.wasReset, isTrue);
      expect(Outbox(store.outboxBox).all(), isEmpty);
      await Outbox(store.outboxBox).add(vente());
      await store.close();

      // La base recréée fonctionne ensuite normalement avec la nouvelle clé.
      store = await LocalStore.open(path: dir.path, namespace: 'perdue', encryptionKey: cle(4));
      expect(store.wasReset, isFalse);
      expect(Outbox(store.outboxBox).pendingFor(1), hasLength(1));
      await store.close();
    });

    test('anciennes données non chiffrées + nouvelle clé : réinitialisées, sans plantage', () async {
      await ecrireDonnees(await LocalStore.open(path: dir.path, namespace: 'ancien'));

      final store = await LocalStore.open(path: dir.path, namespace: 'ancien', encryptionKey: cle(5));

      expect(store.wasReset, isTrue);
      expect(Outbox(store.outboxBox).all(), isEmpty);
      await store.close();
    });

    test('une base neuve n\'est pas signalée comme réinitialisée', () async {
      final store = await LocalStore.open(path: dir.path, namespace: 'neuve', encryptionKey: cle(6));

      expect(store.wasReset, isFalse);
      await store.close();
    });
  });

  group('EncryptionKeyProvider', () {
    test('génère une clé AES-256 au premier appel', () async {
      final key = await EncryptionKeyProvider(MemorySecretStore()).getOrCreateKey();

      expect(key, hasLength(32));
      expect(key.every((b) => b >= 0 && b < 256), isTrue);
      expect(key.toSet().length, greaterThan(8)); // pas une valeur constante
    });

    test('rend toujours la même clé ensuite (sinon la base ne serait plus lisible)', () async {
      final secrets = MemorySecretStore();

      final premiere = await EncryptionKeyProvider(secrets).getOrCreateKey();
      final seconde = await EncryptionKeyProvider(secrets).getOrCreateKey();

      expect(seconde, premiere);
    });

    test('la clé est rangée dans le coffre, encodée, jamais en clair sur disque', () async {
      final secrets = MemorySecretStore();

      final key = await EncryptionKeyProvider(secrets).getOrCreateKey();

      expect(secrets.values.values.single, base64Url.encode(key));
    });

    test('deux installations ont des clés différentes', () async {
      final a = await EncryptionKeyProvider(MemorySecretStore()).getOrCreateKey();
      final b = await EncryptionKeyProvider(MemorySecretStore()).getOrCreateKey();

      expect(a, isNot(b));
    });

    test('valeur du coffre altérée : nouvelle clé générée et enregistrée', () async {
      final secrets = MemorySecretStore();
      await EncryptionKeyProvider(secrets).getOrCreateKey();
      final nomDeLaCle = secrets.values.keys.single;

      for (final abimee in ['pas du base64 !!', base64Url.encode([1, 2, 3])]) {
        secrets.values[nomDeLaCle] = abimee;

        final key = await EncryptionKeyProvider(secrets).getOrCreateKey();

        expect(key, hasLength(32));
        expect(secrets.values[nomDeLaCle], base64Url.encode(key));
      }
    });
  });
}
