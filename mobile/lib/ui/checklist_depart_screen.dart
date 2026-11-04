import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../data/ma_configuration.dart';
import '../services.dart';
import '../sync/action_handlers.dart';
import '../sync/sync_service.dart';
import '../voice/voice_form_session.dart';
import '../voice/voice_text.dart';
import 'voice_dictation_panel.dart';

const _etatOk = 'ok';
const _etatDefaut = 'defaut';

/// Items de la checklist avant-départ, dans l'ordre où on les demande — mêmes items
/// que le tableau de bord web (`frontend/src/pages/ChauffeurDashboard.jsx`,
/// `ITEMS_CHECKLIST`), pour que la checklist dise la même chose des deux côtés.
const checklistItems = ['pneus', 'freins', 'carburant', 'eclairage', 'direction', 'ceintures'];

const _libellesItems = {
  'pneus': 'Pneus',
  'freins': 'Freins',
  'carburant': 'Carburant',
  'eclairage': 'Éclairage',
  'direction': 'Direction',
  'ceintures': 'Ceintures',
};

/// Checklist avant-départ du chauffeur : un état (OK / Défaut) et un commentaire
/// facultatif par item, envoyés un à un au serveur (voir `ActionTypes.checklistDepart`).
/// Un défaut sur un item de sécurité bloque le véhicule côté serveur — l'écran ne fait
/// que transmettre ce que le chauffeur constate, il ne décide de rien lui-même.
class ChecklistDepartScreen extends StatefulWidget {
  const ChecklistDepartScreen({
    super.key,
    required this.feuilleId,
    required this.ligneNom,
    required this.immatriculation,
  });

  final int feuilleId;
  final String ligneNom;
  final String immatriculation;

  @override
  State<ChecklistDepartScreen> createState() => _ChecklistDepartScreenState();
}

class _ChecklistDepartScreenState extends State<ChecklistDepartScreen> {
  final Map<String, String> _etats = {for (final item in checklistItems) item: _etatOk};
  final Map<String, String> _commentaires = {for (final item in checklistItems) item: ''};
  final Map<String, TextEditingController> _commentaireControllers = {
    for (final item in checklistItems) item: TextEditingController(),
  };

  bool _busy = false;
  String? _error;

  // Dictée vocale : voir `_demarrerChecklistVocale`. Remplit les mêmes champs que la
  // saisie tactile (rien n'est envoyé sans passer par `_submit`).
  VoiceFormSession? _voiceSession;
  bool _voiceActive = false;
  String? _voiceStatus;

  @override
  void initState() {
    super.initState();
    // Mode vocal préféré (réglé par l'agent ou par son supérieur) : la dictée démarre d'elle-même, « Annuler » la coupe.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && context.read<MaConfiguration>().prefereVocal) _demarrerChecklistVocale();
    });
  }

  @override
  void dispose() {
    _voiceSession?.dispose();
    for (final controller in _commentaireControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  void _setEtat(String item, String etat) => setState(() {
        _etats[item] = etat;
        if (etat == _etatOk) {
          _commentaires[item] = '';
          _commentaireControllers[item]!.clear();
        }
      });

  void _setCommentaire(String item, String texte) {
    _commentaires[item] = texte;
    _commentaireControllers[item]!.text = texte;
  }

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });

    final sync = context.read<SyncService>();
    final result = await sync.submit(
      type: ActionTypes.checklistDepart,
      payload: {
        'feuille_de_route': widget.feuilleId,
        'items': [
          for (final item in checklistItems)
            {'item': item, 'etat': _etats[item], 'commentaire': _commentaires[item] ?? ''},
        ],
      },
    );
    if (!mounted) return;
    setState(() => _busy = false);

    final defauts = checklistItems.where((item) => _etats[item] == _etatDefaut).toList();
    switch (result.status) {
      case SubmitStatus.sent:
        _toast(
          defauts.isEmpty
              ? 'Checklist enregistrée, aucun défaut.'
              : 'Checklist enregistrée. Défaut signalé sur : '
                  '${defauts.map((i) => _libellesItems[i]).join(', ')}.',
        );
      case SubmitStatus.queued:
        _toast(
          'Checklist enregistrée sur le téléphone (${result.message}) '
          'Elle sera envoyée automatiquement au retour du réseau.',
        );
      case SubmitStatus.rejected:
        setState(() => _error = result.message ?? 'Checklist refusée par le serveur.');
    }
  }

  void _toast(String message) => ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message), duration: const Duration(seconds: 5)));

  /// Demande l'état de chaque item l'un après l'autre, lit un récapitulatif, puis
  /// valide comme le ferait le bouton tactile — seulement si l'utilisateur dit
  /// « confirmer ». Voir `VenteTicketScreen._demarrerVenteVocale` pour le même parcours
  /// côté vente de ticket, et le mode secours qu'il partage avec cet écran.
  Future<void> _demarrerChecklistVocale() async {
    if (_busy || _voiceActive) return;
    final session = context.read<AppServices>().creerSessionVocale();
    setState(() {
      _voiceActive = true;
      _voiceSession = session;
      _voiceStatus = 'Préparation de la reconnaissance vocale…';
    });

    var confirme = false;
    try {
      if (!await session.init()) {
        _toast('Reconnaissance vocale indisponible sur cet appareil. Continuez avec le clavier.');
        return;
      }
      if (!mounted) return;

      for (final item in checklistItems) {
        final label = _libellesItems[item] ?? item;
        setState(() => _voiceStatus = '$label : dites OK ou Défaut…');
        final reponse = await session.ask('$label. Dites OK, ou Défaut.');
        if (!mounted || reponse == null) return;
        final etat = parseEtatChecklist(reponse);
        if (etat == null) {
          // Ni « ok » ni « défaut » compris : par prudence on n'enregistre rien au
          // hasard, on repasse la main au clavier plutôt que de deviner.
          await session.say('Je n\'ai pas compris pour $label. Corrigez avec le clavier.');
          return;
        }
        setState(() => _etats[item] = etat);
        if (etat == _etatDefaut) {
          setState(() => _voiceStatus = 'Décrivez le problème sur $label…');
          final commentaire = await session.ask('Décrivez le problème sur $label.');
          if (!mounted) return;
          if (commentaire != null) {
            final texte = commentaire.length > 500 ? commentaire.substring(0, 500) : commentaire;
            setState(() {
              _commentaires[item] = texte;
              _commentaireControllers[item]!.text = texte;
            });
          }
        } else {
          setState(() {
            _commentaires[item] = '';
            _commentaireControllers[item]!.clear();
          });
        }
      }

      setState(() => _voiceStatus = 'Récapitulatif…');
      final recap = recapChecklistDepart(
        items: checklistItems,
        labels: _libellesItems,
        etats: _etats,
        commentaires: _commentaires,
      );
      final reponse = await session.ask(recap);
      if (!mounted) return;
      final intention = reponse == null ? VoiceIntent.inconnu : parseConfirmationIntent(reponse);
      if (intention == VoiceIntent.confirmer) {
        await session.say('Checklist en cours d\'enregistrement.');
        confirme = true;
      } else {
        await session.say('D\'accord, corrigez avec le clavier.');
      }
    } on Object {
      if (mounted) _toast('La reconnaissance vocale a rencontré un problème. Continuez avec le clavier.');
    } finally {
      await session.dispose();
      if (mounted) {
        setState(() {
          _voiceActive = false;
          _voiceSession = null;
          _voiceStatus = null;
        });
      }
    }
    if (confirme && mounted) await _submit();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Checklist avant-départ')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('${widget.ligneNom} · ${widget.immatriculation}', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          Text(
            'Un défaut sur un item de sécurité (pneus, freins, direction, éclairage, ceintures) '
            'empêche le véhicule de partir tant qu\'il n\'est pas réparé.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          VoiceDictationPanel(
            active: _voiceActive,
            status: _voiceStatus,
            enabled: !_busy,
            onStart: _demarrerChecklistVocale,
            onCancel: () => _voiceSession?.cancel(),
          ),
          const SizedBox(height: 16),
          for (final item in checklistItems) _ChecklistItemRow(
            key: ValueKey(item),
            label: _libellesItems[item] ?? item,
            etat: _etats[item]!,
            commentaireController: _commentaireControllers[item]!,
            enabled: !_busy,
            onEtatChanged: (etat) => _setEtat(item, etat),
            onCommentaireChanged: (texte) => _setCommentaire(item, texte),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Text(
              _error!,
              key: const Key('checklist-erreur'),
              style: TextStyle(color: theme.colorScheme.error),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton(
            key: const Key('valider-checklist'),
            onPressed: _busy ? null : _submit,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
            child: _busy
                ? const SizedBox(
                    height: 22,
                    width: 22,
                    child: CircularProgressIndicator(strokeWidth: 2.5),
                  )
                : const Text('Valider la checklist'),
          ),
        ],
      ),
    );
  }
}

class _ChecklistItemRow extends StatelessWidget {
  const _ChecklistItemRow({
    super.key,
    required this.label,
    required this.etat,
    required this.commentaireController,
    required this.enabled,
    required this.onEtatChanged,
    required this.onCommentaireChanged,
  });

  final String label;
  final String etat;
  final TextEditingController commentaireController;
  final bool enabled;
  final ValueChanged<String> onEtatChanged;
  final ValueChanged<String> onCommentaireChanged;

  @override
  Widget build(BuildContext context) {
    final enDefaut = etat == _etatDefaut;
    return Card(
      key: Key('checklist-item-${label.toLowerCase()}'),
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(label, style: Theme.of(context).textTheme.titleMedium)),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: _etatOk, label: Text('OK')),
                    ButtonSegment(value: _etatDefaut, label: Text('Défaut')),
                  ],
                  selected: {etat},
                  onSelectionChanged: enabled ? (s) => onEtatChanged(s.first) : null,
                ),
              ],
            ),
            if (enDefaut) ...[
              const SizedBox(height: 8),
              TextField(
                controller: commentaireController,
                enabled: enabled,
                onChanged: onCommentaireChanged,
                decoration: const InputDecoration(
                  labelText: 'Commentaire (optionnel)',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
