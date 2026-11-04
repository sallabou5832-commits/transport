import 'package:flutter/widgets.dart';

import '../data/ma_configuration.dart';
import 'app_user.dart';
import 'auth_controller.dart';
import 'code_court_store.dart';

/// Code court (4 à 6 chiffres) qui rouvre l'application sans le mot de passe : demandé à l'ouverture d'une session reprise et
/// après [delaiArrierePlan] passées en arrière-plan. Vérifié sur le téléphone seulement, il marche hors ligne ; après
/// [essaisMax] erreurs, retour au mot de passe. Facultatif pour chacun, exigé si la compagnie le décide (lu dans
/// [MaConfiguration], gardée pour le mode hors ligne).
class CodeCourtController extends ChangeNotifier with WidgetsBindingObserver {
  CodeCourtController({
    required this.store,
    required this.configuration,
    required this.auth,
    DateTime Function()? horloge,
  }) : _horloge = horloge ?? DateTime.now {
    configuration.addListener(notifyListeners); // la compagnie peut se mettre à l'exiger
  }

  static const delaiArrierePlan = Duration(minutes: 5);
  static const essaisMax = 5;
  static final formatValide = RegExp(r'^\d{4,6}$');

  final CodeCourtStore store;
  final MaConfiguration configuration;
  final AuthController auth;
  final DateTime Function() _horloge;

  int? _utilisateur; // le compte pour lequel l'état ci-dessous est chargé
  bool _defini = false;
  bool _verrouille = false;
  int _echecs = 0;
  DateTime? _enArrierePlanDepuis;
  String? _avis;

  /// L'état est chargé pour ce compte (avant cela, l'accueil attend : rien ne s'affiche derrière un verrou).
  bool estPretPour(int? utilisateur) => utilisateur != null && utilisateur == _utilisateur;
  bool get defini => _defini;
  bool get exige => configuration.codeCourtExige;
  bool get verrouille => _verrouille;
  int get essaisRestants => essaisMax - _echecs;

  /// Message à montrer sur l'écran de connexion (après trop d'erreurs), lu une seule fois.
  String? prendreAvis() {
    final avis = _avis;
    _avis = null;
    return avis;
  }

  /// À chaque changement de compte connecté. [reprise] : la session a été reprise au démarrage (pas une saisie du mot de
  /// passe à l'instant) : le code est alors demandé.
  Future<void> surUtilisateur(AppUser? user, {required bool reprise}) async {
    if (user == null) {
      _utilisateur = null;
      _verrouille = false;
      notifyListeners();
      return;
    }
    if (user.id == _utilisateur) return;
    final proprietaire = await store.proprietaire();
    if (proprietaire != null && proprietaire != user.id) await store.effacer(); // un autre agent sur ce téléphone
    _defini = await store.existe();
    // Juste après le mot de passe, les erreurs de code court d'avant ne retirent plus d'essais (T-05).
    if (_defini && !reprise) await store.oublierLesEchecs();
    _echecs = await store.echecs();
    _verrouille = _defini && reprise;
    _utilisateur = user.id;
    notifyListeners();
  }

  /// Vrai si le code est bon. Après [essaisMax] erreurs, le code est effacé et l'agent revient au mot de passe.
  Future<bool> deverrouiller(String code) async {
    if (await store.verifier(code)) {
      _echecs = 0;
      _verrouille = false;
      notifyListeners();
      return true;
    }
    _echecs = await store.echecs();
    if (_echecs >= essaisMax) {
      await store.effacer();
      _defini = false;
      _verrouille = false;
      _echecs = 0;
      _avis = 'Trop d\'erreurs de code court : reconnectez-vous avec votre mot de passe.';
      await auth.logout();
    }
    notifyListeners();
    return false;
  }

  /// Oublié : retour au mot de passe, le code est effacé (il faudra en choisir un nouveau).
  Future<void> oublie() async {
    await store.effacer();
    _defini = false;
    _verrouille = false;
    _echecs = 0;
    await auth.logout();
    notifyListeners();
  }

  Future<void> definir(String code) async {
    final utilisateur = _utilisateur;
    if (utilisateur == null) throw StateError('Aucun compte connecté.');
    if (!formatValide.hasMatch(code)) throw ArgumentError('Le code court compte de 4 à 6 chiffres.');
    await store.definir(utilisateur, code);
    _defini = true;
    _echecs = 0;
    notifyListeners();
  }

  /// Retirer son code (impossible quand la compagnie l'exige).
  Future<void> retirer() async {
    if (exige) throw StateError('Votre compagnie exige un code court.');
    await store.effacer();
    _defini = false;
    notifyListeners();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.paused:
      case AppLifecycleState.hidden:
        _enArrierePlanDepuis ??= _horloge();
      case AppLifecycleState.resumed:
        final depuis = _enArrierePlanDepuis;
        _enArrierePlanDepuis = null;
        if (_defini && _utilisateur != null && depuis != null && _horloge().difference(depuis) >= delaiArrierePlan) {
          _verrouille = true;
          notifyListeners();
        }
      case AppLifecycleState.inactive:
      case AppLifecycleState.detached:
        break;
    }
  }
}
