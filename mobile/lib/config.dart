import 'package:flutter/foundation.dart';

/// URL de base de l'API Django (même API que le frontend web).
///
/// Surchargeable au lancement :
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api
String defaultApiBaseUrl() {
  const fromEnv = String.fromEnvironment('API_BASE_URL');
  if (fromEnv.isNotEmpty) return fromEnv;
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
    // Dans l'émulateur Android, 10.0.2.2 désigne la machine qui héberge l'émulateur.
    return 'http://10.0.2.2:8000/api';
  }
  return 'http://localhost:8000/api';
}
