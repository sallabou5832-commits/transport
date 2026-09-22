import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/voice/voice_text.dart';

/// Tests de la logique de traitement du texte reconnu (voir `lib/voice/voice_text.dart`)
/// — pas de la reconnaissance vocale elle-même, qui dépend du service du téléphone et
/// n'est pas testée ici (voir `test/voice_form_session_test.dart` pour la mécanique
/// d'écoute, avec un faux moteur).
void main() {
  group('normalizeSpoken', () {
    test('met en minuscules et retire les accents', () {
      expect(normalizeSpoken('DÉFAUT côté Éclairage'), 'defaut cote eclairage');
    });

    test('réduit les espaces multiples et les bords', () {
      expect(normalizeSpoken('  Espèces   liquide  '), 'especes liquide');
    });
  });

  group('capitalizeWords', () {
    test('met une majuscule à chaque mot dicté (arrivé en minuscules)', () {
      expect(capitalizeWords('fatou diop'), 'Fatou Diop');
    });

    test('un seul mot', () {
      expect(capitalizeWords('kouassi'), 'Kouassi');
    });

    test('espaces multiples entre les mots : ignorés', () {
      expect(capitalizeWords('  awa   kone  '), 'Awa Kone');
    });
  });

  group('extractDigitsOnly', () {
    test('garde uniquement les chiffres', () {
      expect(extractDigitsOnly('07 00 00 00 00'), '0700000000');
    });

    test('aucun chiffre : chaîne vide', () {
      expect(extractDigitsOnly('pas de numéro'), '');
    });
  });

  group('extractNumber', () {
    test('suite de chiffres simple', () {
      expect(extractNumber('le prix est 2500 francs'), '2500');
    });

    test('décimale dite « virgule »', () {
      expect(extractNumber('2500 virgule 50'), '2500.50');
    });

    test('décimale dite « point »', () {
      expect(extractNumber('12 point 5'), '12.5');
    });

    test('rien à trouver : null', () {
      expect(extractNumber('aucun nombre ici'), isNull);
    });

    test('prend le premier nombre si plusieurs sont dictés', () {
      expect(extractNumber('numéro 12 puis 34'), '12');
    });
  });

  group('parseModePaiement', () {
    test('espèces', () {
      expect(parseModePaiement('en espèces'), 'especes');
    });

    test('liquide et cash sont compris comme espèces', () {
      expect(parseModePaiement('payé en liquide'), 'especes');
      expect(parseModePaiement('cash'), 'especes');
    });

    test('mobile money', () {
      expect(parseModePaiement('par mobile money'), 'mobile_money');
    });

    test('orange money et wave sont compris comme mobile money', () {
      expect(parseModePaiement('orange money'), 'mobile_money');
      expect(parseModePaiement('avec wave'), 'mobile_money');
    });

    test('insensible à la casse et aux accents', () {
      expect(parseModePaiement('ESPÈCES'), 'especes');
    });

    test('rien de reconnu : null', () {
      expect(parseModePaiement('je ne sais pas'), isNull);
    });

    test('mobile money est reconnu avant que « mobile » ne prête à confusion', () {
      expect(parseModePaiement('mobile money orange'), 'mobile_money');
    });
  });

  group('parseEtatChecklist', () {
    test('défaut', () {
      expect(parseEtatChecklist('il y a un défaut'), 'defaut');
    });

    test('synonymes de défaut', () {
      expect(parseEtatChecklist('c\'est en panne'), 'defaut');
      expect(parseEtatChecklist('pneu usé'), 'defaut');
      expect(parseEtatChecklist('à changer'), 'defaut');
    });

    test('ok', () {
      expect(parseEtatChecklist('c\'est ok'), 'ok');
    });

    test('synonymes de ok', () {
      expect(parseEtatChecklist('rien à signaler'), 'ok');
      expect(parseEtatChecklist('impeccable'), 'ok');
    });

    test('rien de reconnu : null (jamais un devinage)', () {
      expect(parseEtatChecklist('je regarde'), isNull);
    });

    test('« moto » ne déclenche pas « ok » par sous-chaîne', () {
      expect(parseEtatChecklist('la moto est garée à côté'), isNull);
    });
  });

  group('parseConfirmationIntent', () {
    test('confirmer', () {
      expect(parseConfirmationIntent('je confirme'), VoiceIntent.confirmer);
      expect(parseConfirmationIntent('valider'), VoiceIntent.confirmer);
    });

    test('modifier', () {
      expect(parseConfirmationIntent('je préfère modifier'), VoiceIntent.modifier);
      expect(parseConfirmationIntent('annuler'), VoiceIntent.modifier);
    });

    test('rien de reconnu : inconnu (jamais confirmé par défaut)', () {
      expect(parseConfirmationIntent('bonjour'), VoiceIntent.inconnu);
    });
  });

  group('recapVenteTicket', () {
    test('reprend les champs dictés', () {
      final recap = recapVenteTicket(
        nom: 'Fatou Diop',
        telephone: '0700000000',
        prix: '2500',
        modePaiement: 'especes',
      );
      expect(recap, contains('Fatou Diop'));
      expect(recap, contains('0700000000'));
      expect(recap, contains('2500 francs'));
      expect(recap, contains('espèces'));
      expect(recap, contains('confirmer'));
    });

    test('mobile money est bien libellé (pas la valeur brute avec underscore)', () {
      final recap = recapVenteTicket(nom: 'A', telephone: '1', prix: '1', modePaiement: 'mobile_money');
      expect(recap, contains('mobile money'));
      expect(recap, isNot(contains('mobile_money')));
    });

    test('champ vide : signalé comme non renseigné plutôt que tu', () {
      final recap = recapVenteTicket(nom: '', telephone: '0700000000', prix: '2500', modePaiement: 'especes');
      expect(recap, contains('nom non renseigné'));
    });
  });

  group('recapChecklistDepart', () {
    const items = ['pneus', 'freins'];
    const labels = {'pneus': 'Pneus', 'freins': 'Freins'};

    test('sans défaut', () {
      final recap = recapChecklistDepart(
        items: items,
        labels: labels,
        etats: const {'pneus': 'ok', 'freins': 'ok'},
        commentaires: const {},
      );
      expect(recap, contains('Pneus OK'));
      expect(recap, contains('Freins OK'));
      expect(recap, contains('Aucun défaut.'));
    });

    test('avec un défaut : signalé et commenté', () {
      final recap = recapChecklistDepart(
        items: items,
        labels: labels,
        etats: const {'pneus': 'defaut', 'freins': 'ok'},
        commentaires: const {'pneus': 'usure avant droite'},
      );
      expect(recap, contains('Pneus en défaut : usure avant droite'));
      expect(recap, contains('Attention, défaut signalé sur : Pneus.'));
    });

    test('défaut sans commentaire : pas de « : » vide', () {
      final recap = recapChecklistDepart(
        items: items,
        labels: labels,
        etats: const {'pneus': 'defaut', 'freins': 'ok'},
        commentaires: const {},
      );
      expect(recap, contains('Pneus en défaut.'));
    });
  });
}
