import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../storage/cache_store.dart';
import 'app_user.dart';
import 'token_storage.dart';

enum AuthStatus { restoring, unauthenticated, authenticated }

/// Connexion de l'utilisateur, avec les mêmes endpoints JWT que le frontend web :
/// `POST /auth/login/` puis `GET /auth/me/`.
class AuthController extends ChangeNotifier {
  AuthController({required this.api, required this.tokens, required this.cache}) {
    api.onSessionExpired = _onSessionExpired;
  }

  static const _userCacheKey = 'session_user';

  final ApiClient api;
  final TokenStorage tokens;
  final CacheStore cache;

  AuthStatus _status = AuthStatus.restoring;
  AppUser? _user;

  AuthStatus get status => _status;
  AppUser? get user => _user;

  /// Au démarrage : reprend la session sans nouvelle saisie, même hors ligne.
  Future<void> restore() async {
    if (await tokens.readAccess() == null) {
      _set(AuthStatus.unauthenticated, null);
      return;
    }
    try {
      final me = await api.get('/auth/me/') as Map<String, dynamic>;
      await _authenticate(AppUser.fromJson(me));
    } on NetworkException {
      // Hors ligne : on ouvre l'application avec le dernier profil connu.
      final cached = cache.get(_userCacheKey);
      if (cached != null) {
        _set(AuthStatus.authenticated, AppUser.fromJson(Map<String, dynamic>.from(cached.data as Map)));
      } else {
        _set(AuthStatus.unauthenticated, null);
      }
    } on ApiException {
      await _forget();
    }
  }

  /// Lève [ApiException] (identifiants refusés) ou [NetworkException] (serveur injoignable).
  Future<void> login(String username, String password) async {
    final data = await api.post(
      '/auth/login/',
      body: {'username': username, 'password': password},
      auth: false,
    ) as Map<String, dynamic>;
    await tokens.save(access: data['access'] as String, refresh: data['refresh'] as String?);
    final me = await api.get('/auth/me/') as Map<String, dynamic>;
    await _authenticate(AppUser.fromJson(me));
  }

  /// Déconnexion. Les actions en attente restent sur l'appareil, rattachées à leur
  /// propriétaire : elles seront envoyées à sa prochaine connexion.
  Future<void> logout() => _forget();

  Future<void> _authenticate(AppUser user) async {
    await cache.put(_userCacheKey, user.toJson());
    _set(AuthStatus.authenticated, user);
  }

  Future<void> _forget() async {
    await tokens.clear();
    await cache.remove(_userCacheKey);
    _set(AuthStatus.unauthenticated, null);
  }

  void _onSessionExpired() {
    _set(AuthStatus.unauthenticated, null);
  }

  void _set(AuthStatus status, AppUser? user) {
    _status = status;
    _user = user;
    notifyListeners();
  }
}
