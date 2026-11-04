import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../storage/cache_store.dart';

/// Ce qui s'applique à l'agent connecté (`/configuration/moi/`) : mode vocal (réglé par son supérieur ou choisi par lui-même),
/// code court exigé par la compagnie. Lu une fois par connexion et gardé pour le mode hors ligne.
class MaConfiguration extends ChangeNotifier {
  MaConfiguration({required this.api, required this.cache});

  final ApiClient api;
  final CacheStore cache;

  int? _utilisateur;
  Map<String, dynamic> _moi = const {};

  /// La dictée vocale démarre d'elle-même dans les formulaires qui la proposent.
  bool get prefereVocal => _moi['prefere_vocal'] == true;

  /// Le supérieur a imposé le mode vocal : l'agent ne le choisit pas lui-même.
  bool get vocalImpose => _moi['vocal_impose'] == true;

  bool get codeCourtExige {
    final session = _moi['session'];
    return session is Map && session['code_court_exige'] == true;
  }

  String _cle(int utilisateur) => 'ma_configuration:$utilisateur';

  /// La dernière configuration connue de ce compte (tout de suite, même hors ligne), puis celle du serveur.
  Future<void> charger(int utilisateur) async {
    _utilisateur = utilisateur;
    final gardee = cache.get(_cle(utilisateur))?.data;
    _moi = gardee is Map ? Map<String, dynamic>.from(gardee) : const {};
    notifyListeners();
    await actualiser();
  }

  Future<void> actualiser() async {
    final utilisateur = _utilisateur;
    if (utilisateur == null) return;
    try {
      final moi = await api.get('/configuration/moi/') as Map<String, dynamic>;
      await cache.put(_cle(utilisateur), moi);
      if (utilisateur != _utilisateur) return; // un autre compte s'est connecté entre-temps
      _moi = moi;
      notifyListeners();
    } on NetworkException {
      // Hors ligne : la dernière configuration connue reste.
    } on ApiException {
      // Réponse inattendue : idem, plutôt que de tout remettre au défaut.
    }
  }

  void oublier() {
    _utilisateur = null;
    _moi = const {};
    notifyListeners();
  }

  /// Le choix de l'agent (« Mes paramètres ») : `true`, `false`, ou `null` pour suivre son supérieur. Lève [ApiException]
  /// (mode vocal imposé) ou [NetworkException].
  Future<void> choisirModeVocal(bool? valeur) async {
    await api.patch('/configuration/mes-preferences/', body: {'prefere_vocal': valeur});
    await actualiser();
  }

  /// Le choix personnel enregistré sur le serveur (`null` : comme son supérieur).
  Future<bool?> choixPersonnel() async {
    final preferences = await api.get('/configuration/mes-preferences/') as Map<String, dynamic>;
    return preferences['prefere_vocal'] as bool?;
  }
}
