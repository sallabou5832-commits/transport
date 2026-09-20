import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/api_exception.dart';
import '../storage/outbox.dart';
import 'action_handlers.dart';
import 'pending_action.dart';

/// Pourquoi une synchronisation s'est arrêtée avant la fin de la file.
enum SyncStop {
  /// Elle est allée au bout.
  none,

  /// Pas de réseau : on réessaiera au retour de la connexion.
  offline,

  /// Session expirée : l'utilisateur doit se reconnecter.
  authRequired,

  /// Le serveur a répondu par une erreur temporaire (5xx, 429...).
  serverError,
}

class SyncResult {
  const SyncResult({this.sent = 0, this.rejected = 0, this.stop = SyncStop.none});

  final int sent;
  final int rejected;
  final SyncStop stop;
}

enum SubmitStatus {
  /// Le serveur a accepté l'action.
  sent,

  /// Enregistrée sur l'appareil, sera envoyée plus tard.
  queued,

  /// Refusée par le serveur : l'utilisateur doit corriger (rien n'est conservé).
  rejected,
}

class SubmitResult {
  const SubmitResult(this.status, [this.message]);

  final SubmitStatus status;
  final String? message;
}

sealed class _Attempt {
  const _Attempt();
}

class _Sent extends _Attempt {
  const _Sent();
}

class _Offline extends _Attempt {
  const _Offline();
}

class _AuthRequired extends _Attempt {
  const _AuthRequired();
}

class _Transient extends _Attempt {
  const _Transient(this.message);
  final String message;
}

class _Rejected extends _Attempt {
  const _Rejected(this.message);
  final String message;
}

/// Vide la file d'actions hors ligne vers le serveur.
///
/// Règles :
///  - envoi dans l'ordre d'arrivée ; une seule synchronisation à la fois ;
///  - seules les actions de l'utilisateur connecté sont envoyées (jamais celles d'un autre) ;
///  - pas de réseau ou serveur en panne : on s'arrête, l'action reste en file ;
///  - refus métier (4xx) : l'action est marquée « refusée » (à revoir) et on continue ;
///  - session expirée (401 après tentative de renouvellement) : on s'arrête.
class SyncService extends ChangeNotifier {
  SyncService({
    required this._outbox,
    required this._handlers,
    required this._currentUserId,
    this.maxAttempts = 5,
    this._probe,
  });

  final Outbox _outbox;
  final Map<String, ActionHandler> _handlers;
  final int? Function() _currentUserId;
  final Future<void> Function()? _probe;

  /// Tâche à lancer à la fin de chaque synchronisation réussie (ex. mettre à jour les
  /// places réservées). Sans effet sur la synchronisation elle-même : ses erreurs sont ignorées.
  Future<void> Function(SyncResult result)? afterSync;

  /// Après ce nombre d'échecs serveur consécutifs, l'action est marquée « refusée ».
  final int maxAttempts;

  Future<SyncResult>? _running;
  int _pending = 0;
  int _rejected = 0;
  bool _online = true;
  bool _syncing = false;
  DateTime? _lastSyncAt;
  SyncStop _lastStop = SyncStop.none;

  int get pendingCount => _pending;
  int get rejectedCount => _rejected;
  bool get online => _online;
  bool get isSyncing => _syncing;
  DateTime? get lastSyncAt => _lastSyncAt;
  SyncStop get lastStop => _lastStop;

  void setOnline(bool value) {
    if (_online == value) return;
    _online = value;
    notifyListeners();
  }

  /// Recalcule les compteurs (à appeler quand l'utilisateur connecté change).
  void refreshCounts() {
    final userId = _currentUserId();
    _pending = userId == null ? 0 : _outbox.pendingFor(userId).length;
    _rejected = userId == null ? 0 : _outbox.rejectedFor(userId).length;
    notifyListeners();
  }

  /// Actions de l'utilisateur connecté, en attente ou refusées.
  List<PendingAction> actions() {
    final userId = _currentUserId();
    return userId == null ? const [] : _outbox.allFor(userId);
  }

  /// Supprime une action refusée après revue par l'utilisateur.
  Future<void> discard(String id) async {
    await _outbox.remove(id);
    refreshCounts();
  }

  /// Le serveur répond-il ? (Une réponse d'erreur du serveur compte comme « oui ».)
  Future<bool> canReachServer() async {
    final probe = _probe;
    if (probe == null) return _online;
    try {
      await probe();
    } on NetworkException {
      setOnline(false);
      return false;
    } on Object {
      // erreur applicative (401...) : le serveur est bien joignable
    }
    setOnline(true);
    return true;
  }

  /// Lance une synchronisation ; si une est déjà en cours, s'y rattache.
  Future<SyncResult> syncNow() {
    final running = _running;
    if (running != null) return running;
    final future = _run().whenComplete(() => _running = null);
    _running = future;
    return future;
  }

  /// Enregistre une action puis tente de l'envoyer immédiatement.
  ///
  /// L'action est d'abord écrite sur l'appareil : elle survit à une coupure ou à
  /// la fermeture de l'application en plein envoi.
  Future<SubmitResult> submit({
    required String type,
    required Map<String, dynamic> payload,
  }) async {
    final userId = _currentUserId();
    if (userId == null) {
      return const SubmitResult(SubmitStatus.rejected, 'Vous devez être connecté.');
    }
    final action = PendingAction.create(userId: userId, type: type, payload: payload);
    await _outbox.add(action);
    refreshCounts();

    final rejoint = _running != null;
    await syncNow();
    // Si on a seulement rejoint une synchronisation déjà en cours, elle a pu se terminer
    // sans voir cette action : on relance. Une synchronisation lancée ici la voit
    // forcément ; la relancer après un échec serait une tentative en trop.
    if (rejoint &&
        _lastStop == SyncStop.none &&
        _outbox.find(action.id)?.status == ActionStatus.pending) {
      await syncNow();
    }

    final fate = _outbox.find(action.id);
    if (fate == null) return const SubmitResult(SubmitStatus.sent);
    if (fate.status == ActionStatus.rejected) {
      // Refus immédiat : l'utilisateur est devant son formulaire, il corrige et
      // recommence ; inutile de garder l'action en « à revoir ».
      await _outbox.remove(fate.id);
      refreshCounts();
      return SubmitResult(SubmitStatus.rejected, fate.lastError);
    }
    return SubmitResult(SubmitStatus.queued, _queuedReason());
  }

  String _queuedReason() => switch (_lastStop) {
        SyncStop.offline => 'Pas de connexion.',
        SyncStop.authRequired => 'Session expirée : reconnectez-vous pour envoyer.',
        SyncStop.serverError => 'Le serveur est momentanément indisponible.',
        SyncStop.none => 'En attente d\'envoi.',
      };

  Future<SyncResult> _run() async {
    final userId = _currentUserId();
    if (userId == null) return const SyncResult();

    if (_outbox.pendingFor(userId).isEmpty) {
      // Rien à envoyer : pas d'état « synchronisation en cours », mais les tâches
      // périodiques (réservation de places) restent dues.
      _runAfterSync(const SyncResult());
      return const SyncResult();
    }

    _syncing = true;
    notifyListeners();
    var sent = 0;
    var rejected = 0;
    var stop = SyncStop.none;
    try {
      while (stop == SyncStop.none) {
        // Relue à chaque tour : une action ajoutée pendant l'envoi est prise en compte.
        final next = _outbox.pendingFor(userId).firstOrNull;
        if (next == null) break;

        switch (await _attempt(next)) {
          case _Sent():
            await _outbox.remove(next.id);
            sent++;
          case _Rejected(:final message):
            await _outbox.update(next.copyWith(status: ActionStatus.rejected, lastError: message));
            rejected++;
          case _Offline():
            stop = SyncStop.offline;
          case _AuthRequired():
            stop = SyncStop.authRequired;
          case _Transient(:final message):
            final attempts = next.attempts + 1;
            if (attempts >= maxAttempts) {
              await _outbox.update(next.copyWith(
                attempts: attempts,
                status: ActionStatus.rejected,
                lastError: 'Échecs répétés du serveur : $message',
              ));
              rejected++;
            } else {
              await _outbox.update(next.copyWith(attempts: attempts, lastError: message));
              stop = SyncStop.serverError;
            }
        }
        refreshCounts();
      }
    } finally {
      _syncing = false;
      _lastStop = stop;
      if (stop == SyncStop.none) _lastSyncAt = DateTime.now();
      _online = stop != SyncStop.offline;
      refreshCounts();
    }
    final result = SyncResult(sent: sent, rejected: rejected, stop: stop);
    if (stop == SyncStop.none) _runAfterSync(result);
    return result;
  }

  /// Lancée sans attendre : elle ne doit jamais retarder l'écran qui a déclenché l'envoi.
  void _runAfterSync(SyncResult result) {
    final task = afterSync;
    if (task == null) return;
    unawaited(task(result).catchError((Object e) {
      debugPrint('afterSync : $e');
    }));
  }

  Future<_Attempt> _attempt(PendingAction action) async {
    final handler = _handlers[action.type];
    if (handler == null) {
      return _Rejected('Action « ${action.type} » inconnue : mettez l\'application à jour.');
    }
    try {
      await handler(action);
      return const _Sent();
    } on NetworkException {
      return const _Offline();
    } on ApiException catch (e) {
      if (e.status == 401) return const _AuthRequired();
      if (e.status == 408 || e.status == 429 || e.status >= 500) return _Transient(e.message);
      return _Rejected(e.message);
    } on Object catch (e) {
      // Erreur inattendue (bug) : on ne bloque pas toute la file derrière elle.
      return _Rejected('Erreur inattendue : $e');
    }
  }
}
