import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../sync/sync_service.dart';
import 'pending_actions_screen.dart';

/// Bandeau d'état du réseau et de la synchronisation, affiché en haut de l'accueil.
class SyncStatusBar extends StatelessWidget {
  const SyncStatusBar({super.key});

  @override
  Widget build(BuildContext context) {
    final sync = context.watch<SyncService>();
    final scheme = Theme.of(context).colorScheme;

    final (Color background, Color foreground, IconData icon, String text) = switch (sync) {
      SyncService(:final rejectedCount) when rejectedCount > 0 => (
          scheme.errorContainer,
          scheme.onErrorContainer,
          Icons.error_outline,
          '$rejectedCount action(s) refusée(s) par le serveur : à revoir',
        ),
      SyncService(:final online, :final pendingCount) when !online => (
          scheme.tertiaryContainer,
          scheme.onTertiaryContainer,
          Icons.cloud_off,
          pendingCount > 0
              ? 'Hors ligne : $pendingCount action(s) en attente d\'envoi'
              : 'Hors ligne : vos actions seront enregistrées sur le téléphone',
        ),
      SyncService(:final pendingCount) when pendingCount > 0 => (
          scheme.secondaryContainer,
          scheme.onSecondaryContainer,
          Icons.sync,
          '$pendingCount action(s) en attente d\'envoi',
        ),
      _ => (
          scheme.primaryContainer,
          scheme.onPrimaryContainer,
          Icons.cloud_done_outlined,
          'Tout est synchronisé',
        ),
    };

    return Material(
      color: background,
      child: InkWell(
        key: const Key('sync-status-bar'),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute<void>(builder: (_) => const PendingActionsScreen()),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            children: [
              Icon(icon, color: foreground, size: 20),
              const SizedBox(width: 10),
              Expanded(child: Text(text, style: TextStyle(color: foreground))),
              if (sync.isSyncing)
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                Icon(Icons.chevron_right, color: foreground),
            ],
          ),
        ),
      ),
    );
  }
}
