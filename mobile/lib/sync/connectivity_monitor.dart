import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

/// Surveille la présence d'une connexion réseau.
abstract interface class ConnectivityMonitor {
  Future<bool> get isOnline;

  /// Émet `true` au retour du réseau, `false` à sa perte.
  Stream<bool> get onlineChanges;
}

/// Version réelle, basée sur le système de l'appareil.
///
/// « Connecté » ne garantit pas l'accès au serveur (Wi-Fi sans internet) : la
/// synchronisation gère de toute façon l'échec réseau et réessaiera.
class PlatformConnectivityMonitor implements ConnectivityMonitor {
  PlatformConnectivityMonitor([Connectivity? connectivity])
      : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  static bool _hasNetwork(List<ConnectivityResult> results) =>
      results.any((result) => result != ConnectivityResult.none);

  @override
  Future<bool> get isOnline async => _hasNetwork(await _connectivity.checkConnectivity());

  @override
  Stream<bool> get onlineChanges =>
      _connectivity.onConnectivityChanged.map(_hasNetwork).distinct();
}

/// Version pilotable à la main, pour les tests.
class FakeConnectivityMonitor implements ConnectivityMonitor {
  FakeConnectivityMonitor([this._online = true]);

  bool _online;
  final _controller = StreamController<bool>.broadcast();

  void setOnline(bool value) {
    _online = value;
    _controller.add(value);
  }

  @override
  Future<bool> get isOnline async => _online;

  @override
  Stream<bool> get onlineChanges => _controller.stream;
}
