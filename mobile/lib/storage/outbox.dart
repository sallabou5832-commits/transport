import 'dart:convert';

import '../sync/pending_action.dart';
import 'string_box.dart';

/// File d'attente des actions faites hors ligne, persistée sur l'appareil.
///
/// L'ordre d'arrivée est conservé (clés numériques auto-incrémentées) : les
/// actions sont renvoyées dans l'ordre où l'utilisateur les a faites.
class Outbox {
  Outbox(this._box);

  final StringBox _box;

  Future<void> add(PendingAction action) => _box.add(jsonEncode(action.toJson()));

  List<PendingAction> all() {
    final actions = <PendingAction>[];
    for (final raw in _box.values) {
      try {
        actions.add(PendingAction.fromJson(jsonDecode(raw) as Map<String, dynamic>));
      } on Object {
        // Entrée corrompue : ignorée plutôt que de bloquer toute la file.
      }
    }
    return actions;
  }

  List<PendingAction> pendingFor(int userId) => all()
      .where((a) => a.userId == userId && a.status == ActionStatus.pending)
      .toList();

  List<PendingAction> rejectedFor(int userId) => all()
      .where((a) => a.userId == userId && a.status == ActionStatus.rejected)
      .toList();

  List<PendingAction> allFor(int userId) => all().where((a) => a.userId == userId).toList();

  PendingAction? find(String id) {
    for (final action in all()) {
      if (action.id == id) return action;
    }
    return null;
  }

  Future<void> update(PendingAction action) async {
    final key = _keyOf(action.id);
    if (key != null) await _box.put(key, jsonEncode(action.toJson()));
  }

  Future<void> remove(String id) async {
    final key = _keyOf(id);
    if (key != null) await _box.delete(key);
  }

  dynamic _keyOf(String id) {
    for (final key in _box.keys) {
      final raw = _box.get(key);
      if (raw == null) continue;
      try {
        if ((jsonDecode(raw) as Map<String, dynamic>)['id'] == id) return key;
      } on Object {
        continue;
      }
    }
    return null;
  }
}
