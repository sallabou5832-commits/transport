import 'package:hive_ce_flutter/hive_flutter.dart';

import 'string_box.dart';

/// Base locale de l'appareil (Hive : Dart pur, fonctionne sur Android, iOS et web).
///
/// Deux « boîtes » de texte JSON, **chiffrées en AES-256** :
///  - `outbox` : les actions faites sans réseau, en attente d'envoi ;
///  - `cache`  : les dernières données lues, pour rester consultable hors ligne.
/// Elles contiennent les noms et téléphones des voyageurs : jamais en clair sur l'appareil.
class LocalStore {
  static const _temoin = '__integrite__';

  LocalStore._(this.outboxBox, this.cacheBox, {this.wasReset = false});

  final StringBox outboxBox;
  final StringBox cacheBox;

  /// Vrai si des données illisibles (clé de chiffrement perdue, fichier corrompu) ont dû
  /// être effacées à l'ouverture : des ventes en attente ont pu être perdues.
  final bool wasReset;

  /// [encryptionKey] chiffre les deux boîtes (obligatoire en production). [path] sert aux
  /// tests (dossier temporaire) ; en application, Hive choisit lui-même l'emplacement.
  static Future<LocalStore> open({
    String? path,
    String namespace = 'transport',
    List<int>? encryptionKey,
  }) async {
    if (path != null) {
      Hive.init(path);
    } else {
      await Hive.initFlutter();
    }
    final cipher = encryptionKey == null ? null : HiveAesCipher(encryptionKey);
    var reset = false;

    Future<Box<String>> ouvrir(String name) => Hive.openBox<String>(name, encryptionCipher: cipher);

    Future<StringBox> open(String name) async {
      final existait = await Hive.boxExists(name);
      Box<String> box;
      try {
        box = await ouvrir(name);
      } on HiveError {
        // Fichier illisible : on repart d'une base vide plutôt que de bloquer l'application.
        reset = true;
        await Hive.deleteBoxFromDisk(name);
        box = await ouvrir(name);
      }
      // Avec une mauvaise clé, Hive ne lève AUCUNE erreur : il « récupère » la boîte en la
      // vidant. Le témoin, écrit à la création, permet de le détecter : sur une boîte qui
      // existait déjà, son absence prouve que les données étaient illisibles.
      if (existait && !box.containsKey(_temoin)) reset = true;
      if (!box.containsKey(_temoin)) await box.put(_temoin, 'ok');
      return HiveStringBox(box, hiddenKey: _temoin);
    }

    final outbox = await open('${namespace}_outbox');
    final cache = await open('${namespace}_cache');
    return LocalStore._(outbox, cache, wasReset: reset);
  }

  /// Stockage éphémère (tests d'écrans).
  factory LocalStore.memory({bool wasReset = false}) =>
      LocalStore._(MemoryStringBox(), MemoryStringBox(), wasReset: wasReset);

  Future<void> close() async {
    await outboxBox.close();
    await cacheBox.close();
  }
}
