import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../auth/auth_controller.dart';
import '../auth/code_court_controller.dart';

/// Saisie du code court : pour rouvrir l'application ([CodeCourtScreen.deverrouiller]) ou pour le choisir
/// ([CodeCourtScreen.creer] ; [obligatoire] quand la compagnie l'exige : on ne peut pas passer).
class CodeCourtScreen extends StatefulWidget {
  const CodeCourtScreen.deverrouiller({super.key})
      : creation = false,
        obligatoire = false;

  const CodeCourtScreen.creer({super.key, this.obligatoire = false}) : creation = true;

  final bool creation;
  final bool obligatoire;

  @override
  State<CodeCourtScreen> createState() => _CodeCourtScreenState();
}

class _CodeCourtScreenState extends State<CodeCourtScreen> {
  final _code = TextEditingController();
  final _confirmation = TextEditingController();
  bool _busy = false;
  String? _erreur;

  @override
  void dispose() {
    _code.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  Future<void> _valider() async {
    final controleur = context.read<CodeCourtController>();
    final code = _code.text;
    if (!CodeCourtController.formatValide.hasMatch(code)) {
      setState(() => _erreur = 'Le code court compte de 4 à 6 chiffres.');
      return;
    }
    setState(() {
      _busy = true;
      _erreur = null;
    });
    if (widget.creation) {
      if (_confirmation.text != code) {
        setState(() {
          _busy = false;
          _erreur = 'La confirmation ne correspond pas au code.';
        });
        return;
      }
      await controleur.definir(code);
      if (!mounted) return;
      if (Navigator.of(context).canPop()) Navigator.of(context).pop(true);
      return;
    }
    final bon = await controleur.deverrouiller(code);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _code.clear();
      if (!bon) {
        final restants = controleur.essaisRestants;
        _erreur = 'Code incorrect. Encore $restants essai${restants > 1 ? 's' : ''} avant le retour au mot de passe.';
      }
    });
  }

  Widget _champ(TextEditingController controleur, String etiquette, Key cle, {bool dernier = false}) => TextField(
        key: cle,
        controller: controleur,
        enabled: !_busy,
        autofocus: controleur == _code,
        obscureText: true,
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
        textInputAction: dernier ? TextInputAction.done : TextInputAction.next,
        onSubmitted: dernier ? (_) => _valider() : null,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 28, letterSpacing: 12),
        decoration: InputDecoration(labelText: etiquette, border: const OutlineInputBorder(), counterText: ''),
      );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final user = context.watch<AuthController>().user;
    final titre = widget.creation ? 'Choisissez votre code court' : 'Bonjour ${user?.displayName ?? ''}';
    final explication = widget.creation
        ? (widget.obligatoire
            ? 'Votre compagnie exige un code court (4 à 6 chiffres) pour rouvrir l\'application sans le mot de passe.'
            : 'De 4 à 6 chiffres : il rouvre l\'application sans le mot de passe, sur ce téléphone seulement.')
        : 'Saisissez votre code court pour continuer.';
    return Scaffold(
      appBar: widget.creation && !widget.obligatoire ? AppBar(title: const Text('Code court')) : null,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(Icons.pin_outlined, size: 64, color: theme.colorScheme.primary),
                  const SizedBox(height: 12),
                  Text(titre, textAlign: TextAlign.center, style: theme.textTheme.headlineSmall),
                  const SizedBox(height: 8),
                  Text(explication, textAlign: TextAlign.center),
                  const SizedBox(height: 24),
                  _champ(_code, widget.creation ? 'Code court' : 'Code', const Key('code-court'),
                      dernier: !widget.creation),
                  if (widget.creation) ...[
                    const SizedBox(height: 16),
                    _champ(_confirmation, 'Confirmation', const Key('code-court-confirmation'), dernier: true),
                  ],
                  if (_erreur != null) ...[
                    const SizedBox(height: 16),
                    Text(_erreur!, key: const Key('code-court-erreur'), style: TextStyle(color: theme.colorScheme.error)),
                  ],
                  const SizedBox(height: 24),
                  FilledButton(
                    key: const Key('code-court-valider'),
                    onPressed: _busy ? null : _valider,
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                    child: Text(widget.creation ? 'Enregistrer le code' : 'Ouvrir'),
                  ),
                  if (!widget.creation || widget.obligatoire) ...[
                    const SizedBox(height: 12),
                    TextButton(
                      key: const Key('code-court-oublie'),
                      onPressed: _busy
                          ? null
                          : () => widget.creation
                              ? context.read<AuthController>().logout()
                              : context.read<CodeCourtController>().oublie(),
                      child: Text(widget.creation ? 'Se déconnecter' : 'Code oublié : se reconnecter avec le mot de passe'),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
