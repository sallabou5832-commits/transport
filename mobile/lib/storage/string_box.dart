import 'package:hive_ce/hive.dart';

/// Une « boîte » de textes clé → valeur, dans l'ordre d'insertion.
///
/// Petite abstraction au-dessus de Hive : les tests d'écrans utilisent la version
/// en mémoire (leurs entrées/sorties fichier se bloquent sous l'horloge simulée de
/// `testWidgets`), les tests de persistance utilisent Hive pour de vrai.
abstract interface class StringBox {
  Iterable<String> get values;
  Iterable<Object> get keys;
  String? get(Object key);
  Future<void> put(Object key, String value);

  /// Ajoute avec une clé numérique auto-incrémentée : l'ordre d'arrivée est conservé.
  Future<void> add(String value);
  Future<void> delete(Object key);
  Future<void> close();
}

class HiveStringBox implements StringBox {
  HiveStringBox(this._box, {this.hiddenKey});

  final Box<String> _box;

  /// Entrée technique (témoin d'intégrité) que la file d'attente et le cache ne voient pas.
  final Object? hiddenKey;

  @override
  Iterable<String> get values => keys.map((key) => _box.get(key)!);

  @override
  Iterable<Object> get keys => _box.keys.cast<Object>().where((key) => key != hiddenKey);

  @override
  String? get(Object key) => _box.get(key);

  @override
  Future<void> put(Object key, String value) => _box.put(key, value);

  @override
  Future<void> add(String value) => _box.add(value);

  @override
  Future<void> delete(Object key) => _box.delete(key);

  @override
  Future<void> close() => _box.close();
}

class MemoryStringBox implements StringBox {
  final _entries = <Object, String>{};
  var _nextKey = 0;

  @override
  Iterable<String> get values => _entries.values;

  @override
  Iterable<Object> get keys => _entries.keys;

  @override
  String? get(Object key) => _entries[key];

  @override
  Future<void> put(Object key, String value) async => _entries[key] = value;

  @override
  Future<void> add(String value) async => _entries[_nextKey++] = value;

  @override
  Future<void> delete(Object key) async => _entries.remove(key);

  @override
  Future<void> close() async {}
}
