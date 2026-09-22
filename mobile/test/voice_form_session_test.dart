import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/voice/speech_services.dart';
import 'package:transport_mobile/voice/voice_form_session.dart';

/// Faux moteur de reconnaissance : piloté à la main (`emitFinal`, `emitError`...), sans
/// microphone ni service externe. Ce fichier teste la mécanique d'écoute/énonciation de
/// `VoiceFormSession` (repli en cas de panne, annulation, délai dépassé) — jamais la
/// reconnaissance vocale elle-même, qui dépend du téléphone.
class _FakeRecognizer implements SpeechRecognizer {
  bool initResult = true;
  bool throwOnInitialize = false;
  bool throwOnListen = false;
  int listenCalls = 0;
  int stopCalls = 0;
  void Function(String texte, bool isFinal)? _onResult;
  void Function(String erreur)? _onError;

  @override
  Future<bool> initialize() async {
    if (throwOnInitialize) throw Exception('moteur de reconnaissance indisponible');
    return initResult;
  }

  @override
  Future<void> listen({
    required void Function(String texte, bool isFinal) onResult,
    required void Function(String erreur) onError,
    String localeId = 'fr_FR',
  }) async {
    listenCalls++;
    if (throwOnListen) throw Exception('écoute impossible');
    _onResult = onResult;
    _onError = onError;
  }

  @override
  Future<void> stop() async => stopCalls++;

  void emitPartial(String texte) => _onResult?.call(texte, false);
  void emitFinal(String texte) => _onResult?.call(texte, true);
  void emitError(String erreur) => _onError?.call(erreur);
}

class _FakeSynthesizer implements SpeechSynthesizer {
  bool initResult = true;
  bool throwOnSpeak = false;
  final spoken = <String>[];
  int stopCalls = 0;

  @override
  Future<bool> initialize() async => initResult;

  @override
  Future<void> speak(String texte) async {
    if (throwOnSpeak) throw Exception('synthèse indisponible');
    spoken.add(texte);
  }

  @override
  Future<void> stop() async => stopCalls++;
}

void main() {
  late _FakeRecognizer recognizer;
  late _FakeSynthesizer synthesizer;
  late VoiceFormSession session;

  setUp(() {
    recognizer = _FakeRecognizer();
    synthesizer = _FakeSynthesizer();
    session = VoiceFormSession(recognizer: recognizer, synthesizer: synthesizer);
  });

  group('init', () {
    test('vrai quand les deux moteurs sont prêts', () async {
      expect(await session.init(), isTrue);
    });

    test('faux si la reconnaissance échoue à s\'initialiser', () async {
      recognizer.initResult = false;
      expect(await session.init(), isFalse);
    });

    test('faux si la synthèse échoue à s\'initialiser', () async {
      synthesizer.initResult = false;
      expect(await session.init(), isFalse);
    });

    test('faux (jamais une exception) si le moteur lève une erreur à l\'initialisation', () async {
      recognizer.throwOnInitialize = true;
      expect(await session.init(), isFalse);
    });
  });

  group('ask', () {
    test('énonce la question puis renvoie le résultat final reconnu', () async {
      final futur = session.ask('Dites le nom du voyageur.');
      // La question est énoncée avant l'écoute : le faux moteur de synthèse l'a reçue
      // dès que `listen` a été appelé côté reconnaissance.
      await Future<void>.delayed(Duration.zero);
      expect(synthesizer.spoken, ['Dites le nom du voyageur.']);
      recognizer.emitFinal('Fatou Diop');

      expect(await futur, 'Fatou Diop');
    });

    test('ignore les résultats provisoires, attend un résultat final', () async {
      final futur = session.ask('Question ?');
      await Future<void>.delayed(Duration.zero);
      recognizer.emitPartial('Fat');
      recognizer.emitPartial('Fatou');
      recognizer.emitFinal('Fatou Diop');

      expect(await futur, 'Fatou Diop');
    });

    test('texte final vide : traité comme rien compris (null)', () async {
      final futur = session.ask('Question ?');
      await Future<void>.delayed(Duration.zero);
      recognizer.emitFinal('   ');

      expect(await futur, isNull);
    });

    test('erreur du moteur pendant l\'écoute : null, jamais d\'exception', () async {
      final futur = session.ask('Question ?');
      await Future<void>.delayed(Duration.zero);
      recognizer.emitError('no-match');

      expect(await futur, isNull);
    });

    test('le moteur lève une exception au démarrage de l\'écoute : null', () async {
      recognizer.throwOnListen = true;

      expect(await session.ask('Question ?'), isNull);
    });

    test('délai dépassé sans réponse : null, et l\'écoute est arrêtée', () async {
      final resultat = await session.ask('Question ?', timeout: const Duration(milliseconds: 20));

      expect(resultat, isNull);
      expect(recognizer.stopCalls, greaterThanOrEqualTo(1));
    });

    test('cancel() débloque une question en attente sans attendre le délai', () async {
      final futur = session.ask('Question ?', timeout: const Duration(seconds: 30));
      await Future<void>.delayed(Duration.zero);

      session.cancel();

      expect(await futur, isNull);
    });

    test('une panne de la synthèse (say) n\'empêche pas d\'écouter la réponse', () async {
      synthesizer.throwOnSpeak = true;
      final futur = session.ask('Question ?');
      await Future<void>.delayed(Duration.zero);
      recognizer.emitFinal('réponse quand même');

      expect(await futur, 'réponse quand même');
    });
  });

  group('dispose', () {
    test('arrête les deux moteurs', () async {
      await session.dispose();

      expect(recognizer.stopCalls, 1);
      expect(synthesizer.stopCalls, 1);
    });

    test('une question après dispose() ne relance rien : null tout de suite', () async {
      await session.dispose();

      expect(await session.ask('Trop tard ?'), isNull);
      expect(recognizer.listenCalls, 0);
    });
  });
}
