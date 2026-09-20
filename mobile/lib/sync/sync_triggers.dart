import 'dart:async';

import 'package:flutter/widgets.dart';

import 'connectivity_monitor.dart';
import 'sync_service.dart';

/// Déclenche la synchronisation aux bons moments :
///  - retour de la connexion réseau ;
///  - retour de l'application au premier plan ;
///  - régulièrement tant qu'il reste des actions en attente (réseau instable).
class SyncTriggers with WidgetsBindingObserver {
  SyncTriggers({
    required this.sync,
    required this.monitor,
    this.interval = const Duration(seconds: 60),
  });

  final SyncService sync;
  final ConnectivityMonitor monitor;
  final Duration interval;

  StreamSubscription<bool>? _subscription;
  Timer? _timer;

  void start() {
    WidgetsBinding.instance.addObserver(this);
    monitor.isOnline.then(sync.setOnline);
    _subscription = monitor.onlineChanges.listen((online) {
      sync.setOnline(online);
      if (online) sync.syncNow();
    });
    _timer = Timer.periodic(interval, (_) {
      if (sync.pendingCount > 0) sync.syncNow();
    });
  }

  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _subscription?.cancel();
    _timer?.cancel();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) sync.syncNow();
  }
}
