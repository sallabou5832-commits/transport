import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/api/api_exception.dart';
import 'package:transport_mobile/storage/outbox.dart';
import 'package:transport_mobile/storage/string_box.dart';
import 'package:transport_mobile/sync/action_handlers.dart';
import 'package:transport_mobile/sync/pending_action.dart';
import 'package:transport_mobile/sync/sync_service.dart';

import 'support/harness.dart';

const type = 'test_action';

void main() {
  late Outbox outbox;
  late int? userId;
  late List<String> envoyes;
  late Future<void> Function(PendingAction) comportement;
  late SyncService sync;

  SyncService creer({int maxAttempts = 5}) => SyncService(
        outbox: outbox,
        handlers: {
          type: (action) {
            envoyes.add(action.payload['nom'] as String);
            return comportement(action);
          },
        },
        currentUserId: () => userId,
        maxAttempts: maxAttempts,
      );

  Future<void> enfiler(String nom, {int user = 1, String t = type}) =>
      outbox.add(PendingAction.create(userId: user, type: t, payload: {'nom': nom}));

  setUp(() {
    outbox = Outbox(MemoryStringBox());
    userId = 1;
    envoyes = [];
    comportement = (_) async {};
    sync = creer();
  });

  test('envoie dans l\'ordre d\'arrivée et vide la file', () async {
    await enfiler('A');
    await enfiler('B');
    await enfiler('C');

    final result = await sync.syncNow();

    expect(envoyes, ['A', 'B', 'C']);
    expect(result.sent, 3);
    expect(result.stop, SyncStop.none);
    expect(outbox.all(), isEmpty);
    expect(sync.pendingCount, 0);
    expect(sync.lastSyncAt, isNotNull);
  });

  test('pas de réseau : s\'arrête, garde tout en file, ne tente pas la suite', () async {
    await enfiler('A');
    await enfiler('B');
    comportement = (_) async => throw const NetworkException('coupé');

    final result = await sync.syncNow();

    expect(result.stop, SyncStop.offline);
    expect(result.sent, 0);
    expect(envoyes, ['A']); // B n'est pas tenté : l'ordre est préservé
    expect(outbox.pendingFor(1), hasLength(2));
    expect(outbox.pendingFor(1).first.attempts, 0); // hors ligne ≠ échec de l'action
    expect(sync.online, isFalse);
    expect(sync.pendingCount, 2);
  });

  test('retour du réseau : la file se vide, dans l\'ordre', () async {
    await enfiler('A');
    await enfiler('B');
    comportement = (_) async => throw const NetworkException('coupé');
    await sync.syncNow();
    envoyes.clear();
    comportement = (_) async {};

    final result = await sync.syncNow();

    expect(envoyes, ['A', 'B']);
    expect(result.sent, 2);
    expect(outbox.all(), isEmpty);
    expect(sync.online, isTrue);
  });

  test('refus métier (4xx) : marquée « refusée » avec le message, la suite continue', () async {
    await enfiler('A');
    await enfiler('B');
    comportement = (action) async {
      if (action.payload['nom'] == 'A') throw const ApiException(400, 'Plus de place.');
    };

    final result = await sync.syncNow();

    expect(result.sent, 1);
    expect(result.rejected, 1);
    expect(result.stop, SyncStop.none);
    final refusee = outbox.rejectedFor(1).single;
    expect(refusee.payload['nom'], 'A');
    expect(refusee.lastError, 'Plus de place.');
    expect(outbox.pendingFor(1), isEmpty);
    expect(sync.rejectedCount, 1);

    // Une action refusée n'est jamais renvoyée en boucle.
    envoyes.clear();
    await sync.syncNow();
    expect(envoyes, isEmpty);
  });

  test('erreur serveur (5xx) : s\'arrête et compte la tentative', () async {
    await enfiler('A');
    await enfiler('B');
    comportement = (_) async => throw const ApiException(503, 'Indisponible');

    final result = await sync.syncNow();

    expect(result.stop, SyncStop.serverError);
    expect(envoyes, ['A']);
    expect(outbox.pendingFor(1).first.attempts, 1);
    expect(outbox.pendingFor(1).first.lastError, 'Indisponible');
  });

  test('erreurs serveur répétées : finit par être marquée « refusée »', () async {
    sync = creer(maxAttempts: 3);
    await enfiler('A');
    comportement = (_) async => throw const ApiException(500, 'Panne');

    await sync.syncNow();
    await sync.syncNow();
    expect(outbox.pendingFor(1), hasLength(1));
    final result = await sync.syncNow();

    expect(result.rejected, 1);
    expect(outbox.pendingFor(1), isEmpty);
    expect(outbox.rejectedFor(1).single.lastError, contains('Échecs répétés'));
  });

  test('session expirée (401) : s\'arrête sans rien perdre', () async {
    await enfiler('A');
    comportement = (_) async => throw const ApiException(401, 'Expiré');

    final result = await sync.syncNow();

    expect(result.stop, SyncStop.authRequired);
    expect(outbox.pendingFor(1), hasLength(1));
    expect(outbox.pendingFor(1).first.attempts, 0);
  });

  test('n\'envoie jamais les actions d\'un autre utilisateur', () async {
    await enfiler('à moi', user: 1);
    await enfiler('à un collègue', user: 2);

    await sync.syncNow();

    expect(envoyes, ['à moi']);
    expect(outbox.pendingFor(2).single.payload['nom'], 'à un collègue');

    userId = 2;
    await sync.syncNow();
    expect(envoyes, ['à moi', 'à un collègue']);
  });

  test('déconnecté : ne fait rien', () async {
    await enfiler('A');
    userId = null;

    final result = await sync.syncNow();

    expect(result.sent, 0);
    expect(envoyes, isEmpty);
    expect(outbox.all(), hasLength(1));
  });

  test('type d\'action inconnu : refusée plutôt que de bloquer la file', () async {
    await enfiler('X', t: 'action_du_futur');
    await enfiler('A');

    final result = await sync.syncNow();

    expect(result.sent, 1);
    expect(outbox.rejectedFor(1).single.lastError, contains('action_du_futur'));
  });

  test('deux demandes simultanées partagent la même synchronisation', () async {
    await enfiler('A');
    await enfiler('B');

    await Future.wait([sync.syncNow(), sync.syncNow(), sync.syncNow()]);

    expect(envoyes, ['A', 'B']); // chaque action une seule fois
  });

  test('une action refusée peut être supprimée après revue', () async {
    await enfiler('A');
    comportement = (_) async => throw const ApiException(400, 'Non');
    await sync.syncNow();

    await sync.discard(outbox.rejectedFor(1).single.id);

    expect(outbox.all(), isEmpty);
    expect(sync.rejectedCount, 0);
  });

  group('submit (vente saisie par l\'utilisateur)', () {
    test('accepté tout de suite : « sent », rien ne reste en file', () async {
      final result = await sync.submit(type: type, payload: {'nom': 'Awa'});

      expect(result.status, SubmitStatus.sent);
      expect(outbox.all(), isEmpty);
    });

    test('hors ligne : « queued », conservée sur l\'appareil', () async {
      comportement = (_) async => throw const NetworkException('coupé');

      final result = await sync.submit(type: type, payload: {'nom': 'Awa'});

      expect(result.status, SubmitStatus.queued);
      expect(result.message, 'Pas de connexion.');
      expect(outbox.pendingFor(1).single.payload['nom'], 'Awa');
      expect(sync.pendingCount, 1);
    });

    test('refus immédiat : « rejected » avec le message, rien n\'est conservé', () async {
      comportement = (_) async => throw const ApiException(400, 'depart : Plus aucune place.');

      final result = await sync.submit(type: type, payload: {'nom': 'Awa'});

      expect(result.status, SubmitStatus.rejected);
      expect(result.message, 'depart : Plus aucune place.');
      expect(outbox.all(), isEmpty);
      expect(sync.rejectedCount, 0);
    });

    test('l\'action est écrite sur l\'appareil AVANT l\'envoi', () async {
      var presenteEnEnvoi = false;
      comportement = (action) async => presenteEnEnvoi = outbox.find(action.id) != null;

      await sync.submit(type: type, payload: {'nom': 'Awa'});

      expect(presenteEnEnvoi, isTrue);
    });

    test('passe après les actions plus anciennes (ordre respecté)', () async {
      await enfiler('ancienne');

      await sync.submit(type: type, payload: {'nom': 'nouvelle'});

      expect(envoyes, ['ancienne', 'nouvelle']);
    });

    test('déconnecté : refusée', () async {
      userId = null;

      final result = await sync.submit(type: type, payload: {'nom': 'Awa'});

      expect(result.status, SubmitStatus.rejected);
    });
  });

  group('vente de ticket (appel API réel simulé)', () {
    test('POST /tickets/ avec le corps de la vente et l\'Idempotency-Key', () async {
      final h = Harness();
      h.server.onJson('POST', '/tickets/', {'id': 99}, 201);
      final service = SyncService(
        outbox: outbox,
        handlers: buildActionHandlers(h.api),
        currentUserId: () => 1,
      );
      await h.tokens.save(access: 'acc');

      final result = await service.submit(
        type: ActionTypes.venteTicket,
        payload: {
          'depart': 5,
          'passager_nom': 'Awa Koné',
          'passager_telephone': '+2250700000000',
          'prix': '5000',
          'mode_paiement': 'especes',
        },
      );

      expect(result.status, SubmitStatus.sent);
      final requete = h.server.requestsTo('POST', '/tickets/').single;
      expect(requete.body, contains('"passager_nom":"Awa Koné"'));
      expect(requete.body, contains('"depart":5'));
      expect(requete.headers['Authorization'], 'Bearer acc');
      expect(requete.headers['Idempotency-Key'], matches(RegExp(r'^[0-9a-f-]{36}$')));
    });

    test('la même action réenvoyée garde la même Idempotency-Key', () async {
      final h = Harness();
      var appels = 0;
      h.server.on('POST', '/tickets/', (_) {
        appels++;
        return jsonResponse({'detail': 'Indisponible'}, 503);
      });
      final service = SyncService(
        outbox: outbox,
        handlers: buildActionHandlers(h.api),
        currentUserId: () => 1,
      );

      await service.submit(type: ActionTypes.venteTicket, payload: {'depart': 5});
      await service.syncNow();

      final cles = h.server.requestsTo('POST', '/tickets/').map((r) => r.headers['Idempotency-Key']);
      expect(appels, 2);
      expect(cles.toSet(), hasLength(1));
    });
  });
}
