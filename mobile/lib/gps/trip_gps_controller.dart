import 'dart:async';

import 'package:flutter/widgets.dart';

import '../auth/app_user.dart';
import '../auth/roles.dart';
import 'location_source.dart';
import 'position_batcher.dart';

/// Démarre et arrête le suivi GPS du conducteur selon l'état réel de son trajet côté serveur
/// (`GET /suivi/moi/`, `en_cours`) : jamais de suivi hors trajet, et pas de bouton dédié — le trajet se
/// démarre depuis le site ou l'administration (voir `RAPPORT_CONFORMITE.md` §6.1 : le mobile ne
/// démarre pas encore lui-même une feuille de route). Un mécanisme silencieux, comme `SyncTriggers` :
/// rien à afficher tant que ça fonctionne.
///
/// Échantillonnage : au plus un relevé tous les [intervalleMinimalReleve], et seulement après
/// [distanceFiltreMetres] parcourus — pas un flux continu, pour la batterie et le réseau. Envoi par
/// lots toutes les [intervalleEnvoi] (voir `PositionBatcher`), vérification de l'état du trajet toutes
/// les [intervalleVerification].
///
/// [verifierTrajetEnCours] interroge le serveur et renvoie `true`/`false`, ou `null` si l'état est
/// inconnu (hors ligne, session expirée) — auquel cas on ne change rien : ni couper un suivi en cours
/// sur un simple accroc réseau, ni en démarrer un sur une supposition. Une fonction plutôt que
/// l'`ApiClient` lui-même, pour se tester sans HTTP (voir `services.dart`).
class TripGpsController with WidgetsBindingObserver {
  TripGpsController({
    required this.verifierTrajetEnCours,
    required this.location,
    required this.batcher,
    this.intervalleVerification = const Duration(minutes: 2),
    this.intervalleEnvoi = const Duration(seconds: 45),
    this.distanceFiltreMetres = 50,
    this.intervalleMinimalReleve = const Duration(seconds: 20),
  });

  final Future<bool?> Function() verifierTrajetEnCours;
  final LocationSource location;
  final PositionBatcher batcher;
  final Duration intervalleVerification;
  final Duration intervalleEnvoi;
  final int distanceFiltreMetres;
  final Duration intervalleMinimalReleve;

  StreamSubscription<dynamic>? _abonnement;
  Timer? _verification;
  Timer? _envoi;

  bool get enSuivi => _abonnement != null;

  /// À chaque changement d'utilisateur (connexion, déconnexion, changement de compte) : démarre la
  /// vérification périodique pour un chauffeur, l'arrête sinon.
  void onUserChanged(AppUser? user) {
    final estChauffeur = user != null && Roles.chauffeurs.contains(user.role);
    if (estChauffeur) {
      _demarrerVerification();
    } else {
      _arreterTout();
    }
  }

  void _demarrerVerification() {
    if (_verification != null) return;
    WidgetsBinding.instance.addObserver(this);
    unawaited(_verifier());
    _verification = Timer.periodic(intervalleVerification, (_) => _verifier());
  }

  Future<void> _verifier() async {
    final enCours = await verifierTrajetEnCours();
    if (enCours == null) return; // État inconnu (hors ligne) : on ne touche pas à un suivi en cours.
    if (enCours && !enSuivi) {
      await _demarrerSuivi();
    } else if (!enCours && enSuivi) {
      await _arreterSuivi();
    }
  }

  Future<void> _demarrerSuivi() async {
    if (!await location.ensurePermission()) return; // Refusé : on continue sans suivi, jamais bloquant.
    _abonnement = location
        .watch(
          distanceFilterMetres: distanceFiltreMetres,
          intervalMinimum: intervalleMinimalReleve,
          notificationTitle: 'Transport Coord',
          notificationText: 'Trajet en cours : position transmise à la régulation.',
        )
        .listen(batcher.ajouter, onError: (Object _) {});
    _envoi = Timer.periodic(intervalleEnvoi, (_) => batcher.flush());
  }

  Future<void> _arreterSuivi() async {
    await _abonnement?.cancel();
    _abonnement = null;
    _envoi?.cancel();
    _envoi = null;
    await batcher.flush(); // Dernier lot du trajet qui vient de se terminer.
  }

  void _arreterTout() {
    if (_verification == null) return;
    WidgetsBinding.instance.removeObserver(this);
    _verification?.cancel();
    _verification = null;
    unawaited(_arreterSuivi());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(_verifier());
  }

  void dispose() => _arreterTout();
}
