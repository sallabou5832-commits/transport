import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_exception.dart';
import '../auth/auth_controller.dart';
import '../auth/code_court_controller.dart';
import '../services.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _obscure = true;
  // « Rester connecté » : décoché à chaque ouverture, la session dure alors 1 jour comme avant.
  bool _resterConnecte = false;
  String _duree = 'deconnexion';
  String? _error;

  @override
  void initState() {
    super.initState();
    _error = context.read<CodeCourtController>().prendreAvis(); // après trop d'erreurs de code court
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.read<AuthController>().login(
            _username.text.trim(),
            _password.text,
            dureeSession: _resterConnecte ? _duree : null,
          );
      // Succès : l'application bascule seule sur l'écran d'accueil.
    } on ApiException catch (e) {
      _showError(e.status == 401 || e.status == 400
          ? 'Identifiant ou mot de passe incorrect.'
          : e.message);
    } on NetworkException {
      _showError('Impossible de joindre le serveur. Vérifiez votre connexion et réessayez.');
    }
    if (mounted) setState(() => _busy = false);
  }

  void _showError(String message) {
    if (mounted) setState(() => _error = message);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Icon(Icons.directions_bus_filled, size: 72, color: theme.colorScheme.primary),
                    const SizedBox(height: 12),
                    Text(
                      'Transport Coord',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Connectez-vous à votre espace',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 32),
                    TextFormField(
                      key: const Key('username'),
                      controller: _username,
                      enabled: !_busy,
                      autofillHints: const [AutofillHints.username],
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        labelText: 'Identifiant',
                        prefixIcon: Icon(Icons.person_outline),
                        border: OutlineInputBorder(),
                      ),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? 'Saisissez votre identifiant.' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      key: const Key('password'),
                      controller: _password,
                      enabled: !_busy,
                      obscureText: _obscure,
                      autofillHints: const [AutofillHints.password],
                      onFieldSubmitted: (_) => _submit(),
                      decoration: InputDecoration(
                        labelText: 'Mot de passe',
                        prefixIcon: const Icon(Icons.lock_outline),
                        border: const OutlineInputBorder(),
                        suffixIcon: IconButton(
                          tooltip: _obscure ? 'Afficher' : 'Masquer',
                          icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                          onPressed: () => setState(() => _obscure = !_obscure),
                        ),
                      ),
                      validator: (v) =>
                          (v == null || v.isEmpty) ? 'Saisissez votre mot de passe.' : null,
                    ),
                    const SizedBox(height: 8),
                    CheckboxListTile(
                      key: const Key('rester-connecte'),
                      value: _resterConnecte,
                      onChanged: _busy ? null : (v) => setState(() => _resterConnecte = v ?? false),
                      title: const Text('Rester connecté'),
                      subtitle: const Text('Sur votre téléphone personnel seulement.'),
                      controlAffinity: ListTileControlAffinity.leading,
                      contentPadding: EdgeInsets.zero,
                    ),
                    if (_resterConnecte)
                      DropdownButtonFormField<String>(
                        key: const Key('duree-session'),
                        initialValue: _duree,
                        decoration: const InputDecoration(labelText: 'Pendant', border: OutlineInputBorder()),
                        items: [
                          for (final duree in const ['semaine', 'mois', 'deconnexion'])
                            DropdownMenuItem(value: duree, child: Text(dureesSession[duree]!)),
                        ],
                        onChanged: _busy ? null : (v) => setState(() => _duree = v ?? _duree),
                      ),
                    if (_error != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        _error!,
                        key: const Key('login-error'),
                        style: TextStyle(color: theme.colorScheme.error),
                      ),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      key: const Key('login-button'),
                      onPressed: _busy ? null : _submit,
                      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                      child: _busy
                          ? const SizedBox(
                              height: 22,
                              width: 22,
                              child: CircularProgressIndicator(strokeWidth: 2.5),
                            )
                          : const Text('Se connecter'),
                    ),
                    if (kDebugMode) ...[
                      const SizedBox(height: 24),
                      Text(
                        'Serveur : ${context.read<AppServices>().api.baseUrl}',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
