import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../auth/app_user.dart';
import '../auth/roles.dart';
import '../storage/cache_store.dart';
import '../storage/outbox.dart';
import '../sync/action_handlers.dart';
import '../sync/sync_service.dart';

/// Places réservées pour vendre hors ligne sur un départ.
class DepartQuota {
  const DepartQuota({required this.places, required this.expireLe, this.consommees = 0});

  factory DepartQuota.fromJson(Map<String, dynamic> json) => DepartQuota(
        places: json['places'] as int,
        expireLe: DateTime.parse(json['expireLe'] as String),
        consommees: json['consommees'] as int? ?? 0,
      );

  /// Places réservées par le serveur à la dernière lecture.
  final int places;
  final DateTime expireLe;

  /// Ventes faites depuis cette lecture (envoyées ou en attente) : elles utilisent ces places.
  final int consommees;

  int remaining(DateTime now) => now.isBefore(expireLe) ? (places - consommees).clamp(0, places) : 0;

  DepartQuota consume() => DepartQuota(
        places: places,
        expireLe: expireLe,
        consommees: consommees < places ? consommees + 1 : consommees,
      );

  Map<String, dynamic> toJson() => {
        'places': places,
        'expireLe': expireLe.toUtc().toIso8601String(),
        'consommees': consommees,
      };
}

/// Places garanties pour la vente hors ligne du guichetier.
///
/// Sans réseau, un guichetier ignore les ventes des autres : il pourrait vendre une place
/// déjà prise, et le serveur refuserait la vente à la synchronisation alors que le voyageur
/// a payé. Tant qu'il a du réseau, le serveur met donc de côté quelques places par départ à
/// son nom ; hors ligne, l'application n'autorise que des ventes couvertes par ces places.
class QuotaService extends ChangeNotifier {
  QuotaService({
    required this._api,
    required this._cache,
    required this._outbox,
    required this._currentUser,
    DateTime Function()? now,
    this.staleAfter = const Duration(minutes: 5),
  }) : _now = now ?? DateTime.now;

  static const path = '/tickets/reserver-hors-ligne/';

  final ApiClient _api;
  final CacheStore _cache;
  final Outbox _outbox;
  final AppUser? Function() _currentUser;
  final DateTime Function() _now;

  /// Au-delà, la lecture est rafraîchie dès que le réseau le permet.
  final Duration staleAfter;

  Map<int, DepartQuota> _quotas = {};
  DateTime? _refreshedAt;
  int? _loadedFor;
  Future<void>? _refreshing;

  static String _cacheKey(int userId) => 'u$userId:quotas';

  bool _concerne(AppUser? user) => user != null && user.role == Roles.guichetier;

  /// Places garanties hors ligne sur ce départ (0 si aucune réservation valide).
  int remainingFor(int departId) {
    _loadIfNeeded();
    return _quotas[departId]?.remaining(_now()) ?? 0;
  }

  /// À appeler après chaque vente d'un ticket (envoyée ou mise en attente).
  Future<void> consume(int departId) async {
    final user = _currentUser();
    if (!_concerne(user)) return;
    _loadIfNeeded();
    final quota = _quotas[departId];
    if (quota == null) return;
    _quotas = {..._quotas, departId: quota.consume()};
    await _persist(user!.id);
    notifyListeners();
  }

  /// Demande au serveur de (re)mettre de côté les places du guichetier. Sans réseau, ne fait
  /// rien : les places déjà obtenues restent valables jusqu'à leur expiration.
  Future<void> refresh() => _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);

  Future<void> refreshIfStale() async {
    final user = _currentUser();
    if (!_concerne(user)) return;
    _loadIfNeeded();
    final last = _refreshedAt;
    if (last == null || _now().difference(last) >= staleAfter) await refresh();
  }

  /// Branché sur la fin de chaque synchronisation : après des ventes envoyées, on complète
  /// tout de suite la réserve ; sinon on la rafraîchit de temps en temps.
  Future<void> onSynced(SyncResult result) => result.sent > 0 ? refresh() : refreshIfStale();

  /// Rend les places réservées (fin de service). Ne fait rien s'il reste des ventes hors ligne
  /// à envoyer : elles ont besoin de ces places pour être acceptées.
  Future<void> release() async {
    final user = _currentUser();
    if (!_concerne(user) || _pendingSalesByDepart(user!.id).isNotEmpty) return;
    try {
      await _api.delete(path);
      _quotas = {};
      _refreshedAt = null;
      await _cache.remove(_cacheKey(user.id));
      notifyListeners();
    } on Object {
      // Au mieux : sans réseau, les places expirent d'elles-mêmes côté serveur.
    }
  }

  Future<void> _doRefresh() async {
    final user = _currentUser();
    if (!_concerne(user)) return;
    try {
      final data = (await _api.post(path) as List).cast<Map<String, dynamic>>();
      // Le serveur ignore encore les ventes en attente sur ce téléphone : on les décompte.
      final pending = _pendingSalesByDepart(user!.id);
      _quotas = {
        for (final r in data)
          r['depart'] as int: DepartQuota(
            places: r['places'] as int,
            expireLe: DateTime.parse(r['expire_le'] as String),
            consommees: pending[r['depart'] as int] ?? 0,
          ),
      };
      _loadedFor = user.id;
      _refreshedAt = _now();
      await _persist(user.id);
      notifyListeners();
    } on NetworkException {
      // hors ligne : on garde ce qu'on a
    } on ApiException {
      // refus du serveur (rôle, ancien serveur sans cette fonction) : on garde l'existant
    }
  }

  Map<int, int> _pendingSalesByDepart(int userId) {
    final counts = <int, int>{};
    for (final action in _outbox.pendingFor(userId)) {
      final depart = action.payload['depart'];
      if (action.type == ActionTypes.venteTicket && depart is int) {
        counts[depart] = (counts[depart] ?? 0) + 1;
      }
    }
    return counts;
  }

  void _loadIfNeeded() {
    final user = _currentUser();
    if (user == null || _loadedFor == user.id) return;
    _loadedFor = user.id;
    _quotas = {};
    _refreshedAt = null;
    final cached = _cache.get(_cacheKey(user.id));
    if (cached == null) return;
    final data = Map<String, dynamic>.from(cached.data as Map);
    _refreshedAt = DateTime.tryParse(data['refreshedAt'] as String? ?? '')?.toLocal();
    _quotas = {
      for (final e in Map<String, dynamic>.from(data['departs'] as Map).entries)
        int.parse(e.key): DepartQuota.fromJson(Map<String, dynamic>.from(e.value as Map)),
    };
  }

  Future<void> _persist(int userId) => _cache.put(_cacheKey(userId), {
        'refreshedAt': _refreshedAt?.toUtc().toIso8601String(),
        'departs': {for (final e in _quotas.entries) '${e.key}': e.value.toJson()},
      });
}
