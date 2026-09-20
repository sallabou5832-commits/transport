/// Réponse d'erreur du serveur (4xx / 5xx).
class ApiException implements Exception {
  const ApiException(this.status, this.message, [this.data]);

  final int status;
  final String message;
  final Object? data;

  @override
  String toString() => 'ApiException($status): $message';
}

/// Le serveur n'a pas pu être joint (pas de réseau, délai dépassé...).
///
/// Distinct d'[ApiException] : c'est ce qui déclenche le mode hors ligne.
class NetworkException implements Exception {
  const NetworkException(this.message);

  final String message;

  @override
  String toString() => 'NetworkException: $message';
}

/// Extrait un message lisible d'une réponse d'erreur DRF (même logique que le frontend web).
String? extractErrorMessage(Object? data) {
  if (data == null) return null;
  if (data is String) return data;
  if (data is List) return data.join(' ');
  if (data is Map) {
    final detail = data['detail'];
    if (detail != null) return detail.toString();
    if (data.isEmpty) return null;
    final key = data.keys.first.toString();
    final value = data[data.keys.first];
    final text = value is List ? value.join(' ') : value.toString();
    return key == 'non_field_errors' ? text : '$key : $text';
  }
  return null;
}
