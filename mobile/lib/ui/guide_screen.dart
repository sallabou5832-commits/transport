import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_exception.dart';
import '../auth/auth_controller.dart';
import '../data/guide.dart';
import '../data/loaded.dart';
import '../services.dart';
import 'formatters.dart';

/// Le guide d'utilisation : la fiche de chaque poste, rangée par pôle — sa mission, ses écrans, ses gestes pas à pas dans l'ordre
/// d'une journée et les postes avec qui il se coordonne. La fiche de l'agent s'ouvre d'abord ; il peut lire celle de tout poste.
/// Gardé sur le téléphone, il se relit sans réseau.
class GuideScreen extends StatefulWidget {
  const GuideScreen({super.key});

  @override
  State<GuideScreen> createState() => _GuideScreenState();
}

class _GuideScreenState extends State<GuideScreen> {
  Loaded<Guide>? _guide;
  String? _erreur;
  String? _poste;

  @override
  void initState() {
    super.initState();
    _charger();
  }

  Future<void> _charger() async {
    final user = context.read<AuthController>().user;
    if (user == null) return;
    Loaded<Guide>? guide;
    String? erreur;
    try {
      guide = await context.read<AppServices>().guides.charger(user);
    } on NoCachedDataException {
      erreur = 'Pas de connexion, et le guide n\'a pas encore été lu sur ce téléphone.';
    } on ApiException catch (e) {
      erreur = e.message;
    }
    if (!mounted) return;
    setState(() {
      _guide = guide;
      _erreur = erreur;
      _poste ??= guide?.data.posteInitial;
    });
  }

  @override
  Widget build(BuildContext context) {
    final charge = _guide;
    return Scaffold(
      appBar: AppBar(title: const Text('Guide')),
      body: charge == null
          ? Center(
              child: _erreur == null
                  ? const CircularProgressIndicator()
                  : Padding(padding: const EdgeInsets.all(24), child: Text(_erreur!, key: const Key('guide-erreur'))),
            )
          : _contenu(context, charge),
    );
  }

  Widget _contenu(BuildContext context, Loaded<Guide> charge) {
    final guide = charge.data;
    final poste = _poste!;
    final pole = guide.poleDe(poste);
    final fiche = guide.fiche(poste);
    final theme = Theme.of(context);
    return RefreshIndicator(
      onRefresh: _charger,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (charge.fromCache)
            Chip(
              key: const Key('guide-hors-ligne'),
              avatar: const Icon(Icons.cloud_off, size: 18),
              label: Text('Hors ligne : guide du ${formatDateHeure(charge.savedAt!)}'),
            ),
          DropdownButtonFormField<String>(
            // Les clés suivent la fiche ouverte : les listes se reconstruisent quand « Avec » mène à un autre poste.
            key: Key('guide-pole-${pole.code}'),
            initialValue: pole.code,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Pôle'),
            items: [
              for (final p in guide.poles)
                DropdownMenuItem(value: p.code, child: Text(p.code == guide.monPole ? '${p.libelle} (votre pôle)' : p.libelle)),
            ],
            onChanged: (code) {
              final choisi = guide.poles.firstWhere((p) => p.code == code);
              final mien = choisi.fiches.any((f) => f.poste == guide.monPoste);
              setState(() => _poste = mien ? guide.monPoste : choisi.fiches.first.poste);
            },
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            key: Key('guide-poste-$poste'),
            initialValue: poste,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Poste'),
            items: [for (final f in pole.fiches) DropdownMenuItem(value: f.poste, child: Text(f.libelle))],
            onChanged: (code) => setState(() => _poste = code),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: Text(fiche.libelle, key: const Key('guide-fiche-titre'), style: theme.textTheme.headlineSmall)),
              if (fiche.poste == guide.monPoste) const Chip(label: Text('Votre poste')),
            ],
          ),
          const SizedBox(height: 8),
          Text(fiche.mission),
          if (fiche.reglePar.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Poste réglé par : ${fiche.reglePar.join(', ')}.', style: theme.textTheme.bodySmall),
          ],
          if (fiche.regle.isNotEmpty)
            Text('Règle les postes : ${fiche.regle.join(', ')}.', style: theme.textTheme.bodySmall),
          ..._sections(context, guide, fiche, onPoste: (code) => setState(() => _poste = code)),
          if (fiche.reglement.isNotEmpty) ...[
            _Titre('Ce que le règlement intérieur de votre compagnie permet à ce poste'),
            for (final regle in fiche.reglement)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(regle.permis ? Icons.check_circle_outline : Icons.block, color: regle.permis ? Colors.green : Colors.orange),
                title: Text(regle.libelle),
                subtitle: Text(
                  '${regle.permis ? 'Permis' : 'Non permis'} — décidé par : ${regle.decide == 'PDG' ? 'PDG' : '${regle.decide} ou PDG'}',
                ),
              ),
          ],
          const SizedBox(height: 16),
          Card(
            child: ExpansionTile(
              key: const Key('guide-communs'),
              title: const Text('Pour tous les postes'),
              subtitle: const Text('Connexion, alertes, congés, doléances, paramètres'),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              expandedCrossAxisAlignment: CrossAxisAlignment.start,
              children: _sections(context, guide, guide.communs, onPoste: (code) => setState(() => _poste = code)),
            ),
          ),
        ],
      ),
    );
  }

  /// Écrans, pas à pas rangé par moment de la journée, contacts et astuces d'une fiche (ou de ce qui vaut pour tous).
  List<Widget> _sections(BuildContext context, Guide guide, GuideFiche fiche, {required ValueChanged<String> onPoste}) {
    final theme = Theme.of(context);
    return [
      if (fiche.ecrans.isNotEmpty) ...[
        _Titre('Écrans'),
        for (final ecran in fiche.ecrans)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(ecran.mobile ? Icons.smartphone : Icons.desktop_windows_outlined),
            title: Text(ecran.titre),
            subtitle: Text(ecran.mobile ? ecran.usage : 'Sur ordinateur. ${ecran.usage}'),
          ),
      ],
      _Titre('Pas à pas'),
      for (final moment in guide.moments.entries)
        if (fiche.taches.any((t) => t.moment == moment.key)) ...[
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 4),
            child: Text(moment.value.toUpperCase(), style: theme.textTheme.labelMedium),
          ),
          for (final tache in fiche.taches.where((t) => t.moment == moment.key))
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(tache.titre, style: theme.textTheme.titleMedium),
                    if (tache.permise != null)
                      Text(
                        tache.permise! ? 'Permis par votre règlement intérieur' : 'Non permis par votre règlement intérieur',
                        style: theme.textTheme.bodySmall?.copyWith(color: tache.permise! ? Colors.green : Colors.orange),
                      ),
                    const SizedBox(height: 4),
                    for (final (rang, etape) in tache.etapes.indexed) Text('${rang + 1}. $etape'),
                    if (tache.avec.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 6,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          const Text('Avec :'),
                          for (final avec in tache.avec.entries)
                            ActionChip(
                              key: Key('guide-avec-${avec.key}'),
                              label: Text(avec.value),
                              onPressed: () => onPoste(avec.key),
                            ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
        ],
      if (fiche.contacts.isNotEmpty) ...[
        _Titre('À qui vous adresser'),
        for (final ligne in fiche.contacts) Text('• $ligne'),
      ],
      if (fiche.astuces.isNotEmpty) ...[
        _Titre('Bon à savoir'),
        for (final ligne in fiche.astuces) Text('• $ligne'),
      ],
    ];
  }
}

class _Titre extends StatelessWidget {
  const _Titre(this.texte);

  final String texte;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 16, bottom: 4),
        child: Text(texte, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
      );
}
