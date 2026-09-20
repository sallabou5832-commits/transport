import 'package:flutter/material.dart';

import '../auth/app_user.dart';
import '../auth/roles.dart';
import 'user_header.dart';

/// Accueil des rôles qui n'ont pas (encore) d'écran dédié dans l'application mobile.
class GenericHome extends StatelessWidget {
  const GenericHome({super.key, required this.user});

  final AppUser user;

  @override
  Widget build(BuildContext context) {
    final terrain = Roles.terrain.contains(user.role);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        UserHeader(user: user),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Icon(terrain ? Icons.construction : Icons.desktop_windows_outlined, size: 32),
                const SizedBox(width: 16),
                Expanded(
                  child: Text(
                    terrain
                        ? 'Votre espace mobile arrive bientôt.'
                        : 'Votre poste s\'utilise sur ordinateur : connectez-vous à '
                            'l\'application web.',
                    key: const Key('generic-message'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
