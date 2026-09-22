import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/app_helpers.dart';

/// Tests d'écran autour de la commande vocale : la présence et l'activation du bouton
/// « Remplir par la voix », et — pour la checklist avant-départ, tout juste ajoutée —
/// le parcours tactile complet (mode secours), sans jamais déclencher le vrai moteur de
/// reconnaissance : l'appuyer dans un test d'écran bloque indéfiniment (aucun canal de
/// plateforme simulé ne répond), ce qui est cohérent avec le cahier des charges : cette
/// logique n'est pas testée ici, seule la logique de traitement du texte reconnu l'est
/// (voir `test/voice_text_test.dart` et `test/voice_form_session_test.dart`, avec un
/// faux moteur).
void main() {
  group('Commande vocale — vente de ticket', () {
    appTest('le bouton est désactivé tant qu\'aucun départ n\'est choisi', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);

      final bouton = tester.widget<OutlinedButton>(find.byKey(const Key('voix-demarrer')));
      expect(bouton.onPressed, isNull);
      expect(find.text('Choisissez d\'abord un départ.'), findsOneWidget);
    });

    appTest('devient utilisable une fois un départ choisi', (tester, h) async {
      h.stubLogin();
      h.stubDeparts();
      await demarrer(tester, h);
      await seConnecter(tester);
      await ouvrirVente(tester);
      await choisirDepart(tester);

      final bouton = tester.widget<OutlinedButton>(find.byKey(const Key('voix-demarrer')));
      expect(bouton.onPressed, isNotNull);
      expect(find.text('Remplir par la voix'), findsOneWidget);
    });
  });

  group('Checklist avant-départ (nouvel écran)', () {
    appTest('accessible depuis la feuille de route du chauffeur, avec ses six items',
        (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      await demarrer(tester, h);
      await seConnecter(tester);

      await tester.tap(find.byKey(const Key('checklist-avant-depart')));
      await tester.pumpAndSettle();

      expect(find.text('Checklist avant-départ'), findsOneWidget);
      for (final label in ['Pneus', 'Freins', 'Carburant', 'Éclairage', 'Direction', 'Ceintures']) {
        expect(find.text(label), findsOneWidget);
      }
      final bouton = tester.widget<OutlinedButton>(find.byKey(const Key('voix-demarrer')));
      expect(bouton.onPressed, isNotNull); // pas besoin de choisir quoi que ce soit avant
    });

    appTest('saisie tactile : tout à OK, un item par requête, dans l\'ordre', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      h.server.onJson('POST', '/checklists/', {'id': 1}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      await tester.tap(find.byKey(const Key('checklist-avant-depart')));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('valider-checklist')));
      await tester.pumpAndSettle();

      expect(find.text('Checklist enregistrée, aucun défaut.'), findsOneWidget);
      final requetes = h.server.requestsTo('POST', '/checklists/');
      expect(requetes, hasLength(6));
      expect(requetes.first.body, contains('"feuille_de_route":10'));
      expect(requetes.first.body, contains('"item":"pneus"'));
      expect(requetes.first.body, contains('"etat":"ok"'));
      expect(requetes.last.body, contains('"item":"ceintures"'));
    });

    appTest('un défaut demande un commentaire et l\'écran le signale', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      h.server.onJson('POST', '/checklists/', {'id': 1}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      await tester.tap(find.byKey(const Key('checklist-avant-depart')));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Défaut').first); // item « pneus », le premier de la liste
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Usure avant droite');
      await tester.tap(find.byKey(const Key('valider-checklist')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Défaut signalé sur : Pneus'), findsOneWidget);
      final requetePneus = h.server.requestsTo('POST', '/checklists/').first;
      expect(requetePneus.body, contains('"etat":"defaut"'));
      expect(requetePneus.body, contains('"commentaire":"Usure avant droite"'));
    });

    appTest('repasser un item à OK efface son commentaire', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      h.server.onJson('POST', '/checklists/', {'id': 1}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      await tester.tap(find.byKey(const Key('checklist-avant-depart')));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Défaut').first);
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'faux problème');
      await tester.tap(find.text('OK').first);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('valider-checklist')));
      await tester.pumpAndSettle();

      expect(find.text('Checklist enregistrée, aucun défaut.'), findsOneWidget);
      final requetePneus = h.server.requestsTo('POST', '/checklists/').first;
      expect(requetePneus.body, contains('"etat":"ok"'));
      expect(requetePneus.body, contains('"commentaire":""'));
    });

    appTest('hors ligne : enregistrée sur le téléphone, envoyée au retour du réseau', (tester, h) async {
      h.stubLogin(id: 7, role: 'chauffeur_principal');
      h.stubFeuilleDuJour(chauffeurId: 7);
      h.server.onJson('POST', '/checklists/', {'id': 1}, 201);
      await demarrer(tester, h);
      await seConnecter(tester);
      h.server.offline = true;
      h.connectivity.setOnline(false);
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('checklist-avant-depart')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('valider-checklist')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Checklist enregistrée sur le téléphone'), findsOneWidget);
      expect(h.server.requestsTo('POST', '/checklists/'), isEmpty);

      h.server.offline = false;
      h.connectivity.setOnline(true);
      await tester.pumpAndSettle();

      expect(h.server.requestsTo('POST', '/checklists/'), hasLength(6));
    });
  });
}
