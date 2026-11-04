import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:transport_mobile/api/api_client.dart';
import 'package:transport_mobile/auth/token_storage.dart';
import 'package:transport_mobile/services.dart';
import 'package:transport_mobile/storage/encryption_key.dart';
import 'package:transport_mobile/storage/local_store.dart';
import 'package:transport_mobile/sync/connectivity_monitor.dart';
import 'package:transport_mobile/voice/voice_form_session.dart';

http.Response jsonResponse(Object? data, [int status = 200]) => http.Response(
      jsonEncode(data),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

typedef Route = http.Response Function(http.Request request);

/// Faux serveur Django : répond à des routes déclarées, ou simule l'absence de réseau.
class FakeServer {
  bool offline = false;
  final requests = <http.Request>[];
  final _routes = <String, Route>{};

  /// [path] est relatif à l'API (ex. `/auth/me/`).
  void on(String method, String path, Route route) => _routes['$method $path'] = route;

  void onJson(String method, String path, Object? data, [int status = 200]) =>
      on(method, path, (_) => jsonResponse(data, status));

  List<http.Request> requestsTo(String method, String path) => requests
      .where((r) => r.method == method && r.url.path == '/api$path')
      .toList();

  MockClient get client => MockClient((request) async {
        if (offline) throw http.ClientException('Connexion impossible');
        requests.add(request);
        final route = _routes['${request.method} ${request.url.path.replaceFirst('/api', '')}'];
        return route == null ? jsonResponse({'detail': 'Introuvable.'}, 404) : route(request);
      });
}

Map<String, dynamic> userJson({int id = 7, String role = 'guichetier'}) => {
      'id': id,
      'username': 'awa',
      'email': '',
      'first_name': 'Awa',
      'last_name': 'Koné',
      'role': role,
      'company': {'id': 1, 'name': 'STC Voyages', 'headquarters_city': 'Abidjan'},
    };

/// Application complète branchée sur un faux serveur, un stockage en mémoire et une
/// connectivité pilotée à la main.
class Harness {
  Harness({LocalStore? store, VoiceFormSession Function()? sessionVocale}) {
    api = ApiClient(baseUrl: 'http://test/api', tokens: tokens, httpClient: server.client);
    services = AppServices.assemble(
      store: store ?? LocalStore.memory(),
      api: api,
      tokens: tokens,
      secrets: secrets,
      connectivity: connectivity,
      sessionVocale: sessionVocale,
    );
  }

  final server = FakeServer();
  final tokens = MemoryTokenStorage();
  final secrets = MemorySecretStore();
  final connectivity = FakeConnectivityMonitor();
  late final ApiClient api;
  late final AppServices services;

  /// Un compte valide de ce rôle (login puis /auth/me/).
  void stubLogin({int id = 7, String role = 'guichetier'}) {
    server.onJson('POST', '/auth/login/', {'access': 'acc-1', 'refresh': 'ref-1'});
    server.onJson('GET', '/auth/me/', userJson(id: id, role: role));
  }

  /// Réponse du serveur à « mettre de côté des places pour la vente hors ligne » :
  /// [places] sur le départ 5 (aucune réservation si 0).
  void stubReservation({int places = 2}) {
    final expire = DateTime.now().add(const Duration(hours: 6)).toUtc().toIso8601String();
    server.onJson('POST', '/tickets/reserver-hors-ligne/', [
      if (places > 0) {'depart': 5, 'places': places, 'expire_le': expire},
    ]);
    server.on('DELETE', '/tickets/reserver-hors-ligne/', (_) => http.Response('', 204));
  }

  /// Un départ vendable et sa ligne (pour l'écran de vente), avec 2 places réservées.
  void stubDeparts({int placesReservees = 2}) {
    stubReservation(places: placesReservees);
    final demain = DateTime.now().add(const Duration(days: 1)).toUtc().toIso8601String();
    server.onJson('GET', '/departs/', [
      {'id': 5, 'ligne': 3, 'statut': 'planifie', 'date_heure': demain, 'places_restantes': 12},
      {'id': 6, 'ligne': 3, 'statut': 'termine', 'date_heure': demain, 'places_restantes': 0},
    ]);
    server.onJson('GET', '/lignes/', [
      {'id': 3, 'nom': 'Adjamé-Bouaké'},
    ]);
  }

  /// Une feuille de route du jour pour ce chauffeur (et celle d'un collègue, à ignorer).
  void stubFeuilleDuJour({required int chauffeurId}) {
    final maintenant = DateTime.now().toUtc().toIso8601String();
    server.onJson('GET', '/feuilles-de-route/', [
      {
        'id': 10,
        'depart': 5,
        'chauffeur': chauffeurId,
        'heure_depart_prevue': maintenant,
        'heure_arrivee_prevue': null,
        'heure_depart_reelle': null,
        'heure_arrivee_reelle': null,
      },
      {
        'id': 11,
        'depart': 6,
        'chauffeur': chauffeurId + 100,
        'heure_depart_prevue': maintenant,
        'heure_arrivee_prevue': null,
        'heure_depart_reelle': null,
        'heure_arrivee_reelle': null,
      },
    ]);
    server.onJson('GET', '/departs/5/', {'id': 5, 'ligne': 3, 'vehicule': 4});
    server.onJson('GET', '/lignes/3/', {'id': 3, 'nom': 'Adjamé-Bouaké'});
    server.onJson('GET', '/vehicules/4/', {'id': 4, 'immatriculation': 'CI-1234-AB'});
  }
}
