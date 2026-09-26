import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/auth/app_user.dart';
import 'package:transport_mobile/gps/gps_fix.dart';
import 'package:transport_mobile/gps/location_source.dart';
import 'package:transport_mobile/gps/position_batcher.dart';
import 'package:transport_mobile/gps/trip_gps_controller.dart';
import 'package:transport_mobile/storage/string_box.dart';

/// Fausse source GPS : pilotée à la main (`emettre`), sans capteur ni permission réelle — comme
/// `_FakeRecognizer` le fait pour la voix (voir `voice_form_session_test.dart`).
class _FakeLocationSource implements LocationSource {
  bool permissionAccordee = true;
  int demandesPermission = 0;
  int suivisDemarres = 0;
  void Function(GpsFix)? _emetteur;

  @override
  Future<bool> ensurePermission() async {
    demandesPermission++;
    return permissionAccordee;
  }

  @override
  Stream<GpsFix> watch({
    required int distanceFilterMetres,
    required Duration intervalMinimum,
    required String notificationTitle,
    required String notificationText,
  }) {
    suivisDemarres++;
    final controleur = StreamController<GpsFix>(onCancel: () => _emetteur = null);
    _emetteur = controleur.add;
    return controleur.stream;
  }

  void emettre(GpsFix fix) => _emetteur?.call(fix);

  bool get enEcoute => _emetteur != null;
}

AppUser _chauffeur() => const AppUser(id: 1, username: 'conducteur_test', role: 'chauffeur_principal');

GpsFix _fix() => GpsFix(latitude: 5.81, longitude: -4.51, vitesseKmh: 60, releveLe: DateTime.now());

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _FakeLocationSource location;
  late StringBox box;
  late List<List<Map<String, dynamic>>> envoyes;
  late bool? etatServeur;
  late PositionBatcher batcher;
  late TripGpsController controller;

  TripGpsController creer() => TripGpsController(
        verifierTrajetEnCours: () async => etatServeur,
        location: location,
        batcher: batcher,
        intervalleVerification: const Duration(milliseconds: 10),
        intervalleEnvoi: const Duration(milliseconds: 10),
      );

  setUp(() {
    location = _FakeLocationSource();
    box = MemoryStringBox();
    envoyes = [];
    batcher = PositionBatcher(
      box: box,
      envoyer: (lot) async => envoyes.add(lot),
    );
    etatServeur = false;
    controller = creer();
  });

  tearDown(() => controller.dispose());

  test('un rôle qui ne conduit pas ne déclenche jamais de vérification', () async {
    controller.onUserChanged(const AppUser(id: 2, username: 'guichetier_test', role: 'guichetier'));
    await Future<void>.delayed(const Duration(milliseconds: 30));

    expect(location.demandesPermission, 0);
    expect(controller.enSuivi, isFalse);
  });

  test('trajet en cours : démarre le suivi, transmet les relevés reçus', () async {
    etatServeur = true;
    controller.onUserChanged(_chauffeur());
    await Future<void>.delayed(const Duration(milliseconds: 5));

    expect(controller.enSuivi, isTrue);
    expect(location.suivisDemarres, 1);

    location.emettre(_fix());
    await Future<void>.delayed(Duration.zero);

    expect(batcher.enAttente, 1);
  });

  test('permission refusée : pas de suivi, mais rien ne casse', () async {
    location.permissionAccordee = false;
    etatServeur = true;
    controller.onUserChanged(_chauffeur());
    await Future<void>.delayed(const Duration(milliseconds: 5));

    expect(controller.enSuivi, isFalse);
    expect(location.demandesPermission, 1);
  });

  test('fin de trajet : arrête le suivi et envoie le dernier lot', () async {
    etatServeur = true;
    controller.onUserChanged(_chauffeur());
    await Future<void>.delayed(const Duration(milliseconds: 5));
    location.emettre(_fix());
    await Future<void>.delayed(Duration.zero);

    etatServeur = false;
    await Future<void>.delayed(const Duration(milliseconds: 15));

    expect(controller.enSuivi, isFalse);
    expect(location.enEcoute, isFalse);
    expect(envoyes, hasLength(1));
    expect(batcher.enAttente, 0);
  });

  test('état inconnu (hors ligne) : ne coupe pas un suivi en cours', () async {
    etatServeur = true;
    controller.onUserChanged(_chauffeur());
    await Future<void>.delayed(const Duration(milliseconds: 5));

    etatServeur = null;
    await Future<void>.delayed(const Duration(milliseconds: 15));

    expect(controller.enSuivi, isTrue);
  });

  test('retour au premier plan : revérifie tout de suite sans attendre le prochain passage', () async {
    controller = TripGpsController(
      verifierTrajetEnCours: () async => etatServeur,
      location: location,
      batcher: batcher,
      intervalleVerification: const Duration(minutes: 10),
      intervalleEnvoi: const Duration(minutes: 10),
    );
    controller.onUserChanged(_chauffeur());
    await Future<void>.delayed(Duration.zero);
    expect(controller.enSuivi, isFalse);

    etatServeur = true;
    controller.didChangeAppLifecycleState(AppLifecycleState.resumed);
    await Future<void>.delayed(Duration.zero);

    expect(controller.enSuivi, isTrue);
  });

  test('déconnexion : arrête le suivi et se désabonne du cycle de vie', () async {
    etatServeur = true;
    controller.onUserChanged(_chauffeur());
    await Future<void>.delayed(const Duration(milliseconds: 5));

    controller.onUserChanged(null);
    await Future<void>.delayed(Duration.zero);

    expect(controller.enSuivi, isFalse);
    expect(location.enEcoute, isFalse);
  });
}
