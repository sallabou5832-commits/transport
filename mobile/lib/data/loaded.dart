/// Données affichées, avec leur provenance : serveur (à jour) ou cache local (hors ligne).
class Loaded<T> {
  const Loaded(this.data, {this.fromCache = false, this.savedAt});

  final T data;
  final bool fromCache;

  /// Date d'enregistrement des données en cache (renseignée si [fromCache]).
  final DateTime? savedAt;
}

/// Pas de réseau et rien d'enregistré sur l'appareil pour cet écran.
class NoCachedDataException implements Exception {
  const NoCachedDataException();

  @override
  String toString() => 'NoCachedDataException';
}
