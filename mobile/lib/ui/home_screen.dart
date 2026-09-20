import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../auth/auth_controller.dart';
import '../auth/roles.dart';
import '../sync/sync_service.dart';
import 'chauffeur_home.dart';
import 'generic_home.dart';
import 'guichetier_home.dart';
import 'sync_status_bar.dart';

/// Écran d'accueil : le contenu dépend du rôle de l'utilisateur connecté.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  Future<void> _logout(BuildContext context) async {
    final auth = context.read<AuthController>();
    final pending = context.read<SyncService>().pendingCount;
    if (pending > 0) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Se déconnecter ?'),
          content: Text(
            '$pending action(s) n\'ont pas encore été envoyées. Elles restent enregistrées '
            'sur ce téléphone et seront envoyées à votre prochaine connexion.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Se déconnecter'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    await auth.logout();
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthController>().user;
    if (user == null) return const SizedBox.shrink();

    final Widget body;
    if (Roles.chauffeurs.contains(user.role)) {
      body = ChauffeurHome(user: user);
    } else if (user.role == Roles.guichetier) {
      body = GuichetierHome(user: user);
    } else {
      body = GenericHome(user: user);
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Accueil'),
        actions: [
          IconButton(
            key: const Key('logout'),
            tooltip: 'Se déconnecter',
            icon: const Icon(Icons.logout),
            onPressed: () => _logout(context),
          ),
        ],
      ),
      body: Column(
        children: [
          const SyncStatusBar(),
          Expanded(child: body),
        ],
      ),
    );
  }
}
