import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:transport_mobile/app.dart';
import 'package:transport_mobile/storage/local_store.dart';
import 'package:transport_mobile/storage/outbox.dart';

import 'support/app_helpers.dart';
import 'support/harness.dart';

const reserver = '/tickets/reserver-hors-ligne/';

/// Guichetier connecté avec le réseau, ayant déjà ouvert l'écran de vente une fois
/// (les départs sont donc mémorisés sur le téléphone).
Future<void> guichetierPret(WidgetTester tester, Harness h, {int places = 2}) async {
  h.stubLogin();
  h.stubDeparts(placesReservees: places);
  h.server.onJson('POST', '/tickets/', {'id': 99}, 201);
  await demarrer(tester, h);
  await seConnecter(tester);
  await ouvrirVente(tester);
  await retour(tester);
}

Future<void> coupureReseau(WidgetTester tester, Harness h) async {
  h.server.offline = true;
  h.connectivity.setOnline(false);
  await tester.pumpAndSettle();
}

Future<void> retourReseau(WidgetTester tester, Harness h) async {
  h.server.offline = false;
  h.connectivity.setOnline(true);
  await tester.pumpAndSettle();
}

int enAttente(Harness h) => Outbox(h.services.store.outboxBox).pendingFor(7).length;

void main() {
  group('Places garanties hors ligne', () {
    appTest('l\'écran de vente indique combien de ventes restent possibles sans réseau',
        (tester, h) async {
      await guichetierPret(tester, h, places: 2);

      await ouvrirVente(tester);
      await choisirDepart(tester);

      expect(find.text('Places garanties hors ligne : 2'), findsOneWidget);
    });

    appTest('HORS LIGNE : autant de ventes que de places garanties, pas une de plus',
        (tester, h) async {
      await guichetierPret(tester, h, places: 2);
      await coupureReseau(tester, h);
      await ouvrirVente(tester);

      await remplirEtValiderVente(tester, nom: 'Premier');
      expect(find.textContaining('Vente enregistrée sur le téléphone'), findsOneWidget);
      expect(find.text('Places garanties hors ligne : 1'), findsOneWidget);

      await remplirEtValiderVente(tester, nom: 'Second');
      expect(find.textContaining('Vente enregistrée sur le téléphone'), findsOneWidget);
      expect(find.byKey(const Key('places-garanties')), findsOneWidget);
      expect(find.text('Aucune place garantie hors ligne : la vente exige le réseau.'), findsOneWidget);

      // La troisième vente n'a AUCUNE garantie : elle est bloquée et rien n'est enregistré.
      await remplirEtValiderVente(tester, nom: 'Troisième');
      expect(find.textContaining("aucune place n'est garantie hors ligne"), findsOneWidget);
      expect(enAttente(h), 2);
      expect(h.server.requestsTo('POST', '/tickets/'), isEmpty);
    });

    appTest('HORS LIGNE, ligne à tarif : tarif gardé sur le téléphone, vente en file sans prix (G-02)',
        (tester, h) async {
      h.stubLogin();
      h.stubDeparts(tarif: '6000.00');
      h.server.onJson('POST', '/tickets/', {'id': 99}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);
      await retour(tester);
      await coupureReseau(tester, h);
      await ouvrirVente(tester);
      await choisirDepart(tester);

      final prix = tester.widget<TextField>(
        find.descendant(of: find.byKey(const Key('prix')), matching: find.byType(TextField)),
      );
      expect(prix.controller!.text, '6000');
      await tester.enterText(find.byKey(const Key('passager-nom')), 'Kouadio Yao');
      await tester.enterText(find.byKey(const Key('passager-telephone')), '0700000000');
      await tester.tap(find.byKey(const Key('valider-vente')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Vente enregistrée sur le téléphone'), findsOneWidget);
      expect(Outbox(h.services.store.outboxBox).pendingFor(7).single.payload.containsKey('prix'), isFalse);

      await retourReseau(tester, h);
      expect(enAttente(h), 0);
      expect(h.server.requestsTo('POST', '/tickets/').single.body, isNot(contains('"prix"')));
    });

    appTest('hors ligne sans aucune réservation : vente bloquée, rien mis en file', (tester, h) async {
      await guichetierPret(tester, h, places: 0);
      await coupureReseau(tester, h);
      await ouvrirVente(tester);

      await remplirEtValiderVente(tester);

      expect(find.textContaining("aucune place n'est garantie hors ligne"), findsOneWidget);
      expect(enAttente(h), 0);
    });

    appTest('avec le réseau, une vente reste possible même sans réservation', (tester, h) async {
      await guichetierPret(tester, h, places: 0);
      await ouvrirVente(tester);

      await remplirEtValiderVente(tester);

      expect(find.text('Ticket vendu.'), findsOneWidget);
      expect(h.server.requestsTo('POST', '/tickets/'), hasLength(1));
    });

    appTest('le réseau « connecté » mais sans internet est détecté avant la vente', (tester, h) async {
      // L'appareil se croit en ligne (Wi-Fi sans accès), mais le serveur ne répond pas.
      await guichetierPret(tester, h, places: 0);
      h.server.offline = true; // le système, lui, n'a rien signalé
      await ouvrirVente(tester);

      await remplirEtValiderVente(tester);

      expect(find.textContaining("aucune place n'est garantie hors ligne"), findsOneWidget);
      expect(enAttente(h), 0);
    });

    appTest('au retour du réseau : ventes envoyées, puis places garanties reconstituées',
        (tester, h) async {
      await guichetierPret(tester, h, places: 2);
      await coupureReseau(tester, h);
      await ouvrirVente(tester);
      await remplirEtValiderVente(tester, nom: 'Premier');
      await remplirEtValiderVente(tester, nom: 'Second');
      await retour(tester);
      final demandesAvant = h.server.requestsTo('POST', reserver).length;

      await retourReseau(tester, h);

      expect(h.server.requestsTo('POST', '/tickets/'), hasLength(2));
      expect(enAttente(h), 0);
      expect(h.server.requestsTo('POST', reserver).length, greaterThan(demandesAvant));
      await ouvrirVente(tester);
      await choisirDepart(tester);
      expect(find.text('Places garanties hors ligne : 2'), findsOneWidget);
    });

    appTest('vente hors ligne refusée à la synchronisation : consigne de remboursement',
        (tester, h) async {
      await guichetierPret(tester, h, places: 2);
      await coupureReseau(tester, h);
      await ouvrirVente(tester);
      await remplirEtValiderVente(tester);
      await retour(tester);
      h.server.onJson('POST', '/tickets/', {'depart': ['Plus aucune place.']}, 400);

      await retourReseau(tester, h);
      await tester.tap(find.byKey(const Key('sync-status-bar')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Refusée : depart : Plus aucune place.'), findsOneWidget);
      expect(find.textContaining('remboursez-le'), findsOneWidget);
    });
  });

  group('Fin de service', () {
    appTest('sans vente en attente : les places réservées sont rendues à la déconnexion',
        (tester, h) async {
      await guichetierPret(tester, h);

      await tester.tap(find.byKey(const Key('logout')));
      await tester.pumpAndSettle();

      expect(h.server.requestsTo('DELETE', reserver), hasLength(1));
      expect(find.byKey(const Key('login-button')), findsOneWidget);
    });

    appTest('avec des ventes en attente : les places sont CONSERVÉES pour qu\'elles passent',
        (tester, h) async {
      await guichetierPret(tester, h);
      await coupureReseau(tester, h);
      await ouvrirVente(tester);
      await remplirEtValiderVente(tester);
      await retour(tester);

      await tester.tap(find.byKey(const Key('logout')));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Se déconnecter'));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('login-button')), findsOneWidget);
      expect(h.server.requestsTo('DELETE', reserver), isEmpty);
      expect(enAttente(h), 1);
    });
  });

  group('Données locales illisibles', () {
    testWidgets('l\'utilisateur est prévenu que des ventes ont pu être perdues', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final h = Harness(store: LocalStore.memory(wasReset: true));
      h.stubLogin();
      await tester.pumpWidget(TransportApp(services: h.services));
      await tester.pumpAndSettle();
      await seConnecter(tester);

      expect(find.byKey(const Key('donnees-locales-effacees')), findsOneWidget);
      expect(find.textContaining('ont été effacées'), findsOneWidget);

      await tester.tap(find.text('Compris'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('donnees-locales-effacees')), findsNothing);

      await tester.pumpWidget(const SizedBox.shrink());
    });

    appTest('aucune alerte quand tout est normal', (tester, h) async {
      h.stubLogin();
      await demarrer(tester, h);

      await seConnecter(tester);

      expect(find.byKey(const Key('donnees-locales-effacees')), findsNothing);
    });
  });
}
