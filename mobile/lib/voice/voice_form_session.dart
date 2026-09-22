import 'dart:async';

import 'speech_services.dart';

/// Une conversation vocale guidée : énonce une question, écoute la réponse, une à la
/// fois. Le texte reconnu est ensuite compris par les fonctions pures de `voice_text.dart`
/// — cette classe ne fait que la mécanique d'écoute/énonciation, jamais l'interprétation.
///
/// Conçue pour ne jamais bloquer l'écran qui l'utilise : toute panne du moteur (service
/// absent, permission refusée, erreur en cours d'écoute, silence trop long) se traduit
/// par un résultat `null`/`false`, jamais par une exception qui remonterait à l'appelant.
/// C'est ce qui permet le mode secours (retour à la saisie tactile) exigé par le cahier
/// des charges.
class VoiceFormSession {
  VoiceFormSession({SpeechRecognizer? recognizer, SpeechSynthesizer? synthesizer})
      : _recognizer = recognizer ?? DeviceSpeechRecognizer(),
        _synthesizer = synthesizer ?? DeviceSpeechSynthesizer();

  final SpeechRecognizer _recognizer;
  final SpeechSynthesizer _synthesizer;
  bool _disposed = false;
  Completer<String?>? _enAttente;

  /// Prépare les deux moteurs. Faux si l'un des deux n'est pas utilisable sur cet
  /// appareil (service absent, permission micro refusée...).
  Future<bool> init() async {
    try {
      final recoOk = await _recognizer.initialize();
      final ttsOk = await _synthesizer.initialize();
      return recoOk && ttsOk;
    } on Object {
      return false;
    }
  }

  /// Énonce [texte]. Une confirmation orale ratée (moteur TTS en défaut) n'interrompt
  /// jamais le parcours : c'est un confort, pas une condition de validation.
  Future<void> say(String texte) async {
    try {
      await _synthesizer.speak(texte);
    } on Object {
      // ignoré : voir le commentaire de la méthode.
    }
  }

  /// Énonce [prompt] puis écoute jusqu'au silence (ou [timeout]) : renvoie le texte
  /// reconnu, ou `null` si rien n'a été compris, en cas d'erreur du moteur, ou si le
  /// délai est dépassé.
  Future<String?> ask(String prompt, {Duration timeout = const Duration(seconds: 8)}) async {
    if (_disposed) return null;
    await say(prompt);
    if (_disposed) return null;

    final resultat = Completer<String?>();
    _enAttente = resultat;
    void terminer(String? valeur) {
      if (!resultat.isCompleted) resultat.complete(valeur);
    }

    try {
      await _recognizer.listen(
        onResult: (texte, isFinal) {
          if (isFinal) terminer(texte.trim().isEmpty ? null : texte.trim());
        },
        onError: (_) => terminer(null),
      );
    } on Object {
      _enAttente = null;
      return null;
    }

    final texte = await resultat.future.timeout(timeout, onTimeout: () => null);
    _enAttente = null;
    await _arreterEcoute();
    return texte;
  }

  /// Interrompt la question en cours : l'utilisateur préfère reprendre au clavier tout
  /// de suite plutôt que d'attendre le silence ou le délai. Sans effet s'il n'y a
  /// aucune question en attente.
  void cancel() => _enAttente?.complete(null);

  Future<void> _arreterEcoute() async {
    try {
      await _recognizer.stop();
    } on Object {
      // déjà arrêté, ou moteur en défaut : sans conséquence.
    }
  }

  /// Libère les moteurs. À appeler à la fin de la conversation (validée, abandonnée,
  /// ou basculée vers la saisie tactile).
  Future<void> dispose() async {
    _disposed = true;
    await _arreterEcoute();
    try {
      await _synthesizer.stop();
    } on Object {
      // sans conséquence.
    }
  }
}
