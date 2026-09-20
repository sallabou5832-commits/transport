import 'package:flutter/material.dart';

import '../auth/app_user.dart';
import 'user_header.dart';
import 'vente_ticket_screen.dart';

/// Accueil du guichetier : accès direct à la vente d'un ticket.
class GuichetierHome extends StatelessWidget {
  const GuichetierHome({super.key, required this.user});

  final AppUser user;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        UserHeader(user: user),
        const SizedBox(height: 24),
        FilledButton.icon(
          key: const Key('vendre-ticket'),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const VenteTicketScreen()),
          ),
          icon: const Icon(Icons.confirmation_number_outlined, size: 32),
          label: const Text('Vendre un ticket'),
          style: FilledButton.styleFrom(
            minimumSize: const Size.fromHeight(88),
            textStyle: Theme.of(context).textTheme.titleLarge,
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'Sans réseau, la vente est enregistrée sur le téléphone et envoyée '
          'automatiquement dès que la connexion revient.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ],
    );
  }
}
