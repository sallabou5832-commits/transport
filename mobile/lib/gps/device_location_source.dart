import 'package:geolocator/geolocator.dart';

import 'gps_fix.dart';
import 'location_source.dart';

/// Localisation réelle du téléphone (`geolocator`), avec service de premier plan Android pour que le
/// suivi continue hors de l'application (voir `android/app/src/main/AndroidManifest.xml` :
/// `ACCESS_BACKGROUND_LOCATION`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`).
///
/// Non testé unitairement (elle appelle le GPS réel) : voir `test/support/fake_location_source.dart`
/// pour ce qui teste `TripGpsController`, et `mobile/TEST_TELEPHONES.md` pour l'essai sur un vrai
/// téléphone (jamais fait dans cet environnement, comme le reste du mobile).
class DeviceLocationSource implements LocationSource {
  @override
  Future<bool> ensurePermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) return false;
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      return false;
    }
    // Le suivi hors de l'application demande l'autorisation « toujours » en plus de « pendant
    // l'utilisation » : sans elle, Android coupe le suivi dès que l'écran s'éteint. Ce n'est pas
    // bloquant si elle est refusée : on continue avec ce qui a été accordé.
    if (permission == LocationPermission.whileInUse) {
      await Geolocator.requestPermission();
    }
    return true;
  }

  @override
  Stream<GpsFix> watch({
    required int distanceFilterMetres,
    required Duration intervalMinimum,
    required String notificationTitle,
    required String notificationText,
  }) {
    final settings = AndroidSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: distanceFilterMetres,
      intervalDuration: intervalMinimum,
      foregroundNotificationConfig: ForegroundNotificationConfig(
        notificationTitle: notificationTitle,
        notificationText: notificationText,
        enableWakeLock: true,
      ),
    );
    return Geolocator.getPositionStream(locationSettings: settings).map(
      (position) => GpsFix(
        latitude: position.latitude,
        longitude: position.longitude,
        // m/s -> km/h. `speed` peut être négative ou infinie sur certains appareils sans capteur fiable.
        vitesseKmh: position.speed.isFinite && position.speed >= 0 ? (position.speed * 3.6).round() : null,
        releveLe: position.timestamp,
      ),
    );
  }
}
