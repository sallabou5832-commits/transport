import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_exception.dart';
import '../auth/auth_controller.dart';
import '../data/depart_repository.dart';
import '../data/loaded.dart';
import '../data/quota_service.dart';
import '../services.dart';
import '../sync/action_handlers.dart';
import '../sync/sync_service.dart';
import 'formatters.dart';

/// Vente d'un ticket. Fonctionne hors ligne : la vente est enregistrée sur le
/// téléphone puis envoyée dès que le réseau revient (voir `SyncService`).
class VenteTicketScreen extends StatefulWidget {
  const VenteTicketScreen({super.key});

  @override
  State<VenteTicketScreen> createState() => _VenteTicketScreenState();
}

class _VenteTicketScreenState extends State<VenteTicketScreen> {
  static const _especes = 'especes';
  static const _mobileMoney = 'mobile_money';

  final _formKey = GlobalKey<FormState>();
  final _nom = TextEditingController();
  final _telephone = TextEditingController();
  final _prix = TextEditingController();

  Loaded<List<DepartOption>>? _departs;
  String? _loadError;
  bool _loading = true;
  int? _departId;
  String _mode = _especes;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDeparts();
  }

  @override
  void dispose() {
    _nom.dispose();
    _telephone.dispose();
    _prix.dispose();
    super.dispose();
  }

  Future<void> _loadDeparts() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    final repository = context.read<AppServices>().departs;
    final user = context.read<AuthController>().user!;
    Loaded<List<DepartOption>>? departs;
    String? error;
    try {
      departs = await repository.loadSellable(user);
    } on NoCachedDataException {
      error = 'Pas de connexion, et aucun départ n\'est enregistré sur ce téléphone. '
          'Connectez-vous une première fois au réseau pour les charger.';
    } on ApiException catch (e) {
      error = e.message;
    }
    if (!mounted) return;
    setState(() {
      _departs = departs;
      _loadError = error;
      _loading = false;
      if (departs != null && !departs.data.any((d) => d.id == _departId)) _departId = null;
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });

    final sync = context.read<SyncService>();
    final quota = context.read<QuotaService>();
    final departId = _departId!;
    // Sans place garantie hors ligne sur ce départ, la vente exige le réseau : sinon le
    // serveur pourrait la refuser à la synchronisation alors que le voyageur a déjà payé.
    if (quota.remainingFor(departId) <= 0 && !await sync.canReachServer()) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = "Pas de connexion, et aucune place n'est garantie hors ligne pour ce départ. "
            'Reconnectez-vous au réseau pour vendre.';
      });
      return;
    }

    final result = await sync.submit(
      type: ActionTypes.venteTicket,
      payload: {
        'depart': _departId,
        'passager_nom': _nom.text.trim(),
        'passager_telephone': _telephone.text.trim(),
        'prix': _prix.text.trim().replaceAll(',', '.'),
        'mode_paiement': _mode,
      },
    );
    // La vente (envoyée ou en attente) utilise une des places réservées à ce guichetier.
    if (result.status != SubmitStatus.rejected) await quota.consume(departId);
    if (!mounted) return;

    setState(() => _busy = false);
    switch (result.status) {
      case SubmitStatus.sent:
        _resetPassenger();
        _toast('Ticket vendu.');
      case SubmitStatus.queued:
        _resetPassenger();
        _toast(
          'Vente enregistrée sur le téléphone (${result.message}) '
          'Elle sera envoyée automatiquement au retour du réseau.',
        );
      case SubmitStatus.rejected:
        setState(() => _error = result.message ?? 'Vente refusée par le serveur.');
    }
  }

  void _resetPassenger() {
    _nom.clear();
    _telephone.clear();
    _formKey.currentState?.reset();
  }

  void _toast(String message) => ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message), duration: const Duration(seconds: 5)));

  String? _validatePrix(String? value) {
    final parsed = double.tryParse((value ?? '').trim().replaceAll(',', '.'));
    if (parsed == null || parsed <= 0) return 'Saisissez un prix supérieur à 0.';
    if (parsed >= 100000000) return 'Prix trop élevé.';
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final quota = context.watch<QuotaService>();
    return Scaffold(
      appBar: AppBar(title: const Text('Vendre un ticket')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _loadError != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(_loadError!, key: const Key('departs-erreur'), textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        OutlinedButton(onPressed: _loadDeparts, child: const Text('Réessayer')),
                      ],
                    ),
                  ),
                )
              : Form(
                  key: _formKey,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_departs!.fromCache)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Chip(
                            avatar: const Icon(Icons.cloud_off, size: 18),
                            label: Text(
                              'Hors ligne : départs du ${formatDateHeure(_departs!.savedAt!)}',
                            ),
                          ),
                        ),
                      DropdownButtonFormField<int>(
                        key: const Key('depart'),
                        initialValue: _departId,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Départ',
                          border: OutlineInputBorder(),
                        ),
                        items: [
                          for (final d in _departs!.data)
                            DropdownMenuItem(
                              value: d.id,
                              child: Text(
                                '${formatDateHeure(d.dateHeure)} · ${d.ligneNom} '
                                '(${d.placesRestantes} pl.)',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                        onChanged: _busy ? null : (value) => setState(() => _departId = value),
                        validator: (v) => v == null ? 'Choisissez un départ.' : null,
                      ),
                      if (_departId != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: _PlacesGaranties(restantes: quota.remainingFor(_departId!)),
                        ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const Key('passager-nom'),
                        controller: _nom,
                        enabled: !_busy,
                        textCapitalization: TextCapitalization.words,
                        decoration: const InputDecoration(
                          labelText: 'Nom du voyageur',
                          border: OutlineInputBorder(),
                        ),
                        validator: (v) =>
                            (v == null || v.trim().isEmpty) ? 'Saisissez le nom du voyageur.' : null,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const Key('passager-telephone'),
                        controller: _telephone,
                        enabled: !_busy,
                        keyboardType: TextInputType.phone,
                        decoration: const InputDecoration(
                          labelText: 'Téléphone du voyageur',
                          helperText: 'Il recevra la confirmation par SMS / WhatsApp.',
                          border: OutlineInputBorder(),
                        ),
                        validator: (v) =>
                            (v ?? '').replaceAll(RegExp(r'\D'), '').length < 8
                                ? 'Saisissez un numéro valide.'
                                : null,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        key: const Key('prix'),
                        controller: _prix,
                        enabled: !_busy,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          labelText: 'Prix',
                          suffixText: 'FCFA',
                          border: OutlineInputBorder(),
                        ),
                        validator: _validatePrix,
                      ),
                      const SizedBox(height: 16),
                      SegmentedButton<String>(
                        key: const Key('mode-paiement'),
                        segments: const [
                          ButtonSegment(
                            value: _especes,
                            label: Text('Espèces'),
                            icon: Icon(Icons.payments_outlined),
                          ),
                          ButtonSegment(
                            value: _mobileMoney,
                            label: Text('Mobile money'),
                            icon: Icon(Icons.smartphone),
                          ),
                        ],
                        selected: {_mode},
                        onSelectionChanged:
                            _busy ? null : (selection) => setState(() => _mode = selection.first),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 16),
                        Text(
                          _error!,
                          key: const Key('vente-erreur'),
                          style: TextStyle(color: theme.colorScheme.error),
                        ),
                      ],
                      const SizedBox(height: 24),
                      FilledButton(
                        key: const Key('valider-vente'),
                        onPressed: _busy ? null : _submit,
                        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
                        child: _busy
                            ? const SizedBox(
                                height: 22,
                                width: 22,
                                child: CircularProgressIndicator(strokeWidth: 2.5),
                              )
                            : const Text('Valider la vente'),
                      ),
                    ],
                  ),
                ),
    );
  }
}

/// Combien de ventes ce guichetier peut encore faire SANS réseau sur le départ choisi.
class _PlacesGaranties extends StatelessWidget {
  const _PlacesGaranties({required this.restantes});

  final int restantes;

  @override
  Widget build(BuildContext context) {
    final ok = restantes > 0;
    return Row(
      children: [
        Icon(ok ? Icons.verified_outlined : Icons.wifi_off, size: 18),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            ok
                ? 'Places garanties hors ligne : $restantes'
                : 'Aucune place garantie hors ligne : la vente exige le réseau.',
            key: const Key('places-garanties'),
          ),
        ),
      ],
    );
  }
}
