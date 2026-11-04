import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'auth/auth_controller.dart';
import 'auth/code_court_controller.dart';
import 'data/ma_configuration.dart';
import 'data/quota_service.dart';
import 'services.dart';
import 'sync/sync_service.dart';
import 'ui/charte.dart';
import 'ui/code_court_screen.dart';
import 'ui/home_screen.dart';
import 'ui/login_screen.dart';
import 'ui/mes_parametres_screen.dart';

class TransportApp extends StatefulWidget {
  const TransportApp({super.key, required this.services});

  final AppServices services;

  @override
  State<TransportApp> createState() => _TransportAppState();
}

class _TransportAppState extends State<TransportApp> {
  AppServices get _services => widget.services;

  @override
  void initState() {
    super.initState();
    _services.triggers.start();
    WidgetsBinding.instance.addObserver(_services.codeCourt);
    _services.auth.addListener(_onAuthChanged);
    _services.auth.restore();
  }

  @override
  void dispose() {
    _services.auth.removeListener(_onAuthChanged);
    WidgetsBinding.instance.removeObserver(_services.codeCourt);
    _services.triggers.dispose();
    _services.gps.dispose();
    super.dispose();
  }

  /// À chaque changement d'utilisateur : recompte ses actions en attente, envoie une fois connecté
  /// tout ce qui a été fait hors ligne, et démarre/arrête le suivi GPS s'il conduit (voir
  /// `TripGpsController` : lui-même vérifie ensuite si un trajet est réellement en cours).
  void _onAuthChanged() {
    _services.sync.refreshCounts();
    if (_services.auth.status == AuthStatus.authenticated) _services.sync.syncNow();
    _services.gps.onUserChanged(_services.auth.user);
    final connecte = _services.auth.status == AuthStatus.authenticated ? _services.auth.user : null;
    if (connecte == null) {
      _services.maConfiguration.oublier();
    } else {
      _services.maConfiguration.charger(connecte.id);
    }
    _services.codeCourt.surUtilisateur(connecte, reprise: _services.auth.sessionReprise);
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<AppServices>.value(value: _services),
        ChangeNotifierProvider<AuthController>.value(value: _services.auth),
        ChangeNotifierProvider<CodeCourtController>.value(value: _services.codeCourt),
        ChangeNotifierProvider<MaConfiguration>.value(value: _services.maConfiguration),
        ChangeNotifierProvider<SyncService>.value(value: _services.sync),
        ChangeNotifierProvider<QuotaService>.value(value: _services.quota),
      ],
      child: MaterialApp(
        title: 'Transport Coord',
        debugShowCheckedModeBanner: false,
        theme: Charte.theme(),
        home: const _AuthGate(),
      ),
    );
  }
}

class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final codeCourt = context.watch<CodeCourtController>();
    const attente = Scaffold(body: Center(child: CircularProgressIndicator()));
    return switch (auth.status) {
      AuthStatus.restoring => attente,
      AuthStatus.unauthenticated => const LoginScreen(),
      AuthStatus.authenticated when auth.user?.doitChangerMotDePasse ?? false => const MotDePasseProvisoireScreen(),
      // Rien ne s'affiche derrière le verrou : l'accueil attend que l'état du code court soit chargé pour ce compte.
      AuthStatus.authenticated when !codeCourt.estPretPour(auth.user?.id) => attente,
      AuthStatus.authenticated when codeCourt.verrouille => const CodeCourtScreen.deverrouiller(),
      AuthStatus.authenticated when codeCourt.exige && !codeCourt.defini => const CodeCourtScreen.creer(obligatoire: true),
      AuthStatus.authenticated => HomeScreen(key: ValueKey(auth.user?.id)),
    };
  }
}
