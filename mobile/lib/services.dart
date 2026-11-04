import 'api/api_client.dart';
import 'api/api_exception.dart';
import 'auth/auth_controller.dart';
import 'auth/code_court_controller.dart';
import 'auth/code_court_store.dart';
import 'auth/token_storage.dart';
import 'config.dart';
import 'data/depart_repository.dart';
import 'data/feuille_repository.dart';
import 'data/guide.dart';
import 'data/ma_configuration.dart';
import 'data/quota_service.dart';
import 'gps/device_location_source.dart';
import 'gps/location_source.dart';
import 'gps/position_batcher.dart';
import 'gps/trip_gps_controller.dart';
import 'storage/cache_store.dart';
import 'storage/encryption_key.dart';
import 'storage/local_store.dart';
import 'storage/outbox.dart';
import 'sync/action_handlers.dart';
import 'sync/connectivity_monitor.dart';
import 'sync/sync_service.dart';
import 'sync/sync_triggers.dart';
import 'voice/voice_form_session.dart';

/// Assemble toutes les briques de l'application (une seule instance, créée au démarrage).
///
/// Les tests construisent leur propre instance avec des doublures (faux réseau,
/// stockage en mémoire, connectivité pilotée à la main).
class AppServices {
  AppServices({
    required this.store,
    required this.api,
    required this.auth,
    required this.codeCourt,
    required this.maConfiguration,
    required this.creerSessionVocale,
    required this.sync,
    required this.quota,
    required this.feuilles,
    required this.departs,
    required this.guides,
    required this.connectivity,
    required this.gps,
  }) : triggers = SyncTriggers(sync: sync, monitor: connectivity);

  factory AppServices.assemble({
    required LocalStore store,
    required ApiClient api,
    required TokenStorage tokens,
    required SecretStore secrets,
    required ConnectivityMonitor connectivity,
    LocationSource? location,
    VoiceFormSession Function()? sessionVocale,
  }) {
    final cache = CacheStore(store.cacheBox);
    final outbox = Outbox(store.outboxBox);
    final auth = AuthController(api: api, tokens: tokens, cache: cache);
    final maConfiguration = MaConfiguration(api: api, cache: cache);
    final codeCourt = CodeCourtController(store: CodeCourtStore(secrets), configuration: maConfiguration, auth: auth);
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
      codeCourt: codeCourt,
      maConfiguration: maConfiguration,
      creerSessionVocale: sessionVocale ?? VoiceFormSession.new,
      sync: sync,
      quota: quota,
      feuilles: FeuilleRepository(api: api, cache: cache),
      departs: DepartRepository(api: api, cache: cache),
      guides: GuideRepository(api: api, cache: cache),
      connectivity: connectivity,
      gps: TripGpsController(
        verifierTrajetEnCours: () async {
          try {
            final reponse = await api.get('/suivi/moi/') as Map<String, dynamic>;
            return reponse['en_cours'] == true;
          } on ApiException {
            return false; // Rôle sans trajet, ou session expirée : pas de suivi.
          } on NetworkException {
            return null; // État inconnu : ne pas couper un suivi en cours sur un accroc réseau.
          }
        },
        location: location ?? DeviceLocationSource(),
        batcher: PositionBatcher(
          box: store.positionsBox,
          envoyer: (lot) async => await api.post('/positions/', body: lot),
        ),
      ),
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
    final secrets = FlutterSecretStore();
    final encryptionKey = await EncryptionKeyProvider(secrets).getOrCreateKey();
    return AppServices.assemble(
      store: await LocalStore.open(encryptionKey: encryptionKey),
      api: ApiClient(baseUrl: baseUrl, tokens: tokens),
      tokens: tokens,
      secrets: secrets,
      connectivity: PlatformConnectivityMonitor(),
    );
  }

  final LocalStore store;
  final ApiClient api;
  final AuthController auth;
  final CodeCourtController codeCourt;
  final MaConfiguration maConfiguration;

  /// Une session de dictée vocale (le vrai moteur du téléphone ; les tests en passent une avec un faux moteur).
  final VoiceFormSession Function() creerSessionVocale;
  final SyncService sync;
  final QuotaService quota;
  final FeuilleRepository feuilles;
  final DepartRepository departs;
  final GuideRepository guides;
  final ConnectivityMonitor connectivity;
  final SyncTriggers triggers;
  final TripGpsController gps;
}
