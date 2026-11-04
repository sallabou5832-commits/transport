import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../auth/auth_controller.dart';
import '../auth/roles.dart';
import '../data/quota_service.dart';
import '../services.dart';
import '../sync/sync_service.dart';
import 'charte.dart';
import 'chauffeur_home.dart';
import 'generic_home.dart';
import 'guichetier_home.dart';
import 'guide_screen.dart';
import 'mes_parametres_screen.dart';
import 'sync_status_bar.dart';

/// Écran d'accueil : le contenu dépend du rôle de l'utilisateur connecté.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  Future<void> _logout(BuildContext context) async {
    final auth = context.read<AuthController>();
    final quota = context.read<QuotaService>();
    final pending = context.read<SyncService>().pendingCount;
    if (pending > 0) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Se déconnecter ?'),
          content: Text(
            "$pending action(s) n'ont pas encore été envoyées. Elles restent enregistrées "
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
    // Rend les places réservées aux autres guichets (sauf s'il reste des ventes à envoyer,
    // qui en ont besoin). Doit se faire avant la déconnexion, tant que le jeton existe.
    // Au mieux et sans faire attendre : si le serveur est lent, les places expireront d'elles-mêmes.
    await quota.release().timeout(const Duration(seconds: 4), onTimeout: () {});
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
        // Le liseré de la couleur du pôle de l'agent, comme sur le site.
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: Container(key: const Key('lisere-pole'), height: 4, color: Charte.couleurDuPole(user.role)),
        ),
        actions: [
          IconButton(
            key: const Key('guide'),
            tooltip: 'Guide',
            icon: const Icon(Icons.menu_book_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const GuideScreen()),
            ),
          ),
          IconButton(
            key: const Key('mes-parametres'),
            tooltip: 'Mes paramètres',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const MesParametresScreen()),
            ),
          ),
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
          if (context.read<AppServices>().store.wasReset) const _LocalDataResetNotice(),
          const SyncStatusBar(),
          Expanded(child: body),
        ],
      ),
    );
  }
}

/// Prévient que des données locales illisibles ont été effacées (clé de chiffrement perdue,
/// fichier corrompu) : des ventes hors ligne en attente ont pu être perdues.
class _LocalDataResetNotice extends StatefulWidget {
  const _LocalDataResetNotice();

  @override
  State<_LocalDataResetNotice> createState() => _LocalDataResetNoticeState();
}

class _LocalDataResetNoticeState extends State<_LocalDataResetNotice> {
  bool _dismissed = false;

  @override
  Widget build(BuildContext context) {
    if (_dismissed) return const SizedBox.shrink();
    final scheme = Theme.of(context).colorScheme;
    return MaterialBanner(
      key: const Key('donnees-locales-effacees'),
      backgroundColor: scheme.errorContainer,
      leading: Icon(Icons.warning_amber_rounded, color: scheme.onErrorContainer),
      content: Text(
        'Les données enregistrées sur ce téléphone étaient illisibles et ont été effacées. '
        "Si des ventes hors ligne étaient en attente, signalez-le à votre chef de gare "
        'avant de continuer.',
        style: TextStyle(color: scheme.onErrorContainer),
      ),
      actions: [
        TextButton(
          onPressed: () => setState(() => _dismissed = true),
          child: const Text('Compris'),
        ),
      ],
    );
  }
}
