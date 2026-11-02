import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../auth/app_user.dart';
import '../storage/cache_store.dart';
import 'loaded.dart';

/// Feuille de route du jour d'un chauffeur, avec les informations utiles au départ.
class FeuilleDuJour {
  const FeuilleDuJour({
    required this.id,
    required this.departId,
    required this.heureDepartPrevue,
    required this.ligneNom,
    required this.immatriculation,
    this.heureArriveePrevue,
    this.heureDepartReelle,
  });

  factory FeuilleDuJour.fromJson(Map<String, dynamic> json) => FeuilleDuJour(
        id: json['id'] as int,
        departId: json['departId'] as int,
        heureDepartPrevue: DateTime.parse(json['heureDepartPrevue'] as String),
        heureArriveePrevue: _optionalDate(json['heureArriveePrevue']),
        heureDepartReelle: _optionalDate(json['heureDepartReelle']),
        ligneNom: json['ligneNom'] as String,
        immatriculation: json['immatriculation'] as String,
      );

  final int id;
  final int departId;
  final DateTime heureDepartPrevue;
  final DateTime? heureArriveePrevue;
  final DateTime? heureDepartReelle;
  final String ligneNom;
  final String immatriculation;

  bool get aDemarre => heureDepartReelle != null;

  Map<String, dynamic> toJson() => {
        'id': id,
        'departId': departId,
        'heureDepartPrevue': heureDepartPrevue.toUtc().toIso8601String(),
        'heureArriveePrevue': heureArriveePrevue?.toUtc().toIso8601String(),
        'heureDepartReelle': heureDepartReelle?.toUtc().toIso8601String(),
        'ligneNom': ligneNom,
        'immatriculation': immatriculation,
      };

  static DateTime? _optionalDate(Object? value) =>
      value == null ? null : DateTime.parse(value as String);
}

bool _memeJour(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

class FeuilleRepository {
  FeuilleRepository({required this.api, required this.cache, DateTime Function()? now})
      : _now = now ?? DateTime.now;

  final ApiClient api;
  final CacheStore cache;
  final DateTime Function() _now;

  static String _cacheKey(int userId) => 'u$userId:feuille_du_jour';

  /// La feuille de route du jour du chauffeur, ou null s'il n'en a pas aujourd'hui.
  ///
  /// Hors ligne, retombe sur la dernière feuille enregistrée (si elle est d'aujourd'hui).
  /// Lève [NoCachedDataException] si le réseau manque et que rien n'est enregistré.
  Future<Loaded<FeuilleDuJour?>> loadToday(AppUser user) async {
    try {
      final feuille = await _fetchToday(user);
      await cache.put(_cacheKey(user.id), feuille?.toJson());
      return Loaded(feuille);
    } on NetworkException {
      final cached = cache.get(_cacheKey(user.id));
      if (cached == null) throw const NoCachedDataException();
      final data = cached.data;
      final feuille =
          data == null ? null : FeuilleDuJour.fromJson(Map<String, dynamic>.from(data as Map));
      final encoreValable =
          feuille != null && _memeJour(feuille.heureDepartPrevue.toLocal(), _now());
      return Loaded(encoreValable ? feuille : null, fromCache: true, savedAt: cached.savedAt);
    }
  }

  Future<FeuilleDuJour?> _fetchToday(AppUser user) async {
    final today = _now();
    // Le serveur ne renvoie que la feuille de ce chauffeur pour ce jour (au lieu de celles de toute la compagnie, sur un
    // réseau mobile) ; le filtre local qui suit reste un garde-fou.
    final jour = '${today.year.toString().padLeft(4, '0')}-${today.month.toString().padLeft(2, '0')}-'
        '${today.day.toString().padLeft(2, '0')}';
    final feuilles = (await api.get('/feuilles-de-route/?chauffeur=${user.id}&date=$jour') as List)
        .cast<Map<String, dynamic>>()
        .where((f) =>
            f['chauffeur'] == user.id &&
            _memeJour(DateTime.parse(f['heure_depart_prevue'] as String).toLocal(), today))
        .toList()
      ..sort((a, b) =>
          (a['heure_depart_prevue'] as String).compareTo(b['heure_depart_prevue'] as String));
    if (feuilles.isEmpty) return null;

    final feuille = feuilles.first;
    final depart = await api.get('/departs/${feuille['depart']}/') as Map<String, dynamic>;
    final details = await Future.wait([
      api.get('/lignes/${depart['ligne']}/'),
      api.get('/vehicules/${depart['vehicule']}/'),
    ]);
    return FeuilleDuJour(
      id: feuille['id'] as int,
      departId: depart['id'] as int,
      heureDepartPrevue: DateTime.parse(feuille['heure_depart_prevue'] as String),
      heureArriveePrevue: FeuilleDuJour._optionalDate(feuille['heure_arrivee_prevue']),
      heureDepartReelle: FeuilleDuJour._optionalDate(feuille['heure_depart_reelle']),
      ligneNom: (details[0] as Map<String, dynamic>)['nom'] as String,
      immatriculation: (details[1] as Map<String, dynamic>)['immatriculation'] as String,
    );
  }
}
