import 'package:flutter/material.dart';

import 'package:provider/provider.dart';

import '../api/api_exception.dart';
import '../auth/app_user.dart';
import '../data/feuille_repository.dart';
import '../data/loaded.dart';
import '../services.dart';
import 'formatters.dart';
import 'user_header.dart';

/// Accueil du chauffeur : sa feuille de route du jour.
class ChauffeurHome extends StatefulWidget {
  const ChauffeurHome({super.key, required this.user});

  final AppUser user;

  @override
  State<ChauffeurHome> createState() => _ChauffeurHomeState();
}

class _ChauffeurHomeState extends State<ChauffeurHome> {
  bool _loading = true;
  String? _error;
  Loaded<FeuilleDuJour?>? _result;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final repository = context.read<AppServices>().feuilles;
    Loaded<FeuilleDuJour?>? result;
    String? error;
    try {
      result = await repository.loadToday(widget.user);
    } on NoCachedDataException {
      error = 'Pas de connexion, et aucune feuille de route n\'est enregistrée sur ce téléphone.';
    } on ApiException catch (e) {
      error = e.message;
    }
    if (!mounted) return;
    setState(() {
      _result = result;
      _error = error;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          UserHeader(user: widget.user),
          const SizedBox(height: 20),
          Text('Feuille de route du jour', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          if (_loading && _result == null)
            const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()))
          else if (_error != null)
            _Message(key: const Key('feuille-erreur'), icon: Icons.cloud_off, text: _error!)
          else if (_result?.data == null)
            const _Message(
              key: Key('feuille-vide'),
              icon: Icons.event_available,
              text: 'Aucune feuille de route pour aujourd\'hui.',
            )
          else
            _FeuilleCard(loaded: _result!),
        ],
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({super.key, required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Icon(icon, size: 32),
              const SizedBox(width: 16),
              Expanded(child: Text(text)),
            ],
          ),
        ),
      );
}

class _FeuilleCard extends StatelessWidget {
  const _FeuilleCard({required this.loaded});

  final Loaded<FeuilleDuJour?> loaded;

  @override
  Widget build(BuildContext context) {
    final feuille = loaded.data!;
    final theme = Theme.of(context);
    return Card(
      key: const Key('feuille-card'),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (loaded.fromCache) ...[
              Chip(
                avatar: const Icon(Icons.cloud_off, size: 18),
                label: Text('Hors ligne : données du ${formatDateHeure(loaded.savedAt!)}'),
              ),
              const SizedBox(height: 12),
            ],
            Text(feuille.ligneNom, style: theme.textTheme.headlineSmall),
            const SizedBox(height: 16),
            _Row(icon: Icons.schedule, label: 'Départ prévu', value: formatHeure(feuille.heureDepartPrevue)),
            if (feuille.heureArriveePrevue != null)
              _Row(
                icon: Icons.flag_outlined,
                label: 'Arrivée prévue',
                value: formatHeure(feuille.heureArriveePrevue!),
              ),
            _Row(icon: Icons.directions_bus, label: 'Véhicule', value: feuille.immatriculation),
            _Row(
              icon: feuille.aDemarre ? Icons.play_circle_outline : Icons.pause_circle_outline,
              label: 'Statut',
              value: feuille.aDemarre
                  ? 'Parti à ${formatHeure(feuille.heureDepartReelle!)}'
                  : 'Pas encore parti',
            ),
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            Icon(icon, size: 22),
            const SizedBox(width: 12),
            Text('$label : ', style: Theme.of(context).textTheme.bodyLarge),
            Expanded(
              child: Text(
                value,
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      );
}
