import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/app.dart';

import 'harness.dart';

/// Test d'écran : fenêtre haute (formulaire entièrement visible) et démontage final
/// (arrête la minuterie de synchronisation, sinon le test signalerait un timer actif).
void appTest(String description, Future<void> Function(WidgetTester tester, Harness h) body) {
  testWidgets(description, (tester) async {
    tester.view.physicalSize = const Size(800, 1600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final harness = Harness();
    await body(tester, harness);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}

Future<void> demarrer(WidgetTester tester, Harness h) async {
  await tester.pumpWidget(TransportApp(services: h.services));
  await tester.pumpAndSettle();
}

Future<void> seConnecter(WidgetTester tester) async {
  await tester.enterText(find.byKey(const Key('username')), 'awa');
  await tester.enterText(find.byKey(const Key('password')), 'Demo!2024');
  await tester.tap(find.byKey(const Key('login-button')));
  await tester.pumpAndSettle();
}

Future<void> ouvrirVente(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('vendre-ticket')));
  await tester.pumpAndSettle();
}

Future<void> choisirDepart(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('depart')));
  await tester.pumpAndSettle();
  await tester.tap(find.textContaining('Adjamé-Bouaké').last);
  await tester.pumpAndSettle();
}

Future<void> remplirEtValiderVente(WidgetTester tester, {String nom = 'Kouadio Yao'}) async {
  if (find.byKey(const Key('places-garanties')).evaluate().isEmpty) await choisirDepart(tester);
  await tester.enterText(find.byKey(const Key('passager-nom')), nom);
  await tester.enterText(find.byKey(const Key('passager-telephone')), '0700000000');
  await tester.enterText(find.byKey(const Key('prix')), '5000');
  await tester.tap(find.byKey(const Key('valider-vente')));
  await tester.pumpAndSettle();
}

Future<void> retour(WidgetTester tester) async {
  await tester.pageBack();
  await tester.pumpAndSettle();
}
