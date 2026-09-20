import 'package:hive_ce_flutter/hive_flutter.dart';

import 'string_box.dart';

/// Base locale de l'appareil (Hive : Dart pur, fonctionne sur Android, iOS et web).
///
/// Deux « boîtes » de texte JSON :
///  - `outbox` : les actions faites sans réseau, en attente d'envoi ;
///  - `cache`  : les dernières données lues, pour rester consultable hors ligne.
class LocalStore {
  LocalStore._(this.outboxBox, this.cacheBox);

  final StringBox outboxBox;
  final StringBox cacheBox;

  /// [path] sert aux tests (dossier temporaire) ; en application, Hive choisit
  /// lui-même l'emplacement adapté à la plateforme.
  static Future<LocalStore> open({String? path, String namespace = 'transport'}) async {
    if (path != null) {
      Hive.init(path);
    } else {
      await Hive.initFlutter();
    }
    return LocalStore._(
      HiveStringBox(await Hive.openBox<String>('${namespace}_outbox')),
      HiveStringBox(await Hive.openBox<String>('${namespace}_cache')),
    );
  }

  /// Stockage éphémère (tests d'écrans).
  factory LocalStore.memory() => LocalStore._(MemoryStringBox(), MemoryStringBox());

  Future<void> close() async {
    await outboxBox.close();
    await cacheBox.close();
  }
}
