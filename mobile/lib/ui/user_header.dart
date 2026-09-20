import 'package:flutter/material.dart';

import '../auth/app_user.dart';
import '../auth/roles.dart';

/// « Bonjour Prénom » + rôle et compagnie, en tête des écrans d'accueil.
class UserHeader extends StatelessWidget {
  const UserHeader({super.key, required this.user});

  final AppUser user;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final company = user.companyName;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Bonjour ${user.displayName}', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(
          company == null
              ? Roles.label(user.role)
              : '${Roles.label(user.role)} · $company',
          style: theme.textTheme.bodyMedium,
        ),
      ],
    );
  }
}
