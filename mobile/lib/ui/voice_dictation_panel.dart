import 'package:flutter/material.dart';

/// Bouton « Remplir par la voix » et son état pendant la dictée, partagés par les
/// écrans qui offrent une commande vocale (vente de ticket, checklist avant-départ).
///
/// Purement visuel : ne connaît rien de la reconnaissance vocale elle-même, seulement
/// ce que l'écran appelant lui donne (en cours ou non, statut à afficher, activable ou
/// non). C'est l'écran qui décide quoi faire (`onStart`) et comment interrompre
/// (`onCancel`) — voir `VoiceFormSession`.
class VoiceDictationPanel extends StatelessWidget {
  const VoiceDictationPanel({
    super.key,
    required this.active,
    required this.status,
    required this.enabled,
    required this.onStart,
    required this.onCancel,
    this.disabledHint,
  });

  /// Une dictée est en cours (bouton remplacé par le statut + bouton d'annulation).
  final bool active;

  /// Étape en cours à afficher pendant la dictée (« Dites le nom du voyageur… »...).
  final String? status;

  /// Faux si la dictée ne peut pas démarrer maintenant (formulaire déjà en cours
  /// d'envoi, ou pré-requis manquant — voir [disabledHint]).
  final bool enabled;

  final VoidCallback onStart;
  final VoidCallback onCancel;

  /// Motif affiché quand [enabled] est faux (ex. « Choisissez d'abord un départ. »).
  final String? disabledHint;

  @override
  Widget build(BuildContext context) {
    if (active) {
      return Card(
        key: const Key('voix-en-cours'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              const SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(strokeWidth: 2.5),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Text(status ?? 'Dictée en cours…', key: const Key('voix-statut')),
              ),
              TextButton(
                key: const Key('voix-annuler'),
                onPressed: onCancel,
                child: const Text('Annuler'),
              ),
            ],
          ),
        ),
      );
    }
    return OutlinedButton.icon(
      key: const Key('voix-demarrer'),
      onPressed: enabled ? onStart : null,
      icon: const Icon(Icons.mic_none),
      label: Text(disabledHint == null || enabled ? 'Remplir par la voix' : disabledHint!),
    );
  }
}
