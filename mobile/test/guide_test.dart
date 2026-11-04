import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/app_helpers.dart';

Map<String, dynamic> _tache(String titre, String moment, {Map<String, String> avec = const {}, bool? permise}) => {
      'titre': titre,
      'etapes': ['Première étape de $titre.'],
      'moment': moment,
      'moment_libelle': moment,
      'avec': [for (final e in avec.entries) {'poste': e.key, 'libelle': e.value}],
      'regle': permise == null ? null : 'drh_gere_les_comptes',
      'permise': permise,
    };

Map<String, dynamic> _fiche(String poste, String libelle, List<Map<String, dynamic>> taches) => {
      'poste': poste,
      'libelle': libelle,
      'mission': 'Mission du poste $libelle.',
      'ecrans': [
        {'support': 'site', 'chemin': '/dashboard/x', 'titre': 'Tableau de bord — $libelle', 'usage': 'Le tableau.'},
      ],
      'taches': taches,
      'contacts': ['Contact de $libelle.'],
      'astuces': <String>[],
      'regle_par': ['PDG'],
      'regle': <String>[],
      'reglement': <Map<String, dynamic>>[],
    };

/// Une réponse de `/guides/` réduite à deux pôles.
Map<String, dynamic> guideJson() => {
      'mon_poste': 'guichetier',
      'mon_pole': 'exploitation',
      'moments': [
        {'code': 'debut', 'libelle': 'En début de journée'},
        {'code': 'journee', 'libelle': 'Au fil de la journée'},
        {'code': 'fin', 'libelle': 'En fin de journée'},
      ],
      'communs': {
        'ecrans': <Map<String, dynamic>>[],
        'taches': [_tache('Lire ses alertes', 'debut')],
        'contacts': <String>[],
        'astuces': <String>[],
      },
      'poles': [
        {
          'pole': 'direction',
          'libelle': 'Direction Générale',
          'postes': [_fiche('pdg', 'PDG', [_tache('Décider', 'journee')])],
        },
        {
          'pole': 'exploitation',
          'libelle': 'Exploitation & Réseau',
          'postes': [
            _fiche('chef_gare', 'Chef de gare', [_tache('Clôturer la caisse d\'un guichetier', 'fin', avec: {'guichetier': 'Guichetier'})]),
            _fiche('guichetier', 'Guichetier', [
              _tache('Vendre un ticket', 'journee'),
              _tache('Clôturer sa caisse', 'fin', avec: {'chef_gare': 'Chef de gare'}),
            ]),
          ],
        },
      ],
    };

/// Le guide d'utilisation : la fiche de l'agent s'ouvre d'abord, « Avec » mène à la fiche du poste avec qui il se coordonne,
/// et le guide déjà lu se relit sans réseau.
void main() {
  Future<void> ouvrirGuide(WidgetTester tester) async {
    await tester.tap(find.byKey(const Key('guide')));
    await tester.pumpAndSettle();
  }

  String titreAffiche(WidgetTester tester) => tester.widget<Text>(find.byKey(const Key('guide-fiche-titre'))).data!;

  appTest('la fiche de l\'agent s\'ouvre d\'abord, rangée par moment de la journée', (tester, h) async {
    h.stubLogin();
    h.server.onJson('GET', '/guides/', guideJson());
    await demarrer(tester, h);
    await seConnecter(tester);

    await ouvrirGuide(tester);

    expect(titreAffiche(tester), 'Guichetier');
    expect(find.text('Votre poste'), findsOneWidget);
    expect(find.text('Exploitation & Réseau (votre pôle)'), findsOneWidget);
    expect(find.text('AU FIL DE LA JOURNÉE'), findsOneWidget);
    expect(find.text('EN FIN DE JOURNÉE'), findsOneWidget);
    expect(find.text('Vendre un ticket'), findsOneWidget);
  });

  appTest('« Avec » mène à la fiche du poste avec qui le geste se coordonne', (tester, h) async {
    h.stubLogin();
    h.server.onJson('GET', '/guides/', guideJson());
    await demarrer(tester, h);
    await seConnecter(tester);
    await ouvrirGuide(tester);

    await tester.tap(find.byKey(const Key('guide-avec-chef_gare')));
    await tester.pumpAndSettle();

    expect(titreAffiche(tester), 'Chef de gare');
    expect(find.text('Votre poste'), findsNothing);
    expect(find.byKey(const Key('guide-avec-guichetier')), findsOneWidget); // le passage de relais, vu de l'autre côté
  });

  appTest('on lit la fiche de tout poste, d\'un autre pôle aussi', (tester, h) async {
    h.stubLogin();
    h.server.onJson('GET', '/guides/', guideJson());
    await demarrer(tester, h);
    await seConnecter(tester);
    await ouvrirGuide(tester);

    await tester.tap(find.byKey(const Key('guide-pole-exploitation')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Direction Générale').last);
    await tester.pumpAndSettle();

    expect(titreAffiche(tester), 'PDG');
  });

  appTest('le guide déjà lu se relit sans réseau', (tester, h) async {
    h.stubLogin();
    h.server.onJson('GET', '/guides/', guideJson());
    await demarrer(tester, h);
    await seConnecter(tester);
    await ouvrirGuide(tester);
    await retour(tester);

    h.server.offline = true;
    await ouvrirGuide(tester);

    expect(titreAffiche(tester), 'Guichetier');
    expect(find.byKey(const Key('guide-hors-ligne')), findsOneWidget);
  });

  appTest('sans réseau ni guide déjà lu, l\'écran le dit', (tester, h) async {
    h.stubLogin();
    await demarrer(tester, h);
    await seConnecter(tester);

    h.server.offline = true;
    await ouvrirGuide(tester);

    expect(find.byKey(const Key('guide-erreur')), findsOneWidget);
  });
}
