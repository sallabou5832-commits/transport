import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../storage/cache_store.dart';
import 'app_user.dart';
import 'token_storage.dart';

enum AuthStatus { restoring, unauthenticated, authenticated }

/// Durées de session proposées quand on coche « Rester connecté » (sans case cochée : 1 jour, comme avant). Le serveur
/// ramène le choix au plafond de la compagnie et du poste.
const dureesSession = {
  'jour': '1 jour',
  'semaine': '7 jours',
  'mois': '30 jours',
  'deconnexion': "Jusqu'à la déconnexion",
};

/// La session de ce téléphone, lue dans son jeton de renouvellement.
class SessionMobile {
  const SessionMobile({required this.duree, required this.expireLe});

  final String duree;
  final DateTime expireLe;
}

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
  bool _reprise = false;

  AuthStatus get status => _status;
  AppUser? get user => _user;

  /// La session a été reprise au démarrage (le code court est alors demandé), et non ouverte à l'instant par le mot de passe.
  bool get sessionReprise => _reprise;

  /// Au démarrage : reprend la session sans nouvelle saisie, même hors ligne.
  Future<void> restore() async {
    if (await tokens.readAccess() == null) {
      _set(AuthStatus.unauthenticated, null);
      return;
    }
    _reprise = true;
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

  /// Lève [ApiException] (identifiants refusés) ou [NetworkException] (serveur injoignable). [dureeSession] : « rester
  /// connecté » (une clé de [dureesSession]) ; absente, la session dure 1 jour comme avant.
  Future<void> login(String username, String password, {String? dureeSession}) async {
    final data = await api.post(
      '/auth/login/',
      body: {'username': username, 'password': password, 'duree_session': ?dureeSession},
      auth: false,
    ) as Map<String, dynamic>;
    await tokens.save(access: data['access'] as String, refresh: data['refresh'] as String?);
    _reprise = false;
    final me = await api.get('/auth/me/') as Map<String, dynamic>;
    await _authenticate(AppUser.fromJson(me));
  }

  /// Change le mot de passe : les autres appareils sont déconnectés, celui-ci reçoit de nouveaux jetons (même durée de
  /// session). Lève [ApiException] (mot de passe actuel faux, nouveau trop faible) ou [NetworkException].
  Future<void> changerMotDePasse(String ancien, String nouveau) async {
    final data = await api.post(
      '/auth/mot-de-passe/',
      body: {'ancien': ancien, 'nouveau': nouveau, 'refresh': await tokens.readRefresh()},
    ) as Map<String, dynamic>;
    await tokens.save(access: data['access'] as String, refresh: data['refresh'] as String?);
    if (_user?.doitChangerMotDePasse ?? false) {
      // Le mot de passe provisoire est remplacé : le profil relu ouvre enfin l'accueil.
      final me = await api.get('/auth/me/') as Map<String, dynamic>;
      await _authenticate(AppUser.fromJson(me));
    }
  }

  /// « Déconnecter mes autres appareils » : ce téléphone reste connecté, à la même échéance.
  Future<void> fermerAutresSessions() async {
    final data = await api.post(
      '/auth/fermer-autres-sessions/',
      body: {'refresh': await tokens.readRefresh()},
    ) as Map<String, dynamic>;
    await tokens.save(access: data['access'] as String, refresh: data['refresh'] as String?);
  }

  /// Durée et échéance de la session de ce téléphone ; `null` si son jeton est illisible.
  Future<SessionMobile?> session() async {
    final jeton = await tokens.readRefresh();
    final parties = jeton?.split('.');
    if (parties == null || parties.length != 3) return null;
    try {
      final charge = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parties[1])))) as Map<String, dynamic>;
      return SessionMobile(
        duree: charge['duree'] as String? ?? 'jour',
        expireLe: DateTime.fromMillisecondsSinceEpoch((charge['exp'] as int) * 1000),
      );
    } on Object {
      return null;
    }
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
