import 'dart:convert';

import 'string_box.dart';

class CachedEntry {
  const CachedEntry(this.data, this.savedAt);

  final Object? data;
  final DateTime savedAt;
}

/// Dernières données lues sur le serveur, gardées pour le mode hors ligne.
class CacheStore {
  CacheStore(this._box);

  final StringBox _box;

  Future<void> put(String key, Object? data) => _box.put(
        key,
        jsonEncode({'savedAt': DateTime.now().toUtc().toIso8601String(), 'data': data}),
      );

  CachedEntry? get(String key) {
    final raw = _box.get(key);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return CachedEntry(map['data'], DateTime.parse(map['savedAt'] as String).toLocal());
    } on Object {
      return null; // entrée illisible : on la traite comme absente
    }
  }

  Future<void> remove(String key) => _box.delete(key);
}
