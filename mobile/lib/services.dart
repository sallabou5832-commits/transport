import 'api/api_client.dart';
import 'auth/auth_controller.dart';
import 'auth/token_storage.dart';
import 'config.dart';
import 'data/depart_repository.dart';
import 'data/feuille_repository.dart';
import 'storage/cache_store.dart';
import 'storage/local_store.dart';
import 'storage/outbox.dart';
import 'sync/action_handlers.dart';
import 'sync/connectivity_monitor.dart';
import 'sync/sync_service.dart';
import 'sync/sync_triggers.dart';

/// Assemble toutes les briques de l'application (une seule instance, créée au démarrage).
///
/// Les tests construisent leur propre instance avec des doublures (faux réseau,
/// stockage en mémoire, connectivité pilotée à la main).
class AppServices {
  AppServices({
    required this.store,
    required this.api,
    required this.auth,
    required this.sync,
    required this.feuilles,
    required this.departs,
    required this.connectivity,
  }) : triggers = SyncTriggers(sync: sync, monitor: connectivity);

  factory AppServices.assemble({
    required LocalStore store,
    required ApiClient api,
    required TokenStorage tokens,
    required ConnectivityMonitor connectivity,
  }) {
    final cache = CacheStore(store.cacheBox);
    final auth = AuthController(api: api, tokens: tokens, cache: cache);
    final sync = SyncService(
      outbox: Outbox(store.outboxBox),
      handlers: buildActionHandlers(api),
      currentUserId: () => auth.user?.id,
    );
    return AppServices(
      store: store,
      api: api,
      auth: auth,
      sync: sync,
      feuilles: FeuilleRepository(api: api, cache: cache),
      departs: DepartRepository(api: api, cache: cache),
      connectivity: connectivity,
    );
  }

  /// Configuration réelle de l'application.
  static Future<AppServices> create() async {
    final tokens = SecureTokenStorage();
    return AppServices.assemble(
      store: await LocalStore.open(),
      api: ApiClient(baseUrl: defaultApiBaseUrl(), tokens: tokens),
      tokens: tokens,
      connectivity: PlatformConnectivityMonitor(),
    );
  }

  final LocalStore store;
  final ApiClient api;
  final AuthController auth;
  final SyncService sync;
  final FeuilleRepository feuilles;
  final DepartRepository departs;
  final ConnectivityMonitor connectivity;
  final SyncTriggers triggers;
}
