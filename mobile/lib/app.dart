import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'auth/auth_controller.dart';
import 'services.dart';
import 'sync/sync_service.dart';
import 'ui/home_screen.dart';
import 'ui/login_screen.dart';

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
    _services.auth.addListener(_onAuthChanged);
    _services.auth.restore();
  }

  @override
  void dispose() {
    _services.auth.removeListener(_onAuthChanged);
    _services.triggers.dispose();
    super.dispose();
  }

  /// À chaque changement d'utilisateur : recompte ses actions en attente et, une fois
  /// connecté, envoie tout ce qui a été fait hors ligne.
  void _onAuthChanged() {
    _services.sync.refreshCounts();
    if (_services.auth.status == AuthStatus.authenticated) _services.sync.syncNow();
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<AppServices>.value(value: _services),
        ChangeNotifierProvider<AuthController>.value(value: _services.auth),
        ChangeNotifierProvider<SyncService>.value(value: _services.sync),
      ],
      child: MaterialApp(
        title: 'Transport Coord',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(colorSchemeSeed: const Color(0xFF0B5FA5), useMaterial3: true),
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
    return switch (auth.status) {
      AuthStatus.restoring => const Scaffold(body: Center(child: CircularProgressIndicator())),
      AuthStatus.unauthenticated => const LoginScreen(),
      AuthStatus.authenticated => HomeScreen(key: ValueKey(auth.user?.id)),
    };
  }
}
