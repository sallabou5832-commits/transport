import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/api/api_exception.dart';
import 'package:transport_mobile/gps/gps_fix.dart';
import 'package:transport_mobile/gps/position_batcher.dart';
import 'package:transport_mobile/storage/string_box.dart';

GpsFix _fix([int minute = 0]) => GpsFix(
      latitude: 5.812345,
      longitude: -4.512345,
      vitesseKmh: 80,
      releveLe: DateTime.utc(2026, 9, 24, 10, minute),
    );

void main() {
  late StringBox box;
  late List<List<Map<String, dynamic>>> envoyes;
  late Future<void> Function(List<Map<String, dynamic>>) comportement;
  late PositionBatcher batcher;

  PositionBatcher creer({int tailleLot = 100}) => PositionBatcher(
        box: box,
        tailleLot: tailleLot,
        envoyer: (lot) {
          envoyes.add(lot);
          return comportement(lot);
        },
      );

  setUp(() {
    box = MemoryStringBox();
    envoyes = [];
    comportement = (_) async {};
    batcher = creer();
  });

  test('un relevé ajouté est en attente jusqu\'au prochain envoi réussi', () async {
    await batcher.ajouter(_fix());

    expect(batcher.enAttente, 1);

    await batcher.flush();

    expect(batcher.enAttente, 0);
    expect(envoyes, hasLength(1));
    expect(envoyes.single.single['vitesse_kmh'], 80);
  });

  test('un envoi sans rien en attente ne fait aucun appel', () async {
    await batcher.flush();

    expect(envoyes, isEmpty);
  });

  test('respecte la taille de lot : garde le reste pour le prochain envoi', () async {
    batcher = creer(tailleLot: 2);
    await batcher.ajouter(_fix(1));
    await batcher.ajouter(_fix(2));
    await batcher.ajouter(_fix(3));

    await batcher.flush();

    expect(envoyes.single, hasLength(2));
    expect(batcher.enAttente, 1);

    await batcher.flush();

    expect(envoyes, hasLength(2));
    expect(batcher.enAttente, 0);
  });

  test('pas de réseau : les relevés restent en attente pour le prochain essai', () async {
    comportement = (_) async => throw const NetworkException('injoignable');
    await batcher.ajouter(_fix());

    await batcher.flush();

    expect(batcher.enAttente, 1);
  });

  test('lot refusé par le serveur : abandonné plutôt que retenté en boucle', () async {
    comportement = (_) async => throw const ApiException(400, 'valeurs invalides');
    await batcher.ajouter(_fix());

    await batcher.flush();

    expect(batcher.enAttente, 0);
  });
}
