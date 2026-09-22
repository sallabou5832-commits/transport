import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../sync/action_handlers.dart';
import '../sync/pending_action.dart';
import '../sync/sync_service.dart';
import 'formatters.dart';

/// Actions faites sur cet appareil et pas encore acceptées par le serveur.
class PendingActionsScreen extends StatelessWidget {
  const PendingActionsScreen({super.key});

  static String _title(PendingAction action) => switch (action.type) {
        ActionTypes.venteTicket => 'Vente de ticket : ${action.payload['passager_nom']}',
        ActionTypes.checklistDepart => 'Checklist avant-départ',
        _ => action.type,
      };

  @override
  Widget build(BuildContext context) {
    final sync = context.watch<SyncService>();
    final actions = sync.actions();
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Synchronisation')),
      body: Column(
        children: [
          Expanded(
            child: actions.isEmpty
                ? const Center(child: Text('Aucune action en attente.'))
                : ListView.separated(
                    itemCount: actions.length,
                    separatorBuilder: (_, _) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final action = actions[index];
                      final rejected = action.status == ActionStatus.rejected;
                      return ListTile(
                        leading: Icon(
                          rejected ? Icons.error_outline : Icons.schedule,
                          color: rejected ? scheme.error : scheme.secondary,
                        ),
                        title: Text(_title(action)),
                        subtitle: Text(
                          rejected
                              ? 'Refusée : ${action.lastError ?? 'erreur inconnue'}'
                                  '${action.type == ActionTypes.venteTicket ? '\nLe voyageur a peut-être déjà payé : remboursez-le ou proposez-lui un autre départ.' : ''}'
                              : 'Faite le ${formatDateHeure(action.createdAt)}, en attente d\'envoi',
                        ),
                        isThreeLine: rejected,
                        trailing: rejected
                            ? IconButton(
                                tooltip: 'Supprimer',
                                icon: const Icon(Icons.delete_outline),
                                onPressed: () => sync.discard(action.id),
                              )
                            : null,
                      );
                    },
                  ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: FilledButton.icon(
                key: const Key('sync-now'),
                onPressed: sync.isSyncing ? null : () => sync.syncNow(),
                icon: const Icon(Icons.sync),
                label: const Text('Synchroniser maintenant'),
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
