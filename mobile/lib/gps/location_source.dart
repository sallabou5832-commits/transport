import 'gps_fix.dart';

/// Source des relevés GPS de l'appareil : une interface étroite pour que
/// [TripGpsController][../gps/trip_gps_controller.dart] se teste sans GPS ni permission réelle,
/// comme [SpeechRecognizer][../voice/speech_services.dart] pour la voix.
abstract interface class LocationSource {
  /// Demande les autorisations nécessaires. Faux si refusées ou si le service de localisation du
  /// téléphone est coupé : l'appelant continue alors sans suivi, jamais bloquant.
  Future<bool> ensurePermission();

  /// Le suivi tant que l'abonnement reste ouvert, échantillonné par distance et par temps minimal
  /// (économie de batterie et de réseau : pas un relevé en continu). `notificationTitle`/
  /// `notificationText` arment, sur Android, le service de premier plan qui permet au suivi de
  /// continuer quand l'application n'est pas au premier plan (voir `DeviceLocationSource`).
  Stream<GpsFix> watch({
    required int distanceFilterMetres,
    required Duration intervalMinimum,
    required String notificationTitle,
    required String notificationText,
  });
}
