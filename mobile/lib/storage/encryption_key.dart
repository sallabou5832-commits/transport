import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Petit coffre de secrets (Keystore Android / Keychain iOS en production).
abstract interface class SecretStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class FlutterSecretStore implements SecretStore {
  FlutterSecretStore([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) => _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

/// Coffre en mémoire, pour les tests.
class MemorySecretStore implements SecretStore {
  final values = <String, String>{};

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;

  @override
  Future<void> delete(String key) async => values.remove(key);
}

/// Clé de chiffrement de la base locale (AES-256).
///
/// Générée une seule fois, au premier lancement, puis conservée dans le coffre du
/// système : elle n'est jamais écrite à côté des données qu'elle protège.
class EncryptionKeyProvider {
  EncryptionKeyProvider(this._secrets, {Random? random}) : _random = random ?? Random.secure();

  static const _storageKey = 'local_db_encryption_key';
  static const keyLength = 32; // 256 bits

  final SecretStore _secrets;
  final Random _random;

  Future<List<int>> getOrCreateKey() async {
    final stored = await _secrets.read(_storageKey);
    if (stored != null) {
      try {
        final key = base64Url.decode(stored);
        if (key.length == keyLength) return key;
      } on FormatException {
        // valeur altérée : on en génère une nouvelle (les anciennes données seront illisibles)
      }
    }
    final key = List<int>.generate(keyLength, (_) => _random.nextInt(256));
    await _secrets.write(_storageKey, base64Url.encode(key));
    return key;
  }
}
