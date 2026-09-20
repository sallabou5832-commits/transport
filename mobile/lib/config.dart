import 'package:flutter/foundation.dart';

/// L'adresse de l'API est absente ou refusée (par ex. HTTP en version release).
class ConfigurationException implements Exception {
  const ConfigurationException(this.message);

  final String message;

  @override
  String toString() => 'ConfigurationException: $message';
}

/// Valide l'adresse de l'API. En version release, **HTTPS est obligatoire** : jeton de
/// connexion, noms et téléphones des voyageurs ne doivent jamais circuler en clair.
String validateApiBaseUrl(String url, {required bool release}) {
  final uri = Uri.tryParse(url.trim());
  if (uri == null ||
      !uri.hasAuthority ||
      uri.host.isEmpty ||
      !{'http', 'https'}.contains(uri.scheme)) {
    throw ConfigurationException("Adresse de l'API invalide : « $url ».");
  }
  if (release && uri.scheme != 'https') {
    throw ConfigurationException(
      "L'API doit être en HTTPS dans une version release (reçu : « $url »). "
      'Compilez avec --dart-define=API_BASE_URL=https://...',
    );
  }
  return url.trim().replaceAll(RegExp(r'/+$'), '');
}

/// Choisit l'adresse de l'API. Fonction pure (entrées explicites) pour pouvoir la tester.
String resolveApiBaseUrl({
  required String fromEnv,
  required bool release,
  required bool isWeb,
  required TargetPlatform platform,
}) {
  if (fromEnv.isNotEmpty) return validateApiBaseUrl(fromEnv, release: release);
  if (release) {
    throw const ConfigurationException(
      "Adresse de l'API non configurée : compilez la version release avec "
      '--dart-define=API_BASE_URL=https://api.votre-domaine.ci/api',
    );
  }
  // Développement : le serveur Django local, en HTTP.
  if (!isWeb && platform == TargetPlatform.android) {
    // Dans l'émulateur Android, 10.0.2.2 désigne la machine qui héberge l'émulateur.
    return 'http://10.0.2.2:8000/api';
  }
  return 'http://localhost:8000/api';
}

/// URL de base de l'API Django (même API que le frontend web).
///
/// Surchargeable au lancement :
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api
/// Lève [ConfigurationException] si l'adresse manque ou n'est pas HTTPS en release.
String defaultApiBaseUrl() => resolveApiBaseUrl(
      fromEnv: const String.fromEnvironment('API_BASE_URL'),
      release: kReleaseMode,
      isWeb: kIsWeb,
      platform: defaultTargetPlatform,
    );
