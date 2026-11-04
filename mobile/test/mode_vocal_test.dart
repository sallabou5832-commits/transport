import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/voice/speech_services.dart';
import 'package:transport_mobile/voice/voice_form_session.dart';

import 'support/app_helpers.dart';
import 'support/harness.dart';

/// Moteur vocal de test : indisponible, ce qui suffit à voir que la dictée a démarré (l'écran le dit et repasse au clavier),
/// sans jamais toucher au vrai moteur du téléphone.
class _MoteurIndisponible implements SpeechRecognizer {
  int demarrages = 0;

  @override
  Future<bool> initialize() async {
    demarrages++;
    return false;
  }

  @override
  Future<void> listen({
    required void Function(String texte, bool isFinal) onResult,
    required void Function(String erreur) onError,
    String localeId = 'fr_FR',
  }) async {}

  @override
  Future<void> stop() async {}
}

class _SyntheseMuette implements SpeechSynthesizer {
  @override
  Future<bool> initialize() async => true;

  @override
  Future<void> speak(String texte) async {}

  @override
  Future<void> stop() async {}
}

/// Mode vocal préféré (lot P1e) : la dictée démarre d'elle-même dans la vente et la checklist ; l'agent le règle lui-même dans
/// « Mes paramètres », sauf si son supérieur l'a imposé.
void main() {
  void essai(String description, Future<void> Function(WidgetTester tester, Harness h, _MoteurIndisponible moteur) corps) {
    testWidgets(description, (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final moteur = _MoteurIndisponible();
      final h = Harness(sessionVocale: () => VoiceFormSession(recognizer: moteur, synthesizer: _SyntheseMuette()));
      await corps(tester, h, moteur);
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }

  void configuration(Harness h, {bool prefereVocal = false, bool impose = false}) {
    h.server.onJson('GET', '/configuration/moi/', {
      'prefere_vocal': prefereVocal,
      'vocal_impose': impose,
      'session': {'duree_max': 'deconnexion', 'code_court_exige': false},
    });
  }

  group('Dictée qui démarre d\'elle-même', () {
    essai('vocal préféré : la dictée démarre au choix du départ, une seule fois', (tester, h, moteur) async {
      h.stubLogin();
      h.stubDeparts();
      configuration(h, prefereVocal: true);
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);

      await choisirDepart(tester);

      expect(moteur.demarrages, 1);
      expect(find.textContaining('Reconnaissance vocale indisponible'), findsOneWidget);
      await choisirDepart(tester); // changer de départ ne relance pas la dictée
      expect(moteur.demarrages, 1);
    });

    essai('sans préférence : rien ne démarre tout seul (comme avant)', (tester, h, moteur) async {
      h.stubLogin();
      h.stubDeparts();
      configuration(h);
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);

      await choisirDepart(tester);

      expect(moteur.demarrages, 0);
    });

    essai('vocal préféré : la checklist avant-départ démarre la dictée à l\'ouverture', (tester, h, moteur) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      configuration(h, prefereVocal: true);
      await demarrer(tester, h);
      await seConnecter(tester);

      await tester.tap(find.byKey(const Key('checklist-avant-depart')));
      await tester.pumpAndSettle();

      expect(moteur.demarrages, 1);
    });
  });

  group('Mes paramètres', () {
    essai('l\'agent choisit lui-même le mode vocal', (tester, h, moteur) async {
      h.stubLogin();
      configuration(h);
      h.server.onJson('GET', '/configuration/mes-preferences/', {'prefere_vocal': null, 'vocal_impose': false});
      h.server.onJson('PATCH', '/configuration/mes-preferences/', {'prefere_vocal': true, 'vocal_impose': false});
      await demarrer(tester, h);
      await seConnecter(tester);
      await tester.tap(find.byKey(const Key('mes-parametres')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Inactif'), findsOneWidget);

      configuration(h, prefereVocal: true); // ce que le serveur renverra après le choix
      await tester.tap(find.byKey(const Key('mode-vocal-oui')));
      await tester.pumpAndSettle();

      expect(h.server.requestsTo('PATCH', '/configuration/mes-preferences/').single.body, '{"prefere_vocal":true}');
      expect(find.textContaining('Actif : la dictée démarre'), findsOneWidget);
    });

    essai('imposé par le supérieur : rien à choisir', (tester, h, moteur) async {
      h.stubLogin();
      configuration(h, prefereVocal: true, impose: true);
      h.server.onJson('GET', '/configuration/mes-preferences/', {'prefere_vocal': null, 'vocal_impose': true});
      await demarrer(tester, h);
      await seConnecter(tester);
      await tester.tap(find.byKey(const Key('mes-parametres')));
      await tester.pumpAndSettle();

      expect(find.text('Fixé par votre supérieur.'), findsOneWidget);
      expect(find.byKey(const Key('mode-vocal-oui')), findsNothing);
    });
  });
}
