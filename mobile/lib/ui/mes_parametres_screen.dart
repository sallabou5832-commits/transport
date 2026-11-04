import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_exception.dart';
import '../auth/auth_controller.dart';
import '../auth/code_court_controller.dart';
import '../data/ma_configuration.dart';
import 'code_court_screen.dart';
import 'formatters.dart';

/// Mes paramètres sur le téléphone : code court, mot de passe, session de cet appareil.
class MesParametresScreen extends StatelessWidget {
  const MesParametresScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mes paramètres')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          _CodeCourt(),
          SizedBox(height: 16),
          _ModeVocal(),
          SizedBox(height: 16),
          _MotDePasse(),
          SizedBox(height: 16),
          _Session(),
        ],
      ),
    );
  }
}

class _CodeCourt extends StatelessWidget {
  const _CodeCourt();

  Future<void> _choisir(BuildContext context) async {
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const CodeCourtScreen.creer()),
    );
    if (ok == true && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Code court enregistré.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final code = context.watch<CodeCourtController>();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Code court', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              code.defini
                  ? 'Actif : il est demandé à l\'ouverture et après 5 minutes en arrière-plan.'
                  : 'Aucun : l\'application s\'ouvre sans code tant que la session dure.',
              key: const Key('code-court-etat'),
            ),
            if (code.exige) ...[
              const SizedBox(height: 4),
              const Text('Exigé par votre compagnie.'),
            ],
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.tonal(
                  key: const Key('code-court-choisir'),
                  onPressed: () => _choisir(context),
                  child: Text(code.defini ? 'Changer le code' : 'Choisir un code court'),
                ),
                if (code.defini && !code.exige)
                  TextButton(
                    key: const Key('code-court-retirer'),
                    onPressed: () => code.retirer(),
                    child: const Text('Retirer le code'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Écran imposé tant que le mot de passe est provisoire : le serveur refuse tout le reste.
class MotDePasseProvisoireScreen extends StatelessWidget {
  const MotDePasseProvisoireScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Choisissez votre mot de passe'),
        actions: [
          IconButton(
            key: const Key('logout'),
            tooltip: 'Se déconnecter',
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthController>().logout(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          Text(
            "Votre mot de passe est provisoire. Choisissez le vôtre pour accéder à votre espace : celui qui vous l'a remis "
            'ne le connaîtra pas.',
            key: Key('mdp-provisoire'),
          ),
          SizedBox(height: 16),
          _MotDePasse(provisoire: true),
        ],
      ),
    );
  }
}

/// Mode vocal : l'agent choisit lui-même (sauf si son supérieur l'a imposé) ; préféré, la dictée démarre d'elle-même dans la
/// vente de ticket et la checklist avant-départ.
class _ModeVocal extends StatefulWidget {
  const _ModeVocal();

  @override
  State<_ModeVocal> createState() => _ModeVocalState();
}

class _ModeVocalState extends State<_ModeVocal> {
  static const _choix = {'suivre': 'Comme réglé par mon supérieur', 'oui': 'Oui, je préfère dicter', 'non': 'Non'};

  String? _valeur; // `null` tant que le choix enregistré n'est pas lu
  bool _busy = false;
  String? _erreur;

  @override
  void initState() {
    super.initState();
    _lire();
  }

  static String _versCle(bool? choix) => choix == null ? 'suivre' : (choix ? 'oui' : 'non');

  Future<void> _lire() async {
    try {
      final choix = await context.read<MaConfiguration>().choixPersonnel();
      if (mounted) setState(() => _valeur = _versCle(choix));
    } on Object {
      if (mounted) setState(() => _erreur = 'Choix indisponible hors ligne.');
    }
  }

  Future<void> _choisir(String cle) async {
    final configuration = context.read<MaConfiguration>();
    setState(() {
      _busy = true;
      _erreur = null;
    });
    try {
      await configuration.choisirModeVocal(cle == 'suivre' ? null : cle == 'oui');
      if (mounted) setState(() => _valeur = cle);
    } on ApiException catch (e) {
      if (mounted) setState(() => _erreur = e.message);
    } on NetworkException {
      if (mounted) setState(() => _erreur = 'Impossible de joindre le serveur : réessayez une fois connecté.');
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final configuration = context.watch<MaConfiguration>();
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Mode vocal', style: theme.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              configuration.prefereVocal
                  ? "Actif : la dictée démarre d'elle-même (vente de ticket, checklist)."
                  : 'Inactif : la dictée se lance avec le bouton « Remplir par la voix ».',
              key: const Key('mode-vocal-etat'),
            ),
            if (configuration.vocalImpose)
              const Padding(padding: EdgeInsets.only(top: 4), child: Text('Fixé par votre supérieur.'))
            else if (_valeur != null)
              RadioGroup<String>(
                groupValue: _valeur,
                onChanged: (cle) => _busy || cle == null ? null : _choisir(cle),
                child: Column(
                  children: [
                    for (final entree in _choix.entries)
                      RadioListTile<String>(
                        key: Key('mode-vocal-${entree.key}'),
                        value: entree.key,
                        title: Text(entree.value),
                        contentPadding: EdgeInsets.zero,
                        enabled: !_busy,
                      ),
                  ],
                ),
              ),
            if (_erreur != null) Text(_erreur!, style: TextStyle(color: theme.colorScheme.error)),
          ],
        ),
      ),
    );
  }
}

class _MotDePasse extends StatefulWidget {
  const _MotDePasse({this.provisoire = false});

  final bool provisoire;

  @override
  State<_MotDePasse> createState() => _MotDePasseState();
}

class _MotDePasseState extends State<_MotDePasse> {
  final _formKey = GlobalKey<FormState>();
  final _ancien = TextEditingController();
  final _nouveau = TextEditingController();
  final _confirmation = TextEditingController();
  bool _busy = false;
  String? _message;
  bool _erreur = false;

  @override
  void dispose() {
    _ancien.dispose();
    _nouveau.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  Future<void> _changer() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await context.read<AuthController>().changerMotDePasse(_ancien.text, _nouveau.text);
      _ancien.clear();
      _nouveau.clear();
      _confirmation.clear();
      _afficher('Mot de passe changé. Vos autres appareils devront se reconnecter.', erreur: false);
    } on ApiException catch (e) {
      _afficher(e.message, erreur: true);
    } on NetworkException {
      _afficher('Impossible de joindre le serveur : réessayez une fois connecté.', erreur: true);
    }
  }

  void _afficher(String message, {required bool erreur}) {
    if (!mounted) return;
    setState(() {
      _busy = false;
      _message = message;
      _erreur = erreur;
    });
  }

  TextFormField _champ(TextEditingController controleur, String etiquette, Key cle, {String? Function(String?)? validator}) =>
      TextFormField(
        key: cle,
        controller: controleur,
        enabled: !_busy,
        obscureText: true,
        decoration: InputDecoration(labelText: etiquette, border: const OutlineInputBorder()),
        validator: validator ?? (v) => (v == null || v.isEmpty) ? 'Obligatoire.' : null,
      );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Mot de passe', style: theme.textTheme.titleMedium),
              const SizedBox(height: 12),
              _champ(_ancien, widget.provisoire ? 'Mot de passe provisoire' : 'Mot de passe actuel', const Key('mdp-ancien')),
              const SizedBox(height: 12),
              _champ(
                _nouveau,
                'Nouveau mot de passe',
                const Key('mdp-nouveau'),
                validator: (v) => (v == null || v.length < 8) ? '8 caractères au moins.' : null,
              ),
              const SizedBox(height: 12),
              _champ(
                _confirmation,
                'Confirmation',
                const Key('mdp-confirmation'),
                validator: (v) => v != _nouveau.text ? 'La confirmation ne correspond pas.' : null,
              ),
              if (_message != null) ...[
                const SizedBox(height: 12),
                Text(
                  _message!,
                  key: const Key('mdp-message'),
                  style: TextStyle(color: _erreur ? theme.colorScheme.error : theme.colorScheme.primary),
                ),
              ],
              const SizedBox(height: 12),
              FilledButton(
                key: const Key('mdp-changer'),
                onPressed: _busy ? null : _changer,
                child: const Text('Changer le mot de passe'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Session extends StatefulWidget {
  const _Session();

  @override
  State<_Session> createState() => _SessionState();
}

class _SessionState extends State<_Session> {
  late Future<SessionMobile?> _session = context.read<AuthController>().session();
  bool _busy = false;

  Future<void> _fermerLesAutres() async {
    final messager = ScaffoldMessenger.of(context);
    final auth = context.read<AuthController>();
    setState(() => _busy = true);
    String message;
    try {
      await auth.fermerAutresSessions();
      message = 'Vos autres appareils sont déconnectés.';
    } on ApiException catch (e) {
      message = e.message;
    } on NetworkException {
      message = 'Impossible de joindre le serveur : réessayez une fois connecté.';
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _session = auth.session();
    });
    messager.showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Session', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            FutureBuilder<SessionMobile?>(
              future: _session,
              builder: (context, instantane) {
                final session = instantane.data;
                if (session == null) return const SizedBox.shrink();
                return Text(
                  'Ce téléphone reste connecté jusqu\'au ${formatDateHeure(session.expireLe)} '
                  '(${dureesSession[session.duree] ?? session.duree}).',
                  key: const Key('session-echeance'),
                );
              },
            ),
            const SizedBox(height: 4),
            const Text('Pour une autre durée, déconnectez-vous puis cochez « Rester connecté » à la connexion.'),
            const SizedBox(height: 12),
            OutlinedButton(
              key: const Key('fermer-autres-sessions'),
              onPressed: _busy ? null : _fermerLesAutres,
              child: const Text('Déconnecter mes autres appareils'),
            ),
          ],
        ),
      ),
    );
  }
}
