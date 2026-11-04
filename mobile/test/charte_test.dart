import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/auth/roles.dart';
import 'package:transport_mobile/ui/charte.dart';

import 'support/app_helpers.dart';

/// La charte : orange, blanc, vert, et une couleur par pôle — la même que celle du site.
void main() {
  test('chaque poste a la couleur de son pôle', () {
    for (final role in Roles.labels.keys) {
      expect(Charte.poleDuRole, contains(role), reason: role);
      expect(Charte.couleursDesPoles, contains(Charte.poleDuRole[role]), reason: role);
    }
    expect(Charte.couleurDuPole('inconnu'), Charte.orange);
  });

  Color lisere(WidgetTester tester) => tester.widget<Container>(find.byKey(const Key('lisere-pole'))).color!;

  appTest('l’accueil porte le liseré du pôle de l’agent : Exploitation pour le guichetier', (tester, h) async {
    h.stubLogin(role: 'guichetier');
    await demarrer(tester, h);
    await seConnecter(tester);

    expect(lisere(tester), Charte.couleursDesPoles['exploitation']);
  });

  appTest('et Personnel roulant pour le chauffeur', (tester, h) async {
    h.stubLogin(role: 'chauffeur_principal');
    h.stubFeuilleDuJour(chauffeurId: 7);
    await demarrer(tester, h);
    await seConnecter(tester);

    expect(lisere(tester), Charte.couleursDesPoles['roulant']);
  });
}
