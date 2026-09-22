import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Reconnaissance vocale : une interface étroite au-dessus du moteur natif du
/// téléphone (Android `SpeechRecognizer` / iOS `SFSpeechRecognizer`, via le paquet
/// `speech_to_text`). Existe pour que `VoiceFormSession` puisse être testée avec un
/// faux moteur, sans microphone (voir `test/voice_form_session_test.dart`).
abstract class SpeechRecognizer {
  /// Prépare le moteur (autorisations, disponibilité du service). Faux s'il n'est pas
  /// utilisable sur cet appareil : l'appelant doit alors proposer la saisie tactile.
  Future<bool> initialize();

  /// Écoute jusqu'au silence. [onResult] peut être appelé plusieurs fois (résultats
  /// provisoires) ; seul un appel avec `isFinal: true` compte. [onError] signale un
  /// échec du moteur (pas de correspondance, permission retirée en cours de route...).
  Future<void> listen({
    required void Function(String texte, bool isFinal) onResult,
    required void Function(String erreur) onError,
    String localeId = 'fr_FR',
  });

  Future<void> stop();
}

/// Synthèse vocale : une interface étroite au-dessus du moteur natif (via `flutter_tts`).
abstract class SpeechSynthesizer {
  Future<bool> initialize();
  Future<void> speak(String texte);
  Future<void> stop();
}

/// Reconnaissance vocale du téléphone (`speech_to_text`), en français.
class DeviceSpeechRecognizer implements SpeechRecognizer {
  DeviceSpeechRecognizer() : _speech = stt.SpeechToText();

  final stt.SpeechToText _speech;
  void Function(String erreur)? _onError;

  @override
  Future<bool> initialize() async {
    try {
      return await _speech.initialize(
        onError: (erreur) => _onError?.call(erreur.errorMsg),
        onStatus: (_) {},
      );
    } on Object {
      // Service absent, permission refusée en amont... : indisponible, jamais une erreur fatale.
      return false;
    }
  }

  @override
  Future<void> listen({
    required void Function(String texte, bool isFinal) onResult,
    required void Function(String erreur) onError,
    String localeId = 'fr_FR',
  }) async {
    _onError = onError;
    void surResultat(SpeechRecognitionResult resultat) =>
        onResult(resultat.recognizedWords, resultat.finalResult);
    await _speech.listen(
      onResult: surResultat,
      listenOptions: stt.SpeechListenOptions(
        localeId: localeId,
        partialResults: true,
        cancelOnError: true,
        listenMode: stt.ListenMode.confirmation,
      ),
    );
  }

  @override
  Future<void> stop() => _speech.stop();
}

/// Synthèse vocale du téléphone (`flutter_tts`), en français.
class DeviceSpeechSynthesizer implements SpeechSynthesizer {
  DeviceSpeechSynthesizer() : _tts = FlutterTts();

  final FlutterTts _tts;
  bool _ready = false;

  @override
  Future<bool> initialize() async {
    try {
      await _tts.awaitSpeakCompletion(true);
      final langueOk = await _tts.setLanguage('fr-FR');
      _ready = langueOk == 1 || langueOk == true || langueOk == null;
      return _ready;
    } on Object {
      return false;
    }
  }

  @override
  Future<void> speak(String texte) async {
    if (texte.trim().isEmpty) return;
    await _tts.speak(texte);
  }

  @override
  Future<void> stop() => _tts.stop();
}
