import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/auth/app_user.dart';
import 'package:transport_mobile/data/quota_service.dart';
import 'package:transport_mobile/storage/cache_store.dart';
import 'package:transport_mobile/storage/outbox.dart';
import 'package:transport_mobile/storage/string_box.dart';
import 'package:transport_mobile/sync/action_handlers.dart';
import 'package:transport_mobile/sync/pending_action.dart';
import 'package:transport_mobile/sync/sync_service.dart';

import 'support/harness.dart';

const guichetier = AppUser(id: 7, username: 'awa', role: 'guichetier');
const chauffeur = AppUser(id: 8, username: 'kofi', role: 'chauffeur_principal');
const reserver = '/tickets/reserver-hors-ligne/';

void main() {
  late Harness h;
  late CacheStore cache;
  late Outbox outbox;
  late DateTime maintenant;
  AppUser? utilisateur;

  QuotaService creer() => QuotaService(
        api: h.api,
        cache: cache,
        outbox: outbox,
        currentUser: () => utilisateur,
        now: () => maintenant,
      );

  Map<String, dynamic> reservation(int depart, int places, {Duration valable = const Duration(hours: 6)}) => {
        'depart': depart,
        'places': places,
        'expire_le': maintenant.add(valable).toUtc().toIso8601String(),
      };

  Future<void> enfilerVente(int depart) => outbox.add(PendingAction.create(
        userId: 7,
        type: ActionTypes.venteTicket,
        payload: {'depart': depart},
      ));

  setUp(() {
    h = Harness();
    h.tokens.access = 'acc';
    cache = CacheStore(MemoryStringBox());
    outbox = Outbox(MemoryStringBox());
    maintenant = DateTime(2026, 9, 20, 10);
    utilisateur = guichetier;
  });

  test('avant toute lecture : aucune place garantie', () {
    expect(creer().remainingFor(5), 0);
  });

  test('refresh : mémorise les places réservées par le serveur', () async {
    h.server.onJson('POST', reserver, [reservation(5, 2), reservation(9, 1)]);
    final quota = creer();

    await quota.refresh();

    expect(quota.remainingFor(5), 2);
    expect(quota.remainingFor(9), 1);
    expect(quota.remainingFor(404), 0);
    expect(h.server.requestsTo('POST', reserver), hasLength(1));
  });

  test('chaque vente consomme une place, sans jamais passer sous zéro', () async {
    h.server.onJson('POST', reserver, [reservation(5, 2)]);
    final quota = creer();
    await quota.refresh();

    await quota.consume(5);
    expect(quota.remainingFor(5), 1);
    await quota.consume(5);
    await quota.consume(5);
    await quota.consume(5);

    expect(quota.remainingFor(5), 0);
  });

  test('consommer un départ sans réservation ne fait rien', () async {
    final quota = creer();

    await quota.consume(5);

    expect(quota.remainingFor(5), 0);
  });

  test('l\'état survit à la fermeture de l\'application (cache local)', () async {
    h.server.onJson('POST', reserver, [reservation(5, 2)]);
    final premiere = creer();
    await premiere.refresh();
    await premiere.consume(5);

    final rouverte = creer(); // même cache, nouvelle instance

    expect(rouverte.remainingFor(5), 1);
  });

  test('une réservation expirée ne garantit plus rien', () async {
    h.server.onJson('POST', reserver, [reservation(5, 2, valable: const Duration(hours: 1))]);
    final quota = creer();
    await quota.refresh();
    expect(quota.remainingFor(5), 2);

    maintenant = maintenant.add(const Duration(hours: 2));

    expect(quota.remainingFor(5), 0);
  });

  test('refresh : décompte les ventes encore en attente sur ce téléphone', () async {
    // Le serveur ignore ces deux ventes : il annonce encore 3 places.
    await enfilerVente(5);
    await enfilerVente(5);
    h.server.onJson('POST', reserver, [reservation(5, 3)]);
    final quota = creer();

    await quota.refresh();

    expect(quota.remainingFor(5), 1);
  });

  test('les ventes en attente d\'un autre utilisateur ne sont pas décomptées', () async {
    await outbox.add(PendingAction.create(
      userId: 99,
      type: ActionTypes.venteTicket,
      payload: {'depart': 5},
    ));
    h.server.onJson('POST', reserver, [reservation(5, 2)]);
    final quota = creer();

    await quota.refresh();

    expect(quota.remainingFor(5), 2);
  });

  test('sans réseau, refresh garde les places déjà obtenues', () async {
    h.server.onJson('POST', reserver, [reservation(5, 2)]);
    final quota = creer();
    await quota.refresh();

    h.server.offline = true;
    await quota.refresh();

    expect(quota.remainingFor(5), 2);
  });

  test('refus du serveur (403, ancien serveur 404) : rien de garanti, pas d\'erreur', () async {
    h.server.onJson('POST', reserver, {'detail': 'Interdit'}, 403);
    final quota = creer();

    await quota.refresh();

    expect(quota.remainingFor(5), 0);
  });

  test('un rôle autre que guichetier ne demande jamais de réservation', () async {
    utilisateur = chauffeur;
    final quota = creer();

    await quota.refresh();
    await quota.refreshIfStale();
    await quota.consume(5);
    await quota.release();

    expect(h.server.requests, isEmpty);
  });

  test('personne de connecté : aucune requête', () async {
    utilisateur = null;

    await creer().refresh();

    expect(h.server.requests, isEmpty);
  });

  test('plusieurs demandes simultanées partagent une seule requête', () async {
    h.server.onJson('POST', reserver, [reservation(5, 2)]);
    final quota = creer();

    await Future.wait([quota.refresh(), quota.refresh(), quota.refresh()]);

    expect(h.server.requestsTo('POST', reserver), hasLength(1));
  });

  group('refreshIfStale', () {
    test('rafraîchit la première fois, puis seulement une fois la lecture périmée', () async {
      h.server.onJson('POST', reserver, [reservation(5, 2)]);
      final quota = creer();

      await quota.refreshIfStale();
      await quota.refreshIfStale();
      expect(h.server.requestsTo('POST', reserver), hasLength(1));

      maintenant = maintenant.add(const Duration(minutes: 6));
      await quota.refreshIfStale();
      expect(h.server.requestsTo('POST', reserver), hasLength(2));
    });

    test('la date de lecture survit à la fermeture (pas de requête inutile au démarrage)', () async {
      h.server.onJson('POST', reserver, [reservation(5, 2)]);
      await creer().refresh();

      await creer().refreshIfStale();

      expect(h.server.requestsTo('POST', reserver), hasLength(1));
    });
  });

  group('onSynced (fin de synchronisation)', () {
    test('après des ventes envoyées : complète la réserve tout de suite', () async {
      h.server.onJson('POST', reserver, [reservation(5, 2)]);
      final quota = creer();
      await quota.refresh();

      await quota.onSynced(const SyncResult(sent: 1));

      expect(h.server.requestsTo('POST', reserver), hasLength(2));
    });

    test('sans rien d\'envoyé : seulement si la lecture est périmée', () async {
      h.server.onJson('POST', reserver, [reservation(5, 2)]);
      final quota = creer();
      await quota.refresh();

      await quota.onSynced(const SyncResult());

      expect(h.server.requestsTo('POST', reserver), hasLength(1));
    });
  });

  group('release (fin de service)', () {
    test('rend les places et efface l\'état local', () async {
      h.server.onJson('POST', reserver, [reservation(5, 2)]);
      h.server.on('DELETE', reserver, (_) => jsonResponse(null, 204));
      final quota = creer();
      await quota.refresh();

      await quota.release();

      expect(h.server.requestsTo('DELETE', reserver), hasLength(1));
      expect(quota.remainingFor(5), 0);
      expect(creer().remainingFor(5), 0); // ni en mémoire, ni sur le disque
    });

    test('ne libère RIEN s\'il reste des ventes hors ligne à envoyer', () async {
      h.server.onJson('POST', reserver, [reservation(5, 2)]);
      final quota = creer();
      await quota.refresh();
      await enfilerVente(5);

      await quota.release();

      expect(h.server.requestsTo('DELETE', reserver), isEmpty);
      expect(quota.remainingFor(5), 2);
    });

    test('sans réseau : sans erreur, les places expireront côté serveur', () async {
      h.server.onJson('POST', reserver, [reservation(5, 2)]);
      final quota = creer();
      await quota.refresh();

      h.server.offline = true;
      await quota.release();

      expect(quota.remainingFor(5), 2);
    });
  });

  test('deux comptes sur le même téléphone ont chacun leurs places', () async {
    h.server.onJson('POST', reserver, [reservation(5, 2)]);
    final quota = creer();
    await quota.refresh();

    utilisateur = const AppUser(id: 12, username: 'autre', role: 'guichetier');

    expect(quota.remainingFor(5), 0);
  });
}
