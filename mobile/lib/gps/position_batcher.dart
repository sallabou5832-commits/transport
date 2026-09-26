import 'dart:convert';

import '../api/api_exception.dart';
import '../storage/string_box.dart';
import 'gps_fix.dart';

/// File d'attente des relevés GPS avant leur envoi : chaque relevé s'ajoute tout de suite (même hors
/// ligne, même si l'application est arrêtée entre-temps — la file vit sur le disque), l'envoi se fait
/// par lots (`flush`), jamais un par un (`POST /positions/` accepte une liste, au plus
/// `MAX_POSITIONS_PAR_ENVOI` = 500 à la fois côté serveur, voir `personnel_roulant/views.py`).
///
/// Contrairement à l'`Outbox` des actions métier (vente, checklist…), un relevé perdu ou envoyé deux
/// fois est sans conséquence pour la compagnie : pas de clé d'idempotence ici, et un lot refusé par le
/// serveur est simplement abandonné plutôt que retenté en boucle.
///
/// [envoyer] fait l'appel réseau (`api.post('/positions/', body: lot)` en pratique, voir
/// `services.dart`) : une fonction plutôt que l'`ApiClient` lui-même, pour se tester sans HTTP.
class PositionBatcher {
  PositionBatcher({required this.box, required this.envoyer, this.tailleLot = 100});

  final StringBox box;
  final Future<void> Function(List<Map<String, dynamic>> lot) envoyer;
  final int tailleLot;

  Future<void> ajouter(GpsFix fix) => box.add(jsonEncode(fix.toJson()));

  int get enAttente => box.keys.length;

  /// Envoie jusqu'à [tailleLot] relevés, les plus anciens d'abord. Ne lève jamais : un échec réseau
  /// laisse les relevés dans la file pour le prochain appel (voir `TripGpsController`, qui rappelle
  /// régulièrement tant que le trajet dure).
  Future<void> flush() async {
    final cles = box.keys.take(tailleLot).toList();
    if (cles.isEmpty) return;
    final lot = cles.map((cle) => jsonDecode(box.get(cle)!) as Map<String, dynamic>).toList();
    try {
      await envoyer(lot);
    } on ApiException {
      // Lot refusé (ex. valeurs invalides) : le retenter à l'identique échouerait à nouveau et
      // bloquerait les relevés suivants. Un relevé isolé n'a pas la valeur d'un ticket : on l'abandonne.
      await _retirer(cles);
      return;
    } on NetworkException {
      return; // Pas de réseau : rien à retirer, on retente au prochain passage.
    }
    await _retirer(cles);
  }

  Future<void> _retirer(List<Object> cles) async {
    for (final cle in cles) {
      await box.delete(cle);
    }
  }
}
