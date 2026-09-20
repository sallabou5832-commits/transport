import 'api/api_client.dart';
import 'auth/auth_controller.dart';
import 'auth/token_storage.dart';
import 'config.dart';
import 'data/depart_repository.dart';
import 'data/feuille_repository.dart';
import 'data/quota_service.dart';
import 'storage/cache_store.dart';
import 'storage/encryption_key.dart';
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
    required this.quota,
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
    final outbox = Outbox(store.outboxBox);
    final auth = AuthController(api: api, tokens: tokens, cache: cache);
    final sync = SyncService(
      outbox: outbox,
      handlers: buildActionHandlers(api),
      currentUserId: () => auth.user?.id,
      // Vérifie que le serveur répond (sert à savoir si une vente hors ligne est possible).
      probe: () => api.get('/auth/me/'),
    );
    final quota = QuotaService(
      api: api,
      cache: cache,
      outbox: outbox,
      currentUser: () => auth.user,
    );
    sync.afterSync = quota.onSynced;
    return AppServices(
      store: store,
      api: api,
      auth: auth,
      sync: sync,
      quota: quota,
      feuilles: FeuilleRepository(api: api, cache: cache),
      departs: DepartRepository(api: api, cache: cache),
      connectivity: connectivity,
    );
  }

  /// Configuration réelle de l'application.
  ///
  /// Lève [ConfigurationException] si l'adresse de l'API est absente ou, en version
  /// release, n'est pas en HTTPS.
  static Future<AppServices> create() async {
    final baseUrl = defaultApiBaseUrl();
    final tokens = SecureTokenStorage();
    // La base locale (noms et téléphones des voyageurs) est chiffrée avec une clé gardée
    // dans le coffre du système : elle doit exister avant l'ouverture de la base.
    final encryptionKey = await EncryptionKeyProvider(FlutterSecretStore()).getOrCreateKey();
    return AppServices.assemble(
      store: await LocalStore.open(encryptionKey: encryptionKey),
      api: ApiClient(baseUrl: baseUrl, tokens: tokens),
      tokens: tokens,
      connectivity: PlatformConnectivityMonitor(),
    );
  }

  final LocalStore store;
  final ApiClient api;
  final AuthController auth;
  final SyncService sync;
  final QuotaService quota;
  final FeuilleRepository feuilles;
  final DepartRepository departs;
  final ConnectivityMonitor connectivity;
  final SyncTriggers triggers;
}
