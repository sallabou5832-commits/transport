import 'package:flutter/material.dart';

/// La charte de l'application, la même que celle du site : orange, blanc et vert comme couleurs de référence, et une couleur par
/// pôle pour savoir d'un coup d'œil dans quel pôle on travaille (frontend/src/index.css, `[data-pole]`).
abstract final class Charte {
  static const vert = Color(0xFF00804F);
  static const orange = Color(0xFFF77F00);

  static const couleursDesPoles = {
    'direction': Color(0xFF7C3AED),
    'exploitation': Color(0xFF2563EB),
    'roulant': Color(0xFFDB2777),
    'technique': Color(0xFF475569),
    'supports': Color(0xFF0E7490),
    'plateforme': Color(0xFF1F2937),
  };

  /// Le pôle de chaque poste, le même rangement que le serveur (communication/poles.py).
  static const poleDuRole = {
    'pdg': 'direction',
    'secretaire_general': 'direction',
    'qhse': 'direction',
    'directeur_exploitation': 'exploitation',
    'chef_gare': 'exploitation',
    'chef_ligne': 'exploitation',
    'guichetier': 'exploitation',
    'bagagiste': 'exploitation',
    'chauffeur_principal': 'roulant',
    'chauffeur_relais': 'roulant',
    'controleur_ligne': 'roulant',
    'directeur_technique': 'technique',
    'magasinier': 'technique',
    'chef_atelier': 'technique',
    'mecanicien': 'technique',
    'drh': 'supports',
    'directeur_financier': 'supports',
    'responsable_juridique': 'supports',
    'superadmin': 'plateforme',
  };

  /// La couleur du pôle de ce poste ; l'orange de référence pour un poste inconnu.
  static Color couleurDuPole(String role) => couleursDesPoles[poleDuRole[role]] ?? orange;

  static ThemeData theme() => ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: vert, primary: vert, secondary: orange),
        useMaterial3: true,
        appBarTheme: const AppBarTheme(backgroundColor: vert, foregroundColor: Colors.white),
      );
}
